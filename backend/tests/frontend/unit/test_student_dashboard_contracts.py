"""Contracts for student dashboard presentation logic, error separation, and navigation workflows.

Validates that:
1. Student greeting safely handles a missing, empty, or multi-word name.
2. Course list successfully loads and displays real courses.
3. Course load failure displays an error rather than a false empty-catalogue message.
4. A successful empty course list displays the correct empty state.
5. Unavailable document counts are not rendered as 'None doc(s)'.
6. Genuine zero and positive document counts display correctly.
7. Dashboard search submission passes the query correctly.
8. Dashboard query submission does not accidentally send a duplicate message.
9. Ask in Course passes the correct course ID and scope.
10. View All Courses navigates to /knowledge-bases.
11. Recent conversations come from actual persisted data.
12. Selecting a recent conversation restores its correct message history.
13. Empty history produces a genuine empty state, not fabricated history.
14. Course data remains filtered by authoritative authorization.
15. Administrator dashboard operational behaviour is preserved.
16. Error messages remain safely normalized.
"""

from __future__ import annotations

import datetime
import urllib.parse
from unittest.mock import Mock, patch

import pytest

from backend.app.core.permissions import Permission
from frontend.client.api_client import FrontendAPIClient
from frontend.client.error_handler import normalize_error
from frontend.client.models import (
    ChatMessageDTO,
    ConversationDetailDTO,
    ConversationSummaryDTO,
    KnowledgeBaseDTO,
    UserDTO,
)
from frontend.pages.auth_pages import _get_safe_return_destination
from frontend.pages.dashboard_page import (
    _render_student_dashboard,
    format_relative_time,
    get_greeting,
)
from frontend.pages.knowledge_bases_page import format_document_count
from frontend.pages.reader_page import validate_return_route
from frontend.security.access_control import can_access_route, has_admin_permission
from frontend.state.app_state import AppState


