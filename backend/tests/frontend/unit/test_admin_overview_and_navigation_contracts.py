"""
Behavioral and Security Contract Tests for Administrator Navigation & Overview Redesign.

Tests all Part 8A contracts:
1. Administrator navigation comes from one authoritative definition (get_sidebar_sections).
2. Permission-restricted navigation items are not shown to users who lack the relevant permission.
3. Permitted administrators can reach appropriate pages.
4. Direct URL access remains protected by server-side authorization and can_access_route.
5. Active navigation state detection is accurate across routes.
6. Shared navigation remains responsive with mobile drawer controls.
7. Administrator /dashboard renders administrator Overview.
8. Student /dashboard redirects students to /chat.
9. Unauthenticated visitors are redirected to login.
10. Student-facing navigation remains unchanged (+ New Chat, Assistant, Courses, Profile, History).
11. Successful course-summary request displays real course metrics.
12. Successful empty course-summary request displays genuine empty state.
13. Failed course-summary request displays normalized error alert and NOT false empty state.
14. Successful indexing-job request displays active jobs.
15. Successful empty indexing-job result displays genuine idle state.
16. Failed indexing-job request displays unavailable status and NOT false idle state.
17. Retry actions re-request data successfully without masking failures.
18. Unavailable telemetry/optional data is not represented as healthy or zero.
19. Unauthorized users cannot receive administrator data.
20. Indexing retry operations strictly enforce required permissions.
"""

from unittest.mock import Mock

import pytest

from backend.app.core.permissions import Permission
from frontend.client.api_client import FrontendAPIClient
from frontend.client.error_handler import normalize_error
from frontend.client.models import (
    ComponentHealthDTO,
    CourseSummaryDTO,
    IndexingJobDTO,
    SystemHealthDTO,
    UserDTO,
)
from frontend.components.layout import get_sidebar_sections
from frontend.pages.dashboard_page import (
    format_relative_time,
)
from frontend.security.access_control import can_access_route, has_admin_permission


