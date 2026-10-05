"""
Unit Tests for Student Dashboard and Chat Fixes.

Verifies:
1. LLM answer sanitization strips reasoning/scratchpad rambling and extracts concise conclusion.
2. Irrelevant reasoning source citations (e.g. [source_1], [source_3], [source_4]) are stripped,
   leaving only the actual grounding source containing the answer (e.g. [source_2]).
3. Sidebar layout does not contain 'CURRENT COURSE' card or forbidden legacy strings.
4. Global theme CSS suppresses Quasar/NiceGUI reconnection overlays.
5. Source viewer CSS includes full-height styles and eliminates empty spaces.
6. Citation link formatting handles both '[1]' and '[source_1]' formats.
"""

from pathlib import Path

from backend.app.services.llm.service import _SOURCE_REF_REGEX, _sanitize_llm_answer
from frontend.client.models import CitationDTO
from frontend.components.theme import GLOBAL_THEME_CSS
from frontend.pages.chat_page import format_citation_links


def test_sanitize_llm_answer_strips_cot_and_extracts_concise_answer() -> None:
    """Verify that rambling CoT monologue is stripped and concise factual answer is preserved."""
    raw_rambling_cot = (
        'We are given the user question: "what is act name"\n\n'
        'We must look for the name of the act in the retrieved evidence.\n\n'
        "Let's check each source:\n\n"
        "* [source_1]: This is from KSU-Act-English.pdf, Page 12. It talks about powers of the Board. "
        "It does not explicitly state the name of the act.\n\n"
        '* [source_2]: This is from KSU-Act-English.pdf, Page 1. It states: "GUJARAT ACT NO. 22 OF 2021... '
        'This Act may be called \\"Kaushalya the Skill University Act 2021\\""\n\n'
        "* [source_3]: This is from KSU-Act-English.pdf, Page 16. It talks about funds and does not state the name.\n\n"
        "* [source_4]: This is from KSU-Act-English.pdf, Page 7. It talks about officers of the University.\n\n"
        'Therefore, the act name is explicitly stated in [source_2] as "Kaushalya the Skill University Act 2021".'
    )

    cleaned = _sanitize_llm_answer(raw_rambling_cot)

    # 1. Preamble and internal monologue must be absent
    assert "We are given the user question" not in cleaned
    assert "We must look for the name" not in cleaned
    assert "Let's check each source" not in cleaned
    assert "* [source_1]" not in cleaned
    assert "* [source_3]" not in cleaned
    assert "* [source_4]" not in cleaned

    # 2. Direct conclusion with the true answer must be preserved
    assert "Kaushalya the Skill University Act 2021" in cleaned
    assert "[source_2]" in cleaned

    # 3. Only source_2 is referenced in the final output
    referenced_sources = set(_SOURCE_REF_REGEX.findall(cleaned))
    assert referenced_sources == {"source_2"}
    assert "source_1" not in referenced_sources
    assert "source_3" not in referenced_sources
    assert "source_4" not in referenced_sources


def test_sanitize_llm_answer_handles_think_tags() -> None:
    """Verify that <think>...</think> tags are stripped completely."""
    raw = (
        "<think>\n"
        "User wants to know the act name.\n"
        "Checking chunks: chunk 1 no, chunk 2 yes.\n"
        "</think>\n"
        'This Act may be called "Kaushalya the Skill University Act 2021" [source_2].'
    )

    cleaned = _sanitize_llm_answer(raw)
    assert "<think>" not in cleaned
    assert "</think>" not in cleaned
    assert "Checking chunks" not in cleaned
    assert 'This Act may be called "Kaushalya the Skill University Act 2021" [source_2].' in cleaned


def test_sidebar_removes_current_course_card() -> None:
    """Verify that 'CURRENT COURSE' card has been completely removed from layout.py."""
    layout_file = Path("frontend/components/layout.py")
    assert layout_file.exists()
    content = layout_file.read_text(encoding="utf-8")

    assert "CURRENT COURSE" not in content
    assert "Query Course" not in content
    assert "Active Target Corpus" not in content
    assert "Active Course Scope" not in content


