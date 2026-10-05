"""
Unit and Integration Tests for Source Viewer Feature.

Verifies:
1. Document file streaming endpoint (/api/v1/documents/{document_id}/file)
2. Knowledge base file endpoint (/api/v1/knowledge-bases/{kb_id}/documents/{document_id}/file)
3. Document lookup and stream by filename (/api/v1/documents/by-name)
4. Query parameter token authentication (?token=...)
5. Strict tenant isolation and student publication access rules (404 for inactive)
6. Unauthenticated rejections (401)
7. Citation link transformation helper (format_citation_links)
"""

import io
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.app.core.security import SESSION_COOKIE_NAME
from backend.app.main import app
from backend.tests.fixtures_documents import create_sample_pdf_bytes
from frontend.client.models import CitationDTO
from frontend.pages.chat_page import format_citation_links
from scripts.bootstrap_admin import bootstrap_admin


@pytest.fixture(autouse=True)
def setup_admin_and_client():
    bootstrap_admin("admin@university.edu", "AdminPass123!", "System Administrator")


class TestSourceViewerFeature:
    """Test suite for Source Viewer endpoints and UI citation integration."""

    def test_document_file_streaming_and_auth_modes(self) -> None:
        client = TestClient(app)

        # 1. Login as Admin
        login_resp = client.post(
            "/api/v1/auth/login/admin",
            json={"email": "admin@university.edu", "password": "AdminPass123!"},
        )
        assert login_resp.status_code == 200
        admin_token = login_resp.cookies.get(SESSION_COOKIE_NAME)
        assert admin_token is not None

        # 2. Create course
        kb_resp = client.post(
            "/api/v1/knowledge-bases",
            json={
                "name": f"Source Viewer Course {uuid.uuid4().hex[:6]}",
                "description": "Testing PDF viewer",
            },
        )
        assert kb_resp.status_code == 201
        kb_id = kb_resp.json()["id"]

        # 3. Upload PDF
        pdf_bytes = create_sample_pdf_bytes()
        upload_resp = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/documents",
            files={"file": ("KSU-Act-English.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        assert upload_resp.status_code == 201
        doc_id = upload_resp.json()["id"]

        # 4. Stream via /api/v1/documents/{doc_id}/file with cookie
        file_resp = client.get(f"/api/v1/documents/{doc_id}/file")
        assert file_resp.status_code == 200
        assert file_resp.headers["content-type"] == "application/pdf"
        assert "inline" in file_resp.headers.get("content-disposition", "")
        assert file_resp.content == pdf_bytes

        # 5. Stream via /api/v1/knowledge-bases/{kb_id}/documents/{doc_id}/file
        kb_file_resp = client.get(f"/api/v1/knowledge-bases/{kb_id}/documents/{doc_id}/file")
        assert kb_file_resp.status_code == 200
        assert kb_file_resp.content == pdf_bytes

        # 6. Stream via /api/v1/documents/by-name?name=KSU-Act-English.pdf
        name_file_resp = client.get(
            f"/api/v1/documents/by-name?name=KSU-Act-English.pdf&kb_id={kb_id}"
        )
        assert name_file_resp.status_code == 200
        assert name_file_resp.content == pdf_bytes

        # 7. Query parameter token authentication is STRICTLY FORBIDDEN and rejected
        client_no_cookie = TestClient(app)
        token_resp = client_no_cookie.get(f"/api/v1/documents/{doc_id}/file?token={admin_token}")
        assert token_resp.status_code == 401, "Query parameter tokens must be rejected with 401 Unauthorized"

        # 8. Unauthenticated request without token or cookies -> 401
        unauth_resp = client_no_cookie.get(f"/api/v1/documents/{doc_id}/file")
        assert unauth_resp.status_code == 401

    def test_student_isolation_and_publication_rules(self) -> None:
        admin_client = TestClient(app)
        admin_client.post(
            "/api/v1/auth/login/admin",
            json={"email": "admin@university.edu", "password": "AdminPass123!"},
        )

        # Create course and upload document (document starts in inactive state)
        kb_resp = admin_client.post(
            "/api/v1/knowledge-bases",
            json={
                "name": f"Student Course {uuid.uuid4().hex[:6]}",
                "description": "Student Access Test",
            },
        )
        kb_id = kb_resp.json()["id"]

        pdf_bytes = create_sample_pdf_bytes()
        doc_resp = admin_client.post(
            f"/api/v1/knowledge-bases/{kb_id}/documents",
            files={"file": ("Student-Handbook.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        doc_id = doc_resp.json()["id"]

        # Register and login a student
        student_client = TestClient(app)
        student_email = f"student_{uuid.uuid4().hex[:6]}@university.edu"
        reg_resp = student_client.post(
            "/api/v1/auth/register",
            json={
                "email": student_email,
                "password": "StudentPass123!",
                "full_name": "Test Student",
            },
        )
        assert reg_resp.status_code == 201
        student_id = reg_resp.json()["id"]

        # Admin enrolls student as member of this course
        mem_resp = admin_client.post(
            f"/api/v1/knowledge-bases/{kb_id}/members",
            json={"user_id": student_id},
        )
        assert mem_resp.status_code == 201

        # Student login
        student_client.post(
            "/api/v1/auth/login/student",
            json={"email": student_email, "password": "StudentPass123!"},
        )

        # Set document to inactive state to verify isolation
        from backend.app.db.session import get_db_session
        from backend.app.models.document import Document

        with get_db_session() as db:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            doc.is_active = False
            db.commit()

        # Inactive document: Student MUST receive 404 (not leak existence)
        inactive_resp = student_client.get(f"/api/v1/documents/{doc_id}/file")
        assert inactive_resp.status_code == 404

        # Admin activates document
        with get_db_session() as db:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            doc.is_active = True
            db.commit()

        # Now active: Student receives 200 and can stream PDF
        active_resp = student_client.get(f"/api/v1/documents/{doc_id}/file")
        assert active_resp.status_code == 200
        assert active_resp.content == pdf_bytes

    def test_citation_link_formatter(self) -> None:
        citations = [
            CitationDTO(
                document_name="KSU-Act-English.pdf",
                page_number=5,
                chunk_id="chunk-1",
                relevance_score=0.92,
                snippet="The University was established under Section 3.",
                document_id="doc-uuid-1",
                knowledge_base_id="kb-uuid-1",
                course_name="BCA Regulations",
            ),
            CitationDTO(
                document_name="Syllabus-2026.pdf",
                page_number=12,
                chunk_id="chunk-2",
                relevance_score=0.88,
                snippet="Examination grading criteria requires 75% attendance.",
                document_id="doc-uuid-2",
                knowledge_base_id="kb-uuid-1",
                course_name="BCA Regulations",
            ),
        ]

        text = "According to the university act [1], the examination syllabus [2] applies. See [external link](https://ksu.edu)."
        formatted = format_citation_links(text, citations)

        # Asserts interactive citation pills with data-citation-index
        assert 'data-citation-index="1"' in formatted
        assert 'data-citation-index="2"' in formatted
        assert "KSU-Act-English.pdf" in formatted
        assert "Syllabus-2026.pdf" in formatted
        # Standard markdown links should NOT be corrupted
        assert "[external link](https://ksu.edu)" in formatted
