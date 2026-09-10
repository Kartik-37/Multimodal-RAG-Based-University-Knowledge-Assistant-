"""
Unit Tests for Frontend Presentation Layer and API Client Boundary.

Validates authentication state transitions, client operations, DTO serialization,
and route registration in the NiceGUI presentation shell.
"""

import pytest

from frontend.client.api_client import FrontendAPIClient
from frontend.client.models import (
    ChatMessageDTO,
    CitationDTO,
    DocumentDTO,
    KnowledgeBaseDTO,
    UserDTO,
)
from frontend.main import init_ui
from frontend.state.app_state import AppState


class TestFrontendAPIClient:
    """Test suite for FrontendAPIClient boundary."""

    def test_auth_lifecycle(self) -> None:
        client = FrontendAPIClient()
        assert client.get_current_user() is None

        # Successful login
        user = client.login("student@university.edu", "secret123")
        assert isinstance(user, UserDTO)
        assert user.email == "student@university.edu"
        assert client.get_current_user() == user

        # Logout
        client.logout()
        assert client.get_current_user() is None

        # Registration
        reg_user = client.register("newuser@university.edu", "pass456", "Jane Doe")
        assert reg_user.full_name == "Jane Doe"
        assert client.get_current_user() == reg_user

    def test_auth_invalid_inputs(self) -> None:
        client = FrontendAPIClient()

        with pytest.raises(ValueError, match="Email and password must not be empty"):
            client.login("", "secret")

        with pytest.raises(ValueError, match="Email and password must not be empty"):
            client.login("user@test.com", "")

        with pytest.raises(ValueError, match="All registration fields are required"):
            client.register("", "secret", "Name")

    def test_knowledge_base_operations(self) -> None:
        client = FrontendAPIClient()
        kbs = client.get_knowledge_bases()
        assert len(kbs) >= 1
        assert isinstance(kbs[0], KnowledgeBaseDTO)

        # Create new KB
        new_kb = client.create_knowledge_base("New Semester Syllabus", "Description text")
        assert new_kb.name == "New Semester Syllabus"
        assert new_kb.document_count == 0
        assert any(k.id == new_kb.id for k in client.get_knowledge_bases())

        # Empty name rejection
        with pytest.raises(ValueError, match="Knowledge base name cannot be empty"):
            client.create_knowledge_base("   ")

    def test_document_operations(self) -> None:
        client = FrontendAPIClient()
        kb = client.get_knowledge_bases()[0]
        initial_count = len(client.get_documents(kb.id))

        doc = client.upload_document(
            kb_id=kb.id,
            filename="curriculum_guide.pdf",
            content_size_bytes=204800,
        )
        assert isinstance(doc, DocumentDTO)
        assert doc.filename == "curriculum_guide.pdf"
        assert doc.file_type == "pdf"
        assert doc.status == "INDEXED"

        updated_docs = client.get_documents(kb.id)
        assert len(updated_docs) == initial_count + 1

    def test_chat_query_and_citations(self) -> None:
        client = FrontendAPIClient()
        kb = client.get_knowledge_bases()[0]

        # Valid chat message
        response = client.send_chat_message(kb_id=kb.id, question="What are the exam rules?")
        assert isinstance(response, ChatMessageDTO)
        assert response.role == "assistant"
        assert len(response.citations) > 0

        first_citation = response.citations[0]
        assert isinstance(first_citation, CitationDTO)
        assert first_citation.document_name != ""
        assert first_citation.chunk_id != ""
        assert first_citation.relevance_score > 0.0

        # Empty query validation
        with pytest.raises(ValueError, match="Question cannot be empty"):
            client.send_chat_message(kb_id=kb.id, question="   ")


class TestAppState:
    """Test suite for AppState presentation manager."""

    def test_active_kb_default(self) -> None:
        state = AppState()
        # Should default to the first available knowledge base
        assert state.active_kb is not None
        assert isinstance(state.active_kb, KnowledgeBaseDTO)

    def test_chat_history_flow(self) -> None:
        state = AppState()
        assert len(state.chat_history) == 0

        user_msg = state.add_user_message("Hello?")
        assert user_msg.role == "user"
        assert len(state.chat_history) == 1

        assistant_msg = ChatMessageDTO(
            id="resp-1",
            role="assistant",
            content="Hello there!",
            citations=[],
        )
        state.add_assistant_message(assistant_msg)
        assert len(state.chat_history) == 2

        state.clear_chat()
        assert len(state.chat_history) == 0
        assert state.selected_citation is None


def test_init_ui_routes() -> None:
    """Verify that NiceGUI route registration runs without error."""
    init_ui()


def test_page_layout_context_manager() -> None:
    """Verify page_layout context manager functions correctly for auth and unauth."""
    from frontend.client.api_client import api_client
    from frontend.components.layout import page_layout

    # Unauthenticated state with require_auth=True
    api_client.logout()
    with page_layout(title="Protected Page", require_auth=True):
        pass  # should not error

    # Authenticated state
    api_client.login("tester@example.edu", "secret")
    with page_layout(title="Protected Page", require_auth=True):
        pass  # should not error

    # Clean up
    api_client.logout()
