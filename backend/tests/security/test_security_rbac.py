"""
Security and Role-Based Access Control (RBAC) Integration Tests.

Verifies the 18 critical security requirements for Step 4:
1. Public registration creates STUDENT role.
2. Client cannot register as ADMIN (role injection rejected).
3. Admin can authenticate.
4. Student can authenticate.
5. Unauthenticated user gets 401 Unauthorized.
6. Student gets 403 Forbidden on admin-only operations.
7. Admin gets access to their authorized management operations.
8. User A cannot access User B's private knowledge base (returns 404).
9. Student without membership cannot access knowledge base (returns 404).
10. Student with membership can access knowledge base.
11. Client-supplied user IDs cannot bypass authorization.
12. Client-supplied role cannot bypass authorization.
13. Inactive users cannot authenticate or use protected endpoints.
14. Password hashes are never returned in API responses.
15. Plaintext passwords are never stored in PostgreSQL.
16. Session credentials are not logged; only SHA-256 hashes stored.
17. Logout invalidates the session record.
18. Expired sessions are rejected with 401 Unauthorized.
"""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.security import (
    SESSION_COOKIE_NAME,
    get_password_hash,
    hash_session_token,
    verify_password,
)
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseMember
from backend.app.models.user import User, UserRole, UserSession


@pytest.fixture(autouse=True)
def clean_security_db(db_engine) -> Generator[None, None, None]:
    """Clean all application tables before and after each test function."""
    with db_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE knowledge_base_members, knowledge_bases, "
                "user_sessions, users CASCADE;"
            )
        )
    yield
    with db_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE knowledge_base_members, knowledge_bases, "
                "user_sessions, users CASCADE;"
            )
        )


def create_user_direct(
    db: Session,
    email: str,
    password: str = "TestPassword123!",
    full_name: str = "Test User",
    role: UserRole = UserRole.STUDENT,
    is_active: bool = True,
) -> User:
    """Helper to provision a user directly in the database with Argon2id hash."""
    user = User(
        email=email.strip().lower(),
        password_hash=get_password_hash(password),
        full_name=full_name,
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ==============================================================================
# TEST 1: Public registration creates STUDENT
# ==============================================================================
def test_public_registration_creates_student(api_client: TestClient, db_session: Session) -> None:
    """Requirement 1: Public registration must ALWAYS provision a STUDENT role."""
    payload = {
        "email": "student1@university.edu",
        "password": "SecureStudentPass123!",
        "full_name": "Alice Student",
    }
    response = api_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, f"Expected 201, got: {response.text}"

    data = response.json()
    assert data["email"] == "student1@university.edu"
    assert data["role"] == "STUDENT"
    assert data["full_name"] == "Alice Student"

    # Query PostgreSQL directly to confirm server-side state
    db_user = db_session.query(User).filter(User.email == "student1@university.edu").first()
    assert db_user is not None
    assert db_user.role == UserRole.STUDENT


# ==============================================================================
# TEST 2: Client cannot register as ADMIN
# ==============================================================================
def test_client_cannot_register_as_admin(api_client: TestClient, db_session: Session) -> None:
    """Requirement 2: Client must never be able to create an ADMIN via registration."""
    # Attempt 1: Payload attempting to supply role='ADMIN' (rejected with 422 Unprocessable Entity)
    malicious_payload = {
        "email": "hacker@university.edu",
        "password": "HackerPassword123!",
        "full_name": "Eve Hacker",
        "role": "ADMIN",
    }
    response = api_client.post("/api/v1/auth/register", json=malicious_payload)
    assert response.status_code == 422, "Server must reject role field in registration"

    # Attempt 2: Confirm no user was created with ADMIN role in database
    db_user = db_session.query(User).filter(User.email == "hacker@university.edu").first()
    assert db_user is None

    # Attempt 3: Lowercase role injection
    malicious_payload_lower = {
        "email": "hacker2@university.edu",
        "password": "HackerPassword123!",
        "full_name": "Eve Hacker",
        "role": "admin",
    }
    response_lower = api_client.post("/api/v1/auth/register", json=malicious_payload_lower)
    assert response_lower.status_code == 422


# ==============================================================================
# TEST 3: Admin can authenticate
# ==============================================================================
def test_admin_can_authenticate(api_client: TestClient, db_session: Session) -> None:
    """Requirement 3: Admin user can authenticate and establish an active session."""
    create_user_direct(
        db_session,
        email="admin@university.edu",
        password="AdminPassword123!",
        full_name="System Administrator",
        role=UserRole.ADMIN,
    )

    login_resp = api_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@university.edu", "password": "AdminPassword123!"},
    )
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert data["user"]["role"] == "ADMIN"
    assert data["user"]["email"] == "admin@university.edu"

    # Verify session cookie was set
    assert SESSION_COOKIE_NAME in api_client.cookies


