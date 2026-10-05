"""
Behavioral Unit Tests for Role Capabilities, Permissions, and Navigation Contracts.

Validates that user roles and fine-grained permissions govern application
capabilities and route availability without enforcing specific human-readable
label orders or visual typography.
"""

from backend.app.core.permissions import Permission
from frontend.client.models import UserDTO
from frontend.components.layout import get_nav_items, has_admin_permission


def test_main_admin_navigation_contains_required_admin_routes() -> None:
    """Main Admin receives full administrator route suite."""
    user = UserDTO(
        id="admin-1",
        email="main@univ.edu",
        full_name="Main Admin",
        role="ADMIN",
        admin_role="MAIN_ADMIN",
        permissions=[],
    )
    routes = [route for _, route, _ in get_nav_items(user)]
    assert "/dashboard" in routes
    assert "/knowledge-bases" in routes
    assert "/documents" in routes
    assert "/chat" in routes
    assert "/administrators" in routes
    assert "/profile" in routes


def test_faculty_admin_navigation_respects_admin_chat_permission() -> None:
    """Faculty Admin route availability strictly respects ADMIN_CHAT permission."""
    without_chat = UserDTO(
        id="faculty-1",
        email="faculty@univ.edu",
        full_name="Faculty Admin",
        role="ADMIN",
        admin_role="FACULTY_ADMIN",
        permissions=[Permission.DOCUMENT_VIEW.value],
    )
    routes_without = [route for _, route, _ in get_nav_items(without_chat)]
    assert "/chat" not in routes_without
    assert "/documents" in routes_without
    assert has_admin_permission(without_chat, Permission.ADMIN_CHAT) is False

    with_chat = without_chat.model_copy(
        update={"permissions": [Permission.DOCUMENT_VIEW.value, Permission.ADMIN_CHAT.value]}
    )
    routes_with = [route for _, route, _ in get_nav_items(with_chat)]
    assert "/chat" in routes_with
    assert has_admin_permission(with_chat, Permission.ADMIN_CHAT) is True


def test_student_navigation_strictly_scoped_to_student_routes() -> None:
    """Student receives only authorized student routes and zero administrator tools."""
    student = UserDTO(
        id="student-1",
        email="student@univ.edu",
        full_name="Enrolled Student",
        role="STUDENT",
    )
    routes = [route for _, route, _ in get_nav_items(student)]
    assert "/dashboard" in routes
    assert "/knowledge-bases" in routes
    assert "/chat" in routes
    assert "/profile" in routes

    # Strict exclusion of administrator routes
    assert "/documents" not in routes
    assert "/administrators" not in routes


def test_student_cannot_gain_admin_capabilities() -> None:
    """Students cannot hold or exercise administrator permissions."""
    student = UserDTO(
        id="student-2",
        email="student2@univ.edu",
        full_name="Student Two",
        role="STUDENT",
    )
    for perm in [
        Permission.ADMIN_CHAT,
        Permission.ADMIN_VIEW,
        Permission.ADMIN_CREATE,
        Permission.COURSE_CREATE,
        Permission.DOCUMENT_UPLOAD,
    ]:
        assert has_admin_permission(student, perm) is False
