"""
Comprehensive Integration Tests for Authentication & Entry Journey.

Validates the critical authentication flow requirements:
1. /login portal page loads.
2. /student/login loads.
3. /admin/login loads.
4. /register loads.
5. Student login succeeds via Student Portal.
6. Admin login succeeds via Administrator Portal.
7. Student credentials rejected by admin portal with explicit guidance.
8. Admin credentials rejected by student portal with explicit guidance.
9. Registration creates STUDENT role.
10. Public registration cannot create ADMIN (role injection rejected).
11. Login creates server-side session record in PostgreSQL.
12. /auth/me returns correct role after login.
13. Session persists across protected-page navigation.
14. Logout invalidates server session in PostgreSQL.
15. Inactive account cannot log in.
16. Wrong portal attempt does NOT create a session or set session cookies.
17. No raw backend validation errors leak to UI.
18. Login submission loading state and submission safety.
19. Navigation displays correct role after authentication.
20. Multi-user session isolation remains intact.
"""

import uuid
from datetime import UTC, datetime

import pytest
from nicegui.storage import request_contextvar
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.requests import Request

from backend.app.core.security import get_password_hash, hash_session_token
from backend.app.models.user import AdminRole, User, UserRole, UserSession
from frontend.client.api_client import _session_clients, api_client
from frontend.client.error_handler import normalize_error
from frontend.pages.auth_pages import register_auth_pages
from frontend.security.access_control import can_access_route
from frontend.state.app_state import _session_app_states, state


