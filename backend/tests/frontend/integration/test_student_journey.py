"""Integration test suite for the complete student journey.

Validates:
1. Student registration & login via student auth endpoint.
2. Authoritative student course catalog access:
   - Active, student-visible courses are accessible WITHOUT manual enrollment.
   - Inactive courses are strictly excluded (HTTP 404).
   - Restricted/private courses (is_student_visible=False) return 404 unless enrolled.
   - Restricted courses become accessible when explicit membership is granted.
3. Conversational chat query flow:
   - Default ALL_COURSES query succeeds without preselecting any course.
   - Specific course-scoped query succeeds.
   - Invalid scope combinations return HTTP 400.
4. Document viewing & source authorization:
   - Active documents in student-visible courses stream successfully.
   - Inactive documents return HTTP 404.
   - Documents in restricted courses return HTTP 404 for unassigned students.
"""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.security import get_password_hash
from backend.app.main import app
from backend.app.models.document import Document, DocumentStatus, IndexingStatus
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseMember
from backend.app.models.user import AdminRole, User, UserRole


def _create_sample_pdf_bytes() -> bytes:
    """Create minimal valid PDF byte payload."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R>>endobj\n"
        b"4 0 obj<</Length 44>>stream\n"
        b"BT /F1 12 Tf 72 712 Td (Academic Evidence) Tj ET\n"
        b"endstream\n"
        b"endobj\n"
        b"xref\n0 5\n0000000000 65535 f\n"
        b"0000000009 00000 n\n0000000052 00000 n\n"
        b"0000000108 00000 n\n0000000187 00000 n\n"
        b"trailer<</Size 5/Root 1 0 R>>\n"
        b"startxref\n279\n%%EOF\n"
    )


@pytest.fixture(autouse=True)
def clean_database(db_engine) -> Generator[None, None, None]:
    """Isolate student journey tests."""
    with db_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE indexing_jobs, document_chunks, documents, "
                "knowledge_base_members, knowledge_bases, user_sessions, users CASCADE;"
            )
        )
    yield
    with db_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE indexing_jobs, document_chunks, documents, "
                "knowledge_base_members, knowledge_bases, user_sessions, users CASCADE;"
            )
        )


def _create_admin(db: Session, email: str = "admin@univ.edu") -> User:
    admin = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=get_password_hash("AdminPass123!"),
        full_name="Admin Faculty",
        role=UserRole.ADMIN,
        admin_role=AdminRole.MAIN_ADMIN,
        permissions=[],
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def _create_course(
    db: Session,
    owner: User,
    name: str,
    *,
    is_active: bool = True,
    is_student_visible: bool = True,
) -> KnowledgeBase:
    kb = KnowledgeBase(
        id=uuid.uuid4(),
        name=name,
        description=f"Course: {name}",
        created_by_id=owner.id,
        is_active=is_active,
        is_student_visible=is_student_visible,
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


def _create_doc(
    db: Session,
    kb: KnowledgeBase,
    filename: str,
    *,
    doc_id: uuid.UUID | None = None,
    storage_key: str | None = None,
    is_active: bool = True,
) -> Document:
    doc = Document(
        id=doc_id or uuid.uuid4(),
        knowledge_base_id=kb.id,
        original_filename=filename,
        storage_key=storage_key or f"uploads/{kb.id}/{filename}",
        file_type="pdf",
        mime_type="application/pdf",
        file_size_bytes=len(_create_sample_pdf_bytes()),
        content_hash=f"hash-{uuid.uuid4()}",
        status=DocumentStatus.COMPLETED,
        indexing_status=IndexingStatus.COMPLETED,
        is_active=is_active,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


class TestStudentJourneyIntegration:
    """Full workflow tests covering student registration, catalog, chat, and sources."""

    def test_student_registration_and_login_lifecycle(self) -> None:
        client = TestClient(app)
        email = "student_journey@univ.edu"

        # 1. Register student
        reg_resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "StudentPass123!",
                "full_name": "Journey Student",
            },
        )
        assert reg_resp.status_code == 201
        assert reg_resp.json()["email"] == email
        assert reg_resp.json()["role"] == "STUDENT"

        # 2. Login via student portal
        login_resp = client.post(
            "/api/v1/auth/login/student",
            json={"email": email, "password": "StudentPass123!"},
        )
        assert login_resp.status_code == 200
        assert "session_id" in login_resp.cookies

        # 3. Check /auth/me
        me_resp = client.get("/api/v1/auth/me")
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == email
        assert me_resp.json()["role"] == "STUDENT"

    def test_authoritative_course_catalog_access_without_enrollment(
        self, db_session: Session
    ) -> None:
        """Active student-visible courses are accessible to students by default."""
        admin = _create_admin(db_session)
        pub_course_1 = _create_course(db_session, admin, "Intro to Python", is_active=True, is_student_visible=True)
        _create_course(db_session, admin, "Data Structures", is_active=True, is_student_visible=True)
        inactive_course = _create_course(db_session, admin, "Archived 1999", is_active=False, is_student_visible=True)
        private_course = _create_course(db_session, admin, "Faculty Research", is_active=True, is_student_visible=False)

        client = TestClient(app)
        email = "student_catalog@univ.edu"
        client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "StudentPass123!", "full_name": "Catalog Student"},
        )
        client.post(
            "/api/v1/auth/login/student",
            json={"email": email, "password": "StudentPass123!"},
        )

        # Student lists courses
        list_resp = client.get("/api/v1/knowledge-bases")
        assert list_resp.status_code == 200
        courses = list_resp.json()
        course_names = {c["name"] for c in courses}

        # Published active courses appear WITHOUT manual enrollment
        assert "Intro to Python" in course_names
        assert "Data Structures" in course_names

        # Inactive courses and private unassigned courses are NOT listed
        assert "Archived 1999" not in course_names
        assert "Faculty Research" not in course_names

        # Direct access to published course succeeds
        assert client.get(f"/api/v1/knowledge-bases/{pub_course_1.id}").status_code == 200

        # Direct access to inactive course returns 404
        assert client.get(f"/api/v1/knowledge-bases/{inactive_course.id}").status_code == 404

        # Direct access to private unassigned course returns 404 (does not leak existence)
        assert client.get(f"/api/v1/knowledge-bases/{private_course.id}").status_code == 404

    def test_restricted_course_accessible_with_explicit_membership(
        self, db_session: Session
    ) -> None:
        """Private courses become accessible if student is explicitly assigned as a member."""
        admin = _create_admin(db_session)
        restricted = _create_course(
            db_session, admin, "Special Honors Seminar", is_active=True, is_student_visible=False
        )

        client = TestClient(app)
        email = "honors_student@univ.edu"
        reg = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "StudentPass123!", "full_name": "Honors Student"},
        )
        student_id = uuid.UUID(reg.json()["id"])
        client.post(
            "/api/v1/auth/login/student",
            json={"email": email, "password": "StudentPass123!"},
        )

        # Before membership: 404
        assert client.get(f"/api/v1/knowledge-bases/{restricted.id}").status_code == 404

        # Grant membership
        db_session.add(
            KnowledgeBaseMember(
                id=uuid.uuid4(),
                knowledge_base_id=restricted.id,
                user_id=student_id,
            )
        )
        db_session.commit()

        # After membership: 200
        assert client.get(f"/api/v1/knowledge-bases/{restricted.id}").status_code == 200

    def test_student_chat_default_scope_and_scoping_rules(
        self, db_session: Session
    ) -> None:
        """Student can query with ALL_COURSES default scope or specific course."""
        admin = _create_admin(db_session)
        course = _create_course(db_session, admin, "Algorithms", is_active=True, is_student_visible=True)

        client = TestClient(app)
        email = "chat_student@univ.edu"
        client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "StudentPass123!", "full_name": "Chat Student"},
        )
        client.post(
            "/api/v1/auth/login/student",
            json={"email": email, "password": "StudentPass123!"},
        )

        # 1. Default ALL_COURSES query succeeds (returns 200 empty context when no docs indexed)
        all_resp = client.post(
            "/api/v1/chat/query",
            json={"question": "What is asymptotic notation?", "scope": "ALL_COURSES"},
        )
        assert all_resp.status_code == 200
        assert all_resp.json()["is_empty_context"] is True

        # 2. Scoped COURSE query succeeds
        course_resp = client.post(
            "/api/v1/chat/query",
            json={
                "question": "What is asymptotic notation?",
                "scope": "COURSE",
                "knowledge_base_id": str(course.id),
            },
        )
        assert course_resp.status_code == 200

        # 3. Invalid scope returns 400
        bad_scope = client.post(
            "/api/v1/chat/query",
            json={"question": "Test", "scope": "INVALID_SCOPE"},
        )
        assert bad_scope.status_code == 400

    def test_student_source_document_viewing_and_isolation(
        self, db_session: Session
    ) -> None:
        """Student can view published document bytes; inactive or private docs are blocked."""
        from backend.app.services.storage import storage_service

        admin = _create_admin(db_session)
        pub_course = _create_course(db_session, admin, "Biology 101", is_active=True, is_student_visible=True)
        priv_course = _create_course(db_session, admin, "Secret Biology", is_active=True, is_student_visible=False)

        pdf_bytes = _create_sample_pdf_bytes()

        pub_doc_id = uuid.uuid4()
        inact_doc_id = uuid.uuid4()
        priv_doc_id = uuid.uuid4()

        storage_key_pub = storage_service.save_file(
            knowledge_base_id=pub_course.id,
            document_id=pub_doc_id,
            extension=".pdf",
            content=pdf_bytes,
        )
        storage_key_inact = storage_service.save_file(
            knowledge_base_id=pub_course.id,
            document_id=inact_doc_id,
            extension=".pdf",
            content=pdf_bytes,
        )
        storage_key_priv = storage_service.save_file(
            knowledge_base_id=priv_course.id,
            document_id=priv_doc_id,
            extension=".pdf",
            content=pdf_bytes,
        )

        pub_doc = _create_doc(
            db_session, pub_course, "bio.pdf", doc_id=pub_doc_id, storage_key=storage_key_pub, is_active=True
        )
        inact_doc = _create_doc(
            db_session, pub_course, "old_bio.pdf", doc_id=inact_doc_id, storage_key=storage_key_inact, is_active=False
        )
        priv_doc = _create_doc(
            db_session, priv_course, "secret.pdf", doc_id=priv_doc_id, storage_key=storage_key_priv, is_active=True
        )

        client = TestClient(app)
        email = "source_student@univ.edu"
        client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "StudentPass123!", "full_name": "Source Student"},
        )
        client.post(
            "/api/v1/auth/login/student",
            json={"email": email, "password": "StudentPass123!"},
        )

        # 1. Published active document in student-visible course streams successfully
        resp = client.get(f"/api/v1/documents/{pub_doc.id}/file")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content == pdf_bytes

        # 2. Inactive document in the same course returns 404
        assert client.get(f"/api/v1/documents/{inact_doc.id}/file").status_code == 404

        # 3. Document in private course returns 404
        assert client.get(f"/api/v1/documents/{priv_doc.id}/file").status_code == 404
