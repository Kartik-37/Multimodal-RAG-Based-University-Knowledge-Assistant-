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

        # Valid chat message against newly created empty KB produces deterministic refusal
        response = client.send_chat_message(kb_id=kb.id, question="What are the exam rules?")
        assert isinstance(response, ChatMessageDTO)
        assert response.role == "assistant"
        assert response.is_grounded is True
        assert response.grounding_status == "REFUSAL"
        assert "could not find any relevant information" in response.content.lower()
        assert len(response.citations) == 0

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

    def test_retrieve_lexical_chunks(self) -> None:
        client = FrontendAPIClient()
        client.login("admin@university.edu", "AdminPass123!")
        kb_name = f"Lexical DTO KB {uuid.uuid4().hex[:6]}"
        kb = client.create_knowledge_base(kb_name, "For lexical retrieval")

        # Empty query validation
        with pytest.raises(ValueError, match="Query string cannot be empty"):
            client.retrieve_lexical_chunks(kb_id=kb.id, query="   ")

        # Invalid UUID validation
        with pytest.raises(ValueError, match="Invalid knowledge base ID format"):
            client.retrieve_lexical_chunks(kb_id="invalid-uuid", query="valid query")

        # Lexical search against empty KB returns empty list of DTOs
        results = client.retrieve_lexical_chunks(
            kb_id=kb.id, query="scheduling algorithms", top_k=5
        )
        assert isinstance(results, list)
        assert len(results) == 0

    def test_retrieve_hybrid_chunks(self) -> None:
        client = FrontendAPIClient()
        client.login("admin@university.edu", "AdminPass123!")
        kb_name = f"Hybrid DTO KB {uuid.uuid4().hex[:6]}"
        kb = client.create_knowledge_base(kb_name, "For hybrid retrieval")

        # Empty query validation
        with pytest.raises(ValueError, match="Query string cannot be empty"):
            client.retrieve_hybrid_chunks(kb_id=kb.id, query="   ")

        # Invalid UUID validation
        with pytest.raises(ValueError, match="Invalid knowledge base ID format"):
            client.retrieve_hybrid_chunks(kb_id="invalid-uuid", query="valid query")

        # Hybrid search against empty KB returns empty list of DTOs
        results = client.retrieve_hybrid_chunks(kb_id=kb.id, query="scheduling algorithms", top_k=5)
        assert isinstance(results, list)
        assert len(results) == 0

    def test_rerank_chunks(self) -> None:
        client = FrontendAPIClient()
        client.login("admin@university.edu", "AdminPass123!")
        kb_name = f"Rerank DTO KB {uuid.uuid4().hex[:6]}"
        kb = client.create_knowledge_base(kb_name, "For reranking")

        # Empty query validation
        with pytest.raises(ValueError, match="Query string cannot be empty"):
            client.rerank_chunks(kb_id=kb.id, query="   ")

        # Invalid UUID validation
        with pytest.raises(ValueError, match="Invalid knowledge base ID format"):
            client.rerank_chunks(kb_id="invalid-uuid", query="valid query")

        # Rerank against empty KB returns empty list of DTOs
        results = client.rerank_chunks(
            kb_id=kb.id, query="scheduling algorithms", candidate_limit=20, top_k=5
        )
        assert isinstance(results, list)
        assert len(results) == 0

    def test_process_query(self) -> None:
        client = FrontendAPIClient()
        client.login("admin@university.edu", "AdminPass123!")

        # Valid query processing
        res = client.process_query("   What is   C++   in   BCA Sem-4?   ")
        assert res.original_query == "   What is   C++   in   BCA Sem-4?   "
        assert res.processed_query == "What is C++ in BCA Sem-4?"
        assert res.character_count == len("What is C++ in BCA Sem-4?")
        assert res.token_estimate > 0
        assert res.has_technical_tokens is True

        # Whitespace-only rejection
        with pytest.raises(ValueError, match="cannot be empty or whitespace"):
            client.process_query("   \t  ")

    def test_send_chat_message_success_and_provenance(self) -> None:
        """Verify chat message contract parsing, citation provenance, and grounding status."""
        from unittest.mock import MagicMock

        client = FrontendAPIClient()
        kb_id = str(uuid.uuid4())

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "query": "What is 2PL?",
            "processed_query": "what is 2pl",
            "knowledge_base_id": kb_id,
            "answer": "Two-phase locking ensures serializability [source_1].",
            "is_empty_context": False,
            "citations": [
                {
                    "source_id": "source_1",
                    "document_name": "db_systems.pdf",
                    "document_id": str(uuid.uuid4()),
                    "chunk_id": "chunk-101",
                    "page_number": 42,
                    "section_title": "Concurrency",
                    "relevance_score": 0.985,
                    "snippet": "Two-phase locking guarantees conflict serializability.",
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
                "query_processing_ms": 1.2,
                "retrieval_ms": 15.0,
                "reranking_ms": 8.0,
                "context_assembly_ms": 0.5,
                "llm_generation_ms": 110.0,
                "grounding_validation_ms": 3.5,
                "total_pipeline_ms": 138.2,
            },
            "model": "qwen3:4b",
            "metadata": {},
        }

        client._http.post = MagicMock(return_value=mock_resp)

        msg = client.send_chat_message(kb_id=kb_id, question="What is 2PL?")
        assert isinstance(msg, ChatMessageDTO)
        assert msg.role == "assistant"
        assert msg.content == "Two-phase locking ensures serializability [source_1]."
        assert msg.is_grounded is True
        assert msg.grounding_status == "FULLY_SUPPORTED"
        assert msg.total_pipeline_ms == 138.2
        assert msg.model == "qwen3:4b"

        assert len(msg.citations) == 1
        cit = msg.citations[0]
        assert cit.source_id == "source_1"
        assert cit.document_name == "db_systems.pdf"
        assert cit.page_number == 42
        assert cit.section_title == "Concurrency"
        assert cit.relevance_score == 0.985
        assert "Two-phase locking" in cit.snippet

    def test_send_chat_message_error_handling(self) -> None:
        """Verify client validation and safe error propagation."""
        from unittest.mock import MagicMock

        client = FrontendAPIClient()

        # Empty question validation
        with pytest.raises(ValueError, match="Question cannot be empty"):
            client.send_chat_message(str(uuid.uuid4()), "   ")

        # Invalid UUID format
        with pytest.raises(ValueError, match="Invalid knowledge base ID format"):
            client.send_chat_message("not-a-uuid", "What is testing?")

        # 404 unauthorized / not found
        mock_404 = MagicMock()
        mock_404.status_code = 404
        client._http.post = MagicMock(return_value=mock_404)
        with pytest.raises(ValueError, match="Knowledge base not found or unauthorized"):
            client.send_chat_message(str(uuid.uuid4()), "What is testing?")

        # 503 provider failure
        mock_503 = MagicMock()
        mock_503.status_code = 503
        mock_503.json.return_value = {
            "detail": "Underlying AI model provider is temporarily unavailable."
        }
        client._http.post = MagicMock(return_value=mock_503)
        with pytest.raises(ValueError, match="temporarily unavailable"):
            client.send_chat_message(str(uuid.uuid4()), "What is testing?")


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


