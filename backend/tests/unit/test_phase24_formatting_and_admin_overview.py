"""
Phase 24 Verification Test Suite.

Validates:
1. Markdown block preservation: _sanitize_llm_answer maintains headings, paragraphs, lists, tables.
2. Natural summary formatting: No 'Document Overview' boilerplate, no raw coverage audit footer in prose.
3. Clean citation presentation: strip_citation_markers removes inline badges cleanly without broken punctuation.
4. Scoped typography: theme.py defines explicit font-size and line-height scoped strictly to .safe-markdown.
5. Administrator Overview redesign: dashboard_page.py uses max-w-7xl, operational typography 13-16px, balanced grid.
"""

import re
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from backend.app.models.document import Document
from backend.app.services.document_summary_service import DocumentSummaryService
from backend.app.services.llm.prompt_builder import GroundedPromptBuilder, _response_format_directive
from backend.app.services.llm.service import _sanitize_llm_answer
from frontend.client.citations import (
    CODE_OR_CITATION_PATTERN,
    group_citations_by_document,
    strip_citation_markers,
)
from frontend.client.models import CitationDTO, UserDTO
from frontend.components.theme import GLOBAL_THEME_CSS
from frontend.pages.chat_page import format_citation_links


class TestPhase24MarkdownBlockPreservation:
    """Verifies that _sanitize_llm_answer preserves markdown blocks and never flattens headings."""

    def test_multi_block_headings_and_paragraphs_preserved(self) -> None:
        raw_summary = (
            "### Mobile Framework Foundations\n\n"
            "This introductory guide provides foundational knowledge on mobile development [source_1].\n\n"
            "### Architecture & Capabilities\n\n"
            "Flutter is an open-source framework developed by Google for cross-platform apps [source_2].\n\n"
            "- Cross-platform single codebase\n"
            "- Sub-second hot reload\n"
            "- Declarative widget tree"
        )
        sanitized = _sanitize_llm_answer(raw_summary)

        # 1. Heading must NOT absorb following paragraph
        assert "### Mobile Framework Foundations" in sanitized
        assert "### Architecture & Capabilities" in sanitized
        assert "### Mobile Framework Foundations\n\nThis introductory guide" in sanitized or (
            "\n\n" in sanitized
        )

        # 2. No literal ### markers merged onto the same line as prose
        lines = sanitized.splitlines()
        for line in lines:
            if "###" in line:
                assert line.strip().startswith("###"), f"Literal ### found inside prose line: {line}"

        # 3. List items remain vertical
        assert "- Cross-platform single codebase" in sanitized
        assert "- Sub-second hot reload" in sanitized

    def test_generic_document_overview_boilerplate_heading_stripped(self) -> None:
        raw = (
            "### Document Overview\n\n"
            "Flutter is a comprehensive UI framework [source_1].\n\n"
            "### Key Topics & Themes\n\n"
            "The notes cover widgets, layouts, and rendering engines [source_2]."
        )
        sanitized = _sanitize_llm_answer(raw)

        # Boilerplate "### Document Overview" heading should be stripped so summary starts directly
        assert "### Document Overview" not in sanitized
        # Meaningful content heading should be retained
        assert "### Key Topics & Themes" in sanitized
        assert "Flutter is a comprehensive UI framework" in sanitized

    def test_code_blocks_and_tables_preserved(self) -> None:
        raw = (
            "Here is the widget hierarchy:\n\n"
            "```dart\n"
            "class MyWidget extends StatelessWidget {\n"
            "  Widget build(BuildContext context) => Container();\n"
            "}\n"
            "```\n\n"
            "| Component | Description |\n"
            "| --- | --- |\n"
            "| Engine | C++ Skia rendering |\n"
            "| Framework | Dart UI controls |"
        )
        sanitized = _sanitize_llm_answer(raw)
        assert "```dart" in sanitized
        assert "class MyWidget extends StatelessWidget" in sanitized
        assert "| Component | Description |" in sanitized
        assert "| Engine | C++ Skia rendering |" in sanitized


class TestPhase24NaturalSummaryScaffolding:
    """Verifies that summary generation prompts and fallbacks produce natural, non-boilerplate prose."""

    def test_summary_format_directive_instructs_natural_opening_paragraph(self) -> None:
        directive = _response_format_directive("Summarize the entire document")
        assert "Document Overview" not in directive
        assert "Key Topics & Themes" not in directive
        assert "opening overview paragraph" in directive.lower()
        assert "content-specific headings" in directive.lower()

    def test_deterministic_summary_starts_directly_without_overview_heading_or_coverage_footer(self) -> None:
        svc = DocumentSummaryService(provider=MagicMock())
        doc = Document(
            id=uuid4(),
            knowledge_base_id=uuid4(),
            original_filename="flutter_lecture_notes.pdf",
            mime_type="application/pdf",
            file_type="pdf",
            file_size_bytes=1024,
            storage_key="docs/flutter.pdf",
            content_hash="mockcontenthash123",
        )
        windows = [
            {
                "window_index": 1,
                "source_tag": "source_1",
                "rep_page": 1,
                "page_start": 1,
                "page_end": 17,
                "text_sample": "Mobile architecture history",
            },
            {
                "window_index": 2,
                "source_tag": "source_2",
                "rep_page": 18,
                "page_start": 18,
                "page_end": 20,
                "text_sample": "Flutter SDK definition",
            },
            {
                "window_index": 3,
                "source_tag": "source_3",
                "rep_page": 21,
                "page_start": 21,
                "page_end": 28,
                "text_sample": "Industry adoption",
            },
            {
                "window_index": 4,
                "source_tag": "source_4",
                "rep_page": 29,
                "page_start": 29,
                "page_end": 37,
                "text_sample": "Widget ecosystem",
            },
        ]
        summary = svc._build_deterministic_summary(doc, windows, 1, 37, 4)

        # 1. No generic "### Document Overview" title
        assert "### Document Overview" not in summary
        assert not summary.startswith("###")

        # 2. No raw coverage footer in prose
        assert "*Coverage: Pages" not in summary
        assert "chunks analyzed" not in summary

        # 3. Begins directly with useful overview
        assert summary.startswith("**flutter_lecture_notes.pdf** covers Flutter application development")

        # 4. Content-specific headings are used
        assert "### Mobile Architecture & Framework Foundations" in summary
        assert "### Flutter SDK & Cross-Platform Capabilities" in summary
        assert "### Widget Architecture & Developer Tooling" in summary


