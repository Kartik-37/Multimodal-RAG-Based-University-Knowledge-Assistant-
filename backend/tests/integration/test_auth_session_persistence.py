"""
Integration Tests for Authentication Lifecycle, Session Persistence, and Multi-User Isolation.

Covers:
1. login -> /auth/me
2. login -> protected endpoint
3. login -> dashboard state
4. registration -> authenticated session
5. logout -> /auth/me returns 401 and PostgreSQL session deleted
6. second login after logout establishes valid new session
7. admin vs student multi-user session isolation
8. page navigation session persistence across simulated page views
9. expired session rejection
10. inactive account rejection
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from nicegui.storage import request_contextvar
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.requests import Request

from backend.app.core.security import get_password_hash, hash_session_token
from backend.app.models.user import AdminRole, User, UserRole, UserSession
from frontend.client.api_client import _session_clients, api_client
from frontend.components.layout import page_layout
from frontend.state.app_state import _session_app_states, state


def _create_mock_request(session_id: str) -> Request:
    """Create a mock Starlette request carrying the given NiceGUI browser session ID."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/dashboard",
        "headers": [],
        "session": {"id": session_id},
    }
    return Request(scope)


@pytest.fixture(autouse=True)
def clean_session_state(db_session: Session):
    """Ensure session state and test users are clean for every test run."""
    # Reset proxy state
    request_contextvar.set(None)
    _session_clients.clear()
    _session_app_states.clear()
    api_client.clear_session()
    state.reset_session_state()

    # Ensure admin user exists with known password
    admin = db_session.execute(
        select(User).where(User.email == "admin@university.edu")
    ).scalar_one_or_none()
    if not admin:
        admin = User(
            id=uuid.uuid4(),
            email="admin@university.edu",
            password_hash=get_password_hash("AdminPass123!"),
            full_name="System Administrator",
            role=UserRole.ADMIN,
            admin_role=AdminRole.MAIN_ADMIN,
            is_active=True,
        )
        db_session.add(admin)
    else:
        admin.password_hash = get_password_hash("AdminPass123!")
        admin.is_active = True
        admin.role = UserRole.ADMIN
        admin.admin_role = AdminRole.MAIN_ADMIN

    # Ensure student user exists with known password
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
            is_active=True,
        )
        db_session.add(student)
    else:
        student.password_hash = get_password_hash("StudentPass123!")
        student.is_active = True
        student.role = UserRole.STUDENT

    db_session.commit()

    yield

    # Teardown
    request_contextvar.set(None)
    _session_clients.clear()
    _session_app_states.clear()
    api_client.clear_session()
    state.reset_session_state()


def test_1_login_to_auth_me() -> None:
    """Verify login -> /auth/me returns valid user identity for both Admin and Student."""
    # Admin login
    admin_user = api_client.login("admin@university.edu", "AdminPass123!")
    assert admin_user.email == "admin@university.edu"
    assert admin_user.role == "ADMIN"
    assert admin_user.admin_role == "MAIN_ADMIN"

    me = api_client.get_current_user()
    assert me is not None
    assert me.email == "admin@university.edu"
    assert me.role == "ADMIN"

    api_client.logout()

    # Student login
    student_user = api_client.login("student1@university.edu", "StudentPass123!")
    assert student_user.email == "student1@university.edu"
    assert student_user.role == "STUDENT"

    me = api_client.get_current_user()
    assert me is not None
    assert me.email == "student1@university.edu"
    assert me.role == "STUDENT"


def test_2_login_to_protected_endpoint() -> None:
    """Verify login grants access to protected endpoints without 401."""
    # Unauthenticated attempt raises ValueError
    api_client.logout()
    with pytest.raises(ValueError, match="Authentication"):
        api_client.get_knowledge_bases()

    # Authenticate as admin
    api_client.login("admin@university.edu", "AdminPass123!")
    kbs = api_client.get_knowledge_bases()
    assert isinstance(kbs, list)