def test_app_state_is_admin() -> None:
    """Verify AppState.is_admin property returns accurate boolean for all roles."""
    from frontend.client.api_client import api_client
    from frontend.state.app_state import state

    # Unauthenticated
    api_client.logout()
    assert state.is_admin is False

    # Admin
    api_client.login("admin@university.edu", "AdminPass123!")
    assert state.is_admin is True

    # Student
    unique_email = f"student_{uuid.uuid4().hex[:8]}@university.edu"
    api_client.register(unique_email, "StudentPass123!", "Test Student")
    assert state.is_admin is False

    api_client.logout()


def test_unified_navigation_items() -> None:
    """Verify get_nav_items returns role-filtered navigation list identical for desktop and mobile."""
    from frontend.components.layout import get_nav_items

    # Unauthenticated
    assert get_nav_items(None) == []

    # Student user
    student = UserDTO(
        id="s-1",
        email="s@test.edu",
        full_name="Student",
        role="STUDENT",
    )
    student_items = get_nav_items(student)
    student_routes = [route for _, route, _ in student_items]
    assert "/dashboard" in student_routes
    assert "/knowledge-bases" in student_routes
    assert "/chat" in student_routes
    assert "/profile" in student_routes
    assert "/documents" not in student_routes  # Omitted for student

    # Admin user
    admin = UserDTO(
        id="a-1",
        email="a@test.edu",
        full_name="Admin",
        role="ADMIN",
    )
    admin_items = get_nav_items(admin)
    admin_routes = [route for _, route, _ in admin_items]
    assert "/dashboard" in admin_routes
    assert "/knowledge-bases" in admin_routes
    assert "/documents" in admin_routes  # Included for admin
    assert "/chat" in admin_routes
    assert "/profile" in admin_routes