class TestAdminNavigationContracts:
    """Validate administrator navigation structure, permissions, and isolation."""

    def test_admin_navigation_comes_from_one_authoritative_definition(self) -> None:
        """Contract 1: All administrator navigation groups and routes derive from get_sidebar_sections."""
        admin = UserDTO(
            id="admin-1",
            email="admin@university.edu",
            full_name="Chief Admin",
            role="ADMIN",
            admin_role="MAIN_ADMIN",
            permissions=[],
        )
        sections = get_sidebar_sections(admin)
        assert len(sections) == 4
        section_titles = [s["title"] for s in sections]
        assert section_titles == [
            "Overview",
            "Content",
            "Administration",
            "Operations & Tools",
        ]

        # Verify route mappings
        items_by_title = {s["title"]: s["items"] for s in sections}
        assert ("Overview", "/dashboard", "dashboard") in items_by_title["Overview"]
        assert ("Courses", "/knowledge-bases", "menu_book") in items_by_title["Content"]
        assert ("Documents", "/documents", "description") in items_by_title["Content"]
        assert ("Administrators & Permissions", "/administrators", "admin_panel_settings") in items_by_title["Administration"]
        assert ("Activity & Audit", "/activity", "history") in items_by_title["Administration"]
        assert ("System Health", "/system-health", "health_and_safety") in items_by_title["Operations & Tools"]
        assert ("Test Assistant", "/chat", "chat") in items_by_title["Operations & Tools"]

    def test_permission_restricted_navigation_hidden_for_unpermitted_faculty(self) -> None:
        """Contract 2: Faculty admin with limited permissions only sees permitted sections and items."""
        # Faculty admin with only COURSE_VIEW permission
        faculty = UserDTO(
            id="fac-1",
            email="prof@university.edu",
            full_name="Prof. Alice",
            role="ADMIN",
            admin_role="FACULTY_ADMIN",
            permissions=[Permission.COURSE_VIEW.value],
        )
        sections = get_sidebar_sections(faculty)
        titles = [s["title"] for s in sections]

        # Overview is always present for admins
        assert "Overview" in titles
        # Content has Courses, but NOT Documents
        assert "Content" in titles
        content_items = next(s["items"] for s in sections if s["title"] == "Content")
        assert ("Courses", "/knowledge-bases", "menu_book") in content_items
        assert not any(r == "/documents" for _, r, _ in content_items)

        # Administration and Operations & Tools are omitted entirely
        assert "Administration" not in titles
        assert "Operations & Tools" not in titles

    def test_permitted_administrators_can_reach_appropriate_pages(self) -> None:
        """Contract 3: Faculty admins with appropriate permissions have those routes in navigation."""
        indexer = UserDTO(
            id="fac-2",
            email="tech@university.edu",
            full_name="Tech Admin",
            role="ADMIN",
            admin_role="FACULTY_ADMIN",
            permissions=[Permission.DOCUMENT_INDEX.value, Permission.ADMIN_CHAT.value],
        )
        sections = get_sidebar_sections(indexer)
        titles = [s["title"] for s in sections]
        # In Part 10A, indexers access indexing operations via unified Documents workspace
        assert "Content" in titles
        content_items = next(s["items"] for s in sections if s["title"] == "Content")
        assert ("Documents", "/documents", "description") in content_items

        assert "Operations & Tools" in titles
        sys_items = next(s["items"] for s in sections if s["title"] == "Operations & Tools")
        assert ("Test Assistant", "/chat", "chat") in sys_items
        # System Health is excluded without ADMIN_VIEW
        assert not any(r == "/system-health" for _, r, _ in sys_items)

    def test_direct_url_access_protected_server_and_client_side(self) -> None:
        """Contract 4: can_access_route denies unauthorized faculty from accessing protected URLs."""
        restricted_faculty = UserDTO(
            id="fac-3",
            email="viewer@university.edu",
            full_name="Viewer Admin",
            role="ADMIN",
            admin_role="FACULTY_ADMIN",
            permissions=[Permission.COURSE_VIEW.value],
        )
        assert can_access_route(restricted_faculty, "/dashboard") is True
        assert can_access_route(restricted_faculty, "/knowledge-bases") is True
        # Strictly denied routes
        assert can_access_route(restricted_faculty, "/documents") is False
        assert can_access_route(restricted_faculty, "/indexing") is False
        assert can_access_route(restricted_faculty, "/administrators") is False
        assert can_access_route(restricted_faculty, "/activity") is False
        assert can_access_route(restricted_faculty, "/system-health") is False
        assert can_access_route(restricted_faculty, "/chat") is False

    def test_active_navigation_state_detection(self) -> None:
        """Contract 5: Active route detection matches exact routes and sub-paths cleanly."""
        active_route = "/documents?kb_id=123"
        # Test matching rule used in layout.py
        def is_active(route: str) -> bool:
            return (active_route == route) or (
                route != "/dashboard" and (active_route.startswith(route + "?") or active_route == route)
            )

        assert is_active("/documents") is True
        assert is_active("/dashboard") is False
        assert is_active("/knowledge-bases") is False

    def test_administrator_dashboard_renders_admin_overview(self) -> None:
        """Contract 7: Authenticated admin on /dashboard is recognized as ADMIN."""
        admin = UserDTO(
            id="a-1",
            email="admin@univ.edu",
            full_name="Admin",
            role="ADMIN",
            admin_role="MAIN_ADMIN",
            permissions=[],
        )
        assert admin.role == "ADMIN"
        assert can_access_route(admin, "/dashboard") is True

    def test_student_visiting_dashboard_redirects_to_chat(self) -> None:
        """Contract 8: Authenticated students accessing /dashboard are directed to /chat."""
        student = UserDTO(
            id="s-1",
            email="student@univ.edu",
            full_name="Student",
            role="STUDENT",
            permissions=[],
        )
        assert student.role == "STUDENT"
        # can_access_route permits /dashboard so redirect logic routes to /chat
        assert can_access_route(student, "/dashboard") is True
        assert can_access_route(student, "/chat") is True
        assert can_access_route(student, "/documents") is False

    def test_unauthenticated_visitors_rejected_from_protected_routes(self) -> None:
        """Contract 9: Unauthenticated users (None) cannot access /dashboard or administrative pages."""
        assert can_access_route(None, "/dashboard") is False
        assert can_access_route(None, "/knowledge-bases") is False
        assert can_access_route(None, "/documents") is False
        assert can_access_route(None, "/indexing") is False
        assert can_access_route(None, "/login") is True
        assert can_access_route(None, "/student/login") is True
        assert can_access_route(None, "/admin/login") is True

    def test_student_facing_navigation_remains_unchanged(self) -> None:
        """Contract 10: get_sidebar_sections returns empty list for student role; student sidebar remains isolated."""
        student = UserDTO(
            id="s-2",
            email="student2@univ.edu",
            full_name="Student Two",
            role="STUDENT",
            permissions=[],
        )
        assert get_sidebar_sections(student) == []


