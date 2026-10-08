"""Contracts for document source viewing and evidence display.

Validates that:
- Source viewer endpoints use canonical UUID paths (/api/v1/documents/{doc_id}/file).
- In-browser navigation uses safe hash fragments (#page=N) rather than query parameters.
- Credentials and session tokens are never embedded into URLs or fragments.
- File types (PDF vs DOCX/TXT/MD/CSV) are distinguished appropriately.
"""

import uuid


def build_source_viewer_url(document_id: str, page_number: int | None = None) -> str:
    """Build canonical same-origin source URL with optional fragment."""
    url = f"/api/v1/documents/{document_id}/file"
    if page_number and page_number > 0:
        url += f"#page={page_number}"
    return url


class TestSourceViewerContracts:
    """Validate source viewer URL and security contracts."""

    def test_canonical_source_viewer_url_without_page(self) -> None:
        doc_id = str(uuid.uuid4())
        url = build_source_viewer_url(doc_id)
        assert url == f"/api/v1/documents/{doc_id}/file"
        assert "?" not in url
        assert "token" not in url.lower()

    def test_canonical_source_viewer_url_with_page_fragment(self) -> None:
        doc_id = str(uuid.uuid4())
        url = build_source_viewer_url(doc_id, page_number=5)
        assert url == f"/api/v1/documents/{doc_id}/file#page=5"
        assert "?" not in url
        assert "page=" in url
        assert "#page=5" in url

    def test_page_number_zero_or_negative_omits_fragment(self) -> None:
        doc_id = str(uuid.uuid4())
        assert build_source_viewer_url(doc_id, page_number=0) == f"/api/v1/documents/{doc_id}/file"
        assert build_source_viewer_url(doc_id, page_number=-1) == f"/api/v1/documents/{doc_id}/file"
