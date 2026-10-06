"""
Integration Tests for Frontend API Client Workflows and Route Registration.

Validates end-to-end integration contracts between FrontendAPIClient, NiceGUI
route registration, FastAPI API endpoints, and the PostgreSQL database:
- User registration, login, and session clearance against real database.
- Knowledge base CRUD workflows.
- Document upload, listing, and deletion workflows.
- Backend query processing integration.
- Public registration strict student role assignment.
- Application and authentication route registration contracts.
"""

import uuid

import pytest
from nicegui import app as nicegui_app

from backend.tests.fixtures_documents import create_sample_pdf_bytes
from frontend.client.api_client import FrontendAPIClient
from frontend.client.models import (
    DocumentDTO,
    KnowledgeBaseDTO,
    UserDTO,
)
from frontend.main import init_ui
from frontend.pages.auth_pages import register_auth_pages
from scripts.bootstrap_admin import bootstrap_admin


@pytest.fixture(autouse=True)
def ensure_admin_bootstrapped() -> None:
    """Ensure standard test administrator exists for client operations."""
    bootstrap_admin("admin@university.edu", "AdminPass123!", "System Administrator")


class TestFrontendAPIClientWorkflows:
    """Integration test suite for FrontendAPIClient interacting with real FastAPI and PostgreSQL."""

    def test_api_client_student_registration_and_login_lifecycle(self) -> None:
        client = FrontendAPIClient()
        unique_email = f"student_{uuid.uuid4().hex[:8]}@university.edu"
        full_name = "Alex Mercer"

        # Registration creates STUDENT account
        reg_user = client.register(unique_email, "SecurePassword123!", full_name)
        assert isinstance(reg_user, UserDTO)
        assert reg_user.email == unique_email
        assert reg_user.full_name == full_name
        assert reg_user.role == "STUDENT"
        assert client.get_current_user() == reg_user

        # Logout clears current user
        client.logout()
        assert client.get_current_user() is None

        # Login re-establishes authenticated session
        login_user = client.login(unique_email, "SecurePassword123!")
        assert isinstance(login_user, UserDTO)
        assert login_user.email == unique_email
        assert client.get_current_user() == login_user

    def test_api_client_knowledge_base_crud_contracts(self) -> None:
        client = FrontendAPIClient()
        client.login("admin@university.edu", "AdminPass123!")
        unique_name = f"Course-{uuid.uuid4().hex[:6]}"

        # Create
        kb = client.create_knowledge_base(unique_name, "Course syllabus")
        assert isinstance(kb, KnowledgeBaseDTO)
        assert kb.name == unique_name
        assert kb.document_count == 0

        # List
        all_kbs = client.get_knowledge_bases()
        assert any(k.id == kb.id for k in all_kbs)

        # Empty name rejection
        with pytest.raises(ValueError, match="Knowledge base name cannot be empty"):
            client.create_knowledge_base("   ")

    def test_api_client_document_crud_contracts(self) -> None:
        client = FrontendAPIClient()
        client.login("admin@university.edu", "AdminPass123!")
        kb = client.create_knowledge_base(f"DocKB-{uuid.uuid4().hex[:6]}", "Docs")

        pdf_bytes = create_sample_pdf_bytes()
        doc = client.upload_document(
            kb_id=kb.id,
            filename="syllabus.pdf",
            content=pdf_bytes,
        )
        assert isinstance(doc, DocumentDTO)
        assert doc.filename == "syllabus.pdf"
        assert doc.file_type == "pdf"
        assert doc.status in ("PENDING", "PROCESSING", "COMPLETED")

        # List contains document
        docs = client.get_documents(kb.id)
        assert any(d.id == doc.id for d in docs)

        # Delete document
        client.delete_document(kb.id, doc.id)
        docs_after = client.get_documents(kb.id)
        assert not any(d.id == doc.id for d in docs_after)

    def test_api_client_query_processing_contract(self) -> None:
        client = FrontendAPIClient()
        client.login("admin@university.edu", "AdminPass123!")

        res = client.process_query("   What is   TCP   in   BCA Sem-4?   ")
        assert res.original_query == "   What is   TCP   in   BCA Sem-4?   "
        assert res.processed_query == "What is TCP in BCA Sem-4?"
        assert res.character_count == len("What is TCP in BCA Sem-4?")
        assert res.token_estimate > 0
        assert res.has_technical_tokens is True

    def test_registration_is_strictly_student(self) -> None:
        client = FrontendAPIClient()
        unique_email = f"student_check_{uuid.uuid4().hex[:6]}@univ.edu"
        user = client.register(unique_email, "StudentPass123!", "Strict Student")

        assert user.role == "STUDENT"
        assert getattr(user, "admin_role", None) is None


class TestFrontendRouteContracts:
    """Integration test suite for NiceGUI route registration contracts."""

    def test_protected_page_routes_registered(self) -> None:
        init_ui()
        registered_paths = [r.path for r in nicegui_app.routes if hasattr(r, "path")]

        expected_routes = [
            "/",
            "/login",
            "/student/login",
            "/admin/login",
            "/register",
            "/dashboard",
            "/knowledge-bases",
            "/chat",
            "/documents",
            "/profile",
        ]
        for route in expected_routes:
            assert route in registered_paths, f"Expected route {route} not registered"

    def test_auth_routes_registration(self) -> None:
        register_auth_pages()
        registered = [r.path for r in nicegui_app.routes if hasattr(r, "path")]
        assert "/login" in registered
        assert "/student/login" in registered
        assert "/admin/login" in registered
        assert "/register" in registered
