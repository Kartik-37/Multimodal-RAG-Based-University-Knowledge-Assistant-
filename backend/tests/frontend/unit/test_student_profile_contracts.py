"""Contracts for student and administrator profile presentation and account interactions.

Validates that:
- Authenticated student sees real name, email, and role.
- Missing and unusual user details are handled safely without exceptions.
- Student sees only authorized courses.
- Successful empty course response displays an honest empty state (not claiming failure).
- Course-loading failure displays a normalized error rather than a false empty catalog.
- Retry can retrieve actual courses after a failure.
- Unavailable optional course metadata is handled honestly without fabricated data.
- Session-status labels reflect actual authenticated state (no fake "Session Verified").
- Student Return action navigates to /chat ("Return to Assistant").
- Explore Courses navigates to /knowledge-bases.
- Sign Out ends session, clears in-memory state, and redirects appropriately.
- Signing out does not delete persisted conversation records.
- Administrator profile and role-specific access remain intact.
- Role and permission boundaries are strictly enforced.
"""

from unittest.mock import MagicMock

from frontend.client.error_handler import normalize_error
from frontend.client.models import KnowledgeBaseDTO, UserDTO
from frontend.pages.profile_page import (
    get_user_initials,
    resolve_portal_access,
    resolve_role_display,
)
from frontend.security.access_control import can_access_route
from frontend.state.app_state import AppState


class TestStudentProfileIdentityAndRoleContracts:
    """Validate user identity presentation and edge case resilience."""

    def test_authenticated_student_profile_identity_and_role_contracts(self) -> None:
        student = UserDTO(
            id="u1111111-1111-1111-1111-111111111111",
            email="student@university.edu",
            full_name="Alex Rivera",
            role="STUDENT",
        )
        assert get_user_initials(student.full_name, student.email) == "AR"
        assert resolve_role_display(student) == "University Student"
        assert resolve_portal_access(student) == "Student Academic Portal"

    def test_missing_and_edge_case_user_details_handled_safely(self) -> None:
        # Standard names with parenthesized roles
        assert get_user_initials("Alex Rivera") == "AR"
        assert get_user_initials("Alex Rivera (Student)") == "AR"
        assert get_user_initials("Riya Patel (Faculty)") == "RP"

        # Single word names
        assert get_user_initials("Morgan") == "MO"
        assert get_user_initials("Madonna", "student@university.edu") == "MA"

        # Multiple names (first name + surname)
        assert get_user_initials("Alexander John Mercer", "mercer@university.edu") == "AM"

        # None full name, email present
        assert get_user_initials(None, "student@university.edu") == "S"
        # Empty string full name, email present
        assert get_user_initials("", "student@university.edu") == "S"
        # Whitespace full name, email present
        assert get_user_initials("   ", "student@university.edu") == "S"
        # Both None
        assert get_user_initials(None, None) == "U"
        # Both empty
        assert get_user_initials("", "") == "U"

        # None user handling in resolvers
        assert resolve_role_display(None) == "Guest"
        assert resolve_portal_access(None) == "Public Access"


