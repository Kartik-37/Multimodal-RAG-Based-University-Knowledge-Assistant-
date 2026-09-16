"""
Unit Tests for Frontend Presentation Layer and API Client Boundary.

Validates authentication state transitions, client operations, DTO serialization,
and route registration in the NiceGUI presentation shell with real backend integration.
"""

import uuid

import pytest

from backend.tests.fixtures_documents import create_sample_pdf_bytes
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
from scripts.bootstrap_admin import bootstrap_admin


@pytest.fixture(autouse=True)
def ensure_admin_bootstrapped() -> None:
    """Ensure the standard test admin exists before running frontend unit tests."""
    bootstrap_admin("admin@university.edu", "AdminPass123!", "System Administrator")


class TestFrontendAPIClient:
    """Test suite for FrontendAPIClient boundary."""

    def test_auth_lifecycle(self) -> None:
        client = FrontendAPIClient()
        assert client.get_current_user() is None

        # Registration creates real student account in database
        unique_email = f"test_student_{uuid.uuid4().hex[:8]}@university.edu"
        reg_user = client.register(unique_email, "SecurePassword123!", "Jane Doe")
        assert isinstance(reg_user, UserDTO)
        assert reg_user.email == unique_email
        assert reg_user.full_name == "Jane Doe"
        assert reg_user.role == "STUDENT"
        assert client.get_current_user() == reg_user

        # Logout
        client.logout()
        assert client.get_current_user() is None

        # Login with newly created user
        user = client.login(unique_email, "SecurePassword123!")
        assert isinstance(user, UserDTO)
        assert user.email == unique_email
        assert client.get_current_user() == user

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
        client.login("admin@university.edu", "AdminPass123!")
        initial_kbs = client.get_knowledge_bases()
        unique_name = f"Test KB {uuid.uuid4().hex[:6]}"

        # Create
        new_kb = client.create_knowledge_base(unique_name, "Unit test knowledge base")
        assert isinstance(new_kb, KnowledgeBaseDTO)
        assert new_kb.name == unique_name
        assert new_kb.document_count == 0

        # List contains created
        kbs = client.get_knowledge_bases()
        assert len(kbs) == len(initial_kbs) + 1
        assert any(k.id == new_kb.id for k in kbs)

        # Empty name rejection
        with pytest.raises(ValueError, match="Knowledge base name cannot be empty"):
            client.create_knowledge_base("   ")

    def test_document_operations(self) -> None:
        client = FrontendAPIClient()
        client.login("admin@university.edu", "AdminPass123!")
        kb_name = f"Doc Test KB {uuid.uuid4().hex[:6]}"
        kb = client.create_knowledge_base(kb_name, "For docs")
        initial_count = len(client.get_documents(kb.id))

        pdf_bytes = create_sample_pdf_bytes()
        doc = client.upload_document(
            kb_id=kb.id,
            filename="curriculum_guide.pdf",
            content=pdf_bytes,
        )
        assert isinstance(doc, DocumentDTO)
        assert doc.filename == "curriculum_guide.pdf"
        assert doc.file_type == "pdf"
        assert doc.status in ("PENDING", "PROCESSING", "COMPLETED")

        updated_docs = client.get_documents(kb.id)
        assert len(updated_docs) == initial_count + 1

        # Delete document
        client.delete_document(kb.id, doc.id)
        remaining_docs = client.get_documents(kb.id)
        assert len(remaining_docs) == initial_count

    def test_chat_query_and_citations(self) -> None:
        client = FrontendAPIClient()
        client.login("admin@university.edu", "AdminPass123!")
        kb_name = f"Chat Test KB {uuid.uuid4().hex[:6]}"
        kb = client.create_knowledge_base(kb_name, "For chat")

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

    def test_retrieve_chunks(self) -> None:
        client = FrontendAPIClient()
        client.login("admin@university.edu", "AdminPass123!")
        kb_name = f"Retrieval DTO KB {uuid.uuid4().hex[:6]}"
        kb = client.create_knowledge_base(kb_name, "For vector retrieval")

        # Empty query validation
        with pytest.raises(ValueError, match="Query string cannot be empty"):
            client.retrieve_chunks(kb_id=kb.id, query="   ")

        # Invalid UUID validation
        with pytest.raises(ValueError, match="Invalid knowledge base ID format"):
            client.retrieve_chunks(kb_id="invalid-uuid", query="valid query")

        # Vector search against empty KB returns empty list of DTOs
        results = client.retrieve_chunks(kb_id=kb.id, query="What is an index?", top_k=5)
        assert isinstance(results, list)
        assert len(results) == 0


class TestAppState:
    """Test suite for AppState presentation manager."""

    def test_active_kb_management(self) -> None:
        state = AppState()
        sample_kb = KnowledgeBaseDTO(
            id=str(uuid.uuid4()),
            name="Sample Active KB",
            description="Sample",
            document_count=0,
            created_at="2026-09-10",
        )
        state.active_kb = sample_kb
        assert state.active_kb == sample_kb
        assert state.active_kb.name == "Sample Active KB"

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
    api_client.login("admin@university.edu", "AdminPass123!")
    with page_layout(title="Protected Page", require_auth=True):
        pass  # should not error

    # Clean up
    api_client.logout()


def test_evidence_panel_rendering() -> None:
    """Verify evidence panel renders both empty and populated states without exception."""
    from frontend.components.evidence_panel import render_evidence_panel

    # Empty citations
    render_evidence_panel(citations=[])

    # Populated citations
    sample_citations = [
        CitationDTO(
            document_name="sample.pdf",
            page_number=1,
            chunk_id="chunk-1",
            relevance_score=0.92,
            snippet="Sample citation text.",
        )
    ]
    render_evidence_panel(
        citations=sample_citations,
        selected_citation=sample_citations[0],
        on_select=lambda _: None,
    )


def test_status_badge_rendering() -> None:
    """Verify status badges render without exception for all lifecycle states."""
    from frontend.components.status_badge import render_status_badge

    for status in ["INDEXED", "PROCESSING", "FAILED", "UPLOADED", "UNKNOWN"]:
        render_status_badge(status)


def test_document_format_helpers() -> None:
    """Verify byte formatting and supported format extensions."""
    from frontend.pages.documents_page import SUPPORTED_EXTENSIONS, format_bytes

    assert format_bytes(500) == "500 B"
    assert format_bytes(2048) == "2.0 KB"
    assert format_bytes(2 * 1024 * 1024) == "2.00 MB"

    for ext in [".pdf", ".docx", ".txt", ".md", ".csv"]:
        assert ext in SUPPORTED_EXTENSIONS
