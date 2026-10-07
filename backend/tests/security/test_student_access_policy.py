"""
Student Course Access Policy Security Tests (Stage 2).

Verifies the authoritative student access model:
- Students can access all ACTIVE courses marked as STUDENT_VISIBLE without mandatory membership.
- Inactive courses are strictly excluded.
- Non-student-visible (admin-only/restricted) courses are strictly hidden and return 404.
- Direct queries, ALL_COURSES global queries, and document streaming endpoints strictly enforce
  server-side authorization.

Covers:
- CASE A: Student sees active student-visible Course A.
- CASE B: Student sees active student-visible Course B.
- CASE C: Inactive course is NOT visible.
- CASE D: Non-student-visible course is NOT visible.
- CASE E: Admin-only/restricted course is NOT visible.
- CASE F: ALL_COURSES chat searches only authorized student-visible courses.
- CASE G: Student cannot query an unauthorized/restricted knowledge base directly.
- CASE H: Student cannot stream an unauthorized document.
- CASE I: Empty available course catalog produces proper empty state.
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.security import get_password_hash
from backend.app.models.document import Document, DocumentStatus, IndexingStatus
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseMember
from backend.app.models.user import User, UserRole


@pytest.fixture(autouse=True)
def clean_security_db(db_engine) -> Generator[None, None, None]:
    """Clean tables before each test function."""
    with db_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE knowledge_base_members, document_chunks, documents, "
                "knowledge_bases, user_sessions, users CASCADE;"
            )
        )
    yield


def _create_user(db: Session, email: str, role: UserRole) -> User:
    user = User(
        email=email,
        password_hash=get_password_hash("StudentPass123!"),
        full_name="Test User",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_course(
    db: Session,
    admin: User,
    name: str,
    is_active: bool = True,
    is_student_visible: bool = True,
) -> KnowledgeBase:
    kb = KnowledgeBase(
        name=name,
        description=f"Description for {name}",
        created_by_id=admin.id,
        is_active=is_active,
        is_student_visible=is_student_visible,
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


def _login_student(api_client: TestClient, email: str = "student@university.edu") -> None:
    api_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StudentPass123!"},
    )


# ==============================================================================
# CASE A & CASE B: Student sees active student-visible courses when enrolled
# ==============================================================================
def test_case_a_and_b_student_sees_active_student_visible_courses(
    api_client: TestClient, db_session: Session
) -> None:
    admin = _create_user(db_session, "admin@university.edu", UserRole.ADMIN)
    student = _create_user(db_session, "student@university.edu", UserRole.STUDENT)

    course_a = _create_course(db_session, admin, "Course A: Data Structures", is_active=True, is_student_visible=True)
    course_b = _create_course(db_session, admin, "Course B: Operating Systems", is_active=True, is_student_visible=True)
    db_session.add(KnowledgeBaseMember(knowledge_base_id=course_a.id, user_id=student.id))
    db_session.add(KnowledgeBaseMember(knowledge_base_id=course_b.id, user_id=student.id))
    db_session.commit()

    _login_student(api_client)

    resp = api_client.get("/api/v1/knowledge-bases")
    assert resp.status_code == 200
    ids = {item["id"] for item in resp.json()}
    assert str(course_a.id) in ids
    assert str(course_b.id) in ids


# ==============================================================================
# CASE C: Inactive course is NOT visible
# ==============================================================================
def test_case_c_inactive_course_is_not_visible(
    api_client: TestClient, db_session: Session
) -> None:
    admin = _create_user(db_session, "admin@university.edu", UserRole.ADMIN)
    student = _create_user(db_session, "student@university.edu", UserRole.STUDENT)

    active_course = _create_course(db_session, admin, "Active Course", is_active=True, is_student_visible=True)
    inactive_course = _create_course(db_session, admin, "Inactive Archived Course", is_active=False, is_student_visible=True)
    db_session.add(KnowledgeBaseMember(knowledge_base_id=active_course.id, user_id=student.id))
    db_session.add(KnowledgeBaseMember(knowledge_base_id=inactive_course.id, user_id=student.id))
    db_session.commit()

    _login_student(api_client)

    resp = api_client.get("/api/v1/knowledge-bases")
    assert resp.status_code == 200
    ids = {item["id"] for item in resp.json()}
    assert str(active_course.id) in ids
    assert str(inactive_course.id) not in ids

    # Direct access to inactive course returns 404
    get_resp = api_client.get(f"/api/v1/knowledge-bases/{inactive_course.id}")
    assert get_resp.status_code == 404


# ==============================================================================
# CASE D: Non-student-visible course is NOT visible
# ==============================================================================
def test_case_d_non_student_visible_course_is_not_visible(
    api_client: TestClient, db_session: Session
) -> None:
    admin = _create_user(db_session, "admin@university.edu", UserRole.ADMIN)
    student = _create_user(db_session, "student@university.edu", UserRole.STUDENT)

    visible_course = _create_course(db_session, admin, "Visible Course", is_active=True, is_student_visible=True)
    hidden_course = _create_course(db_session, admin, "Internal Staff Notes", is_active=True, is_student_visible=False)
    db_session.add(KnowledgeBaseMember(knowledge_base_id=visible_course.id, user_id=student.id))
    db_session.add(KnowledgeBaseMember(knowledge_base_id=hidden_course.id, user_id=student.id))
    db_session.commit()

    _login_student(api_client)

    resp = api_client.get("/api/v1/knowledge-bases")
    assert resp.status_code == 200
    ids = {item["id"] for item in resp.json()}
    assert str(visible_course.id) in ids
    assert str(hidden_course.id) not in ids

    # Direct access returns 404
    get_resp = api_client.get(f"/api/v1/knowledge-bases/{hidden_course.id}")
    assert get_resp.status_code == 404


# ==============================================================================
# CASE E: Admin-only/restricted course is NOT visible
# ==============================================================================
def test_case_e_admin_only_restricted_course_is_not_visible(
    api_client: TestClient, db_session: Session
) -> None:
    admin = _create_user(db_session, "admin@university.edu", UserRole.ADMIN)
    _create_user(db_session, "student@university.edu", UserRole.STUDENT)

    restricted_course = _create_course(db_session, admin, "Restricted Faculty Grading Rubric", is_active=True, is_student_visible=False)

    _login_student(api_client)

    # Student cannot see it
    resp = api_client.get("/api/v1/knowledge-bases")
    assert resp.status_code == 200
    ids = {item["id"] for item in resp.json()}
    assert str(restricted_course.id) not in ids

    # Direct access is blocked
    get_resp = api_client.get(f"/api/v1/knowledge-bases/{restricted_course.id}")
    assert get_resp.status_code == 404


# ==============================================================================
# CASE F: ALL_COURSES chat searches only authorized student-visible courses
# ==============================================================================
def test_case_f_all_courses_chat_searches_only_authorized_student_visible_courses(
    api_client: TestClient, db_session: Session
) -> None:
    from backend.app.api.deps import get_authorized_knowledge_base_ids

    admin = _create_user(db_session, "admin@university.edu", UserRole.ADMIN)
    student = _create_user(db_session, "student@university.edu", UserRole.STUDENT)

    course_a = _create_course(db_session, admin, "Course A", is_active=True, is_student_visible=True)
    course_h = _create_course(db_session, admin, "Course Hidden", is_active=True, is_student_visible=False)
    course_i = _create_course(db_session, admin, "Course Inactive", is_active=False, is_student_visible=True)
    db_session.add(KnowledgeBaseMember(knowledge_base_id=course_a.id, user_id=student.id))
    db_session.add(KnowledgeBaseMember(knowledge_base_id=course_h.id, user_id=student.id))
    db_session.add(KnowledgeBaseMember(knowledge_base_id=course_i.id, user_id=student.id))
    db_session.commit()

    auth_ids = get_authorized_knowledge_base_ids(current_user=student, db=db_session)
    assert auth_ids == [course_a.id]


# ==============================================================================
# CASE G: Student cannot query an unauthorized/restricted knowledge base directly
# ==============================================================================
def test_case_g_student_cannot_query_unauthorized_kb_directly(
    api_client: TestClient, db_session: Session
) -> None:
    admin = _create_user(db_session, "admin@university.edu", UserRole.ADMIN)
    _create_user(db_session, "student@university.edu", UserRole.STUDENT)

    restricted_kb = _create_course(db_session, admin, "Restricted KB", is_active=True, is_student_visible=False)

    _login_student(api_client)

    chat_resp = api_client.post(
        "/api/v1/chat/query",
        json={"knowledge_base_id": str(restricted_kb.id), "question": "What is on the exam?"},
    )
    assert chat_resp.status_code == 404
    assert "not found" in chat_resp.json()["detail"].lower()


# ==============================================================================
# CASE H: Student cannot stream an unauthorized document
# ==============================================================================
def test_case_h_student_cannot_stream_unauthorized_document(
    api_client: TestClient, db_session: Session
) -> None:
    admin = _create_user(db_session, "admin@university.edu", UserRole.ADMIN)
    _create_user(db_session, "student@university.edu", UserRole.STUDENT)

    restricted_kb = _create_course(db_session, admin, "Restricted KB", is_active=True, is_student_visible=False)

    doc = Document(
        knowledge_base_id=restricted_kb.id,
        original_filename="confidential_answers.pdf",
        storage_key="storage/mock/confidential_answers.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        content_hash="mockhash",
        status=DocumentStatus.COMPLETED,
        indexing_status=IndexingStatus.COMPLETED,
        is_active=True,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    _login_student(api_client)

    resp = api_client.get(f"/api/v1/documents/{doc.id}/file")
    assert resp.status_code == 404


# ==============================================================================
# CASE I: Empty available course catalog produces proper empty state
# ==============================================================================
def test_case_i_empty_available_course_catalog_produces_proper_empty_state(
    api_client: TestClient, db_session: Session
) -> None:
    _create_user(db_session, "student@university.edu", UserRole.STUDENT)

    _login_student(api_client)

    # Empty list
    resp = api_client.get("/api/v1/knowledge-bases")
    assert resp.status_code == 200
    assert resp.json() == []

    # Chat query on empty catalog returns safe empty context refusal
    chat_resp = api_client.post(
        "/api/v1/chat/query",
        json={"question": "What courses are available?"},
    )
    assert chat_resp.status_code == 200
    data = chat_resp.json()
    assert data["is_empty_context"] is True
    assert "No course material is currently available" in data["answer"]
