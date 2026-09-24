"""Step 21E frontend navigation/state contract tests."""

from backend.app.core.permissions import Permission
from frontend.client.models import UserDTO
from frontend.components.layout import get_nav_items, has_admin_permission


def test_main_admin_navigation_contains_admin_chat() -> None:
    user = UserDTO(
        id="1",
        email="main@univ.edu",
        full_name="Main Admin",
        role="ADMIN",
        admin_role="MAIN_ADMIN",
        permissions=[],
    )
    labels = [label for label, _, _ in get_nav_items(user)]
    assert labels == [
        "Dashboard",
        "Courses",
        "Documents",
        "Admin Chat",
        "Administrators",
        "Profile",
    ]


def test_faculty_admin_navigation_respects_admin_chat_permission() -> None:
    without_chat = UserDTO(
        id="2",
        email="faculty@univ.edu",
        full_name="Faculty",
        role="ADMIN",
        admin_role="FACULTY_ADMIN",
        permissions=[Permission.DOCUMENT_VIEW.value],
    )
    labels_without = [label for label, _, _ in get_nav_items(without_chat)]
    assert "Admin Chat" not in labels_without
    assert "Documents" in labels_without

    with_chat = without_chat.model_copy(
        update={"permissions": [Permission.DOCUMENT_VIEW.value, Permission.ADMIN_CHAT.value]}
    )
    labels_with = [label for label, _, _ in get_nav_items(with_chat)]
    assert "Admin Chat" in labels_with
    assert has_admin_permission(with_chat, Permission.ADMIN_CHAT) is True


def test_student_navigation_has_student_chat_only() -> None:
    user = UserDTO(
        id="3",
        email="student@univ.edu",
        full_name="Student",
        role="STUDENT",
    )
    labels = [label for label, _, _ in get_nav_items(user)]
    assert labels == ["Home", "Ask Assistant", "Courses", "Profile"]
    assert "Admin Chat" not in labels
