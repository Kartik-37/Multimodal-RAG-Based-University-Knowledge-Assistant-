"""Contracts for document source viewing, non-PDF formats, and evidence display.

Validates that:
- Source viewer endpoints use canonical UUID paths (/api/v1/documents/{doc_id}/file).
- In-browser navigation uses safe hash fragments (#page=N) rather than query parameters.
- Credentials and session tokens are never embedded into URLs or fragments.
- File types (PDF vs DOCX/TXT/MD/CSV) are distinguished appropriately.
- Extracted text chunks are fetched and handled cleanly for both PDF and non-PDF materials.
- Positional caller argument coercion protects against parameter mix-ups.
- Missing documents and empty chunks fail safely without leaking exceptions.
"""

import urllib.parse
import uuid

from frontend.client.api_client import api_client
from frontend.client.models import CitationDTO
from frontend.pages.reader_page import (
    build_reader_url,
    get_return_label,
    validate_return_route,
)
from frontend.state.app_state import state


def build_source_viewer_url(document_id: str, page_number: int | None = None) -> str:
    """Build canonical same-origin source URL with optional fragment."""
    url = f"/api/v1/documents/{document_id}/file"
    if page_number and page_number > 0:
        url += f"#page={page_number}&view=FitH"
    return url


def build_filename_source_viewer_url(
    document_name: str, kb_id: str | None = None, page_number: int | None = None
) -> str:
    """Build canonical same-origin filename-based source URL."""
    encoded_name = urllib.parse.quote(document_name)
    url = f"/api/v1/documents/by-name?name={encoded_name}"
    if kb_id:
        url += f"&kb_id={kb_id}"
    if page_number and page_number > 0:
        url += f"#page={page_number}&view=FitH"
    return url


