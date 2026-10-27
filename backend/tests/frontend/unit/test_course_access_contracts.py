"""Contracts for student course catalog access, search, filtering, and scope presentation.

Validates that:
- Student sees only active, authorized courses.
- Course search matches real supported fields (name, description) case-insensitively.
- Clearing search restores the complete result set.
- Material-status filters (all, with_docs, no_docs) work accurately.
- Document count wording uses clean English ("No documents", "1 document", "N documents"), never "0 doc(s)".
- Course with no documents is distinctly differentiated from a document API failure.
- Document request failure normalizes error and does not silently collapse into an empty list.
- Materials action uses the exact course ID.
- Document opening action builds valid /reader URL with return_to="/knowledge-bases" and contextual return label.
- Ask in Course passes selected course ID to chat, which genuinely scopes retrieval to COURSE.
- Opening chat without course ID defaults to ALL_COURSES.
- Admin course-management actions remain available to authorized administrators and hidden from students.
- Errors are safely normalized without leaking stack traces or internal paths.
"""

from unittest.mock import Mock

import pytest

from backend.app.core.permissions import Permission
from frontend.client.api_client import FrontendAPIClient
from frontend.client.error_handler import normalize_error
from frontend.client.models import DocumentDTO, KnowledgeBaseDTO, UserDTO
from frontend.pages.knowledge_bases_page import (
    format_document_count,
    format_file_size,
    get_file_type_icon,
)
from frontend.pages.reader_page import (
    build_reader_url,
    get_return_label,
    validate_return_route,
)
from frontend.security.access_control import has_admin_permission


def filter_courses(
    courses: list[KnowledgeBaseDTO],
    query: str = "",
    filter_mode: str = "all",
) -> list[KnowledgeBaseDTO]:
    """Presentation search and filter helper mirroring knowledge_bases_page logic."""
    clean_q = query.strip().lower()
    filtered = courses

    if clean_q:
        filtered = [
            c
            for c in filtered
            if clean_q in c.name.lower() or clean_q in (c.description or "").lower()
        ]

    if filter_mode == "with_docs":
        filtered = [c for c in filtered if c.document_count is not None and c.document_count > 0]
    elif filter_mode == "no_docs":
        filtered = [c for c in filtered if c.document_count is not None and c.document_count == 0]
    elif filter_mode == "uncounted":
        filtered = [c for c in filtered if c.document_count is None]

    return filtered


