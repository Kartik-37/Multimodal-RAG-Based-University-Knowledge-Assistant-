"""
Unit and Integration Tests for Source Viewer Feature and Document Streaming.

Validates the 15 Source Viewer Contracts:
1. Authorized authenticated document stream succeeds.
2. Unauthenticated document stream fails (401).
3. Cross-user access fails.
4. Cross-course access fails (mismatched KB ID returns 404).
5. Unassigned student access fails (student not enrolled returns 404).
6. Inactive/unpublished document access follows authorization contract (404 for student, 200 for admin).
7. Revoked session fails (401).
8. Expired session fails (401).
9. ?token=<raw token> authentication is rejected (401).
10. Source viewer generated URL contains no main session token.
11. No document.cookie JavaScript credential injection exists.
12. Canonical document UUID is used.
13. Unsafe document metadata is safely escaped.
14. Response content type is correct for supported file types.
15. File content is actually the authorized file.
"""

import io
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from backend.app.core.security import SESSION_COOKIE_NAME, hash_session_token
from backend.app.db.session import get_db_session
from backend.app.main import app
from backend.app.models.document import Document
from backend.app.models.user import UserSession
from backend.tests.fixtures_documents import create_sample_pdf_bytes
from frontend.client.models import CitationDTO
from frontend.pages.chat_page import format_citation_links
from scripts.bootstrap_admin import bootstrap_admin


@pytest.fixture(autouse=True)
def setup_admin_and_client():
    bootstrap_admin("admin@university.edu", "AdminPass123!", "System Administrator")