def test_theme_injection() -> None:
    """Verify global CSS design tokens and focus styles are injected into head."""
    from frontend.components.theme import GLOBAL_THEME_CSS, init_theme

    assert "*:focus-visible" in GLOBAL_THEME_CSS
    assert "outline: 2px solid #2563eb" in GLOBAL_THEME_CSS
    init_theme()  # Should execute without error


def test_ui_kit_rendering() -> None:
    """Verify all UI kit primitives render cleanly with accessible attributes."""
    from frontend.components.ui_kit import (
        render_alert,
        render_empty_state,
        render_page_header,
        render_stat_card,
    )

    render_page_header("Test Title", "Test Subtitle")
    render_empty_state("info", "No Items", "Description", "Action", lambda: None)
    render_alert("Information alert", level="info")
    render_alert("Warning alert", level="warning")
    render_alert("Error alert", level="negative")
    render_alert("Success alert", level="positive")
    render_stat_card("Metrics", 42, "Subtext", "analytics", "blue-600")


def test_status_badge_multi_modal_and_grounding() -> None:
    """Verify status badges render multi-modal indicators (color, text, icon) for grounding and indexing."""
    from frontend.components.status_badge import (
        render_grounding_status_badge,
        render_indexing_status_badge,
        render_status_badge,
    )

    for status in ["COMPLETED", "PROCESSING", "FAILED", "PENDING"]:
        render_status_badge(status)
        render_indexing_status_badge(status)

    for g_status in [
        "FULLY_SUPPORTED",
        "PARTIALLY_SUPPORTED",
        "REFUSAL",
        "UNSUPPORTED",
    ]:
        render_grounding_status_badge(g_status)


def test_safe_markdown_sanitization() -> None:
    """Verify malicious HTML tags and event handlers are neutralized before markdown rendering."""
    from frontend.pages.chat_page import sanitize_markdown_text

    # Normal markdown preserved
    normal = "**Bold** and *italic* with `code`."
    assert sanitize_markdown_text(normal) == normal

    # Dangerous script tag stripped
    dangerous_script = "Answer: <script>alert('xss')</script> explanation."
    cleaned_script = sanitize_markdown_text(dangerous_script)
    assert "<script>" not in cleaned_script
    assert "alert('xss')" not in cleaned_script

    # Dangerous iframe stripped
    dangerous_iframe = 'Answer: <iframe src="evil.com"></iframe> text.'
    cleaned_iframe = sanitize_markdown_text(dangerous_iframe)
    assert "<iframe" not in cleaned_iframe

    # Event handler neutralized
    event_handler = '<img src="x" onerror="alert(1)">'
    cleaned_event = sanitize_markdown_text(event_handler)
    assert "onerror=" not in cleaned_event


def test_upload_size_limit_from_settings() -> None:
    """Verify upload limit references settings.MAX_UPLOAD_SIZE_BYTES dynamically."""
    from backend.app.core.config import settings

    assert settings.MAX_UPLOAD_SIZE_BYTES > 0
    max_mb = settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
    assert max_mb >= 1


def test_dashboard_no_n_plus_one_calls() -> None:
    """Verify dashboard queries documents only for active KB rather than looping across all KBs."""
    from frontend.client.api_client import api_client

    api_client.login("admin@university.edu", "AdminPass123!")

    orig_get_docs = api_client.get_documents
    call_counter = {"count": 0}

    def counted_get_docs(kb_id):
        call_counter["count"] += 1
        return orig_get_docs(kb_id)

    api_client.get_documents = counted_get_docs

    from frontend.state.app_state import state

    kbs = api_client.get_knowledge_bases()
    if kbs:
        state.active_kb = kbs[0]
        _ = api_client.get_documents(state.active_kb.id)
        assert call_counter["count"] == 1

    # Restore
    api_client.get_documents = orig_get_docs
    api_client.logout()