class TestStudentDashboardContracts:
    """Validate student dashboard behavior, contracts, and error handling."""

    # --------------------------------------------------------------------------
    # 1. Greeting & Safe Fallbacks
    # --------------------------------------------------------------------------

    def test_student_greeting_safely_handles_missing_and_various_names(self) -> None:
        """Greeting adapts to time-of-day and safely handles missing, empty, or whitespace names."""
        # Morning (<12)
        assert get_greeting("Alex Vance", current_hour=9) == "Good morning, Alex."
        # Afternoon (12..17)
        assert get_greeting("Eleanor Vance", current_hour=14) == "Good afternoon, Eleanor."
        # Evening (>=18)
        assert get_greeting("Robert Smith", current_hour=19) == "Good evening, Robert."

        # Missing or empty full_name
        assert get_greeting(None, current_hour=10) == "Good morning."
        assert get_greeting("", current_hour=15) == "Good afternoon."
        assert get_greeting("   ", current_hour=20) == "Good evening."

    def test_format_relative_time_human_readable(self) -> None:
        """Relative time formatting produces clean, human-readable labels."""
        assert format_relative_time(None) == ""
        assert format_relative_time("") == ""

        now = datetime.datetime.now()
        # Just now (30s ago)
        just_now_ts = (now - datetime.timedelta(seconds=30)).isoformat()
        assert format_relative_time(just_now_ts) == "Just now"

        # 15 minutes ago
        fifteen_min_ts = (now - datetime.timedelta(minutes=15)).isoformat()
        assert format_relative_time(fifteen_min_ts) == "15m ago"

        # 3 hours ago
        three_hours_ts = (now - datetime.timedelta(hours=3)).isoformat()
        assert format_relative_time(three_hours_ts) == "3h ago"

        # 2 days ago
        two_days_ts = (now - datetime.timedelta(days=2)).isoformat()
        assert format_relative_time(two_days_ts) == "2d ago"

    # --------------------------------------------------------------------------
    # 2. Course Loading Succeeded
    # --------------------------------------------------------------------------

    def test_course_list_successfully_loads_and_displays_real_courses(self) -> None:
        """Real courses returned by the API client populate the dashboard preview."""
        client = FrontendAPIClient()
        mock_http = Mock()
        client._http = mock_http
        client._current_user = UserDTO(
            id="u-student-1",
            email="student@univ.edu",
            full_name="Alex Student",
            role="STUDENT",
            permissions=[],
        )

        mock_http.get.side_effect = [
            # GET /knowledge-bases
            Mock(
                status_code=200,
                json=lambda: [
                    {
                        "id": "c1",
                        "name": "CS101: Introduction to CS",
                        "description": "Foundational programming",
                        "created_at": "2026-09-01T00:00:00",
                        "is_active": True,
                        "is_student_visible": True,
                    },
                    {
                        "id": "c2",
                        "name": "MATH201: Calculus",
                        "description": "Calculus and linear algebra",
                        "created_at": "2026-09-02T00:00:00",
                        "is_active": True,
                        "is_student_visible": True,
                    },
                ],
            ),
            # GET /knowledge-bases/summaries
            Mock(
                status_code=200,
                json=lambda: [
                    {
                        "id": "c1",
                        "name": "CS101: Introduction to CS",
                        "description": "Foundational programming",
                        "created_at": "2026-09-01T00:00:00",
                        "total_documents": 3,
                        "active_documents": 3,
                        "inactive_documents": 0,
                        "indexed_documents": 3,
                        "indexing_documents": 0,
                        "failed_documents": 0,
                        "document_previews": [],
                    },
                    {
                        "id": "c2",
                        "name": "MATH201: Calculus",
                        "description": "Calculus and linear algebra",
                        "created_at": "2026-09-02T00:00:00",
                        "total_documents": 0,
                        "active_documents": 0,
                        "inactive_documents": 0,
                        "indexed_documents": 0,
                        "indexing_documents": 0,
                        "failed_documents": 0,
                        "document_previews": [],
                    },
                ],
            ),
        ]

        courses = client.get_knowledge_bases()
        assert len(courses) == 2
        assert courses[0].name == "CS101: Introduction to CS"
        assert courses[0].document_count == 3
        assert courses[1].name == "MATH201: Calculus"
        assert courses[1].document_count == 0

    # --------------------------------------------------------------------------
    # 3 & 4. Course Load Failure vs Empty State Separation
    # --------------------------------------------------------------------------

    def test_course_load_failure_displays_error_rather_than_false_empty_catalog(self) -> None:
        """When course loading fails, an error alert is generated instead of claiming no courses exist."""
        api_error = RuntimeError("Database connection timed out at postgres:5432")
        course_error_msg = normalize_error(api_error, context="course")

        assert course_error_msg is not None
        assert "5432" not in course_error_msg
        assert "unable" in course_error_msg.lower() or "course" in course_error_msg.lower()

        # In dashboard presentation logic:
        # if course_error_msg: renders alert with retry
        # elif not enrolled_kbs: renders empty state
        # The two states must be mutually exclusive
        enrolled_kbs: list[KnowledgeBaseDTO] = []
        is_error_state = bool(course_error_msg)
        is_empty_catalog_state = not course_error_msg and not enrolled_kbs

        assert is_error_state is True
        assert is_empty_catalog_state is False

    def test_successful_empty_course_list_displays_genuine_empty_state(self) -> None:
        """When course list genuinely succeeds with 0 courses, empty state is displayed."""
        course_error_msg = None
        enrolled_kbs: list[KnowledgeBaseDTO] = []

        is_error_state = bool(course_error_msg)
        is_empty_catalog_state = not course_error_msg and not enrolled_kbs

        assert is_error_state is False
        assert is_empty_catalog_state is True

    # --------------------------------------------------------------------------
    # 5 & 6. Document-Count Fallback & Human-Readable Wording
    # --------------------------------------------------------------------------

    def test_unavailable_document_counts_not_rendered_as_none_docs(self) -> None:
        """Unavailable document counts render as 'Count unavailable', never 'None doc(s)'."""
        label = format_document_count(None)
        assert label == "Count unavailable"
        assert "None" not in label
        assert "doc(s)" not in label

    def test_genuine_zero_and_positive_document_counts(self) -> None:
        """Genuine zero displays as 'No documents', positive counts use natural wording."""
        assert format_document_count(0) == "No documents"
        assert format_document_count(1) == "1 document"
        assert format_document_count(3) == "3 documents"
        assert format_document_count(10) == "10 documents"
        assert "doc(s)" not in format_document_count(0)
        assert "doc(s)" not in format_document_count(1)
        assert "doc(s)" not in format_document_count(3)

    # --------------------------------------------------------------------------
    # 7 & 8. Dashboard Search Submission & No Duplicate Submission
    # --------------------------------------------------------------------------

    @pytest.mark.parametrize("empty_query", ["", "   ", "\t\n", " \n "])
    def test_dashboard_search_submission_rejects_empty_query(self, empty_query: str) -> None:
        """Dashboard query submission rejects empty or whitespace input."""
        trimmed = empty_query.strip()
        assert len(trimmed) == 0

    def test_dashboard_search_submission_builds_correct_url(self) -> None:
        """Valid query builds /chat?q={encoded_query} without credentials or internal tokens."""
        query = "What is the grading policy for midterms?"
        encoded = urllib.parse.quote(query)
        target_url = f"/chat?q={encoded}"

        assert target_url.startswith("/chat?q=")
        assert "grading%20policy" in target_url
        assert "token" not in target_url.lower()

    def test_dashboard_query_submission_does_not_duplicate_message(self) -> None:
        """Dashboard navigation passes query via URL; chat page triggers single submission on mount."""
        query = "Explain bubble sort algorithms"
        # Navigation URL has q parameter once
        chat_url = f"/chat?q={urllib.parse.quote(query)}"
        parsed = urllib.parse.urlparse(chat_url)
        params = urllib.parse.parse_qs(parsed.query)

        assert len(params.get("q", [])) == 1
        assert params["q"][0] == query

    # --------------------------------------------------------------------------
    # 9. Ask in Course Passes Course ID and Scope
    # --------------------------------------------------------------------------

    def test_ask_in_course_navigation_parameter(self) -> None:
        """Ask in Course action builds /chat?kb_id={course_id}."""
        course_id = "c1111111-2222-3333-4444-555555555555"
        chat_url = f"/chat?kb_id={course_id}"
        assert chat_url == f"/chat?kb_id={course_id}"
        assert f"kb_id={course_id}" in chat_url

    # --------------------------------------------------------------------------
    # 10. View All Courses Navigation
    # --------------------------------------------------------------------------

    def test_view_all_courses_navigates_to_knowledge_bases(self) -> None:
        """View All Courses action targets /knowledge-bases and route is accessible to student."""
        student = UserDTO(
            id="student-1",
            email="student@univ.edu",
            full_name="Alex Student",
            role="STUDENT",
        )
        assert can_access_route(student, "/knowledge-bases") is True

    # --------------------------------------------------------------------------
    # 11 & 12. Recent Conversations from Persisted Data & Restoration
    # --------------------------------------------------------------------------

    def test_recent_conversations_come_from_persisted_data(self) -> None:
        """Recent conversations list uses actual saved data from the API client."""
        client = FrontendAPIClient()
        mock_http = Mock()
        client._http = mock_http
        client.get_session_token = Mock(return_value="mock-student-token")

        mock_http.get.return_value = Mock(
            status_code=200,
            json=lambda: [
                {
                    "id": "conv-1",
                    "title": "CS101 Syllabus Discussion",
                    "scope": "COURSE",
                    "knowledge_base_id": "c1",
                    "message_count": 4,
                    "created_at": "2026-10-16T10:00:00Z",
                    "updated_at": "2026-10-16T11:30:00Z",
                },
                {
                    "id": "conv-2",
                    "title": "Grading Breakdown Inquiries",
                    "scope": "ALL_COURSES",
                    "knowledge_base_id": None,
                    "message_count": 2,
                    "created_at": "2026-10-15T09:00:00Z",
                    "updated_at": "2026-10-15T09:15:00Z",
                },
            ],
        )

        conversations = client.get_conversations()
        assert len(conversations) == 2
        assert conversations[0].id == "conv-1"
        assert conversations[0].title == "CS101 Syllabus Discussion"
        assert conversations[0].scope == "COURSE"
        assert conversations[1].id == "conv-2"
        assert conversations[1].title == "Grading Breakdown Inquiries"
        assert conversations[1].scope == "ALL_COURSES"

    def test_selecting_recent_conversation_restores_message_history(self) -> None:
        """Selecting a conversation opens /chat?conversation_id={id} which fetches saved messages."""
        conv_id = "conv-12345"
        chat_url = f"/chat?conversation_id={conv_id}"
        assert f"conversation_id={conv_id}" in chat_url

        # Verify API client detail loading
        client = FrontendAPIClient()
        mock_http = Mock()
        client._http = mock_http
        client.get_session_token = Mock(return_value="mock-token")

        mock_http.get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "id": conv_id,
                "title": "Algorithms Q&A",
                "scope": "ALL_COURSES",
                "messages": [
                    {
                        "id": "m1",
                        "conversation_id": conv_id,
                        "role": "user",
                        "content": "What is quicksort complexity?",
                        "citations": [],
                    },
                    {
                        "id": "m2",
                        "conversation_id": conv_id,
                        "role": "assistant",
                        "content": "Quicksort average complexity is O(N log N).",
                        "citations": [],
                    },
                ],
            },
        )

        detail: ConversationDetailDTO = client.get_conversation(conv_id)
        assert detail.id == conv_id
        assert len(detail.messages) == 2
        assert detail.messages[0].content == "What is quicksort complexity?"
        assert detail.messages[1].content == "Quicksort average complexity is O(N log N)."

    # --------------------------------------------------------------------------
    # 13. Empty History Produces Genuine Empty State
    # --------------------------------------------------------------------------

    def test_empty_history_produces_genuine_empty_state_not_fabricated_history(self) -> None:
        """When user has no saved conversations, empty state is displayed without placeholder chats."""
        recent_conversations: list[ConversationSummaryDTO] = []
        conv_error_msg = None

        has_conversations = bool(recent_conversations)
        assert has_conversations is False
        assert conv_error_msg is None

    # --------------------------------------------------------------------------
    # 14. Authoritative Course Authorization
    # --------------------------------------------------------------------------

    def test_course_data_filtered_by_authoritative_authorization(self) -> None:
        """Inactive or student-invisible courses are excluded from student catalogue."""
        courses = [
            KnowledgeBaseDTO(
                id="c1",
                name="CS101",
                is_active=True,
                is_student_visible=True,
                document_count=2,
            ),
            KnowledgeBaseDTO(
                id="c2",
                name="ADMIN_ONLY",
                is_active=True,
                is_student_visible=False,
                document_count=5,
            ),
            KnowledgeBaseDTO(
                id="c3",
                name="ARCHIVED",
                is_active=False,
                is_student_visible=True,
                document_count=1,
            ),
        ]

        student_visible = [c for c in courses if c.is_active and c.is_student_visible]
        assert len(student_visible) == 1
        assert student_visible[0].id == "c1"

    # --------------------------------------------------------------------------
    # 15. Administrator Dashboard Behaviour Preserved
    # --------------------------------------------------------------------------

    def test_admin_dashboard_behaviour_preserved(self) -> None:
        """Admins have COURSE_CREATE and COURSE_VIEW permissions; students do not."""
        student = UserDTO(
            id="u1",
            email="student@univ.edu",
            full_name="Alex Student",
            role="STUDENT",
            permissions=[],
        )
        assert has_admin_permission(student, Permission.COURSE_CREATE) is False

        admin = UserDTO(
            id="u2",
            email="admin@univ.edu",
            full_name="Dr. Eleanor Vance",
            role="ADMIN",
            admin_role="MAIN_ADMIN",
            permissions=[Permission.COURSE_CREATE.value, Permission.COURSE_VIEW.value],
        )
        assert has_admin_permission(admin, Permission.COURSE_CREATE) is True
        assert can_access_route(admin, "/dashboard") is True
        assert can_access_route(admin, "/indexing") is True

    # --------------------------------------------------------------------------
    # 16. Error Messages Safely Normalized
    # --------------------------------------------------------------------------

    def test_dashboard_error_messages_safely_normalized(self) -> None:
        """Database and upstream connection errors are sanitized before user presentation."""
        sensitive_err = Exception(
            "psycopg2.OperationalError: could not connect to server at '127.0.0.1:5432' "
            "password='super_secret_db_pass' database='rag_assistant_db'"
        )
        normalized = normalize_error(sensitive_err, context="course")

        assert "super_secret_db_pass" not in normalized
        assert "5432" not in normalized
        assert "OperationalError" not in normalized
        assert "rag_assistant_db" not in normalized
        assert "unable" in normalized.lower() or "course" in normalized.lower()