def test_theme_css_suppresses_reconnect_popups() -> None:
    """Verify that theme CSS suppresses Quasar/NiceGUI reconnection overlays."""
    assert ".nicegui-reconnect-alert" in GLOBAL_THEME_CSS
    assert ".nicegui-reconnect" in GLOBAL_THEME_CSS
    assert "#reconnection_modal" in GLOBAL_THEME_CSS
    assert "display: none !important;" in GLOBAL_THEME_CSS


def test_theme_css_has_source_viewer_full_height() -> None:
    """Verify that theme CSS has full height styles for the PDF source viewer drawer."""
    assert ".source-viewer-card" in GLOBAL_THEME_CSS
    assert "height: 100vh !important;" in GLOBAL_THEME_CSS


def test_format_citation_links_supports_both_formats() -> None:
    """Verify that citation link formatter replaces both [1] and [source_1] markers."""
    citations = [
        CitationDTO(
            document_id="doc-123",
            document_name="KSU-Act-English.pdf",
            page_number=1,
            chunk_id="chunk-456",
            snippet="Act title snippet",
            relevance_score=0.98,
        )
    ]

    # Test numeric format: [1]
    res_numeric = format_citation_links("As stated in [1].", citations)
    assert 'data-citation-index="1"' in res_numeric
    assert "citation-pill" in res_numeric

    # Test source_X format: [source_1]
    res_source = format_citation_links("As stated in [source_1].", citations)
    assert 'data-citation-index="1"' in res_source
    assert "citation-pill" in res_source


def test_knowledge_bases_page_persistent_search() -> None:
    """Verify that knowledge_bases_page does not destroy s_box in render loop."""
    kb_page_file = Path("frontend/pages/knowledge_bases_page.py")
    assert kb_page_file.exists()
    content = kb_page_file.read_text(encoding="utf-8")

    # s_box is wired with on_value_change without being cleared in render_cards_grid
    assert "s_box.on_value_change" in content
    assert "cards_container.clear()" in content
    assert "render_cards_grid()" in content


def test_chat_page_academic_assistant_branding_and_no_badges() -> None:
    """Verify that chat_page uses 'Academic Assistant', hides badges and debug mode for students."""
    chat_file = Path("frontend/pages/chat_page.py")
    assert chat_file.exists()
    content = chat_file.read_text(encoding="utf-8")

    # Branding: Academic Assistant, not BCA Academic Assistant
    assert "Ask Academic Assistant" in content
    assert "Ask BCA Assistant" not in content
    assert "BCA Academic Assistant" not in content

    # Grounding badges removed
    assert "render_grounding_status_badge" not in content

    # Single loading / single-line thinking indicator
    assert "loading_row" not in content
    assert "Thinking..." in content

    # Debug mode is guarded for admin only
    assert "if is_admin and diag_kb_id:" in content


def test_app_state_background_generation_state() -> None:
    """Verify that AppState supports decoupled background generation flags."""
    from frontend.state.app_state import AppState

    state = AppState()
    assert state.is_generating is False
    assert state.generation_error is None

    # Test clear_chat resets states cleanly
    state._is_generating = True
    state._generation_error = "some error"
    state.clear_chat()
    assert state.is_generating is False
    assert state.generation_error is None
    assert len(state.chat_history) == 0


def test_source_viewer_uses_object_and_full_height() -> None:
    """Verify source_viewer embeds inline viewer with full height and no token/cookie leakage."""
    sv_file = Path("frontend/components/source_viewer.py")
    assert sv_file.exists()
    content = sv_file.read_text(encoding="utf-8")

    # Embeds native browser viewer with robust minimum height
    assert "<iframe" in content or "<object" in content
    assert "min-height: 520px" in content

    # Security: No raw token parameter in streaming URL and no document.cookie script
    assert "params.append(f\"token=" not in content
    assert "document.cookie" not in content