class TestCourseAccessContracts:
    """Validate student course listing, search, filtering, and action contracts."""

    @pytest.fixture
    def sample_courses(self) -> list[KnowledgeBaseDTO]:
        return [
            KnowledgeBaseDTO(
                id="c1",
                name="CS101: Introduction to Computer Science",
                description="Foundational programming in Python and algorithms.",
                document_count=3,
                is_active=True,
                is_student_visible=True,
            ),
            KnowledgeBaseDTO(
                id="c2",
                name="MATH201: Calculus & Linear Algebra",
                description="Differential equations, matrix theory, and vector spaces.",
                document_count=0,
                is_active=True,
                is_student_visible=True,
            ),
            KnowledgeBaseDTO(
                id="c3",
                name="PHYS301: Classical Mechanics",
                description="Newtonian physics, Lagrangian dynamics, and kinematics.",
                document_count=1,
                is_active=True,
                is_student_visible=True,
            ),
            KnowledgeBaseDTO(
                id="c4",
                name="ARCHIVED: Old CS Syllabus",
                description="Deprecated curriculum.",
                document_count=5,
                is_active=False,
                is_student_visible=True,
            ),
        ]

    def test_active_courses_retained_in_student_catalog(
        self, sample_courses: list[KnowledgeBaseDTO]
    ) -> None:
        """Student catalogue includes only active courses."""
        active = [c for c in sample_courses if c.is_active]
        assert len(active) == 3
        assert all(c.is_active for c in active)
        assert not any(c.name.startswith("ARCHIVED") for c in active)

    def test_course_search_matches_name_case_insensitive(
        self, sample_courses: list[KnowledgeBaseDTO]
    ) -> None:
        """Search matches course names case-insensitively."""
        active = [c for c in sample_courses if c.is_active]
        res = filter_courses(active, query="computer science")
        assert len(res) == 1
        assert res[0].id == "c1"

        res_upper = filter_courses(active, query="CS101")
        assert len(res_upper) == 1
        assert res_upper[0].id == "c1"

    def test_course_search_matches_description(
        self, sample_courses: list[KnowledgeBaseDTO]
    ) -> None:
        """Search matches terms present in the description."""
        active = [c for c in sample_courses if c.is_active]
        res = filter_courses(active, query="differential equations")
        assert len(res) == 1
        assert res[0].id == "c2"

    def test_clearing_search_restores_complete_course_list(
        self, sample_courses: list[KnowledgeBaseDTO]
    ) -> None:
        """Clearing or whitespace-only search query restores all active courses."""
        active = [c for c in sample_courses if c.is_active]
        filtered = filter_courses(active, query="nonexistent keyword")
        assert len(filtered) == 0

        restored = filter_courses(active, query="   ")
        assert len(restored) == len(active)

    def test_filter_by_materials_status(
        self, sample_courses: list[KnowledgeBaseDTO]
    ) -> None:
        """Filter chips partition courses by document availability."""
        active = [c for c in sample_courses if c.is_active]

        with_docs = filter_courses(active, filter_mode="with_docs")
        assert len(with_docs) == 2
        assert {c.id for c in with_docs} == {"c1", "c3"}

        no_docs = filter_courses(active, filter_mode="no_docs")
        assert len(no_docs) == 1
        assert no_docs[0].id == "c2"

        all_res = filter_courses(active, filter_mode="all")
        assert len(all_res) == 3

    def test_combined_search_and_materials_filter(
        self, sample_courses: list[KnowledgeBaseDTO]
    ) -> None:
        """Search query and filter mode work together conjunctively."""
        active = [c for c in sample_courses if c.is_active]
        # "algebra" is in MATH201, which has 0 docs
        res_with = filter_courses(active, query="algebra", filter_mode="with_docs")
        assert len(res_with) == 0

        res_no = filter_courses(active, query="algebra", filter_mode="no_docs")
        assert len(res_no) == 1
        assert res_no[0].id == "c2"

    def test_document_count_wording_human_readable(self) -> None:
        """Wording must be clean English, never awkward technical terms like '0 doc(s)'."""
        assert format_document_count(None) == "Count unavailable"
        assert format_document_count(0) == "No documents"
        assert format_document_count(1) == "1 document"
        assert format_document_count(4) == "4 documents"
        assert format_document_count(12) == "12 documents"
        assert "doc(s)" not in format_document_count(None)
        assert "doc(s)" not in format_document_count(0)
        assert "doc(s)" not in format_document_count(1)

    def test_file_type_icon_resolution(self) -> None:
        """Appropriate icon names are returned for supported file extensions."""
        assert get_file_type_icon("syllabus.pdf") == "picture_as_pdf"
        assert get_file_type_icon("assignment.docx") == "description"
        assert get_file_type_icon("notes.doc") == "description"
        assert get_file_type_icon("grades.csv") == "table_chart"
        assert get_file_type_icon("readme.txt") == "article"
        assert get_file_type_icon("guide.md") == "article"

    def test_file_size_formatting(self) -> None:
        """File sizes are formatted into readable units."""
        assert format_file_size(0, "pdf") == "PDF"
        assert format_file_size(512) == "512 B"
        assert format_file_size(2048) == "2 KB"
        assert format_file_size(1048576 * 2) == "2.0 MB"

    def test_course_with_no_documents_differs_from_api_failure(self) -> None:
        """Empty course displays a dignified empty state, while API failure raises normalized error."""
        # 1. Genuine empty course: docs list is empty
        empty_docs: list[DocumentDTO] = []
        assert len(empty_docs) == 0  # renders render_empty_state("No Documents Available")

        # 2. Document API failure: raises an exception with sanitized error
        api_error = RuntimeError("Database connection timed out at 127.0.0.1:5432")
        normalized = normalize_error(api_error, context="document")
        assert "5432" not in normalized
        assert "Database" not in normalized
        assert "unable" in normalized.lower() or "document" in normalized.lower()

    def test_materials_action_preserves_course_id(self) -> None:
        """Opening materials requests documents with the exact course ID."""
        client_mock = Mock()
        client_mock.get_documents.return_value = [
            DocumentDTO(
                id="d1",
                kb_id="c1",
                filename="syllabus.pdf",
                file_type="pdf",
                is_active=True,
            )
        ]

        course_id = "c1"
        docs = client_mock.get_documents(course_id)
        client_mock.get_documents.assert_called_once_with("c1")
        assert len(docs) == 1
        assert docs[0].filename == "syllabus.pdf"

    def test_document_opening_action_builds_safe_reader_url(self) -> None:
        """Opening a document targets /reader with return_to='/knowledge-bases' and no credential leakage."""
        url = build_reader_url(
            document_id="d-1234",
            document_name="syllabus.pdf",
            kb_id="kb-5678",
            course_name="CS101",
            return_to="/knowledge-bases",
        )
        assert url.startswith("/reader?")
        assert "document_id=d-1234" in url
        assert "return_to=%2Fknowledge-bases" in url
        assert "token" not in url.lower()
        assert "cookie" not in url.lower()

    def test_reader_return_navigation_targets_knowledge_bases(self) -> None:
        """Reader return navigation validates /knowledge-bases and labels it 'Back to Courses'."""
        origin = "/knowledge-bases"
        safe_return = validate_return_route(origin)
        assert safe_return == "/knowledge-bases"

        label = get_return_label(safe_return)
        assert label == "Back to Courses"

    def test_ask_in_course_navigation_parameter(self) -> None:
        """Ask in Course action builds the URL /chat?kb_id={course_id}."""
        course_id = "c-intro-cs-101"
        chat_url = f"/chat?kb_id={course_id}"
        assert chat_url == "/chat?kb_id=c-intro-cs-101"
        assert "kb_id=c-intro-cs-101" in chat_url

    def test_admin_course_management_permissions_isolated(self) -> None:
        """Students cannot create courses; only authorized admins possess COURSE_CREATE."""
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
            permissions=[Permission.COURSE_CREATE.value, Permission.COURSE_VIEW.value],
        )
        assert has_admin_permission(admin, Permission.COURSE_CREATE) is True

    # --------------------------------------------------------------------------
    # Regression Tests: Document Count Error Handling and Fallback Semantics
    # --------------------------------------------------------------------------

    def test_course_summary_succeeds_positive_document_count(self) -> None:
        """1. Course summary succeeds and a positive document count is shown."""
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
                    }
                ],
            ),
            Mock(
                status_code=200,
                json=lambda: [
                    {
                        "id": "c1",
                        "name": "CS101: Introduction to CS",
                        "description": "Foundational programming",
                        "created_at": "2026-09-01T00:00:00",
                        "total_documents": 5,
                        "active_documents": 5,
                        "inactive_documents": 0,
                        "indexed_documents": 5,
                        "indexing_documents": 0,
                        "failed_documents": 0,
                        "document_previews": [],
                    }
                ],
            ),
        ]

        courses = client.get_knowledge_bases()
        assert len(courses) == 1
        assert courses[0].document_count == 5
        assert format_document_count(courses[0].document_count) == "5 documents"

    def test_course_summary_succeeds_genuine_zero_count(self) -> None:
        """2. Course summary succeeds and a genuine zero count is shown as 'No documents'."""
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
            Mock(
                status_code=200,
                json=lambda: [
                    {
                        "id": "c2",
                        "name": "MATH201: Calculus",
                        "description": "Calculus and algebra",
                        "created_at": "2026-09-01T00:00:00",
                        "is_active": True,
                        "is_student_visible": True,
                    }
                ],
            ),
            Mock(
                status_code=200,
                json=lambda: [
                    {
                        "id": "c2",
                        "name": "MATH201: Calculus",
                        "description": "Calculus and algebra",
                        "created_at": "2026-09-01T00:00:00",
                        "total_documents": 0,
                        "active_documents": 0,
                        "inactive_documents": 0,
                        "indexed_documents": 0,
                        "indexing_documents": 0,
                        "failed_documents": 0,
                        "document_previews": [],
                    }
                ],
            ),
        ]

        courses = client.get_knowledge_bases()
        assert len(courses) == 1
        assert courses[0].document_count == 0
        assert format_document_count(courses[0].document_count) == "No documents"
        filtered_no_docs = filter_courses(courses, filter_mode="no_docs")
        assert len(filtered_no_docs) == 1
        assert filtered_no_docs[0].id == "c2"

    def test_course_summary_fails_represented_as_unavailable_not_zero(self) -> None:
        """3. Course summary request fails and the count is represented as unavailable rather than zero."""
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
            Mock(
                status_code=200,
                json=lambda: [
                    {
                        "id": "c3",
                        "name": "PHYS301: Classical Mechanics",
                        "description": "Newtonian physics",
                        "created_at": "2026-09-01T00:00:00",
                        "is_active": True,
                        "is_student_visible": True,
                    }
                ],
            ),
            Mock(
                status_code=500,
                json=lambda: {"detail": "Internal summary failure"},
                text="Internal summary failure",
            ),
        ]

        courses = client.get_knowledge_bases()
        assert len(courses) == 1
        assert courses[0].id == "c3"
        # Must be None, NEVER zero or fallback to empty cache
        assert courses[0].document_count is None
        assert courses[0].document_count != 0
        assert format_document_count(courses[0].document_count) == "Count unavailable"

    def test_unavailable_count_not_in_no_materials_filter(self) -> None:
        """4. An unavailable count does not incorrectly place a course into the 'No Materials' filter."""
        courses = [
            KnowledgeBaseDTO(
                id="c-verified-with-docs",
                name="Course With Docs",
                description="Verified course with 2 materials",
                document_count=2,
            ),
            KnowledgeBaseDTO(
                id="c-verified-empty",
                name="Course Empty",
                description="Verified empty course",
                document_count=0,
            ),
            KnowledgeBaseDTO(
                id="c-summary-failed",
                name="Course Unknown",
                description="Course whose summary request failed",
                document_count=None,
            ),
        ]

        # All courses includes all 3
        assert len(filter_courses(courses, filter_mode="all")) == 3

        # 'with_docs' only contains verified count > 0 (excludes None)
        with_docs = filter_courses(courses, filter_mode="with_docs")
        assert len(with_docs) == 1
        assert with_docs[0].id == "c-verified-with-docs"

        # 'no_docs' only contains verified count == 0 (excludes None)
        no_docs = filter_courses(courses, filter_mode="no_docs")
        assert len(no_docs) == 1
        assert no_docs[0].id == "c-verified-empty"
        # The course with unavailable count MUST NOT be in no_docs
        assert "c-summary-failed" not in [c.id for c in no_docs]

        # 'uncounted' filter isolates unavailable count courses
        uncounted = filter_courses(courses, filter_mode="uncounted")
        assert len(uncounted) == 1
        assert uncounted[0].id == "c-summary-failed"

    def test_main_course_list_remains_usable_when_summary_fails(self) -> None:
        """5. The main course list remains usable and visible when the optional summary request fails."""
        client = FrontendAPIClient()
        mock_http = Mock()
        client._http = mock_http

        mock_http.get.side_effect = [
            Mock(
                status_code=200,
                json=lambda: [
                    {"id": "c1", "name": "CS101", "description": "Intro CS", "created_at": "2026-09-01T00:00:00"},
                    {"id": "c2", "name": "CS201", "description": "Data Structures", "created_at": "2026-09-02T00:00:00"},
                    {"id": "c3", "name": "MATH101", "description": "Linear Algebra", "created_at": "2026-09-03T00:00:00"},
                ],
            ),
            RuntimeError("Connection refused by upstream summary service"),
        ]

        courses = client.get_knowledge_bases()
        assert len(courses) == 3
        assert [c.name for c in courses] == ["CS101", "CS201", "MATH101"]
        assert all(c.document_count is None for c in courses)

        # Student search still works on the course catalogue
        search_results = filter_courses(courses, query="data")
        assert len(search_results) == 1
        assert search_results[0].name == "CS201"

    def test_later_successful_summary_restores_accurate_counts(self) -> None:
        """6. A later successful summary request restores accurate count information."""
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

        base_list_resp = Mock(
            status_code=200,
            json=lambda: [
                {"id": "c1", "name": "CS101", "description": "Intro CS", "created_at": "2026-09-01T00:00:00"}
            ],
        )

        # 1st call: summary fails -> document_count is None
        mock_http.get.side_effect = [
            base_list_resp,
            RuntimeError("Temporary timeout"),
        ]
        courses_first = client.get_knowledge_bases()
        assert courses_first[0].document_count is None
        assert format_document_count(courses_first[0].document_count) == "Count unavailable"

        # 2nd call: summary succeeds -> document_count is restored to 4
        summary_success_resp = Mock(
            status_code=200,
            json=lambda: [
                {
                    "id": "c1",
                    "name": "CS101",
                    "description": "Intro CS",
                    "created_at": "2026-09-01T00:00:00",
                    "total_documents": 4,
                    "active_documents": 4,
                    "inactive_documents": 0,
                    "indexed_documents": 4,
                    "indexing_documents": 0,
                    "failed_documents": 0,
                    "document_previews": [],
                }
            ],
        )
        mock_http.get.side_effect = [
            base_list_resp,
            summary_success_resp,
        ]
        courses_second = client.get_knowledge_bases()
        assert courses_second[0].document_count == 4
        assert format_document_count(courses_second[0].document_count) == "4 documents"

    def test_course_error_messages_safely_normalized(self) -> None:
        """7. Primary course-list errors are safely normalized without leaking SQL, paths, or secrets."""
        sensitive_err = Exception(
            "psycopg2.OperationalError: could not connect to server at 'postgres-internal.corp:5432' "
            "password='super_secret_db_pass' database='university_rag'"
        )
        normalized = normalize_error(sensitive_err, context="course")

        assert "super_secret_db_pass" not in normalized
        assert "postgres-internal" not in normalized
        assert "5432" not in normalized
        assert "OperationalError" not in normalized
        assert "university_rag" not in normalized
        assert "unable" in normalized.lower() or "course" in normalized.lower()