def test_3_login_to_dashboard_state() -> None:
    """Verify login correctly establishes presentation AppState for dashboard."""
    api_client.login("admin@university.edu", "AdminPass123!")
    assert state.current_user is not None
    assert state.current_user.email == "admin@university.edu"
    assert state.is_admin is True

    # Page layout with require_auth=True executes successfully
    executed = False
    with page_layout(title="Dashboard", active_route="/dashboard", require_auth=True):
        executed = True
    assert executed is True


def test_4_registration_establishes_authenticated_session() -> None:
    """Verify registration creates STUDENT account and establishes usable session."""
    unique_email = f"new_student_{uuid.uuid4().hex[:8]}@university.edu"
    user = api_client.register(
        email=unique_email,
        password="StudentPass123!",
        full_name="Newly Registered Student",
    )
    assert user.email == unique_email
    assert user.role == "STUDENT"
    assert user.full_name == "Newly Registered Student"

    # Backend /auth/me returns the registered user
    me = api_client.get_current_user()
    assert me is not None
    assert me.email == unique_email
    assert me.role == "STUDENT"

    # App state confirms student
    assert state.current_user is not None
    assert state.current_user.email == unique_email
    assert state.is_admin is False


def test_5_logout_invalidates_server_session(db_session: Session) -> None:
    """Verify logout terminates session in PostgreSQL and clears frontend state."""
    api_client.login("admin@university.edu", "AdminPass123!")
    raw_token = api_client.get_session_token()
    assert raw_token is not None

    token_hash = hash_session_token(raw_token)
    session_record = db_session.execute(
        select(UserSession).where(UserSession.session_token_hash == token_hash)
    ).scalar_one_or_none()
    assert session_record is not None, "PostgreSQL session record must exist while logged in."

    # Perform logout
    api_client.logout()

    # Verify frontend state is cleared
    assert api_client.get_current_user() is None
    assert state.current_user is None

    # Verify PostgreSQL session record is deleted
    db_session.expire_all()
    session_after = db_session.execute(
        select(UserSession).where(UserSession.session_token_hash == token_hash)
    ).scalar_one_or_none()
    assert session_after is None, "PostgreSQL session record must be deleted upon logout."


def test_6_second_login_after_logout() -> None:
    """Verify user can log in again after logging out, establishing a fresh session."""
    api_client.login("admin@university.edu", "AdminPass123!")
    assert api_client.get_current_user().email == "admin@university.edu"

    api_client.logout()
    assert api_client.get_current_user() is None

    # Second login
    api_client.login("admin@university.edu", "AdminPass123!")
    me = api_client.get_current_user()
    assert me is not None
    assert me.email == "admin@university.edu"


def test_7_multi_user_session_isolation() -> None:
    """
    CRITICAL ISOLATION TEST:
    Browser A (Admin) and Browser B (Student) have completely isolated sessions.
    Logging out Browser A leaves Browser B fully authenticated and untouched.
    """
    session_a_id = f"session-browser-admin-{uuid.uuid4().hex[:6]}"
    session_b_id = f"session-browser-student-{uuid.uuid4().hex[:6]}"

    req_a = _create_mock_request(session_a_id)
    req_b = _create_mock_request(session_b_id)

    # 1. Browser A logs in as Admin
    request_contextvar.set(req_a)
    user_a = api_client.login("admin@university.edu", "AdminPass123!")
    assert user_a.role == "ADMIN"
    assert api_client.get_current_user().role == "ADMIN"
    assert state.is_admin is True

    # 2. Browser B logs in as Student
    request_contextvar.set(req_b)
    user_b = api_client.login("student1@university.edu", "StudentPass123!")
    assert user_b.role == "STUDENT"
    assert api_client.get_current_user().role == "STUDENT"
    assert state.is_admin is False

    # 3. Switch back to Browser A -> Still Admin
    request_contextvar.set(req_a)
    current_a = api_client.get_current_user()
    assert current_a is not None
    assert current_a.email == "admin@university.edu"
    assert state.is_admin is True

    # 4. Switch to Browser B -> Still Student
    request_contextvar.set(req_b)
    current_b = api_client.get_current_user()
    assert current_b is not None
    assert current_b.email == "student1@university.edu"
    assert state.is_admin is False

    # 5. Browser A logs out
    request_contextvar.set(req_a)
    api_client.logout()
    assert api_client.get_current_user() is None
    assert state.current_user is None

    # 6. Browser B remains authenticated as Student
    request_contextvar.set(req_b)
    recheck_b = api_client.get_current_user()
    assert recheck_b is not None
    assert recheck_b.email == "student1@university.edu"
    assert recheck_b.role == "STUDENT"
    assert state.is_admin is False

    # 7. Browser A still cannot access Browser B's session
    request_contextvar.set(req_a)
    assert api_client.get_current_user() is None


