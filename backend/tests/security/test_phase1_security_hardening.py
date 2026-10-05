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

import uuid
from datetime import UTC
from pathlib import Path

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
        assert "nicegui" not in deps_code.lower()

    def test_backend_deps_contains_no_nicegui_dependency(self) -> None:
        """Requirement F: backend deps.py must NOT import or depend on NiceGUI internals."""
        deps_code = Path("backend/app/api/deps.py").read_text(encoding="utf-8")
        assert "from nicegui" not in deps_code
        assert "import nicegui" not in deps_code
        assert "nicegui_app" not in deps_code
        assert "nicegui" not in deps_code.lower()

    def test_no_app_storage_user_session_token_persistence(self) -> None:
        """Requirement G: app.storage.user is not used to persist raw auth session tokens."""
        for path in Path("frontend").rglob("*.py"):
            code = path.read_text(encoding="utf-8")
            assert "auth_session_token" not in code, f"Found auth_session_token in {path}"
            assert "_get_persistent_token" not in code, f"Found _get_persistent_token in {path}"
            assert "_set_persistent_token" not in code, f"Found _set_persistent_token in {path}"

    def test_session_lifecycle_and_logout_invalidation(self, db_session: Session) -> None:
        """Requirements H & I: Normal session lifecycle works, and logout invalidates session."""
        email = f"user_{uuid.uuid4().hex[:6]}@university.edu"
        password = "UserPass123!"
        _create_test_user(db_session, email=email, password=password, role=UserRole.STUDENT)

        client = TestClient(app)
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login_resp.status_code == 200
        token = client.cookies.get(SESSION_COOKIE_NAME)
        assert token is not None

        # Verify active session works
        me_resp = client.get("/api/v1/auth/me")
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == email

        # Logout
        logout_resp = client.post("/api/v1/auth/logout")
        assert logout_resp.status_code == 200

        # Verify cookie is invalidated and subsequent request returns 401
        post_logout_resp = client.get("/api/v1/auth/me")
        assert post_logout_resp.status_code == 401

    def test_expired_session_is_rejected(self, db_session: Session) -> None:
        """Requirement J: Expired sessions are rejected with 401."""
        from datetime import datetime, timedelta

        from backend.app.core.security import hash_session_token
        from backend.app.models.user import UserSession

        email = f"expired_{uuid.uuid4().hex[:6]}@university.edu"
        password = "ExpiredPass123!"
        user = _create_test_user(db_session, email=email, password=password, role=UserRole.STUDENT)

        raw_token = f"fake_token_{uuid.uuid4().hex}"
        token_hash = hash_session_token(raw_token)
        past_time = datetime.now(UTC) - timedelta(hours=2)

        expired_session = UserSession(
            user_id=user.id,
            session_token_hash=token_hash,
            expires_at=past_time,
        )
        db_session.add(expired_session)
        db_session.commit()

        client = TestClient(app)
        client.cookies.set(SESSION_COOKIE_NAME, raw_token)
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_multiple_browser_sessions_remain_isolated(self, db_session: Session) -> None:
        """Requirement K: Multiple user sessions remain strictly isolated."""
        user_a = _create_test_user(
            db_session,
            email=f"user_a_{uuid.uuid4().hex[:6]}@university.edu",
            password="PasswordA123!",
            role=UserRole.ADMIN,
        )
        user_b = _create_test_user(
            db_session,
            email=f"user_b_{uuid.uuid4().hex[:6]}@university.edu",
            password="PasswordB123!",
            role=UserRole.ADMIN,
        )

        client_a = TestClient(app)
        client_b = TestClient(app)

        client_a.post("/api/v1/auth/login", json={"email": user_a.email, "password": "PasswordA123!"})
        client_b.post("/api/v1/auth/login", json={"email": user_b.email, "password": "PasswordB123!"})

        assert client_a.cookies.get(SESSION_COOKIE_NAME) != client_b.cookies.get(SESSION_COOKIE_NAME)

        # Admin A creates a course
        kb_resp = client_a.post("/api/v1/knowledge-bases", json={"name": "A Private Course"})
        assert kb_resp.status_code == 201
        kb_id = kb_resp.json()["id"]

        # Admin B cannot access Admin A's private course (returns 404)
        get_b = client_b.get(f"/api/v1/knowledge-bases/{kb_id}")
        assert get_b.status_code == 404

    def test_registration_failure_does_not_expose_raw_exception(self) -> None:
        """Requirement M: Registration error handling never exposes raw internal exception details."""
        from unittest.mock import MagicMock

        from frontend.client.api_client import FrontendAPIClient

        test_client = FrontendAPIClient()
        test_client._http = MagicMock()

        # Mock successful registration response
        mock_reg_resp = MagicMock()
        mock_reg_resp.status_code = 201
        mock_reg_resp.json.return_value = {
            "id": str(uuid.uuid4()),
            "email": "newstudent@university.edu",
            "full_name": "New Student",
            "role": "STUDENT",
        }
        test_client._http.post.side_effect = [
            mock_reg_resp,
            Exception("Internal Server Traceback: connection to postgresql://admin:secret@127.0.0.1:5432 failed"),
        ]

        with pytest.raises(ValueError) as exc_info:
            test_client.register(
                email="newstudent@university.edu",
                password="StudentPassword123!",
                full_name="New Student",
            )

        err_msg = str(exc_info.value)
        assert "postgresql://" not in err_msg
        assert "5432" not in err_msg
        assert "secret" not in err_msg
        assert "traceback" not in err_msg.lower()
        assert "Account created successfully. Please sign in with your credentials on the login page." in err_msg

    def test_api_client_error_paths_sanitize_raw_backend_details(self) -> None:
        """Requirement N: Retrieval, indexing, reranking, and query processing normalize error details."""
        from unittest.mock import MagicMock

        from frontend.client.api_client import FrontendAPIClient

        test_client = FrontendAPIClient()
        test_client._http = MagicMock()

        raw_leak_response = MagicMock()
        raw_leak_response.status_code = 500
        raw_leak_response.headers = {"content-type": "application/json"}
        raw_leak_response.json.return_value = {
            "detail": "sqlalchemy.exc.OperationalError: SELECT * FROM documents WHERE port 5432 D:\\Kartik\\db.py"
        }
        test_client._http.post.return_value = raw_leak_response

        # Test index_document
        with pytest.raises(ValueError) as exc:
            test_client.index_document(str(uuid.uuid4()), str(uuid.uuid4()))
        assert "sqlalchemy" not in str(exc.value)
        assert "5432" not in str(exc.value)
        assert "D:\\" not in str(exc.value)

        # Test retry_indexing
        with pytest.raises(ValueError) as exc:
            test_client.retry_indexing(str(uuid.uuid4()), str(uuid.uuid4()))
        assert "sqlalchemy" not in str(exc.value)

        # Test retrieve_chunks
        with pytest.raises(ValueError) as exc:
            test_client.retrieve_chunks(str(uuid.uuid4()), "search query")
        assert "sqlalchemy" not in str(exc.value)
        assert "Unable to complete query synthesis" in str(exc.value) or "server processing error" in str(exc.value)

        # Test retrieve_lexical_chunks
        with pytest.raises(ValueError) as exc:
            test_client.retrieve_lexical_chunks(str(uuid.uuid4()), "search query")
        assert "sqlalchemy" not in str(exc.value)

        # Test retrieve_hybrid_chunks
        with pytest.raises(ValueError) as exc:
            test_client.retrieve_hybrid_chunks(str(uuid.uuid4()), "search query")
        assert "sqlalchemy" not in str(exc.value)

        # Test rerank_chunks
        with pytest.raises(ValueError) as exc:
            test_client.rerank_chunks(str(uuid.uuid4()), "search query")
        assert "sqlalchemy" not in str(exc.value)

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