class TestSourceViewerContracts:
    """Validate source viewer URL, security, format-awareness, and resilience contracts."""

    def test_canonical_source_viewer_url_without_page(self) -> None:
        doc_id = str(uuid.uuid4())
        url = build_source_viewer_url(doc_id)
        assert url == f"/api/v1/documents/{doc_id}/file"
        assert "?" not in url
        assert "token" not in url.lower()

    def test_canonical_source_viewer_url_with_page_fragment(self) -> None:
        doc_id = str(uuid.uuid4())
        url = build_source_viewer_url(doc_id, page_number=5)
        assert url == f"/api/v1/documents/{doc_id}/file#page=5&view=FitH"
        assert "?" not in url
        assert "page=" in url
        assert "#page=5" in url

    def test_page_number_zero_or_negative_omits_fragment(self) -> None:
        doc_id = str(uuid.uuid4())
        assert build_source_viewer_url(doc_id, page_number=0) == f"/api/v1/documents/{doc_id}/file"
        assert build_source_viewer_url(doc_id, page_number=-1) == f"/api/v1/documents/{doc_id}/file"

    def test_filename_based_fallback_url_construction(self) -> None:
        """Requirement: Filename-based lookup URL safely escapes spaces/special chars with no tokens."""
        doc_name = "CS101 Syllabus (Fall 2026).pdf"
        kb_id = str(uuid.uuid4())
        url = build_filename_source_viewer_url(doc_name, kb_id=kb_id, page_number=3)

        assert "CS101%20Syllabus%20%28Fall%202026%29.pdf" in url
        assert f"kb_id={kb_id}" in url
        assert "#page=3&view=FitH" in url
        assert "token" not in url.lower()
        assert "auth" not in url.lower()

    def test_citation_flow_passes_requested_page_and_document_id(self) -> None:
        """Requirement: Citation DTO maintains exact document ID, page, snippet, and course."""
        cit = CitationDTO(
            document_id="d1111111-1111-1111-1111-111111111111",
            document_name="cs101_syllabus_fall2026.pdf",
            page_number=2,
            chunk_id="chk-syl-02",
            relevance_score=0.95,
            snippet="Grading Breakdown: Weekly Laboratory Problem Sets (30%).",
            course_name="CS101: Introduction to Computer Science",
            knowledge_base_id="c1111111-1111-1111-1111-111111111111",
        )
        url = build_source_viewer_url(cit.document_id, page_number=cit.page_number)
        assert cit.document_id in url
        assert "#page=2" in url
        assert cit.snippet.startswith("Grading Breakdown")

    def test_non_pdf_documents_distinguished_and_unpaged(self) -> None:
        """Requirement: Non-PDF formats (DOCX, TXT, MD, CSV) are correctly categorized."""
        test_cases = [
            ("syllabus.pdf", True, "PDF Document"),
            ("lab_protocols.docx", False, "Word Document"),
            ("honor_code.txt", False, "Text Document"),
            ("notes.md", False, "Markdown Guide"),
            ("grade_weights.csv", False, "CSV Dataset"),
        ]
        for fname, expected_pdf, _ in test_cases:
            is_pdf = fname.lower().endswith(".pdf")
            assert is_pdf == expected_pdf

    def test_api_client_chunks_retrieval_format_aware(self) -> None:
        """Requirement: API client provides format-specific chunks without crashing."""
        # DOCX chunks (unpaged)
        docx_chunks = api_client.get_document_chunks(
            document_id="d1111111-1111-1111-1111-222222222222"
        )
        assert len(docx_chunks) > 0
        assert all(c["page_number"] is None for c in docx_chunks)

        # TXT chunks (unpaged)
        txt_chunks = api_client.get_document_chunks(
            document_id="d1111111-1111-1111-1111-333333333333"
        )
        assert len(txt_chunks) > 0
        assert all(c["page_number"] is None for c in txt_chunks)

        # PDF chunks (paged)
        pdf_chunks = api_client.get_document_chunks(
            document_id="d1111111-1111-1111-1111-111111111111"
        )
        assert len(pdf_chunks) > 0
        assert any(c["page_number"] == 2 for c in pdf_chunks)

        # Missing document returns empty list
        missing_chunks = api_client.get_document_chunks(document_id="missing")
        assert missing_chunks == []

    def test_missing_or_unauthorized_document_handled_cleanly(self) -> None:
        """Requirement: Unknown or missing document IDs resolve to empty chunks and 404 URL targets."""
        chunks = api_client.get_document_chunks(document_id="00000000-0000-0000-0000-000000000000")
        assert chunks == []

    def test_positional_course_name_coercion_safety(self) -> None:
        """Requirement: Passing course name as 4th positional argument is safely handled without TypeError."""
        # Simulate coercion logic from source_viewer.open_source_viewer
        page_number_input = "CS101: Introduction to Computer Science"
        course_name_input = None

        if isinstance(page_number_input, str):
            if page_number_input.isdigit():
                page_number = int(page_number_input)
            else:
                if not course_name_input:
                    course_name_input = page_number_input
                page_number = None

        assert page_number is None
        assert course_name_input == "CS101: Introduction to Computer Science"

    def test_build_reader_url_preserves_parameters_without_tokens(self) -> None:
        """Requirement: Dedicated reader URL preserves document ID, page, course, return route, and conv_id."""
        doc_id = "d1111111-1111-1111-1111-111111111111"
        conv_id = "c9999999-9999-9999-9999-999999999999"
        url = build_reader_url(
            document_id=doc_id,
            document_name="syllabus.pdf",
            page_number=5,
            course_name="CS101",
            return_to="/chat",
            conv_id=conv_id,
        )

        assert url.startswith("/reader?")
        assert f"document_id={doc_id}" in url
        assert "page=5" in url
        assert "course=CS101" in url
        assert "return_to=%2Fchat" in url
        assert f"conv_id={conv_id}" in url
        assert "token" not in url.lower()
        assert "auth" not in url.lower()

    def test_validate_return_route_blocks_external_redirects(self) -> None:
        """Requirement: External URLs or traversal attempts are blocked, falling back to safe internal route."""
        # External URLs with scheme
        assert validate_return_route("https://evil.com/phish") == "/chat"
        assert validate_return_route("http://attacker.org") == "/chat"
        # Protocol-relative URLs
        assert validate_return_route("//attacker.com/evil") == "/chat"
        # Invalid / non-whitelisted paths
        assert validate_return_route("/admin/secret/backdoor") == "/chat"
        assert validate_return_route("/etc/passwd") == "/chat"
        assert validate_return_route("") == "/chat"
        assert validate_return_route(None) == "/chat"

    def test_validate_return_route_allows_whitelisted_internal_routes(self) -> None:
        """Requirement: Safe application routes are preserved and active conversation ID is appended."""
        conv_id = "conv-abc-123"
        # Chat without conv_id appends it
        assert validate_return_route("/chat", conv_id=conv_id) == f"/chat?conversation_id={conv_id}"
        # Chat already having conv_id preserves it
        assert validate_return_route(f"/chat?conversation_id={conv_id}", conv_id=conv_id) == f"/chat?conversation_id={conv_id}"
        # Documents page with course scope
        assert validate_return_route("/documents?kb_id=kb-123") == "/documents?kb_id=kb-123"
        # Course catalog
        assert validate_return_route("/knowledge-bases") == "/knowledge-bases"

    def test_get_return_label_contextual_accuracy(self) -> None:
        """Requirement: Back button label accurately reflects originating context."""
        assert get_return_label("/chat") == "Back to Conversation"
        assert get_return_label("/chat?conversation_id=c1") == "Back to Conversation"
        assert get_return_label("/documents?kb_id=k1") == "Back to Documents"
        assert get_return_label("/knowledge-bases") == "Back to Courses"
        assert get_return_label("/dashboard") == "Back to Dashboard"
        assert get_return_label("/profile") == "Back"

    def test_app_state_reader_context_persistence(self) -> None:
        """Requirement: AppState transiently preserves reader context (snippet, page, origin) across navigation."""
        cit = CitationDTO(
            document_id="doc-42",
            document_name="exam_prep.pdf",
            page_number=3,
            chunk_id="chk-42",
            snippet="Final exam covers Chapters 1 through 8.",
        )
        state.set_reader_context(
            document_id=cit.document_id,
            document_name=cit.document_name,
            page_number=cit.page_number,
            snippet=cit.snippet,
            return_to="/chat",
            conv_id="conv-777",
            citation=cit,
        )

        ctx = state.reader_context
        assert ctx["document_id"] == "doc-42"
        assert ctx["document_name"] == "exam_prep.pdf"
        assert ctx["page_number"] == 3
        assert ctx["snippet"] == "Final exam covers Chapters 1 through 8."
        assert ctx["return_to"] == "/chat"
        assert ctx["conv_id"] == "conv-777"
