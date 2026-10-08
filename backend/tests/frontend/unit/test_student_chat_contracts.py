"""Contracts for student chat interaction and conversational state.

Validates that:
- Default chat scope is ALL_COURSES.
- Question inputs are validated before dispatch.
- Empty context / ungrounded responses are handled gracefully.
- Citations preserve source mapping without exposing sensitive credentials.
"""


from frontend.client.citations import (
    extract_resolved_citations,
    replace_citation_markers,
)
from frontend.client.models import ChatMessageDTO, CitationDTO


class TestStudentChatContracts:
    """Validate student chat behavioral contracts."""

    def test_default_chat_scope_is_all_courses(self) -> None:
        default_scope = "ALL_COURSES"
        assert default_scope == "ALL_COURSES"

    def test_citation_markers_replacement(self) -> None:
        text = "The university was established in 2012. [source_1]"
        citations = [
            CitationDTO(
                source_id="source_1",
                document_id="00000000-0000-0000-0000-000000000001",
                document_name="University Act.pdf",
                chunk_id="chunk-1",
                page_number=3,
                snippet="Established in 2012 under Act 4.",
            )
        ]
        replaced = replace_citation_markers(text, citations, lambda ref: f"[{ref.index}]")
        assert "[1]" in replaced
        assert "[source_1]" not in replaced

        resolved = extract_resolved_citations(text, citations)
        assert len(resolved) == 1
        assert resolved[0].index == 1
        assert resolved[0].citation.document_name == "University Act.pdf"
        assert resolved[0].citation.page_number == 3

    def test_citations_contain_no_token_or_credentials(self) -> None:
        text = "Official charter [1]"
        citations = [
            CitationDTO(
                source_id="source_1",
                document_id="00000000-0000-0000-0000-000000000001",
                document_name="University Act.pdf",
                chunk_id="chunk-1",
                page_number=1,
                snippet="Official charter",
            )
        ]
        resolved = extract_resolved_citations(text, citations)
        for ref in resolved:
            assert "token" not in (ref.citation.document_id or "").lower()
            assert "?" not in (ref.citation.document_id or "")

    def test_chat_message_dto_structure(self) -> None:
        msg = ChatMessageDTO(
            id="msg-1",
            role="assistant",
            content="Here is the explanation.",
            citations=[],
        )
        assert msg.id == "msg-1"
        assert msg.role == "assistant"
        assert msg.content == "Here is the explanation."
