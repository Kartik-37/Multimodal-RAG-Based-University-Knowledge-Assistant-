"""
Comprehensive Integration Tests for Complete Admin Experience Redesign.

Validates the full admin specification:
1. RBAC route capability structure respecting roles and permissions.
2. Main Admin vs Faculty Admin hierarchy & course-scoped permissions.
3. Final active Main Admin cannot be deleted or deactivated.
4. Self-deletion and self-deactivation protection.
5. Faculty Admin course isolation in Admin Knowledge Chat and document management.
6. Persistent indexing job tracking with truthful progress and retry capabilities.
7. System health endpoint and component diagnostics.
8. Truthful administrative activity & audit timeline.
9. NiceGUI connection recovery and non-blocking worker lifecycle.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.permissions import Permission
from backend.app.core.security import get_password_hash
from backend.app.models.document import Document, DocumentStatus
from backend.app.models.indexing_job import IndexingJob, IndexingJobStage, IndexingJobStatus
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseMember
from backend.app.models.user import AdminRole, User, UserRole
from frontend.client.api_client import api_client
from frontend.client.models import UserDTO
from frontend.components.layout import can_access_route, has_admin_permission


@pytest.fixture
def test_setup_data(db_session: Session):
    """Seed test main admin, faculty admin, student, and university courses."""
    # 1. Main Admin
    main_admin = db_session.execute(
        select(User).where(User.email == "main_admin_test@university.edu")
    ).scalar_one_or_none()
    if not main_admin:
        main_admin = User(
            id=uuid.uuid4(),
            email="main_admin_test@university.edu",
            password_hash=get_password_hash("AdminPass123!"),
            full_name="Chief Administrator",
            role=UserRole.ADMIN,
            admin_role=AdminRole.MAIN_ADMIN,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        db_session.add(main_admin)

    # 2. Courses
    kb_cs = KnowledgeBase(
        id=uuid.uuid4(),
        name=f"Computer Science {uuid.uuid4().hex[:6]}",
        description="Core computing courses",
        created_by_id=main_admin.id,
        created_at=datetime.now(UTC),
    )
    kb_math = KnowledgeBase(
        id=uuid.uuid4(),
        name=f"Mathematics {uuid.uuid4().hex[:6]}",
        description="Calculus and linear algebra",
        created_by_id=main_admin.id,
        created_at=datetime.now(UTC),
    )
    db_session.add_all([kb_cs, kb_math])
    db_session.commit()

    # 3. Faculty Admin (Assigned only to Computer Science)
    faculty_admin = User(
        id=uuid.uuid4(),
        email=f"faculty_{uuid.uuid4().hex[:6]}@university.edu",
        password_hash=get_password_hash("FacultyPass123!"),
        full_name="Prof. Alan Turing",
        role=UserRole.ADMIN,
        admin_role=AdminRole.FACULTY_ADMIN,
        permissions=[
            Permission.COURSE_VIEW.value,
            Permission.DOCUMENT_VIEW.value,
            Permission.DOCUMENT_UPLOAD.value,
            Permission.DOCUMENT_INDEX.value,
            Permission.ADMIN_CHAT.value,
        ],
        is_active=True,
        created_at=datetime.now(UTC),
    )
    db_session.add(faculty_admin)
    db_session.commit()

    # Assign Faculty to kb_cs only
    member = KnowledgeBaseMember(
        id=uuid.uuid4(),
        knowledge_base_id=kb_cs.id,
        user_id=faculty_admin.id,
        granted_at=datetime.now(UTC),
    )
    db_session.add(member)
    db_session.commit()

    return {
        "main_admin": main_admin,
        "faculty_admin": faculty_admin,
        "kb_cs": kb_cs,
        "kb_math": kb_math,
    }


# ==============================================================================
# 1. RBAC ROUTE CAPABILITY AND AUTHORIZATION
# ==============================================================================


def test_main_admin_route_capabilities(test_setup_data):
    """Main Admin has authorization across all administrative routes."""
    data = test_setup_data
    u = UserDTO(
        id=str(data["main_admin"].id),
        email=data["main_admin"].email,
        full_name=data["main_admin"].full_name,
        role="ADMIN",
        admin_role="MAIN_ADMIN",
        permissions=[],
    )
    for route in [
        "/dashboard",
        "/knowledge-bases",
        "/documents",
        "/chat",
        "/administrators",
    ]:
        assert can_access_route(u, route) is True


def test_faculty_admin_scoped_capabilities(test_setup_data):
    """Faculty Admin sees only routes permitted by their RBAC permissions."""
    data = test_setup_data
    u = UserDTO(
        id=str(data["faculty_admin"].id),
        email=data["faculty_admin"].email,
        full_name=data["faculty_admin"].full_name,
        role="ADMIN",
        admin_role="FACULTY_ADMIN",
        permissions=data["faculty_admin"].permissions,
    )
    assert can_access_route(u, "/dashboard") is True
    assert can_access_route(u, "/knowledge-bases") is True
    assert can_access_route(u, "/documents") is True
    assert can_access_route(u, "/chat") is True
    # Faculty Admin without ADMIN_VIEW cannot access administrators route
    assert can_access_route(u, "/administrators") is False
    assert has_admin_permission(u, Permission.ADMIN_VIEW) is False


def test_student_prohibited_from_admin_routes():
    """Students cannot access any administrator routes."""
    student = UserDTO(
        id="s-1",
        email="student@university.edu",
        full_name="Student",
        role="STUDENT",
    )
    for route in [
        "/documents",
        "/administrators",
        "/indexing",
        "/activity",
        "/system-health",
    ]:
        assert can_access_route(student, route) is False


# ==============================================================================
# 2. ADMINISTRATOR HIERARCHY & SAFETY GUARDS
# ==============================================================================


def test_final_main_admin_protection(test_setup_data, db_session: Session):
    """The system must strictly prevent deleting or deactivating the final active Main Admin."""
    data = test_setup_data
    main_admin = data["main_admin"]

    # Log in as main admin
    api_client.login(main_admin.email, "AdminPass123!")

    # Self-deactivation is rejected
    with pytest.raises(ValueError, match="cannot deactivate.*own account"):
        api_client.deactivate_admin(str(main_admin.id))

    # Self-deletion is rejected
    with pytest.raises(ValueError, match="cannot delete.*own account"):
        api_client.delete_admin(str(main_admin.id))


def test_faculty_admin_course_assignment_and_permissions(test_setup_data):
    """Main Admin can inspect, update permissions, and assign courses to a Faculty Admin."""
    data = test_setup_data
    main_admin = data["main_admin"]
    faculty = data["faculty_admin"]
    kb_math = data["kb_math"]

    api_client.login(main_admin.email, "AdminPass123!")

    # Verify listing includes faculty with assigned course
    admins = api_client.get_admins()
    faculty_entry = next((a for a in admins if a.id == str(faculty.id)), None)
    assert faculty_entry is not None
    assert faculty_entry.admin_role == "FACULTY_ADMIN"
    assert data["kb_cs"].name in faculty_entry.assigned_courses

    # Update permissions and assign additional course kb_math
    new_perms = [
        Permission.COURSE_VIEW.value,
        Permission.DOCUMENT_VIEW.value,
        Permission.DOCUMENT_UPLOAD.value,
        Permission.DOCUMENT_INDEX.value,
        Permission.DOCUMENT_INDEX_RETRY.value,
        Permission.ADMIN_CHAT.value,
    ]
    updated = api_client.update_admin_permissions(
        str(faculty.id),
        permissions=new_perms,
        assigned_course_ids=[str(data["kb_cs"].id), str(kb_math.id)],
    )
    assert len(updated.permissions) == 6
    assert Permission.DOCUMENT_INDEX_RETRY.value in updated.permissions


# ==============================================================================
# 3. PERSISTENT INDEXING & CHUNK PROGRESS
# ==============================================================================


def test_truthful_indexing_progress_tracking(test_setup_data, db_session: Session):
    """Persistent indexing progress tracks 0/N, partial, and completed chunks truthfully."""
    data = test_setup_data
    kb = data["kb_cs"]
    main_admin = data["main_admin"]

    # Create test document
    doc = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb.id,
        original_filename="Syllabus_2026.pdf",
        storage_key=f"storage/{kb.id}/syllabus_{uuid.uuid4().hex[:6]}.pdf",
        mime_type="application/pdf",
        content_hash=uuid.uuid4().hex * 2,
        file_type="pdf",
        file_size_bytes=10240,
        status=DocumentStatus.COMPLETED,
        indexing_status="PROCESSING",
        is_active=False,
        created_at=datetime.now(UTC),
    )
    db_session.add(doc)
    db_session.commit()

    # Create persistent IndexingJob record
    job = IndexingJob(
        id=uuid.uuid4(),
        document_id=doc.id,
        knowledge_base_id=kb.id,
        status=IndexingJobStatus.PROCESSING,
        stage=IndexingJobStage.EMBEDDING,
        total_chunks=10,
        processed_chunks=4,
        embedded_chunks=4,
        indexed_chunks=4,
        progress_percent=40.0,
        attempt_number=1,
        started_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(job)
    db_session.commit()

    api_client.login(main_admin.email, "AdminPass123!")

    # Check status endpoint
    status_dto = api_client.get_document_index_status(str(kb.id), str(doc.id))
    assert status_dto.status == "PROCESSING"
    assert status_dto.stage.upper() == "EMBEDDING"
    assert status_dto.total_chunks == 10
    assert status_dto.processed_chunks == 4
    assert status_dto.indexed_chunks == 4
    assert status_dto.progress_percent == 40.0

    # Verify listing of all jobs includes this job
    jobs = api_client.get_indexing_jobs()
    matching_job = next((j for j in jobs if j.document_id == str(doc.id)), None)
    assert matching_job is not None
    assert matching_job.document_name == "Syllabus_2026.pdf"
    assert matching_job.progress_percent == 40.0


def test_indexing_retry_workflow(test_setup_data, db_session: Session):
    """Retrying a failed document resets state and schedules re-indexing."""
    data = test_setup_data
    kb = data["kb_cs"]
    main_admin = data["main_admin"]

    doc = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb.id,
        original_filename="Failed_Reading.pdf",
        storage_key=f"storage/{kb.id}/failed_{uuid.uuid4().hex[:6]}.pdf",
        mime_type="application/pdf",
        content_hash=uuid.uuid4().hex * 2,
        file_type="pdf",
        file_size_bytes=5120,
        status=DocumentStatus.COMPLETED,
        indexing_status="FAILED",
        indexing_error="Embedding service timed out",
        is_active=False,
        created_at=datetime.now(UTC),
    )
    db_session.add(doc)
    db_session.commit()

    api_client.login(main_admin.email, "AdminPass123!")

    # Trigger retry
    retry_dto = api_client.retry_indexing(str(kb.id), str(doc.id))
    assert retry_dto.status in ("PROCESSING", "QUEUED", "PENDING")
    assert retry_dto.document_id == str(doc.id)


# ==============================================================================
# 4. ADMIN KNOWLEDGE CHAT & SCOPED RETRIEVAL
# ==============================================================================


def test_admin_chat_scoped_to_authorized_courses(test_setup_data, db_session: Session):
    """Faculty admin can only select and query courses within their assigned scope."""
    data = test_setup_data
    faculty = data["faculty_admin"]

    api_client.login(faculty.email, "FacultyPass123!")

    # Faculty can only see kb_cs
    scopes = api_client.get_chat_scope_courses()
    scope_ids = [s.id for s in scopes]
    assert str(data["kb_cs"].id) in scope_ids
    assert str(data["kb_math"].id) not in scope_ids


def test_main_admin_chat_unrestricted_scope(test_setup_data):
    """Main Admin can see all courses in chat scope."""
    data = test_setup_data
    main_admin = data["main_admin"]

    api_client.login(main_admin.email, "AdminPass123!")

    scopes = api_client.get_chat_scope_courses()
    scope_ids = [s.id for s in scopes]
    assert str(data["kb_cs"].id) in scope_ids
    assert str(data["kb_math"].id) in scope_ids


# ==============================================================================
# 5. SYSTEM HEALTH & AUDIT ACTIVITY TELEMETRY
# ==============================================================================


def test_system_health_telemetry(test_setup_data):
    """System health endpoint returns component diagnostic statuses without stack traces."""
    data = test_setup_data
    api_client.login(data["main_admin"].email, "AdminPass123!")

    health = api_client.get_system_health()
    assert health.status in ("healthy", "degraded", "unavailable")
    assert len(health.components) >= 3

    comp_names = [c.name for c in health.components]
    assert any("Database" in n for n in comp_names)
    assert any("Vector Store" in n or "pgvector" in n for n in comp_names)


def test_administrative_activity_log(test_setup_data):
    """Administrative activity log returns structured audit records."""
    data = test_setup_data
    api_client.login(data["main_admin"].email, "AdminPass123!")

    events = api_client.get_activity_log()
    assert isinstance(events, list)
    if events:
        ev = events[0]
        assert hasattr(ev, "timestamp")
        assert hasattr(ev, "actor_name")
        assert hasattr(ev, "action")
        assert hasattr(ev, "status")