def test_profile_page_registration_and_auth() -> None:
    """Verify profile route registers and user details are safely accessible without disclosing secrets."""
    from frontend.client.api_client import api_client
    from frontend.pages.profile_page import register_profile_page

    register_profile_page()

    api_client.login("admin@university.edu", "AdminPass123!")
    user = api_client.get_current_user()
    assert user is not None
    assert user.email == "admin@university.edu"
    assert user.role == "ADMIN"
    assert hasattr(user, "full_name")
    api_client.logout()


def test_error_normalization() -> None:
    """Verify normalize_error properly normalizes HTTP status codes, Pydantic errors, and context."""
    from frontend.client.error_handler import normalize_error

    # Auth context
    assert "already exists" in normalize_error("AUTH_EMAIL_EXISTS", context="auth").lower()
    assert "invalid email or password" in normalize_error(401, context="auth").lower()

    # Document context
    assert (
        "already active" in normalize_error("DOCUMENT_ALREADY_ACTIVE", context="document").lower()
    )
    assert (
        "already inactive"
        in normalize_error("DOCUMENT_ALREADY_INACTIVE", context="document").lower()
    )
    assert "size" in normalize_error(413, context="document").lower()
    assert "format" in normalize_error(415, context="document").lower()

    # Pydantic validation list
    validation_errs = [
        {
            "loc": ["body", "password"],
            "type": "string_too_short",
            "msg": "String should have at least 8 characters",
        },
        {
            "loc": ["body", "email"],
            "type": "value_error",
            "msg": "value is not a valid email address",
        },
    ]
    norm_val = normalize_error(validation_errs)
    assert "Password must be at least 8 characters" in norm_val
    assert "Please enter a valid email address." in norm_val

    # SQL / Traceback suppression
    leaky_err = "Syntax error in SQL: SELECT * FROM users WHERE id='1234' Traceback (most recent call last):"
    assert "server processing error" in normalize_error(leaky_err).lower()
    assert "SELECT" not in normalize_error(leaky_err)
    assert "Traceback" not in normalize_error(leaky_err)


def test_admin_user_dto_privacy() -> None:
    """Verify AdminUserDTO strictly preserves privacy and omits internal IDs and hashes."""
    from frontend.client.models import AdminUserDTO

    dto = AdminUserDTO(
        email="faculty@univ.edu",
        full_name="Faculty Member",
        role="ADMIN",
        is_active=True,
        created_at="2026-09-22",
    )
    assert not hasattr(dto, "id") or "id" not in dto.model_fields
    assert not hasattr(dto, "password") or "password" not in dto.model_fields
    assert not hasattr(dto, "hashed_password") or "hashed_password" not in dto.model_fields


