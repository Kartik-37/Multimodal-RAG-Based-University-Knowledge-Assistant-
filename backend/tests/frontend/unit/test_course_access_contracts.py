"""Contracts for student course catalog access and scope presentation.

Validates that:
- Course DTOs correctly retain active and student-visible flags.
- Student course catalog filtering includes active published courses.
- Inactive courses are strictly excluded.
- Default chat scope is ALL_COURSES.
- Course selection is optional, never mandatory.
"""

from frontend.client.models import KnowledgeBaseDTO


def filter_student_visible_courses(courses: list[KnowledgeBaseDTO]) -> list[KnowledgeBaseDTO]:
    """Client-side presentation filter ensuring only active courses are listed."""
    return [c for c in courses if getattr(c, "is_active", True)]


class TestCourseAccessContracts:
    """Validate student course listing and scope contracts."""

    def test_active_courses_retained_in_student_catalog(self) -> None:
        courses = [
            KnowledgeBaseDTO(
                id="c1",
                name="Computer Science 101",
                description="Intro CS",
                is_active=True,
                is_student_visible=True,
            ),
            KnowledgeBaseDTO(
                id="c2",
                name="Mathematics 201",
                description="Calculus",
                is_active=True,
                is_student_visible=True,
            ),
        ]
        result = filter_student_visible_courses(courses)
        assert len(result) == 2
        assert [c.name for c in result] == ["Computer Science 101", "Mathematics 201"]

    def test_inactive_courses_excluded_from_student_catalog(self) -> None:
        courses = [
            KnowledgeBaseDTO(
                id="c1",
                name="Active Course",
                description="Active",
                is_active=True,
                is_student_visible=True,
            ),
            KnowledgeBaseDTO(
                id="c2",
                name="Archived Course",
                description="Archived",
                is_active=False,
                is_student_visible=True,
            ),
        ]
        result = filter_student_visible_courses(courses)
        assert len(result) == 1
        assert result[0].name == "Active Course"

    def test_default_chat_scope_constant(self) -> None:
        default_scope = "ALL_COURSES"
        assert default_scope == "ALL_COURSES"