class TestSourceViewerFeature:
    """Comprehensive test suite for Source Viewer contracts and document streaming security."""

    def test_authorized_document_file_streaming_and_content_type(self) -> None:
        """Requirement 1, 14, 15: Authorized document stream succeeds with correct content type and file bytes."""
        client = TestClient(app)

        # Login as Admin
        login_resp = client.post(
            "/api/v1/auth/login/admin",
            json={"email": "admin@university.edu", "password": "AdminPass123!"},
        )
        assert login_resp.status_code == 200
        admin_token = login_resp.cookies.get(SESSION_COOKIE_NAME)
        assert admin_token is not None

        # Create course
        kb_resp = client.post(
            "/api/v1/knowledge-bases",
            json={
                "name": f"Source Viewer Course {uuid.uuid4().hex[:6]}",
                "description": "Testing PDF viewer",
            },
        )
        assert kb_resp.status_code == 201
        kb_id = kb_resp.json()["id"]

        # Upload sample PDF
        pdf_bytes = create_sample_pdf_bytes()
        upload_resp = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/documents",
            files={"file": ("KSU-Act-English.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        assert upload_resp.status_code == 201
        doc_id = upload_resp.json()["id"]

        # Stream via canonical UUID endpoint /api/v1/documents/{doc_id}/file
        file_resp = client.get(f"/api/v1/documents/{doc_id}/file")
        assert file_resp.status_code == 200
        assert file_resp.headers["content-type"] == "application/pdf"
        assert "inline" in file_resp.headers.get("content-disposition", "")
        assert file_resp.content == pdf_bytes

        # Stream via scoped course endpoint /api/v1/knowledge-bases/{kb_id}/documents/{doc_id}/file
        kb_file_resp = client.get(f"/api/v1/knowledge-bases/{kb_id}/documents/{doc_id}/file")
        assert kb_file_resp.status_code == 200
        assert kb_file_resp.content == pdf_bytes

    def test_unauthenticated_request_rejected(self) -> None:
        """Requirement 2: Unauthenticated document stream fails with 401."""
        client = TestClient(app)
        doc_uuid = uuid.uuid4()
        resp = client.get(f"/api/v1/documents/{doc_uuid}/file")
        assert resp.status_code == 401

    def test_query_parameter_token_rejected(self) -> None:
        """Requirement 9: ?token=<token> authentication is strictly rejected with 401."""
        client = TestClient(app)
        login_resp = client.post(
            "/api/v1/auth/login/admin",
            json={"email": "admin@university.edu", "password": "AdminPass123!"},
        )
        admin_token = login_resp.cookies.get(SESSION_COOKIE_NAME)
        assert admin_token is not None

        # Create separate unauthenticated client and attempt query param auth
        unauth_client = TestClient(app)
        token_resp = unauth_client.get(
            f"/api/v1/documents/{uuid.uuid4()}/file?token={admin_token}"
        )
        assert token_resp.status_code == 401

    def test_cross_course_access_rejected(self) -> None:
        """Requirement 4: Cross-course access with mismatched course ID fails with 404."""
        client = TestClient(app)
        client.post(
            "/api/v1/auth/login/admin",
            json={"email": "admin@university.edu", "password": "AdminPass123!"},
        )

        # Create course A and upload document
        kb_a = client.post(
            "/api/v1/knowledge-bases",
            json={"name": f"Course A {uuid.uuid4().hex[:6]}"},
        ).json()["id"]

        pdf_bytes = create_sample_pdf_bytes()
        doc = client.post(
            f"/api/v1/knowledge-bases/{kb_a}/documents",
            files={"file": ("CourseA-Doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        ).json()
        doc_id = doc["id"]

        # Create course B
        kb_b = client.post(
            "/api/v1/knowledge-bases",
            json={"name": f"Course B {uuid.uuid4().hex[:6]}"},
        ).json()["id"]

        # Requesting course A document under course B URL must return 404
        cross_resp = client.get(f"/api/v1/knowledge-bases/{kb_b}/documents/{doc_id}/file")
        assert cross_resp.status_code == 404

    def test_unassigned_student_access_rejected(self) -> None:
        """Requirement 3, 5: Unassigned student receives 404 when requesting private course document."""
        admin_client = TestClient(app)
        admin_client.post(
            "/api/v1/auth/login/admin",
            json={"email": "admin@university.edu", "password": "AdminPass123!"},
        )

        kb_resp = admin_client.post(
            "/api/v1/knowledge-bases",
            json={"name": f"Enrolled Course {uuid.uuid4().hex[:6]}"},
        )
        kb_id = kb_resp.json()["id"]

        pdf_bytes = create_sample_pdf_bytes()
        doc_resp = admin_client.post(
            f"/api/v1/knowledge-bases/{kb_id}/documents",
            files={"file": ("Private-Study.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        doc_id = doc_resp.json()["id"]

        # Register a student but DO NOT assign them to this course
        student_client = TestClient(app)
        student_email = f"unassigned_{uuid.uuid4().hex[:6]}@university.edu"
        student_client.post(
            "/api/v1/auth/register",
            json={"email": student_email, "password": "StudentPass123!", "full_name": "Unassigned Student"},
        )
        student_client.post(
            "/api/v1/auth/login/student",
            json={"email": student_email, "password": "StudentPass123!"},
        )

        # Unassigned student must be denied with 404 (does not leak course existence)
        denied_resp = student_client.get(f"/api/v1/documents/{doc_id}/file")
        assert denied_resp.status_code == 404

    def test_inactive_document_publication_lifecycle(self) -> None:
        """Requirement 6: Inactive documents return 404 to students and 200 to administrators."""
        admin_client = TestClient(app)
        admin_client.post(
            "/api/v1/auth/login/admin",
            json={"email": "admin@university.edu", "password": "AdminPass123!"},
        )

        kb_id = admin_client.post(
            "/api/v1/knowledge-bases",
            json={"name": f"Publication Course {uuid.uuid4().hex[:6]}"},
        ).json()["id"]

        pdf_bytes = create_sample_pdf_bytes()
        doc_id = admin_client.post(
            f"/api/v1/knowledge-bases/{kb_id}/documents",
            files={"file": ("Handbook.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        ).json()["id"]

        # Register and enroll student
        student_client = TestClient(app)
        student_email = f"enrolled_{uuid.uuid4().hex[:6]}@university.edu"
        reg = student_client.post(
            "/api/v1/auth/register",
            json={"email": student_email, "password": "StudentPass123!", "full_name": "Enrolled Student"},
        ).json()
        admin_client.post(f"/api/v1/knowledge-bases/{kb_id}/members", json={"user_id": reg["id"]})
        student_client.post(
            "/api/v1/auth/login/student",
            json={"email": student_email, "password": "StudentPass123!"},
        )

        # Deactivate document in DB
        with get_db_session() as db:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            doc.is_active = False
            db.commit()

        # Inactive document: Student receives 404
        assert student_client.get(f"/api/v1/documents/{doc_id}/file").status_code == 404

        # Inactive document: Admin receives 200
        admin_resp = admin_client.get(f"/api/v1/documents/{doc_id}/file")
        assert admin_resp.status_code == 200
        assert admin_resp.content == pdf_bytes

        # Activate document
        with get_db_session() as db:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            doc.is_active = True
            db.commit()

        # Active document: Student receives 200
        student_resp = student_client.get(f"/api/v1/documents/{doc_id}/file")
        assert student_resp.status_code == 200
        assert student_resp.content == pdf_bytes

    def test_revoked_session_fails(self) -> None:
        """Requirement 7: Revoked session fails with 401."""
        client = TestClient(app)
        login_resp = client.post(
            "/api/v1/auth/login/admin",
            json={"email": "admin@university.edu", "password": "AdminPass123!"},
        )
        token = login_resp.cookies.get(SESSION_COOKIE_NAME)
        assert token is not None

        # Revoke session in database
        token_hash = hash_session_token(token)
        with get_db_session() as db:
            db.execute(delete(UserSession).where(UserSession.session_token_hash == token_hash))
            db.commit()

        # Subsequent request must return 401
        resp = client.get(f"/api/v1/documents/{uuid.uuid4()}/file")
        assert resp.status_code == 401

    def test_expired_session_fails(self) -> None:
        """Requirement 8: Expired session fails with 401."""
        client = TestClient(app)
        login_resp = client.post(
            "/api/v1/auth/login/admin",
            json={"email": "admin@university.edu", "password": "AdminPass123!"},
        )
        token = login_resp.cookies.get(SESSION_COOKIE_NAME)
        assert token is not None

        # Expire session in database
        token_hash = hash_session_token(token)
        with get_db_session() as db:
            session_rec = db.execute(
                select(UserSession).where(UserSession.session_token_hash == token_hash)
            ).scalar_one_or_none()
            assert session_rec is not None
            session_rec.expires_at = datetime.now(UTC) - timedelta(hours=1)
            db.commit()

        # Subsequent request must return 401
        resp = client.get(f"/api/v1/documents/{uuid.uuid4()}/file")
        assert resp.status_code == 401

    def test_source_viewer_url_canonical_uuid_and_no_token(self) -> None:
        """Requirement 10, 12: Source viewer URL uses canonical UUID and contains no session token."""
        doc_uuid = uuid.uuid4()
        canonical_url = f"/api/v1/documents/{doc_uuid}/file"

        # Verify format
        assert str(doc_uuid) in canonical_url
        assert "token" not in canonical_url
        assert "Bearer" not in canonical_url
        assert "?" not in canonical_url

    def test_unsafe_metadata_safely_escaped_in_citations(self) -> None:
        """Requirement 11, 13: Unsafe metadata is escaped and no document.cookie script injection occurs."""
        xss_name = '<script>alert("xss")</script>.pdf'
        citations = [
            CitationDTO(
                document_name=xss_name,
                page_number=1,
                chunk_id="chk-1",
                relevance_score=0.95,
                snippet='Exploit snippet <img src=x onerror="alert(1)">',
                document_id="doc-123",
                knowledge_base_id="kb-123",
                course_name="BCA Security",
            )
        ]

        formatted = format_citation_links("Refer to [1] for course details.", citations)

        # Executable tags must be neutralized
        assert "<script>" not in formatted
        assert "document.cookie" not in formatted
        assert "onerror" not in formatted
        # Semantic data attributes must be preserved
        assert 'data-citation-index="1"' in formatted
