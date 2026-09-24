"""
Step 21E integration coverage for real authorization, chat scopes, and document isolation.

These tests intentionally exercise HTTP contracts rather than only service methods.
They cover the regressions that can be hidden by passing direct API-client tests.
"""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.permissions import Permission
from backend.app.core.security import get_password_hash
from backend.app.models.document import Document, DocumentStatus, IndexingStatus
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseMember
from backend.app.models.user import AdminRole, User, UserRole


@pytest.fixture(autouse=True)
def clean_workflow_data(db_engine) -> Generator[None, None, None]:
    """Keep the workflow integration suite isolated from prior test records."""
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


def _user(
    db: Session,
    *,
    email: str,
    role: UserRole,
    admin_role: AdminRole | None = None,
    permissions: list[str] | None = None,
) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=get_password_hash("TestPass123!"),
        full_name=email.split("@", 1)[0],
        role=role,
        admin_role=admin_role,
        permissions=permissions or [],
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _course(db: Session, owner: User, name: str) -> KnowledgeBase:
    kb = KnowledgeBase(id=uuid.uuid4(), name=name, created_by_id=owner.id)
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


def _login(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "TestPass123!"},
    )
    assert response.status_code == 200, response.text


def test_course_visibility_is_canonical_and_role_scoped(
    api_client: TestClient, db_session: Session
) -> None:
    main = _user(
        db_session,
        email="main21e@univ.edu",
        role=UserRole.ADMIN,
        admin_role=AdminRole.MAIN_ADMIN,
    )
    faculty = _user(
        db_session,
        email="faculty21e@univ.edu",
        role=UserRole.ADMIN,
        admin_role=AdminRole.FACULTY_ADMIN,
        permissions=[Permission.COURSE_VIEW.value, Permission.ADMIN_CHAT.value],
    )
    student = _user(
        db_session,
        email="student21e@univ.edu",
        role=UserRole.STUDENT,
    )

    main_course = _course(db_session, main, "BCA")
    faculty_course = _course(db_session, faculty, "Faculty Course")
    foreign_course = _course(db_session, main, "Private Main Course")

    db_session.add(
        KnowledgeBaseMember(
            id=uuid.uuid4(),
            knowledge_base_id=main_course.id,
            user_id=student.id,
        )
    )
    db_session.add(
        KnowledgeBaseMember(
            id=uuid.uuid4(),
            knowledge_base_id=faculty_course.id,
            user_id=faculty.id,
        )
    )
    db_session.commit()

    _login(api_client, "main21e@univ.edu")
    main_courses = api_client.get("/api/v1/knowledge-bases")
    assert main_courses.status_code == 200
    assert {item["name"] for item in main_courses.json()} == {
        "BCA",
        "Faculty Course",
        "Private Main Course",
    }

    _login(api_client, "faculty21e@univ.edu")
    faculty_courses = api_client.get("/api/v1/knowledge-bases")
    assert faculty_courses.status_code == 200
    assert {item["name"] for item in faculty_courses.json()} == {"Faculty Course"}

    # ADMIN_CHAT has its own course-scope endpoint, so a faculty admin with
    # ADMIN_CHAT can use Admin Chat without receiving COURSE management access.
    faculty_chat_courses = api_client.get("/api/v1/knowledge-bases/chat-scopes")
    assert faculty_chat_courses.status_code == 200
    assert {item["name"] for item in faculty_chat_courses.json()} == {"Faculty Course"}

    _login(api_client, "student21e@univ.edu")
    student_courses = api_client.get("/api/v1/knowledge-bases")
    assert student_courses.status_code == 200
    assert {item["name"] for item in student_courses.json()} == {"BCA"}

    # The foreign course is never exposed to the student.
    assert str(foreign_course.id) not in {item["id"] for item in student_courses.json()}


def test_admin_chat_permission_is_server_authoritative(
    api_client: TestClient, db_session: Session
) -> None:
    faculty = _user(
        db_session,
        email="faculty-no-chat21e@univ.edu",
        role=UserRole.ADMIN,
        admin_role=AdminRole.FACULTY_ADMIN,
        permissions=[Permission.DOCUMENT_VIEW.value],
    )
    student = _user(
        db_session,
        email="student-no-admin-chat21e@univ.edu",
        role=UserRole.STUDENT,
    )
    main = _user(
        db_session,
        email="main-chat21e@univ.edu",
        role=UserRole.ADMIN,
        admin_role=AdminRole.MAIN_ADMIN,
    )

    _login(api_client, faculty.email)
    denied = api_client.post(
        "/api/v1/chat/query",
        json={"question": "test", "scope": "ALL_COURSES"},
    )
    assert denied.status_code == 403
    assert "ADMIN_CHAT" in denied.json()["detail"]

    _login(api_client, student.email)
    student_response = api_client.post(
        "/api/v1/chat/query",
        json={"question": "test", "scope": "ALL_COURSES"},
    )
    # Student access is the normal chat path; because this test student has no
    # membership, the endpoint returns a safe no-material response.
    assert student_response.status_code == 200
    assert student_response.json()["is_empty_context"] is True

    _login(api_client, main.email)
    main_response = api_client.post(
        "/api/v1/chat/query",
        json={"question": "test", "scope": "ALL_COURSES"},
    )
    # Main Admin is authorized for Admin Chat; with no authorized courses the
    # endpoint returns its deterministic safe no-material response.
    assert main_response.status_code == 200


