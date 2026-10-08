"""Behavioral contracts for frontend navigation and route capability checks.

Validates that:
- Public routes are accessible to unauthenticated visitors.
- Protected application routes are rejected when unauthenticated.
- Students have capability access strictly to the student suite:
  /dashboard, /knowledge-bases, /chat, /profile.
- Students cannot access administrative management routes.
- Unknown roles fail closed.
"""

import pytest

from frontend.client.models import UserDTO
from frontend.security.access_control import PUBLIC_ROUTES, can_access_route

STUDENT_NAVIGATION_ROUTES = [
    "/dashboard",
    "/knowledge-bases",
    "/chat",
    "/profile",
]

ADMIN_ONLY_ROUTES = [
    "/documents",
    "/indexing",
    "/administrators",
    "/activity",
    "/system-health",
]


class TestNavigationContracts:
    """Validate client-side route access control and navigation contracts."""

    @pytest.mark.parametrize("route", sorted(PUBLIC_ROUTES))
    def test_unauthenticated_user_can_access_public_routes(self, route: str) -> None:
        assert can_access_route(None, route) is True

    @pytest.mark.parametrize("route", STUDENT_NAVIGATION_ROUTES + ADMIN_ONLY_ROUTES)
    def test_unauthenticated_user_cannot_access_protected_routes(self, route: str) -> None:
        assert can_access_route(None, route) is False

    @pytest.mark.parametrize("route", STUDENT_NAVIGATION_ROUTES)
    def test_student_can_access_student_routes(self, route: str) -> None:
        student = UserDTO(
            id="student-1",
            email="student@univ.edu",
            full_name="Student User",
            role="STUDENT",
        )
        assert can_access_route(student, route) is True

    @pytest.mark.parametrize("route", ADMIN_ONLY_ROUTES)
    def test_student_cannot_access_admin_routes(self, route: str) -> None:
        student = UserDTO(
            id="student-1",
            email="student@univ.edu",
            full_name="Student User",
            role="STUDENT",
        )
        assert can_access_route(student, route) is False

    def test_unknown_role_fails_closed(self) -> None:
        unknown_user = UserDTO(
            id="unknown-1",
            email="unknown@univ.edu",
            full_name="Unknown User",
            role="GUEST",
        )
        for route in STUDENT_NAVIGATION_ROUTES + ADMIN_ONLY_ROUTES:
            assert can_access_route(unknown_user, route) is False