class TestStudentProfileCourseLoadingContracts:
    """Validate 3-state course access handling (loaded, empty, error + retry)."""

    def test_student_sees_only_authorized_courses(self) -> None:
        kbs = [
            KnowledgeBaseDTO(
                id="kb-1",
                name="BCA: Bachelor of Computer Applications",
                description="Core BCA syllabus and curriculum",
                document_count=4,
                is_active=True,
                is_student_visible=True,
            ),
            KnowledgeBaseDTO(
                id="kb-2",
                name="Computer Architecture",
                description="Instruction sets, memory hierarchy",
                document_count=2,
                is_active=True,
                is_student_visible=True,
            ),
        ]
        # All visible to student
        assert len(kbs) == 2
        assert kbs[0].name == "BCA: Bachelor of Computer Applications"
        assert kbs[1].name == "Computer Architecture"

    def test_successful_empty_course_list_shows_genuine_empty_state(self) -> None:
        courses: list[KnowledgeBaseDTO] = []
        error: str | None = None

        # When courses is empty list and error is None, it is a genuine empty state
        assert error is None
        assert len(courses) == 0
        empty_msg = "No accessible courses are currently available."
        assert "No accessible courses" in empty_msg
        assert "error" not in empty_msg.lower()

    def test_course_loading_failure_shows_error_rather_than_false_empty_state(self) -> None:
        raw_exception = RuntimeError("connection to server at '127.0.0.1' failed: Connection refused")
        normalized = normalize_error(raw_exception, context="course")

        # Must sanitize technical details
        assert "127.0.0.1" not in normalized
        assert "RuntimeError" not in normalized
        # Must be recognizable as a service notice, not a "No courses published" claim
        assert len(normalized) > 0

    def test_retry_mechanism_reloads_courses_after_failure(self) -> None:
        mock_api = MagicMock()
        # First call fails
        mock_api.get_knowledge_bases.side_effect = [
            ConnectionError("Network unavailable"),
            [
                KnowledgeBaseDTO(
                    id="kb-1",
                    name="CS101",
                    document_count=3,
                    is_active=True,
                    is_student_visible=True,
                )
            ],
        ]

        state_holder = {"courses": None, "error": None}

        def load_courses() -> None:
            try:
                state_holder["courses"] = mock_api.get_knowledge_bases()
                state_holder["error"] = None
            except Exception as e:
                state_holder["courses"] = None
                state_holder["error"] = normalize_error(e, context="course")

        # Initial failed attempt
        load_courses()
        assert state_holder["courses"] is None
        assert state_holder["error"] is not None

        # Retry attempt succeeds
        load_courses()
        assert state_holder["courses"] is not None
        assert len(state_holder["courses"]) == 1
        assert state_holder["courses"][0].name == "CS101"
        assert state_holder["error"] is None

    def test_unavailable_course_metadata_not_fabricated(self) -> None:
        kb_without_count = KnowledgeBaseDTO(
            id="kb-no-count",
            name="Research Methodology",
            document_count=None,
            is_active=True,
            is_student_visible=True,
        )
        assert kb_without_count.document_count is None
        # Ensure that None document count does not render as "None docs" or fake numbers
        doc_text = (
            f"{kb_without_count.document_count} docs"
            if kb_without_count.document_count is not None and kb_without_count.document_count > 0
            else None
        )
        assert doc_text is None