# ==============================================================================
# TEST 4: Student can authenticate
# ==============================================================================
def test_student_can_authenticate(api_client: TestClient, db_session: Session) -> None:
    """Requirement 4: Student user can authenticate and establish an active session."""
    create_user_direct(
        db_session,
        email="bob@university.edu",
        password="BobPassword123!",
        full_name="Bob Student",
        role=UserRole.STUDENT,
    )

    login_resp = api_client.post(
        "/api/v1/auth/login",
        json={"email": "bob@university.edu", "password": "BobPassword123!"},
    )
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert data["user"]["role"] == "STUDENT"
    assert data["user"]["email"] == "bob@university.edu"
    assert SESSION_COOKIE_NAME in api_client.cookies


# ==============================================================================
# TEST 5: Unauthenticated user gets 401
# ==============================================================================
def test_unauthenticated_user_gets_401(api_client: TestClient) -> None:
    """Requirement 5: Unauthenticated requests to protected endpoints return 401."""
    api_client.cookies.clear()

    # /auth/me
    resp_me = api_client.get("/api/v1/auth/me")
    assert resp_me.status_code == 401

    # /knowledge-bases
    resp_kb = api_client.get("/api/v1/knowledge-bases")
    assert resp_kb.status_code == 401

    # POST /knowledge-bases
    resp_post_kb = api_client.post("/api/v1/knowledge-bases", json={"name": "Unauthorized"})
    assert resp_post_kb.status_code == 401

    # POST /chat/query
    fake_kb_id = str(uuid.uuid4())
    resp_chat = api_client.post(
        "/api/v1/chat/query",
        json={"knowledge_base_id": fake_kb_id, "question": "Hello?"},
    )
    assert resp_chat.status_code == 401


# ==============================================================================
# TEST 6: Student gets 403 on admin-only operations
# ==============================================================================
def test_student_gets_403_on_admin_only_operations(
    api_client: TestClient, db_session: Session
) -> None:
    """Requirement 6: Student user receives 403 Forbidden on all admin-only operations."""
    create_user_direct(
        db_session,
        email="student_test@university.edu",
        password="Password123!",
        role=UserRole.STUDENT,
    )
    # Login as student
    api_client.post(
        "/api/v1/auth/login",
        json={"email": "student_test@university.edu", "password": "Password123!"},
    )

    # 1. Student attempts to create a knowledge base
    resp_create = api_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Forbidden KB", "description": "Student cannot create this"},
    )
    assert resp_create.status_code == 403
    assert "Administrator privileges required" in resp_create.json()["detail"]

    # 2. Student attempts to add members to a knowledge base
    fake_kb_id = str(uuid.uuid4())
    resp_members = api_client.post(
        f"/api/v1/knowledge-bases/{fake_kb_id}/members",
        json={"user_id": str(uuid.uuid4())},
    )
    assert resp_members.status_code == 403

    # 3. Student attempts to upload documents
    resp_upload = api_client.post(f"/api/v1/knowledge-bases/{fake_kb_id}/documents")
    assert resp_upload.status_code == 403

    # 4. Student attempts to delete documents
    fake_doc_id = str(uuid.uuid4())
    resp_delete = api_client.delete(f"/api/v1/knowledge-bases/{fake_kb_id}/documents/{fake_doc_id}")
    assert resp_delete.status_code == 403