def test_document_scope_rejects_course_document_mismatch(
    api_client: TestClient, db_session: Session
) -> None:
    main = _user(
        db_session,
        email="main-doc21e@univ.edu",
        role=UserRole.ADMIN,
        admin_role=AdminRole.MAIN_ADMIN,
    )
    kb_a = _course(db_session, main, "Course A")
    kb_b = _course(db_session, main, "Course B")
    doc = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb_a.id,
        original_filename="KSU-Act-English.pdf",
        storage_key=f"uploads/{kb_a.id}/document.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size_bytes=100,
        content_hash=f"hash-{uuid.uuid4()}",
        status=DocumentStatus.COMPLETED,
        indexing_status=IndexingStatus.COMPLETED,
        is_active=True,
    )
    db_session.add(doc)
    db_session.commit()

    _login(api_client, main.email)
    response = api_client.post(
        "/api/v1/chat/query",
        json={
            "question": "What is the territorial jurisdiction of the University?",
            "scope": "DOCUMENT",
            "knowledge_base_id": str(kb_b.id),
            "document_id": str(doc.id),
        },
    )
    assert response.status_code == 404


def test_chat_scope_contract_rejects_invalid_combinations(
    api_client: TestClient, db_session: Session
) -> None:
    main = _user(
        db_session,
        email="main-scope21e@univ.edu",
        role=UserRole.ADMIN,
        admin_role=AdminRole.MAIN_ADMIN,
    )
    kb = _course(db_session, main, "BCA")
    _login(api_client, main.email)

    invalid_scope = api_client.post(
        "/api/v1/chat/query",
        json={"question": "test", "scope": "UNKNOWN"},
    )
    assert invalid_scope.status_code == 400

    course_without_id = api_client.post(
        "/api/v1/chat/query",
        json={"question": "test", "scope": "COURSE"},
    )
    assert course_without_id.status_code == 400

    all_with_course = api_client.post(
        "/api/v1/chat/query",
        json={
            "question": "test",
            "scope": "ALL_COURSES",
            "knowledge_base_id": str(kb.id),
        },
    )
    assert all_with_course.status_code == 400

    document_without_id = api_client.post(
        "/api/v1/chat/query",
        json={
            "question": "test",
            "scope": "DOCUMENT",
            "knowledge_base_id": str(kb.id),
        },
    )
    assert document_without_id.status_code == 400


def test_student_document_listing_exposes_only_published_material(
    api_client: TestClient, db_session: Session
) -> None:
    main = _user(
        db_session,
        email="main-pub21e@univ.edu",
        role=UserRole.ADMIN,
        admin_role=AdminRole.MAIN_ADMIN,
    )
    student = _user(
        db_session,
        email="student-pub21e@univ.edu",
        role=UserRole.STUDENT,
    )
    kb = _course(db_session, main, "BCA")
    db_session.add(
        KnowledgeBaseMember(
            id=uuid.uuid4(),
            knowledge_base_id=kb.id,
            user_id=student.id,
        )
    )
    active_doc = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb.id,
        original_filename="published.pdf",
        storage_key=f"uploads/{kb.id}/published.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size_bytes=10,
        content_hash=f"active-{uuid.uuid4()}",
        status=DocumentStatus.COMPLETED,
        indexing_status=IndexingStatus.COMPLETED,
        is_active=True,
    )
    inactive_doc = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb.id,
        original_filename="historical.pdf",
        storage_key=f"uploads/{kb.id}/historical.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size_bytes=10,
        content_hash=f"inactive-{uuid.uuid4()}",
        status=DocumentStatus.COMPLETED,
        indexing_status=IndexingStatus.COMPLETED,
        is_active=False,
    )
    db_session.add_all([active_doc, inactive_doc])
    db_session.commit()

    _login(api_client, student.email)
    response = api_client.get(f"/api/v1/knowledge-bases/{kb.id}/documents")
    assert response.status_code == 200
    assert [item["original_filename"] for item in response.json()] == ["published.pdf"]

    inactive_detail = api_client.get(f"/api/v1/knowledge-bases/{kb.id}/documents/{inactive_doc.id}")
    assert inactive_detail.status_code == 404