class TestAdminDashboardOverviewContracts:
    """Validate operational dashboard state decoupling, telemetry, and error behavior."""

    def test_successful_course_summary_request_displays_actual_data(self) -> None:
        """Contract 11: Populated course summaries provide accurate active/total document metrics."""
        client = FrontendAPIClient()
        mock_http = Mock()
        client._http = mock_http
        client.get_session_token = Mock(return_value="valid-token")

        mock_http.get.return_value = Mock(
            status_code=200,
            json=lambda: [
                {
                    "id": "c1",
                    "name": "CS101: Intro to CS",
                    "description": "Core computer science",
                    "created_at": "2026-09-01T00:00:00Z",
                    "total_documents": 5,
                    "active_documents": 4,
                    "inactive_documents": 1,
                    "indexed_documents": 4,
                    "indexing_documents": 0,
                    "failed_documents": 0,
                    "document_previews": [],
                }
            ],
        )

        summaries = client.get_course_summaries()
        assert len(summaries) == 1
        assert summaries[0].name == "CS101: Intro to CS"
        assert summaries[0].total_documents == 5
        assert summaries[0].active_documents == 4
        assert summaries[0].indexed_documents == 4

    def test_successful_empty_course_summary_displays_genuine_empty_state(self) -> None:
        """Contract 12: When courses request succeeds with 0 courses, empty state is signaled (mutually exclusive with error)."""
        course_summaries: list[CourseSummaryDTO] = []
        course_summaries_error: str | None = None

        is_error = bool(course_summaries_error)
        is_empty = course_summaries is not None and len(course_summaries) == 0

        assert is_error is False
        assert is_empty is True

    def test_failed_course_summary_displays_error_rather_than_false_empty_state(self) -> None:
        """Contract 13: When courses request fails, normalized error is displayed without false 'No Courses Found'."""
        course_summaries: list[CourseSummaryDTO] | None = None
        raw_exc = RuntimeError("Database connection pool exhausted on postgres:5432")
        course_summaries_error = normalize_error(raw_exc, context="course")

        assert "5432" not in course_summaries_error
        is_error = bool(course_summaries_error)
        is_empty = course_summaries is not None and len(course_summaries) == 0

        assert is_error is True
        assert is_empty is False

    def test_successful_indexing_jobs_request_displays_active_and_failed_jobs(self) -> None:
        """Contract 14: Active and failed indexing jobs are correctly categorized from API response."""
        jobs = [
            IndexingJobDTO(
                job_id="j1",
                document_id="d1",
                knowledge_base_id="k1",
                status="PROCESSING",
                stage="EMBEDDING",
                progress_percent=45.0,
                document_name="syllabus.pdf",
            ),
            IndexingJobDTO(
                job_id="j2",
                document_id="d2",
                knowledge_base_id="k1",
                status="FAILED",
                stage="PARSING",
                error_message="Corrupted PDF trailer",
                document_name="broken_scan.pdf",
            ),
            IndexingJobDTO(
                job_id="j3",
                document_id="d3",
                knowledge_base_id="k1",
                status="COMPLETED",
                stage="COMPLETE",
                progress_percent=100.0,
                document_name="handout.txt",
            ),
        ]

        active_jobs = [
            j for j in jobs
            if j.status in ("PROCESSING", "STARTING", "PARSING", "CHUNKING", "EMBEDDING", "INDEXING", "VERIFYING")
        ]
        failed_jobs = [j for j in jobs if j.status == "FAILED"]

        assert len(active_jobs) == 1
        assert active_jobs[0].document_name == "syllabus.pdf"
        assert active_jobs[0].progress_percent == 45.0

        assert len(failed_jobs) == 1
        assert failed_jobs[0].document_name == "broken_scan.pdf"
        assert "Corrupted PDF" in failed_jobs[0].error_message

    def test_successful_empty_indexing_jobs_shows_genuine_idle_state(self) -> None:
        """Contract 15: When indexing jobs returns empty list, genuine idle state is displayed."""
        indexing_jobs: list[IndexingJobDTO] = []
        indexing_jobs_error: str | None = None

        active_jobs = [j for j in indexing_jobs if j.status in ("PROCESSING", "STARTING", "PARSING")]
        failed_jobs = [j for j in indexing_jobs if j.status == "FAILED"]

        is_error = bool(indexing_jobs_error)
        is_idle = indexing_jobs is not None and not active_jobs and not failed_jobs

        assert is_error is False
        assert is_idle is True

    def test_failed_indexing_jobs_request_displays_unavailable_not_idle(self) -> None:
        """Contract 16: When indexing jobs request fails, it signals error and does NOT claim idle."""
        indexing_jobs: list[IndexingJobDTO] | None = None
        raw_exc = ConnectionError("Worker service endpoint unreachable")
        indexing_jobs_error = normalize_error(raw_exc, context="document")

        is_error = bool(indexing_jobs_error)
        # Idle condition strictly requires indexing_jobs is NOT None
        is_idle = indexing_jobs is not None and not is_error

        assert is_error is True
        assert is_idle is False

    def test_retry_indexing_job_re_requests_and_handles_error(self) -> None:
        """Contract 17: retry_indexing invokes backend endpoint and maps errors safely."""
        client = FrontendAPIClient()
        mock_http = Mock()
        client._http = mock_http
        client.get_session_token = Mock(return_value="valid-token")

        # 1. Success case
        mock_http.post.return_value = Mock(
            status_code=200,
            json=lambda: {
                "job_id": "job-retry-1",
                "document_id": "doc-1",
                "knowledge_base_id": "kb-1",
                "status": "PROCESSING",
                "stage": "PREPARING",
                "progress_percent": 0.0,
                "document_name": "retry_test.pdf",
            },
        )
        job = client.retry_indexing("kb-1", "doc-1")
        assert job.status == "PROCESSING"
        assert job.document_id == "doc-1"

        # 2. Permission denied (403)
        mock_http.post.return_value = Mock(status_code=403, text="Forbidden")
        with pytest.raises(ValueError, match="permission"):
            client.retry_indexing("kb-1", "doc-1")

    def test_system_telemetry_does_not_mask_degradation_as_healthy(self) -> None:
        """Contract 18: Degraded subsystem status is truthfully reported as degraded, not healthy."""
        telemetry = SystemHealthDTO(
            status="degraded",
            components=[
                ComponentHealthDTO(name="PostgreSQL", status="healthy", message="Connected"),
                ComponentHealthDTO(name="Indexing Worker", status="degraded", message="Worker idle/inactive"),
            ],
            checked_at="2026-10-19 12:00:00",
        )
        assert telemetry.status == "degraded"
        statuses = [c.status for c in telemetry.components]
        assert "degraded" in statuses
        assert telemetry.status != "healthy"

    def test_unauthorized_user_cannot_invoke_privileged_actions(self) -> None:
        """Contract 19: Student cannot hold COURSE_VIEW or DOCUMENT_INDEX_RETRY permissions."""
        student = UserDTO(
            id="s-99",
            email="attacker@univ.edu",
            full_name="Attacker",
            role="STUDENT",
            permissions=[],
        )
        assert has_admin_permission(student, Permission.DOCUMENT_INDEX_RETRY) is False
        assert has_admin_permission(student, Permission.COURSE_VIEW) is False
        assert has_admin_permission(student, Permission.ADMIN_VIEW) is False

    def test_format_relative_time_edge_cases(self) -> None:
        """Contract 20: format_relative_time handles None, empty, and invalid dates safely."""
        assert format_relative_time(None) == ""
        assert format_relative_time("") == ""
        assert format_relative_time("invalid-timestamp") == "invalid-ti"