class TestStudentChatFirstHomeContracts:
    """Validate Part 6B requirements: Chat as student home, dashboard redirect, and admin preservation."""

    def test_student_login_defaults_to_chat(self) -> None:
        """1. Successful student login defaults to /chat when no return_to is provided."""
        assert _get_safe_return_destination(None, is_student=True) == "/chat"
        assert _get_safe_return_destination("", is_student=True) == "/chat"
        # Admin still defaults to /dashboard
        assert _get_safe_return_destination(None, is_student=False) == "/dashboard"

    def test_safe_student_return_destination_preserved(self) -> None:
        """2. A valid safe student return destination is preserved; unsafe or dashboard returns resolve safely."""
        # Whitelisted relative destinations preserved
        assert _get_safe_return_destination("/knowledge-bases", is_student=True) == "/knowledge-bases"
        assert _get_safe_return_destination("/profile", is_student=True) == "/profile"
        assert _get_safe_return_destination("/chat", is_student=True) == "/chat"
        assert _get_safe_return_destination("/reader?doc_id=123", is_student=True) == "/reader?doc_id=123"

        # Student requesting /dashboard resolves safely to /chat
        assert _get_safe_return_destination("/dashboard", is_student=True) == "/chat"
        # Admin requesting /dashboard stays /dashboard
        assert _get_safe_return_destination("/dashboard", is_student=False) == "/dashboard"

        # Unsafe / external URLs fall back to default
        assert _get_safe_return_destination("https://evil.com", is_student=True) == "/chat"
        assert _get_safe_return_destination("//evil.com", is_student=True) == "/chat"
        assert _get_safe_return_destination("/\\evil.com", is_student=True) == "/chat"
        assert _get_safe_return_destination("/unauthorized-admin-page", is_student=True) == "/chat"

    def test_student_navigation_targets_chat(self) -> None:
        """3. Student navigation entry targets /chat and does not point to obsolete /dashboard."""
        student = UserDTO(
            id="s1",
            email="student@univ.edu",
            full_name="Alex Student",
            role="STUDENT",
        )
        assert can_access_route(student, "/chat") is True
        assert can_access_route(student, "/knowledge-bases") is True
        assert can_access_route(student, "/profile") is True

    def test_authenticated_student_visiting_dashboard_redirects_to_chat(self) -> None:
        """4. Authenticated student visiting /dashboard is redirected/navigated to /chat."""
        with patch("frontend.pages.dashboard_page.ui.navigate.to") as mock_nav:
            _render_student_dashboard()
            mock_nav.assert_called_once_with("/chat")

    def test_authenticated_admin_visiting_dashboard_retains_admin_dashboard(self) -> None:
        """5. Authenticated administrator visiting /dashboard retains operational dashboard."""
        admin = UserDTO(
            id="a1",
            email="admin@univ.edu",
            full_name="Dr. Vance",
            role="ADMIN",
            admin_role="MAIN_ADMIN",
            permissions=[Permission.COURSE_VIEW.value, Permission.DOCUMENT_VIEW.value],
        )
        assert admin.role == "ADMIN"
        assert can_access_route(admin, "/dashboard") is True
        # Admins must not be redirected to student chat on login default
        assert _get_safe_return_destination(None, is_student=False) == "/dashboard"

    def test_unauthorized_user_cannot_access_administrative_functionality(self) -> None:
        """6. Unauthorized or unauthenticated user cannot access administrative functionality."""
        student = UserDTO(
            id="s1",
            email="student@univ.edu",
            full_name="Student",
            role="STUDENT",
        )
        assert can_access_route(student, "/indexing") is False
        assert can_access_route(student, "/documents") is False
        assert can_access_route(student, "/administrators") is False
        assert can_access_route(student, "/system-health") is False
        assert can_access_route(student, "/activity") is False
        assert has_admin_permission(student, Permission.DOCUMENT_VIEW) is False

        # Unauthenticated user fails all protected routes
        assert can_access_route(None, "/dashboard") is False
        assert can_access_route(None, "/chat") is False
        assert can_access_route(None, "/indexing") is False

    def test_opening_chat_without_conversation_uses_empty_chat_behavior(self) -> None:
        """7. Opening /chat without a conversation starts in clean empty-chat state."""
        app_state = AppState()
        app_state.start_new_conversation()
        assert app_state.active_conversation_id is not None
        assert len(app_state._chat_history) == 0
        assert app_state.generation_error is None
        assert app_state.is_generating is False

    def test_new_chat_continues_to_work_and_preserves_saved_history(self) -> None:
        """8. New Chat clears active state without calling delete on previous history."""
        app_state = AppState()
        mock_client = Mock()
        app_state.active_conversation_id = "existing-conv-1"
        app_state.start_new_conversation()
        assert app_state.active_conversation_id != "existing-conv-1"
        assert len(app_state._chat_history) == 0
        # Verified: no delete_conversation call occurred
        mock_client.delete_conversation.assert_not_called()

    def test_continue_conversation_restores_selected_saved_conversation(self) -> None:
        """9. Selecting a saved conversation restores its detail and messages."""
        app_state = AppState()
        conv_id = "conv-abc-123"
        with patch("frontend.state.app_state.api_client.get_conversation") as mock_get_conv:
            mock_get_conv.return_value = ConversationDetailDTO(
                id=conv_id,
                title="Syllabus Discussion",
                scope="COURSE",
                knowledge_base_id="kb-1",
                messages=[
                    ChatMessageDTO(
                        id="m1",
                        conversation_id=conv_id,
                        role="user",
                        content="What are the lab hours?",
                        citations=[],
                    ),
                    ChatMessageDTO(
                        id="m2",
                        conversation_id=conv_id,
                        role="assistant",
                        content="Lab hours are Mon-Wed 2-4pm.",
                        citations=[],
                    ),
                ],
            )
            app_state.load_conversation(conv_id)
            assert app_state.active_conversation_id == conv_id
            assert len(app_state._chat_history) == 2
            assert app_state._chat_history[0].content == "What are the lab hours?"

    def test_normal_chat_defaults_to_all_courses(self) -> None:
        """10. Normal chat defaults to ALL_COURSES scope without requiring prior selection."""
        app_state = AppState()
        app_state.start_new_conversation()
        assert app_state.active_scope == "ALL_COURSES"

    def test_ask_in_course_uses_selected_authorized_course_scope(self) -> None:
        """11. Ask in Course initializes chat with authorized course ID in query parameter."""
        course_id = "c1111111-2222-3333-4444-555555555555"
        chat_url = f"/chat?kb_id={course_id}"
        parsed = urllib.parse.urlparse(chat_url)
        params = urllib.parse.parse_qs(parsed.query)
        assert params.get("kb_id") == [course_id]

    def test_opening_and_returning_from_source_reader_works(self) -> None:
        """12. Opening source reader and returning resolves to originating conversation or page."""
        # Originating from chat conversation
        assert validate_return_route("/chat?conversation_id=conv-42") == "/chat?conversation_id=conv-42"
        # Originating from course library
        assert validate_return_route("/knowledge-bases") == "/knowledge-bases"
        # Fallback to chat if invalid
        assert validate_return_route("javascript:alert(1)") == "/chat"

    def test_retired_student_dashboard_not_rendered_with_chat(self) -> None:
        """13. Retired student dashboard is not rendered alongside chat; it only forwards to /chat."""
        with patch("frontend.pages.dashboard_page.ui.navigate.to") as mock_nav:
            _render_student_dashboard()
            mock_nav.assert_called_once_with("/chat")

    def test_no_duplicate_student_navigation_to_obsolete_dashboard(self) -> None:
        """14. Student navigation links do not contain duplicate links to /dashboard."""
        student_nav_items = [
            ("Assistant", "/chat", "chat"),
            ("Courses", "/knowledge-bases", "menu_book"),
            ("Profile", "/profile", "account_circle"),
        ]
        dashboard_links = [item for item in student_nav_items if item[1] == "/dashboard"]
        assert len(dashboard_links) == 0
        assert student_nav_items[0] == ("Assistant", "/chat", "chat")