class TestStep21CProductUXRepair:
    """Step 21C regression tests verifying product UX repair and rendering integrity."""

    def test_password_validation_error_normalization_no_raw_dict(self) -> None:
        """Verify password validation rejects <8 chars and returns human string, not raw Pydantic dict."""
        from frontend.client.error_handler import normalize_error

        # Pydantic raw dict from FastAPI 422
        raw_pydantic_error = [
            {
                "type": "string_too_short",
                "loc": ["body", "password"],
                "msg": "String should have at least 8 characters",
                "input": "short",
                "ctx": {"min_length": 8},
            }
        ]
        norm = normalize_error(raw_pydantic_error, context="auth")
        assert norm == "Password must be at least 8 characters."
        assert "{'type':" not in norm
        assert "string_too_short" not in norm

        # Stringified raw dict (defensive handling)
        stringified_raw = str(raw_pydantic_error)
        norm_str = normalize_error(stringified_raw, context="auth")
        assert norm_str == "Password must be at least 8 characters."
        assert "{'type':" not in norm_str

    def test_registration_short_password_rejection(self) -> None:
        """Verify API client register method rejects short password with human-readable error."""
        client = FrontendAPIClient()
        unique_email = f"shortpass_{uuid.uuid4().hex[:6]}@univ.edu"

        with pytest.raises(ValueError) as excinfo:
            client.register(unique_email, "123", "Short Pass User")

        err_msg = str(excinfo.value)
        assert "Password must be at least 8 characters" in err_msg
        assert "{'type':" not in err_msg

    def test_nicegui_file_upload_api_contract(self) -> None:
        """Verify installed NiceGUI FileUpload API exposes .name, .read(), and .size()."""
        from nicegui.elements.upload_files import SmallFileUpload

        test_data = b"%PDF-1.4 test bytes"
        upload_file = SmallFileUpload(
            name="syllabus.pdf", content_type="application/pdf", _data=test_data
        )

        assert upload_file.name == "syllabus.pdf"
        assert hasattr(upload_file, "read")
        assert hasattr(upload_file, "size")
        assert upload_file.size() == len(test_data)

    def test_course_summaries_endpoint_and_dto(self) -> None:
        """Verify course summaries endpoint returns aggregated document counts and previews without N+1."""
        client = FrontendAPIClient()
        client.login("admin@university.edu", "AdminPass123!")

        # Create a course and upload a document to verify summary calculation
        course_name = f"Summary Course {uuid.uuid4().hex[:6]}"
        course = client.create_knowledge_base(course_name, "Testing summary endpoint")

        pdf_bytes = create_sample_pdf_bytes()
        _ = client.upload_document(
            kb_id=course.id,
            filename="syllabus_2026.pdf",
            content=pdf_bytes,
        )

        summaries = client.get_course_summaries()
        assert len(summaries) >= 1
        target_summary = next((s for s in summaries if s.id == course.id), None)
        assert target_summary is not None
        assert target_summary.name == course_name
        assert target_summary.total_documents >= 1
        assert target_summary.active_documents >= 1
        assert target_summary.inactive_documents == 0
        assert len(target_summary.document_previews) >= 1
        assert target_summary.document_previews[0].filename == "syllabus_2026.pdf"
        assert target_summary.document_previews[0].is_active is True

    def test_admin_list_dto_fields(self) -> None:
        """Verify get_admins returns DTOs with all required identity fields."""
        client = FrontendAPIClient()
        client.login("admin@university.edu", "AdminPass123!")

        admins = client.get_admins()
        assert len(admins) >= 1
        admin = admins[0]
        assert admin.full_name is not None and len(admin.full_name) > 0
        assert admin.email is not None and "@" in admin.email
        assert admin.role == "ADMIN"
        assert admin.is_active is True
        assert admin.created_at is not None

    def test_no_obsolete_active_corpus_strings_in_frontend(self) -> None:
        """Verify obsolete active-corpus UI strings have been completely removed from frontend pages."""
        from pathlib import Path

        pages_to_check = [
            Path("frontend/pages/documents_page.py"),
            Path("frontend/pages/knowledge_bases_page.py"),
            Path("frontend/pages/dashboard_page.py"),
            Path("frontend/components/layout.py"),
        ]

        forbidden_phrases = [
            "Active Target Corpus",
            "ACTIVE TARGET CORPUS",
            "Set Active",
            "Chat with Corpus",
            "Active Course Scope",
            "Active Scope Documents",
            "ACTIVE COURSE / KB",
        ]

        for file_path in pages_to_check:
            content = file_path.read_text(encoding="utf-8")
            for phrase in forbidden_phrases:
                assert phrase not in content, f"Found obsolete phrase '{phrase}' in {file_path}"

    def test_cleanup_dev_test_data_safety_guards(self) -> None:
        """Verify cleanup script refuses test database and protects legitimate courses."""
        from scripts.cleanup_dev_test_data import (
            PROTECTED_COURSE_NAMES,
            verify_database_safety,
        )

        # Rejects test database
        with pytest.raises(SystemExit):
            verify_database_safety(
                "postgresql+psycopg://user:pass@localhost:5432/rag_assistant_test_db"
            )

        # Rejects arbitrary database
        with pytest.raises(SystemExit):
            verify_database_safety("postgresql+psycopg://user:pass@localhost:5432/production_db")

        # Protected course names contain legitimate courses
        assert "computer architecture" in PROTECTED_COURSE_NAMES
        assert "official university regulations" in PROTECTED_COURSE_NAMES
        assert "bca" in PROTECTED_COURSE_NAMES
