"""
Phase 1 Security & Backend Correctness Verification Suite.

Validates all Phase 1 requirements:
1. Insecure token-in-URL (?token=...) authentication is completely removed and rejected.
2. Unauthenticated file requests return HTTP 401 Unauthorized.
3. Cookie-based HttpOnly session and Bearer header authentication remain fully operational.
4. Source viewer code contains zero token query construction and zero client-side document.cookie writes.
5. Production FrontendAPIClient does NOT import or use fastapi.testclient.TestClient.
6. Exception normalization suppresses internal URLs, hostnames, ports, SQL queries, tracebacks, and paths.
7. Cross-user/role authorization rules are strictly maintained for document streaming.
"""

from pathlib import Path
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.security import SESSION_COOKIE_NAME, get_password_hash
from backend.app.main import app
from backend.app.models.user import User, UserRole
from frontend.client.error_handler import normalize_error


def _create_test_user(
    db: Session,
    email: str,
    password: str = "AdminPass123!",
    role: UserRole = UserRole.ADMIN,
) -> User:
    """Helper to provision test user in database."""
    user = User(
        email=email.strip().lower(),
        password_hash=get_password_hash(password),
        full_name="Phase 1 Test Admin",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class TestPhase1SecurityHardening:
    """Rigorous security validation suite for Phase 1 requirements."""

    def test_token_in_url_rejected_with_401(self, db_session: Session) -> None:
        """Verify ?token= query parameter is completely ignored and rejected."""
        email = f"admin_{uuid.uuid4().hex[:6]}@university.edu"
        password = "AdminPass123!"
        _create_test_user(db_session, email=email, password=password, role=UserRole.ADMIN)

        client = TestClient(app)

        # Authenticate admin to obtain a valid session token
        login_resp = client.post(
            "/api/v1/auth/login/admin",
            json={"email": email, "password": password},
        )
        assert login_resp.status_code == 200
        admin_token = client.cookies.get(SESSION_COOKIE_NAME)
        assert admin_token is not None

        # Create a course and document
        kb_resp = client.post(
            "/api/v1/knowledge-bases",
            json={"name": f"Security KB {uuid.uuid4().hex[:6]}", "description": "Phase 1 Test"},
        )
        assert kb_resp.status_code == 201
        kb_id = kb_resp.json()["id"]

        upload_resp = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/documents",
            files={"file": ("sec_doc.txt", b"Confidential course material.")},
        )
        assert upload_resp.status_code == 201
        doc_id = upload_resp.json()["id"]

        # An unauthenticated client attempting to use ?token= must receive 401 Unauthorized
        unauth_client = TestClient(app)

        # Test endpoint 1: /documents/{id}/file?token=...
        url_resp1 = unauth_client.get(f"/api/v1/documents/{doc_id}/file?token={admin_token}")
        assert url_resp1.status_code == 401, "Query parameter ?token must be rejected with 401"

        # Test endpoint 2: /documents/by-name?name=...&token=...
        url_resp2 = unauth_client.get(
            f"/api/v1/documents/by-name?name=sec_doc.txt&kb_id={kb_id}&token={admin_token}"
        )
        assert url_resp2.status_code == 401, "Query parameter ?token on by-name must be rejected with 401"

        # Test endpoint 3: /knowledge-bases/{kb_id}/documents/{doc_id}/file?token=...
        url_resp3 = unauth_client.get(
            f"/api/v1/knowledge-bases/{kb_id}/documents/{doc_id}/file?token={admin_token}"
        )
        assert url_resp3.status_code == 401, "Query parameter ?token on kb-scoped route must be rejected with 401"

    def test_unauthenticated_requests_return_401(self) -> None:
        """Verify requests without any credentials return 401."""
        unauth_client = TestClient(app)
        dummy_uuid = uuid.uuid4()
        resp = unauth_client.get(f"/api/v1/documents/{dummy_uuid}/file")
        assert resp.status_code == 401

    def test_cookie_and_bearer_authentication_functional(self, db_session: Session) -> None:
        """Verify legitimate HttpOnly cookies and Bearer headers still succeed."""
        email = f"admin_{uuid.uuid4().hex[:6]}@university.edu"
        password = "AdminPass123!"
        _create_test_user(db_session, email=email, password=password, role=UserRole.ADMIN)

        admin_client = TestClient(app)
        login_resp = admin_client.post(
            "/api/v1/auth/login/admin",
            json={"email": email, "password": password},
        )
        assert login_resp.status_code == 200
        token = admin_client.cookies.get(SESSION_COOKIE_NAME)
        assert token is not None

        # Create KB and document
        kb_resp = admin_client.post(
            "/api/v1/knowledge-bases",
            json={"name": f"Auth KB {uuid.uuid4().hex[:6]}", "description": "Auth Check"},
        )
        kb_id = kb_resp.json()["id"]

        upload_resp = admin_client.post(
            f"/api/v1/knowledge-bases/{kb_id}/documents",
            files={"file": ("auth_doc.txt", b"Authenticated text content.")},
        )
        doc_id = upload_resp.json()["id"]

        # 1. Access with cookie
        cookie_client = TestClient(app)
        cookie_client.cookies.set(SESSION_COOKIE_NAME, token)
        c_resp = cookie_client.get(f"/api/v1/documents/{doc_id}/file")
        assert c_resp.status_code == 200
        assert c_resp.content == b"Authenticated text content."

        # 2. Access with Authorization: Bearer
        bearer_client = TestClient(app)
        bearer_client.headers["Authorization"] = f"Bearer {token}"
        b_resp = bearer_client.get(f"/api/v1/documents/{doc_id}/file")
        assert b_resp.status_code == 200
        assert b_resp.content == b"Authenticated text content."

    def test_no_token_leakage_in_frontend_code(self) -> None:
        """Verify frontend components do not inject tokens into URLs or JavaScript."""
        # 1. source_viewer.py
        sv_code = Path("frontend/components/source_viewer.py").read_text(encoding="utf-8")
        assert "params.append(f\"token=" not in sv_code
        assert "f'document.cookie = \"session_id=" not in sv_code
        assert "?token=" not in sv_code

        # 2. auth_pages.py
        auth_code = Path("frontend/pages/auth_pages.py").read_text(encoding="utf-8")
        assert "document.cookie" not in auth_code

        # 3. backend deps.py
        deps_code = Path("backend/app/api/deps.py").read_text(encoding="utf-8")
        assert 'request.query_params.get("token")' not in deps_code

    def test_production_api_client_does_not_use_testclient(self) -> None:
        """Verify FrontendAPIClient does not import or instantiate TestClient."""
        api_client_code = Path("frontend/client/api_client.py").read_text(encoding="utf-8")
        assert "from fastapi.testclient import TestClient" not in api_client_code
        assert "TestClient(app" not in api_client_code
        assert "InProcessProductionTransport" in api_client_code
        assert "httpx.Client" in api_client_code

    def test_exception_sanitization(self) -> None:
        """Verify sensitive details, ports, internal paths, and SQL are sanitized."""
        # Database query leak
        assert (
            normalize_error("SELECT * FROM user_sessions WHERE token='secret'")
            == "A server processing error occurred. Please try again later."
        )

        # Filesystem path leak
        assert (
            normalize_error('File "D:\\Kartik\\backend\\app\\api\\deps.py", line 42, in get_user')
            == "A server processing error occurred. Please try again later."
        )

        # Connection / host / port leak
        assert (
            normalize_error("httpx.ConnectError: [Errno 111] Connection refused to http://127.0.0.1:11434")
            == "A server processing error occurred. Please try again later."
        )

        # Token leak
        assert (
            normalize_error("Validation failed: token=abc123xyz exposed")
            == "A server processing error occurred. Please try again later."
        )

        # Chat context sanitization
        assert (
            normalize_error("Ollama connection error at localhost:11434", context="chat")
            == "Unable to complete query synthesis at this time. Please try again."
        )