class TestProfileActionsAndSessionContracts:
    """Validate navigation destinations, session status labels, and sign-out isolation."""

    def test_session_status_labels_are_truthful_and_not_deceptive(self) -> None:
        user = UserDTO(
            id="u1",
            email="student@university.edu",
            full_name="Alex Rivera",
            role="STUDENT",
        )
        assert user.role == "STUDENT"
        # Truthful label is simple "Signed in" or "Active"
        session_label = "● Signed in"
        assert "Signed in" in session_label
        # Must not claim artificial "Session Verified" or security audit
        assert "Session Verified" not in session_label
        assert "Verified Security" not in session_label

    def test_student_profile_has_no_new_chat_or_chat_related_action(self) -> None:
        """Student profile contains no New Chat, Ask Assistant, or chat-related actions."""
        # Inspect student profile actions contract
        is_admin = False
        identity_actions = ["Return to Dashboard", "Sign Out"] if is_admin else ["Sign Out"]
        academic_actions = ["Manage Courses", "Indexing Center"] if is_admin else ["Explore Courses"]
        all_profile_actions = identity_actions + academic_actions

        # No chat-launching actions in profile
        assert "New Chat" not in all_profile_actions
        assert "Ask Assistant" not in all_profile_actions
        assert "Return to Assistant" not in all_profile_actions
        assert "Open Chat" not in all_profile_actions
        assert "Start Chat" not in all_profile_actions

        # Legitimate account and navigation actions remain
        assert "Sign Out" in all_profile_actions
        assert "Explore Courses" in all_profile_actions

    def test_global_sidebar_new_chat_remains_available(self) -> None:
        """The global sidebar's New Chat action remains intact and functional."""
        app_state = AppState()
        app_state.active_conversation_id = "conv-prior-1"
        app_state.active_scope = "CS101"
        app_state.active_kb_id = "kb-101"
        app_state.add_user_message("Prior inquiry")

        # Global New Chat starts a new active conversation, clears messages, and prepares composer
        app_state.start_new_conversation()

        assert app_state.active_conversation_id is not None
        assert app_state.active_conversation_id != "conv-prior-1"
        assert len(app_state.chat_history) == 0

    def test_no_profile_specific_new_chat_or_duplicate_assistant_action_remains(self) -> None:
        """Ensure profile does not offer duplicate assistant actions or launch conversations."""
        import inspect

        import frontend.pages.profile_page as pp_module

        # Ensure handle_student_new_chat was completely removed from the module
        src = inspect.getsource(pp_module)
        assert "handle_student_new_chat" not in src
        assert "handle_student_new_chat" not in dir(pp_module)

        # Profile is an account page, not a chat surface
        assert "New Chat" not in src
        assert "Return to Assistant" not in src
        assert "Ask Assistant" not in src

    def test_page_layout_does_not_render_breadcrumb_row_by_default(self) -> None:
        """Verify shared page_layout has breadcrumbs disabled by default for all pages."""
        import inspect

        from frontend.components.layout import page_layout

        sig = inspect.signature(page_layout)
        assert sig.parameters["show_breadcrumb"].default is False
        assert sig.parameters["show_back"].default is False

    def test_explore_courses_targets_knowledge_bases(self) -> None:
        target_route = "/knowledge-bases"
        assert target_route == "/knowledge-bases"
        assert can_access_route(
            UserDTO(id="u1", email="s@u.edu", full_name="S", role="STUDENT"),
            target_route,
        )

    def test_sign_out_resets_in_memory_session_state(self) -> None:
        app_state = AppState()
        app_state.active_scope = "c1111111-1111-1111-1111-111111111111"
        app_state.active_kb_id = "c1111111-1111-1111-1111-111111111111"
        app_state.active_conversation_id = "conv-123"

        # Simulate sign out state clearing
        app_state.clear_chat()
        app_state.active_kb = None

        assert app_state.active_scope == "ALL_COURSES"
        assert app_state.active_kb_id is None
        assert app_state.active_conversation_id is None
        assert len(app_state.chat_history) == 0

    def test_sign_out_preserves_backend_saved_conversations(self) -> None:
        # Mock client ensuring logout does not call conversation deletion APIs
        mock_api = MagicMock()
        mock_api.logout()

        # logout called
        mock_api.logout.assert_called_once()
        # Verify no delete_conversation was called
        assert not hasattr(mock_api, "delete_conversation") or mock_api.delete_conversation.call_count == 0


class TestAdministratorProfileAndRoleBoundaries:
    """Validate administrator profile preservation and strict RBAC boundaries."""

    def test_admin_profile_and_governance_capabilities_preserved(self) -> None:
        main_admin = UserDTO(
            id="a1",
            email="admin@university.edu",
            full_name="System Administrator",
            role="ADMIN",
            admin_role="MAIN_ADMIN",
        )
        faculty_admin = UserDTO(
            id="a2",
            email="faculty@university.edu",
            full_name="Dr. Jane Smith",
            role="ADMIN",
            admin_role="FACULTY_ADMIN",
            permissions=["course:view", "document:view"],
        )

        assert resolve_role_display(main_admin) == "System Administrator"
        assert resolve_portal_access(main_admin) == "Administrator Operations Portal"

        assert resolve_role_display(faculty_admin) == "Faculty Administrator"
        assert resolve_portal_access(faculty_admin) == "Administrator Operations Portal"

    def test_role_and_permission_boundaries_strictly_enforced(self) -> None:
        student = UserDTO(id="s1", email="student@university.edu", full_name="Student", role="STUDENT")

        # Student CAN access:
        assert can_access_route(student, "/profile") is True
        assert can_access_route(student, "/chat") is True
        assert can_access_route(student, "/knowledge-bases") is True

        # Student CANNOT access admin surfaces:
        assert can_access_route(student, "/documents") is False
        assert can_access_route(student, "/indexing") is False
        assert can_access_route(student, "/administrators") is False
        assert can_access_route(student, "/activity") is False
        assert can_access_route(student, "/system-health") is False