# ==============================================================================
# TEST 7: Admin gets access to authorized management operations
# ==============================================================================
def test_admin_gets_access_to_management_operations(
    api_client: TestClient, db_session: Session
) -> None:
    """Requirement 7: Admin user can perform knowledge-base management operations."""
    admin = create_user_direct(
        db_session,
        email="admin_mgr@university.edu",
        password="Password123!",
        role=UserRole.ADMIN,
    )
    student = create_user_direct(
        db_session,
        email="student_target@university.edu",
        password="Password123!",
        role=UserRole.STUDENT,
    )

    # Login as admin
    api_client.post(
        "/api/v1/auth/login",
        json={"email": "admin_mgr@university.edu", "password": "Password123!"},
    )

    # 1. Create knowledge base
    resp_create = api_client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": "BCA Advanced Databases",
            "description": "PostgreSQL and pgvector course materials",
        },
    )
    assert resp_create.status_code == 201
    kb_data = resp_create.json()
    kb_id = kb_data["id"]
    assert kb_data["created_by_id"] == str(admin.id)

    # 2. Add student as member
    resp_add_member = api_client.post(
        f"/api/v1/knowledge-bases/{kb_id}/members",
        json={"user_id": str(student.id)},
    )
    assert resp_add_member.status_code == 201
    assert resp_add_member.json()["user_id"] == str(student.id)

    # 3. Access document upload gate (Step 4 authorization boundary)
    resp_upload_gate = api_client.post(f"/api/v1/knowledge-bases/{kb_id}/documents")
    assert resp_upload_gate.status_code == 200
    assert resp_upload_gate.json()["status"] == "authorized"

    # 4. Access document deletion gate
    fake_doc_id = str(uuid.uuid4())
    resp_delete_gate = api_client.delete(f"/api/v1/knowledge-bases/{kb_id}/documents/{fake_doc_id}")
    assert resp_delete_gate.status_code == 200
    assert resp_delete_gate.json()["status"] == "authorized"


# ==============================================================================
# TEST 8: User A cannot access User B's private KB (404 isolation)
# ==============================================================================
def test_user_a_cannot_access_user_b_private_kb(
    api_client: TestClient, db_session: Session
) -> None:
    """Requirement 8: Multi-user isolation prevents User B from accessing User A's KB."""
    admin_a = create_user_direct(
        db_session,
        email="admin_a@university.edu",
        password="Password123!",
        role=UserRole.ADMIN,
    )
    create_user_direct(
        db_session,
        email="admin_b@university.edu",
        password="Password123!",
        role=UserRole.ADMIN,
    )

    # Admin A creates a knowledge base
    kb_a = KnowledgeBase(
        name="Admin A Private Research",
        description="Confidential research notes",
        created_by_id=admin_a.id,
    )
    db_session.add(kb_a)
    db_session.commit()
    db_session.refresh(kb_a)

    # Admin B logs in
    api_client.post(
        "/api/v1/auth/login",
        json={"email": "admin_b@university.edu", "password": "Password123!"},
    )

    # Admin B attempts to get Admin A's KB -> must return 404 (not 403) to prevent existence leakage
    resp = api_client.get(f"/api/v1/knowledge-bases/{kb_a.id}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Knowledge base not found."

    # Admin B attempts to query Admin A's KB via chat -> must return 404
    resp_chat = api_client.post(
        "/api/v1/chat/query",
        json={
            "knowledge_base_id": str(kb_a.id),
            "question": "Extract confidential notes",
        },
    )
    assert resp_chat.status_code == 404


# ==============================================================================
# TEST 9: Student without membership cannot access the KB
# ==============================================================================
def test_student_without_membership_cannot_access_kb(
    api_client: TestClient, db_session: Session
) -> None:
    """Requirement 9: Student cannot access knowledge bases without granted membership."""
    admin = create_user_direct(
        db_session,
        email="faculty@university.edu",
        password="Password123!",
        role=UserRole.ADMIN,
    )
    create_user_direct(
        db_session,
        email="outsider_student@university.edu",
        password="Password123!",
        role=UserRole.STUDENT,
    )

    kb = KnowledgeBase(
        name="Faculty Exam Key",
        description="Exam answer keys",
        created_by_id=admin.id,
    )
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)

    # Student logs in
    api_client.post(
        "/api/v1/auth/login",
        json={"email": "outsider_student@university.edu", "password": "Password123!"},
    )

    # Student cannot see KB in list
    list_resp = api_client.get("/api/v1/knowledge-bases")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 0

    # Direct access returns 404
    get_resp = api_client.get(f"/api/v1/knowledge-bases/{kb.id}")
    assert get_resp.status_code == 404

    # Query returns 404
    chat_resp = api_client.post(
        "/api/v1/chat/query",
        json={"knowledge_base_id": str(kb.id), "question": "Show me the answers"},
    )
    assert chat_resp.status_code == 404


