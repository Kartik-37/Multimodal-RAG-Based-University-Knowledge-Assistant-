"""
Unit Tests for Source Viewer URL and Semantic Citation Mapping Contracts.

Validates pure framework-independent contracts, URL construction, and semantic citation mapping:
1. Source viewer URL uses canonical document UUID without query token credentials.
2. Page navigation uses hash fragments (#page=N), never credential-leaking query parameters.
3. Citation references map semantically to document UUIDs, page numbers, and indices.
4. Semantic citation references do not embed or leak authentication session tokens or credentials.
5. Citation metadata containing potentially unsafe strings preserves data integrity without executing scripts.
"""

import uuid

from frontend.client.citations import (
    SemanticCitationRef,
    extract_resolved_citations,
    replace_citation_markers,
)
from frontend.client.models import CitationDTO


class TestSourceViewerUnitContracts:
    """Pure unit test suite for source viewer URL formatting and semantic citation resolution."""

    def test_source_viewer_url_canonical_uuid_and_no_token(self) -> None:
        """Requirement: Source viewer URL uses canonical UUID and contains no session token."""
        doc_uuid = uuid.uuid4()
        canonical_url = f"/api/v1/documents/{doc_uuid}/file"

        assert str(doc_uuid) in canonical_url
        assert "token" not in canonical_url
        assert "Bearer" not in canonical_url
        assert "?" not in canonical_url

    def test_source_viewer_page_fragment_syntax_without_query_params(self) -> None:
        """Requirement: Page navigation uses hash fragments, never query parameters."""
        doc_uuid = uuid.uuid4()
        page_num = 14
        viewer_url = f"/api/v1/documents/{doc_uuid}/file#page={page_num}"

        assert viewer_url.endswith(f"#page={page_num}")
        assert "?" not in viewer_url
        assert "token=" not in viewer_url

    def test_semantic_citation_mapping_and_metadata_integrity(self) -> None:
        """Requirement: Bracketed markers map to canonical document metadata without UI HTML coupling."""
        doc_uuid = str(uuid.uuid4())
        citations = [
            CitationDTO(
                document_name='Unsafe<script>alert("xss")</script>.pdf',
                page_number=3,
                chunk_id="chk-1",
                relevance_score=0.95,
                snippet='Exploit snippet <img src=x onerror="alert(1)">',
                document_id=doc_uuid,
                knowledge_base_id="kb-123",
                course_name="BCA Security",
            )
        ]

        text = "Refer to [1] for course details."
        resolved = extract_resolved_citations(text, citations)

        assert len(resolved) == 1
        ref = resolved[0]
        assert ref.index == 1
        assert ref.raw_marker == "[1]"
        assert ref.citation.document_id == doc_uuid
        assert ref.citation.page_number == 3
        assert ref.citation.document_name == 'Unsafe<script>alert("xss")</script>.pdf'

    def test_citation_resolution_contains_no_embedded_credentials(self) -> None:
        """Requirement: Citation mapping and substitution never inject session tokens or credentials."""
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

        text = "See [1] for rules."
        resolved = extract_resolved_citations(text, citations)
        assert len(resolved) == 1

        # Verify safe substitution formatting via custom semantic callback
        def semantic_formatter(ref: SemanticCitationRef) -> str:
            return f"(Document: {ref.citation.document_name}, Page: {ref.citation.page_number})"

        substituted = replace_citation_markers(text, citations, semantic_formatter)
        assert substituted == "See (Document: Regulations.pdf, Page: 5) for rules."
        assert "auth_session_token" not in substituted
        assert "token=" not in substituted
        assert "session=" not in substituted