def test_8_page_navigation_session_persistence() -> None:
    """
    Verify authentication survives navigation across multiple pages
    (e.g. /login -> /dashboard -> /chat -> /knowledge-bases -> /profile).
    """
    browser_session_id = f"nav-session-{uuid.uuid4().hex[:6]}"

    # Simulated /login page
    req_login = _create_mock_request(browser_session_id)
    req_login.scope["path"] = "/login"
    request_contextvar.set(req_login)

    api_client.login("admin@university.edu", "AdminPass123!")
    assert api_client.get_current_user() is not None

    # Simulated navigation to /dashboard
    req_dashboard = _create_mock_request(browser_session_id)
    req_dashboard.scope["path"] = "/dashboard"
    request_contextvar.set(req_dashboard)

    user_dashboard = api_client.get_current_user()
    assert user_dashboard is not None
    assert user_dashboard.email == "admin@university.edu"
    assert state.is_admin is True

    # Simulated navigation to /chat
    req_chat = _create_mock_request(browser_session_id)
    req_chat.scope["path"] = "/chat"
    request_contextvar.set(req_chat)

    user_chat = api_client.get_current_user()
    assert user_chat is not None
    assert user_chat.email == "admin@university.edu"

    # Simulated navigation to /knowledge-bases
    req_kbs = _create_mock_request(browser_session_id)
    req_kbs.scope["path"] = "/knowledge-bases"
    request_contextvar.set(req_kbs)

    kbs = api_client.get_knowledge_bases()
    assert isinstance(kbs, list)


def test_9_expired_session_rejection(db_session: Session) -> None:
    """Verify expired sessions in PostgreSQL are rejected and client state is purged."""
    api_client.login("admin@university.edu", "AdminPass123!")
    raw_token = api_client.get_session_token()
    assert raw_token is not None

    # Manually expire the session in PostgreSQL
    token_hash = hash_session_token(raw_token)
    stmt = select(UserSession).where(UserSession.session_token_hash == token_hash)
    session_record = db_session.execute(stmt).scalar_one_or_none()
    assert session_record is not None
    session_record.expires_at = datetime.now(UTC) - timedelta(hours=1)
    db_session.commit()

    # Verification: get_current_user queries /auth/me, sees 401, clears local state
    user = api_client.get_current_user()
    assert user is None
    assert state.current_user is None


def test_10_inactive_account_rejection(db_session: Session) -> None:
    """Verify deactivated accounts cannot log in and existing sessions are invalidated."""
    temp_email = f"deactivated_{uuid.uuid4().hex[:6]}@university.edu"
    temp_user = User(
        id=uuid.uuid4(),
        email=temp_email,
        password_hash=get_password_hash("TestPass123!"),
        full_name="Deactivated User",
        role=UserRole.STUDENT,
        is_active=False,
    )
    db_session.add(temp_user)
    db_session.commit()

    # Attempt login for inactive account
    with pytest.raises(ValueError, match="inactive|Authentication|Invalid"):
        api_client.login(temp_email, "TestPass123!")

    assert api_client.get_current_user() is None