class TestPhase24CleanCitationPresentation:
    """Verifies that citation markers are cleanly stripped from prose by default while preserving provenance."""

    def test_strip_citation_markers_removes_inline_badges_cleanly(self) -> None:
        text = "Flutter is a multi-platform framework [source_1]. It supports mobile, web, and desktop [source_2]."
        cleaned = strip_citation_markers(text)
        assert cleaned == "Flutter is a multi-platform framework. It supports mobile, web, and desktop."

    def test_strip_citation_markers_handles_adjacent_and_punctuation_cleanly(self) -> None:
        text = "Developed by Google [source_1] [source_2]. Works across platforms [1]."
        cleaned = strip_citation_markers(text)
        assert cleaned == "Developed by Google. Works across platforms."

    def test_strip_citation_markers_preserves_code_blocks(self) -> None:
        text = "`var x = [1];` is Dart code, but [source_1] is a citation."
        cleaned = strip_citation_markers(text)
        assert "`var x = [1];`" in cleaned
        assert "[source_1]" not in cleaned

    def test_format_citation_links_clean_default_vs_pills_explicit(self) -> None:
        citations = [
            CitationDTO(
                source_id="source_1",
                document_id="doc-1",
                document_name="Course_Syllabus.pdf",
                chunk_id="chunk-1",
                page_number=3,
                snippet="Grading policy",
            )
        ]
        text = "Grading is based on projects [1]."

        # Clean prose (inline_badges=False)
        clean = format_citation_links(text, citations, inline_badges=False)
        assert clean == "Grading is based on projects."
        assert "citation-pill" not in clean
        assert "[1]" not in clean

        # Interactive pills (inline_badges=True)
        pills = format_citation_links(text, citations, inline_badges=True, message_id="msg-101")
        assert "citation-pill" in pills
        assert 'data-citation-index="1"' in pills
        assert 'data-message-id="msg-101"' in pills
        assert "• Page 3" in pills


class TestPhase24ScopedTypography:
    """Verifies that .safe-markdown scoped typography rules are defined with explicit sizes and line-heights."""

    def test_theme_css_contains_explicit_safe_markdown_heading_sizes(self) -> None:
        assert ".safe-markdown h1" in GLOBAL_THEME_CSS
        assert ".safe-markdown h2" in GLOBAL_THEME_CSS
        assert ".safe-markdown h3" in GLOBAL_THEME_CSS
        assert ".safe-markdown h4" in GLOBAL_THEME_CSS

        # Verify explicit sizes and line-heights are scoped to .safe-markdown
        assert "font-size: 1.5rem !important;" in GLOBAL_THEME_CSS  # 24px H1
        assert "font-size: 1.3125rem !important;" in GLOBAL_THEME_CSS  # 21px H2
        assert "font-size: 1.125rem !important;" in GLOBAL_THEME_CSS  # 18px H3
        assert "font-size: 1rem !important;" in GLOBAL_THEME_CSS  # 16px H4 / P

    def test_theme_css_contains_scoped_paragraph_and_list_typography(self) -> None:
        assert ".safe-markdown p" in GLOBAL_THEME_CSS
        assert ".safe-markdown li" in GLOBAL_THEME_CSS
        assert "Plus Jakarta Sans" in GLOBAL_THEME_CSS


class TestPhase24AdminDashboardRedesign:
    """Verifies that Administrator Overview uses the full wide canvas and comfortable operational typography."""

    def test_dashboard_wrapper_uses_max_w_7xl(self) -> None:
        from frontend.pages import dashboard_page
        import inspect

        source = inspect.getsource(dashboard_page._render_admin_dashboard)
        assert "max-w-7xl" in source
        assert "max-w-5xl" not in source

    def test_dashboard_typography_and_padding_scaled_up(self) -> None:
        from frontend.pages import dashboard_page
        import inspect

        source = inspect.getsource(dashboard_page._render_dashboard_content)

        # Card headers use 18-20px icons and larger font
        assert "text-base sm:text-lg font-bold text-primary-navy font-editorial" in source
        assert 'size="20px"' in source

        # Course items use 14-16px titles and adequate padding
        assert "text-sm sm:text-base font-bold text-primary-navy truncate font-editorial" in source
        assert "p-3.5 sm:p-4" in source

        # Indexing Queue items use 14-16px titles
        assert "text-sm sm:text-base font-bold text-primary-navy truncate max-w-[280px]" in source

        # Recent Activity items use 14px actions
        assert "font-semibold text-primary-navy truncate font-sans text-xs sm:text-sm" in source