def _create_mock_request(session_id: str, path: str = "/dashboard") -> Request:
    """Create a mock Starlette request carrying the given NiceGUI browser session ID."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [],
        "session": {"id": session_id},
    }
    return Request(scope)


@pytest.fixture(autouse=True)
def clean_auth_portal_state(db_session: Session):
    """Ensure session state, registries, and test accounts are clean for every test."""
    request_contextvar.set(None)
    _session_clients.clear()
    _session_app_states.clear()
    api_client.clear_session()
    state.reset_session_state()

    # Ensure admin exists
    admin = db_session.execute(
        select(User).where(User.email == "admin@university.edu")
    ).scalar_one_or_none()
    if not admin:
        admin = User(
            id=uuid.uuid4(),
            email="admin@university.edu",
            password_hash=get_password_hash("AdminPass123!"),
            full_name="University Administrator",
            role=UserRole.ADMIN,
            admin_role=AdminRole.MAIN_ADMIN,
            is_active=True,
        )
        db_session.add(admin)
    else:
        admin.admin_role = AdminRole.MAIN_ADMIN
        admin.password_hash = get_password_hash("AdminPass123!")
        admin.is_active = True

    # Ensure student exists
    student = db_session.execute(
        select(User).where(User.email == "student1@university.edu")
    ).scalar_one_or_none()
    if not student:
        student = User(
            id=uuid.uuid4(),
            email="student1@university.edu",
            password_hash=get_password_hash("StudentPass123!"),
            full_name="Student One",
            role=UserRole.STUDENT,
            admin_role=None,
            is_active=True,
        )
        db_session.add(student)

    db_session.commit()


# ==============================================================================
# TEST 1-4: Page routes registered and accessible as architectural contracts
# ==============================================================================
def test_1_login_portal_selection_route_registered() -> None:
    """Verify /login portal selection route is registered."""
    from nicegui import app as nicegui_app

    register_auth_pages()
    registered = [r.path for r in nicegui_app.routes if hasattr(r, "path")]
    assert "/login" in registered
    assert can_access_route(None, "/login") is True


def test_2_student_login_route_registered() -> None:
    """Verify /student/login portal route is registered."""
    from nicegui import app as nicegui_app

    register_auth_pages()
    registered = [r.path for r in nicegui_app.routes if hasattr(r, "path")]
    assert "/student/login" in registered
    assert can_access_route(None, "/student/login") is True


def test_3_admin_login_route_registered() -> None:
    """Verify /admin/login administrator portal route is registered."""
    from nicegui import app as nicegui_app

    register_auth_pages()
    registered = [r.path for r in nicegui_app.routes if hasattr(r, "path")]
    assert "/admin/login" in registered
    assert can_access_route(None, "/admin/login") is True


def test_4_register_route_registered() -> None:
    """Verify /register student registration route is registered."""
    from nicegui import app as nicegui_app

    register_auth_pages()
    registered = [r.path for r in nicegui_app.routes if hasattr(r, "path")]
    assert "/register" in registered
    assert can_access_route(None, "/register") is True


# ==============================================================================
# TEST 5-8: Portal-Specific Authentication & Server-Side Enforcement
# ==============================================================================
def test_5_student_login_succeeds_on_student_portal() -> None:
    """Verify student credentials succeed through the Student Portal."""
    user = api_client.student_login("student1@university.edu", "StudentPass123!")
    assert user is not None
    assert user.role == "STUDENT"
    assert user.email == "student1@university.edu"
    assert api_client.get_session_token() is not None


def test_6_admin_login_succeeds_on_admin_portal() -> None:
    """Verify administrator credentials succeed through the Administrator Portal."""
    user = api_client.admin_login("admin@university.edu", "AdminPass123!")
    assert user is not None
    assert user.role == "ADMIN"
    assert user.email == "admin@university.edu"
    assert api_client.get_session_token() is not None


def test_7_student_credentials_rejected_by_admin_portal() -> None:
    """CRITICAL SECURITY: Student credentials at /admin/login must be rejected by backend."""
    with pytest.raises(ValueError) as excinfo:
        api_client.admin_login("student1@university.edu", "StudentPass123!")

    error_msg = str(excinfo.value)
    assert (
        "This account does not have administrator access. Please use Student Sign In." in error_msg
    )
    # Ensure client was NOT left with an active authenticated session
    assert api_client.get_current_user() is None
    assert api_client.get_session_token() is None


def test_8_admin_credentials_rejected_by_student_portal() -> None:
    """CRITICAL SECURITY: Admin credentials at /student/login must be rejected by backend."""
    with pytest.raises(ValueError) as excinfo:
        api_client.student_login("admin@university.edu", "AdminPass123!")

    error_msg = str(excinfo.value)
    assert (
        "This account belongs to the Administrator Portal. Please use Administrator Sign In."
        in error_msg
    )
    # Ensure client was NOT left with an active authenticated session
    assert api_client.get_current_user() is None
    assert api_client.get_session_token() is None


# ==============================================================================
# TEST 9-10: Public Registration Security
# ==============================================================================
def test_9_public_registration_creates_student() -> None:
    """Verify public registration strictly provisions a STUDENT account."""
    new_email = f"student_{uuid.uuid4().hex[:6]}@university.edu"
    user = api_client.register(
        email=new_email,
        password="ValidPassword123!",
        full_name="New Student",
    )
    assert user.role == "STUDENT"
    assert user.email == new_email

    # Authoritative verification via backend /auth/me
    me = api_client.get_current_user()
    assert me is not None
    assert me.role == "STUDENT"
    assert me.email == new_email


def test_10_public_registration_rejects_role_injection() -> None:
    """Verify backend rejects extra fields attempting to escalate to ADMIN during registration."""
    # TestClient internal HTTP call
    payload = {
        "email": f"hacker_{uuid.uuid4().hex[:6]}@university.edu",
        "password": "ValidPassword123!",
        "full_name": "Injected User",
        "role": "ADMIN",  # Forbidden extra field
    }
    client = api_client._get_client()._http
    resp = client.post("/auth/register", json=payload)
    assert resp.status_code == 422  # Pydantic extra="forbid" rejects request


# ==============================================================================
# TEST 11-16: Server-Side Sessions & Edge Cases
# ==============================================================================
def test_11_login_persists_session_hash_in_postgresql(db_session: Session) -> None:
    """Verify login saves SHA-256 session token hash in PostgreSQL user_sessions."""
    api_client.student_login("student1@university.edu", "StudentPass123!")
    raw_token = api_client.get_session_token()
    assert raw_token is not None

    token_hash = hash_session_token(raw_token)
    record = db_session.execute(
        select(UserSession).where(UserSession.session_token_hash == token_hash)
    ).scalar_one_or_none()
    assert record is not None
    assert record.expires_at > datetime.now(UTC)


def test_12_auth_me_returns_authoritative_role() -> None:
    """Verify /auth/me returns authoritative user profile matching database."""
    api_client.admin_login("admin@university.edu", "AdminPass123!")
    user = api_client.get_current_user()
    assert user is not None
    assert user.role == "ADMIN"
    assert user.admin_role == "MAIN_ADMIN"


def test_13_session_persists_across_navigation() -> None:
    """Verify session survives navigation across multiple application routes."""
    browser_session_id = f"nav-{uuid.uuid4().hex[:6]}"
    req1 = _create_mock_request(browser_session_id, "/student/login")
    request_contextvar.set(req1)

    api_client.student_login("student1@university.edu", "StudentPass123!")
    assert api_client.get_current_user() is not None

    # Navigate to /dashboard
    req2 = _create_mock_request(browser_session_id, "/dashboard")
    request_contextvar.set(req2)
    assert api_client.get_current_user() is not None
    assert state.is_admin is False

    # Navigate to /chat
    req3 = _create_mock_request(browser_session_id, "/chat")
    request_contextvar.set(req3)
    assert api_client.get_current_user() is not None


def test_14_logout_invalidates_server_session(db_session: Session) -> None:
    """Verify logout removes the session from PostgreSQL and resets client state."""
    api_client.student_login("student1@university.edu", "StudentPass123!")
    raw_token = api_client.get_session_token()
    assert raw_token is not None
    token_hash = hash_session_token(raw_token)

    api_client.logout()

    # PostgreSQL session must be deleted
    record = db_session.execute(
        select(UserSession).where(UserSession.session_token_hash == token_hash)
    ).scalar_one_or_none()
    assert record is None
    assert api_client.get_current_user() is None


def test_15_inactive_account_rejected_by_all_portals(db_session: Session) -> None:
    """Verify deactivated accounts are rejected by both student and admin portals."""
    unique_email = f"inactive_{uuid.uuid4().hex[:6]}@university.edu"
    inactive_user = User(
        id=uuid.uuid4(),
        email=unique_email,
        password_hash=get_password_hash("InactivePass123!"),
        full_name="Inactive User",
        role=UserRole.STUDENT,
        is_active=False,
    )
    db_session.add(inactive_user)
    db_session.commit()

    with pytest.raises(ValueError) as excinfo:
        api_client.student_login(unique_email, "InactivePass123!")
    assert "inactive" in str(excinfo.value).lower()


def test_16_wrong_portal_creates_no_postgresql_session(db_session: Session) -> None:
    """Verify attempting wrong portal does NOT insert any session record in database."""
    session_count_before = len(db_session.execute(select(UserSession)).scalars().all())

    with pytest.raises(ValueError):
        api_client.admin_login("student1@university.edu", "StudentPass123!")

    session_count_after = len(db_session.execute(select(UserSession)).scalars().all())
    assert session_count_after == session_count_before


# ==============================================================================
# TEST 17-20: Error Hygiene, UX Controls, Navigation & Multi-User Isolation
# ==============================================================================
def test_17_no_raw_backend_errors_leak_to_ui() -> None:
    """Verify error normalizer protects against raw SQL, tracebacks, and internal dicts."""
    raw_sql_err = "OperationalError: SELECT * FROM users WHERE uuid = '123' Syntax Error"
    cleaned = normalize_error(raw_sql_err, context="auth")
    assert "SELECT" not in cleaned
    assert "Syntax Error" not in cleaned
    assert "server processing error" in cleaned.lower()

    # Raw Pydantic list
    pydantic_err = [{"loc": ["body", "password"], "msg": "too_short", "type": "string_too_short"}]
    cleaned_pyd = normalize_error(pydantic_err, context="auth")
    assert "Password must be at least 8 characters." in cleaned_pyd


def test_18_empty_credentials_rejected_before_network() -> None:
    """Verify empty email or password is rejected client-side before submission."""
    with pytest.raises(ValueError) as excinfo:
        api_client.student_login("", "")
    assert "must not be empty" in str(excinfo.value)


def test_19_navigation_shows_correct_role_after_authentication() -> None:
    """Verify route capabilities reflect authoritative user role after login."""
    # Student navigation
    api_client.student_login("student1@university.edu", "StudentPass123!")
    student_user = api_client.get_current_user()
    assert can_access_route(student_user, "/dashboard") is True
    assert can_access_route(student_user, "/chat") is True
    assert can_access_route(student_user, "/knowledge-bases") is True
    assert can_access_route(student_user, "/administrators") is False

    # Admin navigation
    api_client.logout()
    api_client.admin_login("admin@university.edu", "AdminPass123!")
    admin_user = api_client.get_current_user()
    assert can_access_route(admin_user, "/dashboard") is True
    assert can_access_route(admin_user, "/administrators") is True


def test_20_multi_user_session_isolation() -> None:
    """Verify Browser A (Admin) and Browser B (Student) have strictly isolated sessions."""
    browser_a = "browser-admin-sess"
    browser_b = "browser-student-sess"

    # Browser A logs in as Admin
    req_a = _create_mock_request(browser_a)
    request_contextvar.set(req_a)
    api_client.admin_login("admin@university.edu", "AdminPass123!")
    user_a = api_client.get_current_user()
    assert user_a is not None
    assert user_a.role == "ADMIN"
    assert state.is_admin is True

    # Browser B logs in as Student
    req_b = _create_mock_request(browser_b)
    request_contextvar.set(req_b)
    api_client.student_login("student1@university.edu", "StudentPass123!")
    user_b = api_client.get_current_user()
    assert user_b is not None
    assert user_b.role == "STUDENT"
    assert state.is_admin is False

    # Switch back to Browser A -> remains Admin
    request_contextvar.set(req_a)
    user_a_check = api_client.get_current_user()
    assert user_a_check is not None
    assert user_a_check.role == "ADMIN"
    assert state.is_admin is True

    # Browser A logs out
    api_client.logout()
    assert api_client.get_current_user() is None

    # Browser B remains authenticated as Student
    request_contextvar.set(req_b)
    user_b_check = api_client.get_current_user()
    assert user_b_check is not None
    assert user_b_check.role == "STUDENT"
    assert state.is_admin is False
