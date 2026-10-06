"""
Behavioral Unit Tests for Student Dashboard and Conversational RAG Operations.

Validates core conversational behaviors and state contracts without locking
frontend visual layouts, CSS, or implementation-specific DOM fragments.
"""

from backend.app.services.llm.service import _SOURCE_REF_REGEX, _sanitize_llm_answer
from frontend.client.citations import extract_resolved_citations
from frontend.client.models import CitationDTO
from frontend.state.app_state import AppState


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
    """Verify that reasoning within <think>...</think> tags is stripped completely."""
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


def test_semantic_citation_resolution_for_numeric_and_source_markers() -> None:
    """Verify semantic citation resolution handles both [1] and [source_1] markers without UI coupling."""
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
    res_numeric = extract_resolved_citations("As stated in [1].", citations)
    assert len(res_numeric) == 1
    assert res_numeric[0].index == 1
    assert res_numeric[0].citation.document_name == "KSU-Act-English.pdf"
    assert res_numeric[0].citation.document_id == "doc-123"

    # Test source_X format: [source_1]
    res_source = extract_resolved_citations("As stated in [source_1].", citations)
    assert len(res_source) == 1
    assert res_source[0].index == 1
    assert res_source[0].citation.document_name == "KSU-Act-English.pdf"
    assert res_source[0].citation.document_id == "doc-123"


def test_app_state_background_generation_state() -> None:
    """Verify AppState background generation flags and clean lifecycle reset."""
    state = AppState()
    assert state.is_generating is False
    assert state.generation_error is None

    # Test state lifecycle reset
    state._is_generating = True
    state._generation_error = "Server temporarily unavailable"
    state.clear_chat()
    assert state.is_generating is False
    assert state.generation_error is None
    assert len(state.chat_history) == 0


def test_app_state_safe_error_handling_contract() -> None:
    """Verify AppState stores sanitized user-facing error strings without leaking internal details."""
    state = AppState()
    state._generation_error = "The AI service is temporarily unavailable. Please retry shortly."
    assert "temporarily unavailable" in state.generation_error
    assert "Traceback" not in state.generation_error
    assert "password" not in state.generation_error
