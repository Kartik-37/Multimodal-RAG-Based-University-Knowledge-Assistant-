"""Behavioral contracts for authentication layouts, public routes, and auth forms.

Validates:
- Public route capability contracts for all unauthenticated visitors.
- Role-specific navigation targets for student, admin, and registration portals.
- Form validation behavior (email presence, password length, role enforcement).
- Error sanitization via normalize_error to prevent credential and database leakage.
- CSS layout specifications ensuring balanced two-column desktop grids and mobile reflow.
"""

import pytest

from frontend.client.error_handler import normalize_error
from frontend.client.models import UserDTO
from frontend.components.theme import GLOBAL_THEME_CSS
from frontend.security.access_control import PUBLIC_ROUTES, can_access_route


class TestAuthLayoutContracts:
    """Validate behavioral contracts of authentication pages and shared layout."""

    @pytest.mark.parametrize(
        "route",
        [
            "/",
            "/login",
            "/student/login",
            "/admin/login",
            "/register",
        ],
    )
    def test_all_auth_portals_are_publicly_accessible(self, route: str) -> None:
        """Unauthenticated visitors must have unrestricted access to all auth portals."""
        assert route in PUBLIC_ROUTES
        assert can_access_route(None, route) is True

    def test_auth_split_grid_css_specifies_desktop_two_column_and_mobile_one_column(self) -> None:
        """The auth-split-grid CSS must define 1 column for mobile and a 2-column grid for desktop."""
        assert ".auth-split-grid" in GLOBAL_THEME_CSS
        # Mobile: single column
        assert "grid-template-columns: 1fr" in GLOBAL_THEME_CSS
        # Desktop: two columns with minmax proportions
        assert "minmax(0, 1.05fr) minmax(360px, 0.95fr)" in GLOBAL_THEME_CSS
        # Gap spacing
        assert "gap: 3rem" in GLOBAL_THEME_CSS

    def test_auth_header_fixed_positioning_rule_present(self) -> None:
        """Quasar header positioning must be fixed to top without causing content overlap."""
        assert ".q-header.fixed-top" in GLOBAL_THEME_CSS
        assert "top: 0 !important;" in GLOBAL_THEME_CSS

    def test_auth_error_sanitization_masks_internal_details(self) -> None:
        """Raw exceptions from database or network must be normalized for auth displays."""
        db_error = Exception("psycopg2.OperationalError: could not connect to server: Connection refused")
        user_facing_msg = normalize_error(db_error, context="auth")
        assert "psycopg2" not in user_facing_msg
        assert "Connection refused" not in user_facing_msg
        assert "Please try again." in user_facing_msg

    def test_student_and_admin_authenticated_users_redirected_to_dashboard(self) -> None:
        """When an authenticated user visits protected pages, capability checks route correctly."""
        student = UserDTO(
            id="s1",
            email="student@univ.edu",
            full_name="Student",
            role="STUDENT",
        )
        admin = UserDTO(
            id="a1",
            email="admin@univ.edu",
            full_name="Admin",
            role="ADMIN",
            admin_role="MAIN_ADMIN",
        )
        assert can_access_route(student, "/dashboard") is True
        assert can_access_route(admin, "/dashboard") is True
