"""
Behavioral Unit Tests for Role Capabilities, Permissions, and Route Access Semantics.

Validates that user roles and fine-grained permissions govern application capabilities
and route availability according to stable authorization contracts, independent of
specific visual navigation component structures or markup implementations.
"""

from backend.app.core.permissions import Permission
from frontend.client.models import UserDTO
from frontend.components.layout import can_access_route, has_admin_permission


def test_main_admin_capabilities_and_routes() -> None:
    """Main Admin possesses full administrator route suite and capabilities."""
    user = UserDTO(
        id="admin-1",
        email="main@univ.edu",
        full_name="Main Admin",
        role="ADMIN",
        admin_role="MAIN_ADMIN",
        permissions=[],
    )
    for route in [
        "/dashboard",
        "/knowledge-bases",
        "/documents",
        "/chat",
        "/administrators",
        "/profile",
    ]:
        assert can_access_route(user, route) is True


def test_faculty_admin_chat_capability_respects_permission() -> None:
    """Faculty Admin chat capability strictly respects ADMIN_CHAT permission."""
    without_chat = UserDTO(
        id="faculty-1",
        email="faculty@univ.edu",
        full_name="Faculty Admin",
        role="ADMIN",
        admin_role="FACULTY_ADMIN",
        permissions=[Permission.DOCUMENT_VIEW.value],
    )
    assert can_access_route(without_chat, "/chat") is False
    assert can_access_route(without_chat, "/documents") is True
    assert has_admin_permission(without_chat, Permission.ADMIN_CHAT) is False

    with_chat = without_chat.model_copy(
        update={"permissions": [Permission.DOCUMENT_VIEW.value, Permission.ADMIN_CHAT.value]}
    )
    assert can_access_route(with_chat, "/chat") is True
    assert has_admin_permission(with_chat, Permission.ADMIN_CHAT) is True


def test_student_capabilities_strictly_scoped_to_student_routes() -> None:
    """Student receives only authorized student routes and zero administrator tools."""
    student = UserDTO(
        id="student-1",
        email="student@univ.edu",
        full_name="Enrolled Student",
        role="STUDENT",
    )
    # Permitted student routes
    assert can_access_route(student, "/dashboard") is True
    assert can_access_route(student, "/knowledge-bases") is True
    assert can_access_route(student, "/chat") is True
    assert can_access_route(student, "/profile") is True

    # Strict exclusion of administrator routes
    assert can_access_route(student, "/documents") is False
    assert can_access_route(student, "/administrators") is False
    assert can_access_route(student, "/system-health") is False


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
