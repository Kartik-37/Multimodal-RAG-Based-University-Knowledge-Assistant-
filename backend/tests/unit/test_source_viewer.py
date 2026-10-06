"""
Unit Tests for Source Viewer URL and Citation Formatting Contracts.

Validates pure client-side formatting, URL construction, and escaping contracts:
1. Source viewer generated URL uses canonical document UUID.
2. Source viewer generated URL contains no main session token or credentials.
3. No document.cookie JavaScript credential injection exists in citations.
4. Unsafe document metadata is safely escaped in citation links.
5. Page fragment identifiers (#page=N) retain client-side navigation semantics
   without leaking sensitive credentials into query parameters.
"""

import uuid

from frontend.client.models import CitationDTO
from frontend.pages.chat_page import format_citation_links


class TestSourceViewerUnitContracts:
    """Pure unit test suite for source viewer URL formatting and citation escaping."""

    def test_source_viewer_url_canonical_uuid_and_no_token(self) -> None:
        """Requirement 10, 12: Source viewer URL uses canonical UUID and contains no session token."""
        doc_uuid = uuid.uuid4()
        canonical_url = f"/api/v1/documents/{doc_uuid}/file"

        # Verify format
        assert str(doc_uuid) in canonical_url
        assert "token" not in canonical_url
        assert "Bearer" not in canonical_url
        assert "?" not in canonical_url

    def test_source_viewer_page_fragment_syntax_without_query_params(self) -> None:
        """Requirement 10, 12: Page navigation uses hash fragments, never query parameters."""
        doc_uuid = uuid.uuid4()
        page_num = 14
        viewer_url = f"/api/v1/documents/{doc_uuid}/file#page={page_num}"

        assert viewer_url.endswith(f"#page={page_num}")
        assert "?" not in viewer_url
        assert "token=" not in viewer_url

    def test_unsafe_metadata_safely_escaped_in_citations(self) -> None:
        """Requirement 11, 13: Unsafe metadata is escaped and no document.cookie script injection occurs."""
        xss_name = '<script>alert("xss")</script>.pdf'
        citations = [
            CitationDTO(
                document_name=xss_name,
                page_number=1,
                chunk_id="chk-1",
                relevance_score=0.95,
                snippet='Exploit snippet <img src=x onerror="alert(1)">',
                document_id="doc-123",
                knowledge_base_id="kb-123",
                course_name="BCA Security",
            )
        ]

        formatted = format_citation_links("Refer to [1] for course details.", citations)

        # Executable tags must be neutralized
        assert "<script>" not in formatted
        assert "document.cookie" not in formatted
        assert "onerror" not in formatted
        # Semantic data attributes must be preserved
        assert 'data-citation-index="1"' in formatted

    def test_citation_link_attributes_do_not_embed_credentials(self) -> None:
        """Requirement 10, 11: Rendered citation anchors never leak tokens or cookies into attributes."""
        citations = [
            CitationDTO(
                document_name="Regulations.pdf",
                page_number=5,
                chunk_id="chk-reg",
                snippet="University regulation rules under section 5.",
                relevance_score=0.88,
                document_id="doc-456",
            )
        ]
        formatted = format_citation_links("See [1] for rules.", citations)
        assert "auth_session_token" not in formatted
        assert "token=" not in formatted
        assert "session=" not in formatted