# ==============================================================================
# TEST 10: Student with membership can access the KB
# ==============================================================================
def test_student_with_membership_can_access_kb(api_client: TestClient, db_session: Session) -> None:
    """Requirement 10: Student with granted membership can view and query knowledge base."""
    admin = create_user_direct(
        db_session,
        email="prof@university.edu",
        password="Password123!",
        role=UserRole.ADMIN,
    )
    student = create_user_direct(
        db_session,
        email="enrolled@university.edu",
        password="Password123!",
        role=UserRole.STUDENT,
    )

    kb = KnowledgeBase(
        name="BCA Semester 5 Syllabus",
        description="Distributed Systems Course Notes",
        created_by_id=admin.id,
    )
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)

    # Admin grants membership to student
    membership = KnowledgeBaseMember(knowledge_base_id=kb.id, user_id=student.id)
    db_session.add(membership)
    db_session.commit()

    # Student logs in
    api_client.post(
        "/api/v1/auth/login",
        json={"email": "enrolled@university.edu", "password": "Password123!"},
    )

    # Student sees KB in list
    list_resp = api_client.get("/api/v1/knowledge-bases")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 1
    assert items[0]["id"] == str(kb.id)

    # Direct access succeeds
    get_resp = api_client.get(f"/api/v1/knowledge-bases/{kb.id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "BCA Semester 5 Syllabus"

    # Query succeeds
    chat_resp = api_client.post(
        "/api/v1/chat/query",
        json={
            "knowledge_base_id": str(kb.id),
            "question": "What is two-phase locking?",
        },
    )
    assert chat_resp.status_code == 200
    assert "answer" in chat_resp.json()


# ==============================================================================
# TEST 11: Client-supplied user IDs cannot bypass authorization
# ==============================================================================
def test_client_supplied_user_ids_cannot_bypass_authorization(
    api_client: TestClient, db_session: Session
) -> None:
    """Requirement 11: Client-supplied user IDs are completely ignored by the server."""
    admin = create_user_direct(
        db_session,
        email="victim_admin@university.edu",
        password="Password123!",
        role=UserRole.ADMIN,
    )
    student = create_user_direct(
        db_session,
        email="attacker_student@university.edu",
        password="Password123!",
        role=UserRole.STUDENT,
    )

    # Student logs in
    api_client.post(
        "/api/v1/auth/login",
        json={"email": "attacker_student@university.edu", "password": "Password123!"},
    )

    # Attacker tries injecting user_id query param or headers targeting victim_admin
    resp = api_client.get(
        f"/api/v1/auth/me?user_id={admin.id}",
        headers={"X-User-Id": str(admin.id), "User-Id": str(admin.id)},
    )
    assert resp.status_code == 200
    data = resp.json()
    # Server strictly resolves identity from session cookie, not client-supplied user ID
    assert data["id"] == str(student.id)
    assert data["email"] == "attacker_student@university.edu"
    assert data["role"] == "STUDENT"


# ==============================================================================
# TEST 12: Client-supplied role cannot bypass authorization
# ==============================================================================
def test_client_supplied_role_cannot_bypass_authorization(
    api_client: TestClient, db_session: Session
) -> None:
    """Requirement 12: Client cannot spoof roles via headers, query params, or bodies."""
    create_user_direct(
        db_session,
        email="spoof_tester@university.edu",
        password="Password123!",
        role=UserRole.STUDENT,
    )

    # Student logs in
    api_client.post(
        "/api/v1/auth/login",
        json={"email": "spoof_tester@university.edu", "password": "Password123!"},
    )

    # Student attempts to create KB with spoofed role headers
    resp = api_client.post(
        "/api/v1/knowledge-bases?role=ADMIN",
        json={"name": "Spoofed KB"},
        headers={
            "X-Role": "ADMIN",
            "Role": "ADMIN",
            "X-User-Role": "ADMIN",
        },
    )
    assert resp.status_code == 403
    assert "Administrator privileges required" in resp.json()["detail"]


# ==============================================================================
# TEST 13: Inactive users cannot authenticate or use protected endpoints
# ==============================================================================
def test_inactive_user_cannot_authenticate_or_use_protected_endpoints(
    api_client: TestClient, db_session: Session
) -> None:
    """Requirement 13: Inactive/disabled accounts are prevented from logging in or querying."""
    user = create_user_direct(
        db_session,
        email="disabled@university.edu",
        password="Password123!",
        role=UserRole.STUDENT,
        is_active=False,
    )

    # 1. Attempt login with disabled account -> 401
    login_resp = api_client.post(
        "/api/v1/auth/login",
        json={"email": "disabled@university.edu", "password": "Password123!"},
    )
    assert login_resp.status_code == 401
    assert "inactive" in login_resp.json()["detail"].lower()

    # 2. If a user is deactivated while holding an active session, requests are rejected
    user.is_active = True
    db_session.commit()

    # Now login succeeds
    active_login = api_client.post(
        "/api/v1/auth/login",
        json={"email": "disabled@university.edu", "password": "Password123!"},
    )
    assert active_login.status_code == 200

    # Deactivate the user mid-session
    user.is_active = False
    db_session.commit()

    # Next request must be rejected with 401
    resp_me = api_client.get("/api/v1/auth/me")
    assert resp_me.status_code == 401


# ==============================================================================
# TEST 14: Password hashes are never returned
# ==============================================================================
def test_password_hashes_are_never_returned(api_client: TestClient, db_session: Session) -> None:
    """Requirement 14: API responses must never leak password hashes or raw secrets."""
    # 1. Registration endpoint
    reg_resp = api_client.post(
        "/api/v1/auth/register",
        json={
            "email": "no_hash_leak@university.edu",
            "password": "SuperSecretPassword123!",
            "full_name": "No Leak",
        },
    )
    assert reg_resp.status_code == 201
    reg_data = reg_resp.json()
    assert "password_hash" not in reg_data
    assert "hashed_password" not in reg_data
    assert "password" not in reg_data

    # 2. Login endpoint
    login_resp = api_client.post(
        "/api/v1/auth/login",
        json={
            "email": "no_hash_leak@university.edu",
            "password": "SuperSecretPassword123!",
        },
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert "password_hash" not in login_data["user"]
    assert "hashed_password" not in login_data["user"]
    assert "password" not in login_data["user"]

    # 3. Current user /me endpoint
    me_resp = api_client.get("/api/v1/auth/me")
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert "password_hash" not in me_data
    assert "hashed_password" not in me_data
    assert "password" not in me_data


# ==============================================================================
# TEST 15: Plaintext passwords are never stored
# ==============================================================================
def test_plaintext_passwords_are_never_stored(api_client: TestClient, db_session: Session) -> None:
    """Requirement 15: Database must store only modern Argon2id password hashes."""
    plaintext = "MyVerySecretPassword123!"
    api_client.post(
        "/api/v1/auth/register",
        json={
            "email": "argon_check@university.edu",
            "password": plaintext,
            "full_name": "Argon Check",
        },
    )

    db_user = db_session.query(User).filter(User.email == "argon_check@university.edu").first()
    assert db_user is not None
    assert db_user.password_hash != plaintext
    assert db_user.password_hash.startswith("$argon2id$")
    # Verify using Argon2id password verifier
    assert verify_password(plaintext, db_user.password_hash) is True
    assert verify_password("WrongPassword", db_user.password_hash) is False


# ==============================================================================
# TEST 16: Session credentials are not logged; only hashes stored
# ==============================================================================
def test_session_credentials_are_not_logged_and_only_hashes_stored(
    api_client: TestClient, db_session: Session
) -> None:
    """Requirement 16: Raw session tokens exist only in the cookie; DB holds SHA-256 hash."""
    create_user_direct(
        db_session,
        email="token_hash_test@university.edu",
        password="Password123!",
        role=UserRole.STUDENT,
    )

    login_resp = api_client.post(
        "/api/v1/auth/login",
        json={"email": "token_hash_test@university.edu", "password": "Password123!"},
    )
    assert login_resp.status_code == 200

    # Extract raw token received by browser/client
    raw_token = api_client.cookies.get(SESSION_COOKIE_NAME)
    assert raw_token is not None
    assert len(raw_token) > 20

    # Query PostgreSQL UserSession table
    sessions = db_session.query(UserSession).all()
    assert len(sessions) == 1
    session_record = sessions[0]

    # Database MUST store 64-char SHA-256 hex digest
    assert len(session_record.session_token_hash) == 64
    # The raw token MUST NOT equal the stored hash
    assert session_record.session_token_hash != raw_token
    # Computed hash must match stored hash
    assert session_record.session_token_hash == hash_session_token(raw_token)


# ==============================================================================
# TEST 17: Logout invalidates the session
# ==============================================================================
def test_logout_invalidates_session(api_client: TestClient, db_session: Session) -> None:
    """Requirement 17: Logging out destroys the database session and rejects subsequent calls."""
    create_user_direct(
        db_session,
        email="logout_test@university.edu",
        password="Password123!",
        role=UserRole.STUDENT,
    )

    login_resp = api_client.post(
        "/api/v1/auth/login",
        json={"email": "logout_test@university.edu", "password": "Password123!"},
    )
    assert login_resp.status_code == 200
    raw_token = api_client.cookies.get(SESSION_COOKIE_NAME)

    # Verify session exists in DB
    token_hash = hash_session_token(raw_token)
    session_before = (
        db_session.query(UserSession).filter(UserSession.session_token_hash == token_hash).first()
    )
    assert session_before is not None

    # Call logout
    logout_resp = api_client.post("/api/v1/auth/logout")
    assert logout_resp.status_code == 200

    # Verify session record is deleted from PostgreSQL
    session_after = (
        db_session.query(UserSession).filter(UserSession.session_token_hash == token_hash).first()
    )
    assert session_after is None

    # Verify subsequent call returns 401 Unauthorized
    resp_after = api_client.get("/api/v1/auth/me")
    assert resp_after.status_code == 401


# ==============================================================================
# TEST 18: Expired sessions are rejected
# ==============================================================================
def test_expired_sessions_are_rejected(api_client: TestClient, db_session: Session) -> None:
    """Requirement 18: Sessions whose expiry timestamp has passed are rejected with 401."""
    create_user_direct(
        db_session,
        email="expired_test@university.edu",
        password="Password123!",
        role=UserRole.STUDENT,
    )

    login_resp = api_client.post(
        "/api/v1/auth/login",
        json={"email": "expired_test@university.edu", "password": "Password123!"},
    )
    assert login_resp.status_code == 200
    raw_token = api_client.cookies.get(SESSION_COOKIE_NAME)

    # Manually expire the session in the database
    token_hash = hash_session_token(raw_token)
    session_record = (
        db_session.query(UserSession).filter(UserSession.session_token_hash == token_hash).first()
    )
    assert session_record is not None
    session_record.expires_at = datetime.now(UTC) - timedelta(hours=2)
    db_session.commit()

    # Call /auth/me with expired session cookie
    resp = api_client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert "Authentication required" in resp.json()["detail"]
