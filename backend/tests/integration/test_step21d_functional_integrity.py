"""
Step 21D Functional Integrity Integration Tests.

Validates the full functional integrity matrix:
1. Real vector indexing pipeline lifecycle:
   - Persistent IndexingJob creation & incremental batch progress
   - Vector persistence verification (embedding dimension & count)
   - Idempotent re-run / retry
2. Retrieval publication gate:
   - Documents with indexing_status != COMPLETED cannot be activated (HTTP 400)
   - Indexed documents activate cleanly (HTTP 200)
3. Admin hierarchy & granular RBAC:
   - Main Admin has inherent full authority
   - Faculty Admin is strictly restricted to assigned permissions (HTTP 403 on missing)
   - Permission updates via PATCH /auth/admins/{id}/permissions
   - Faculty Admins cannot create Main Admins
4. Administrator lifecycle safety guards:
   - Self-deactivation rejection (HTTP 400)
   - Self-deletion rejection (HTTP 400)
   - Final active Main Admin protection (HTTP 400)
5. Scoped Admin Chat:
   - Controlled refusal when querying an unindexed document
   - SQL-level document scoping (only chunks belonging to target document are retrieved)
"""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.app.core.permissions import Permission
from backend.app.core.security import get_password_hash
from backend.app.models.document import Document, DocumentChunk, DocumentStatus, IndexingStatus
from backend.app.models.indexing_job import IndexingJob, IndexingJobStage, IndexingJobStatus
from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.models.user import AdminRole, User, UserRole
from backend.app.services.embedding.base import BaseEmbeddingProvider
from backend.app.services.indexing import IndexingPipeline
from backend.app.services.lexical_retrieval import LexicalRetrievalService
from backend.app.services.retrieval import VectorRetrievalService


class Mock1024EmbeddingProvider(BaseEmbeddingProvider):
    """Deterministic 1024-dimensional mock embedding provider."""

    @property
    def dimension(self) -> int:
        return 1024

    @property
    def model_name(self) -> str:
        return "mock-1024"

    def _embed_str(self, text_val: str) -> list[float]:
        vec = [0.0] * 1024
        for i, ch in enumerate(text_val[:16]):
            idx = (ord(ch) * 31 + i * 17) % 1024
            vec[idx] += 1.0
        vec[0] += 0.1
        return vec

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_str(t) for t in texts]

    async def embed_query(self, query: str) -> list[float]:
        return self._embed_str(query)


@pytest.fixture(autouse=True)
def clean_db(db_engine) -> Generator[None, None, None]:
    """Clean all tables before and after each test."""
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


# ------------------------------------------------------------------------------
# 1. Real Vector Indexing Pipeline Lifecycle & Progress
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_indexing_pipeline_lifecycle_and_batch_progress(db_session: Session) -> None:
    """
    Verify persistent IndexingJob creation, batch progress persistence,
    vector persistence, and idempotent retries.
    """
    admin = User(
        id=uuid.uuid4(),
        email="mainadmin@univ.edu",
        password_hash=get_password_hash("AdminPass123!"),
        full_name="Main Administrator",
        role=UserRole.ADMIN,
        admin_role=AdminRole.MAIN_ADMIN,
    )
    db_session.add(admin)
    db_session.commit()

    kb = KnowledgeBase(id=uuid.uuid4(), name="Computer Science", created_by_id=admin.id)
    db_session.add(kb)
    db_session.commit()

    doc = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb.id,
        original_filename="syllabus.txt",
        storage_key=f"uploads/{kb.id}/syllabus.txt",
        file_type="txt",
        mime_type="text/plain",
        file_size_bytes=500,
        content_hash="hash123",
        status=DocumentStatus.COMPLETED,
        indexing_status=IndexingStatus.PENDING,
    )
    db_session.add(doc)
    db_session.commit()

    # Create 6 chunks
    for i in range(6):
        chunk = DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc.id,
            knowledge_base_id=kb.id,
            chunk_index=i,
            text=f"Chunk {i} content discussing algorithms and data structures module {i}.",
            token_count=15,
            embedding=None,
        )
        db_session.add(chunk)
    db_session.commit()

    provider = Mock1024EmbeddingProvider()
    pipeline = IndexingPipeline(provider=provider)

    # Create persistent job
    job = pipeline.create_or_reuse_job(doc.id, kb.id)
    assert job is not None
    assert job.status == IndexingJobStatus.QUEUED.value

    # Execute indexing pipeline
    success = await pipeline.index_document_async(
        document_id=doc.id,
        job_id=job.id,
    )
    assert success is True

    # Verify IndexingJob record
    db_session.expire_all()
    job_record = (
        db_session.execute(
            select(IndexingJob).where(IndexingJob.document_id == doc.id)
        )
        .scalars()
        .first()
    )
    assert job_record is not None
    assert job_record.status == IndexingJobStatus.COMPLETED.value
    assert job_record.stage == IndexingJobStage.COMPLETED.value
    assert job_record.total_chunks == 6
    assert job_record.indexed_chunks == 6
    assert job_record.progress_percent == 100.0

    # Verify Document state
    db_session.refresh(doc)
    assert doc.indexing_status == IndexingStatus.COMPLETED
    assert doc.indexed_at is not None

    # Verify chunks have vectors persisted
    chunks = (
        db_session.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
        )
        .scalars()
        .all()
    )
    assert len(chunks) == 6
    for c in chunks:
        assert c.embedding is not None
        assert len(c.embedding) == 1024

    # Test Idempotent Retry: re-running again succeeds cleanly
    job_retry = pipeline.create_or_reuse_job(doc.id, kb.id)
    retry_success = await pipeline.index_document_async(
        document_id=doc.id,
        job_id=job_retry.id,
    )
    assert retry_success is True


# ------------------------------------------------------------------------------
# 2. Document Activation Gate Enforces Completed Indexing
# ------------------------------------------------------------------------------


def test_document_activation_gate_enforces_completed_indexing(
    api_client: TestClient, db_session: Session
) -> None:
    """
    Ensure documents CANNOT be activated if indexing_status != COMPLETED (HTTP 400).
    Once indexed, activation succeeds (HTTP 200).
    """
    admin = User(
        id=uuid.uuid4(),
        email="admin_gate@univ.edu",
        password_hash=get_password_hash("AdminPass123!"),
        full_name="Gate Admin",
        role=UserRole.ADMIN,
        admin_role=AdminRole.MAIN_ADMIN,
    )
    db_session.add(admin)
    db_session.commit()

    kb = KnowledgeBase(id=uuid.uuid4(), name="Physics", created_by_id=admin.id)
    db_session.add(kb)
    db_session.commit()

    doc = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb.id,
        original_filename="lab_guide.pdf",
        storage_key=f"uploads/{kb.id}/lab_guide.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size_bytes=1000,
        content_hash="labhash",
        status=DocumentStatus.COMPLETED,
        indexing_status=IndexingStatus.PENDING,  # Not completed!
        is_active=False,
    )
    db_session.add(doc)
    db_session.commit()

    # Log in as admin
    api_client.post(
        "/api/v1/auth/login",
        json={"email": "admin_gate@univ.edu", "password": "AdminPass123!"},
    )

    # Attempt to activate unindexed document -> must return HTTP 400
    act_resp = api_client.patch(
        f"/api/v1/knowledge-bases/{kb.id}/documents/{doc.id}/activate"
    )
    assert act_resp.status_code == 400
    assert "vector indexing" in act_resp.json()["detail"].lower()

    # Mark document as indexed
    doc.indexing_status = IndexingStatus.COMPLETED
    db_session.commit()

    # Now activate -> must succeed
    act_resp2 = api_client.patch(
        f"/api/v1/knowledge-bases/{kb.id}/documents/{doc.id}/activate"
    )
    assert act_resp2.status_code == 200
    assert act_resp2.json()["is_active"] is True


# ------------------------------------------------------------------------------
# 3. Admin Hierarchy & Granular RBAC
# ------------------------------------------------------------------------------


def test_admin_hierarchy_and_permissions(
    api_client: TestClient, db_session: Session
) -> None:
    """
    Validate that Main Admin has inherent full authority, Faculty Admin is restricted
    to assigned permissions, and permission updates take immediate effect.
    """
    main_admin = User(
        id=uuid.uuid4(),
        email="super@univ.edu",
        password_hash=get_password_hash("SuperAdmin123!"),
        full_name="Super Administrator",
        role=UserRole.ADMIN,
        admin_role=AdminRole.MAIN_ADMIN,
    )
    faculty_admin = User(
        id=uuid.uuid4(),
        email="faculty_limited@univ.edu",
        password_hash=get_password_hash("FacultyPass123!"),
        full_name="Dr. Limited",
        role=UserRole.ADMIN,
        admin_role=AdminRole.FACULTY_ADMIN,
        permissions=[Permission.COURSE_VIEW.value, Permission.DOCUMENT_VIEW.value],  # No COURSE_CREATE
    )
    db_session.add_all([main_admin, faculty_admin])
    db_session.commit()

    # 1. Faculty Admin logs in
    api_client.post(
        "/api/v1/auth/login",
        json={"email": "faculty_limited@univ.edu", "password": "FacultyPass123!"},
    )

    # Faculty tries to create a course (requires COURSE_CREATE) -> 403 Forbidden
    create_resp = api_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Disallowed Course", "description": "Should fail"},
    )
    assert create_resp.status_code == 403
    assert "COURSE_CREATE" in create_resp.json()["detail"]

    # Faculty tries to provision an admin (requires ADMIN_CREATE) -> 403 Forbidden
    adm_resp = api_client.post(
        "/api/v1/auth/admin",
        json={
            "email": "another@univ.edu",
            "password": "Password123!",
            "full_name": "Another Person",
            "admin_role": "FACULTY_ADMIN",
        },
    )
    assert adm_resp.status_code == 403

    # 2. Main Admin logs in and grants COURSE_CREATE to Faculty Admin
    api_client.post(
        "/api/v1/auth/login",
        json={"email": "super@univ.edu", "password": "SuperAdmin123!"},
    )
    perm_resp = api_client.patch(
        f"/api/v1/auth/admins/{faculty_admin.id}/permissions",
        json={"permissions": [Permission.COURSE_VIEW.value, Permission.DOCUMENT_VIEW.value, Permission.COURSE_CREATE.value]},
    )
    assert perm_resp.status_code == 200
    assert Permission.COURSE_CREATE.value in perm_resp.json()["permissions"]

    # 3. Faculty logs back in -> now can create course
    api_client.post(
        "/api/v1/auth/login",
        json={"email": "faculty_limited@univ.edu", "password": "FacultyPass123!"},
    )
    create_resp2 = api_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Now Allowed Course", "description": "Created with new permission"},
    )
    assert create_resp2.status_code == 201
    assert create_resp2.json()["name"] == "Now Allowed Course"


# ------------------------------------------------------------------------------
# 4. Administrator Lifecycle Safety Guards
# ------------------------------------------------------------------------------


def test_admin_lifecycle_safety_guards(
    api_client: TestClient, db_session: Session
) -> None:
    """
    Ensure safety guards:
    - Cannot deactivate self (HTTP 400)
    - Cannot delete self (HTTP 400)
    - Cannot deactivate or delete the final active Main Admin (HTTP 400)
    """
    main_admin = User(
        id=uuid.uuid4(),
        email="sole_main@univ.edu",
        password_hash=get_password_hash("SoleMain123!"),
        full_name="Sole Main Admin",
        role=UserRole.ADMIN,
        admin_role=AdminRole.MAIN_ADMIN,
    )
    db_session.add(main_admin)
    db_session.commit()

    api_client.post(
        "/api/v1/auth/login",
        json={"email": "sole_main@univ.edu", "password": "SoleMain123!"},
    )

    # 1. Attempt self-deactivation -> rejected
    deact_resp = api_client.patch(f"/api/v1/auth/admins/{main_admin.id}/deactivate")
    assert deact_resp.status_code == 400
    assert "cannot deactivate their own account" in deact_resp.json()["detail"].lower()

    # 2. Attempt self-deletion -> rejected
    del_resp = api_client.delete(f"/api/v1/auth/admins/{main_admin.id}")
    assert del_resp.status_code == 400
    assert "cannot delete their own account" in del_resp.json()["detail"].lower()

    # 3. Create a second admin (Faculty Admin with ADMIN_DELETE permission)
    second_admin = User(
        id=uuid.uuid4(),
        email="second_admin@univ.edu",
        password_hash=get_password_hash("Second123!"),
        full_name="Second Admin",
        role=UserRole.ADMIN,
        admin_role=AdminRole.FACULTY_ADMIN,
        permissions=[Permission.ADMIN_DELETE.value, Permission.ADMIN_EDIT.value],
    )
    db_session.add(second_admin)
    db_session.commit()

    # Second admin tries to deactivate/delete the ONLY Main Admin -> rejected
    api_client.post(
        "/api/v1/auth/login",
        json={"email": "second_admin@univ.edu", "password": "Second123!"},
    )
    deact_main = api_client.patch(f"/api/v1/auth/admins/{main_admin.id}/deactivate")
    assert deact_main.status_code == 400
    assert "final active Main Admin" in deact_main.json()["detail"]

    del_main = api_client.delete(f"/api/v1/auth/admins/{main_admin.id}")
    assert del_main.status_code == 400
    assert "final Main Admin" in del_main.json()["detail"]


# ------------------------------------------------------------------------------
# 5. Scoped Admin Chat & Database Filtering
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_document_scoping_enforcement(
    api_client: TestClient, db_session: Session
) -> None:
    """
    Ensure:
    - Querying an unindexed document returns a controlled refusal (HTTP 400)
    - Document-scoped query strictly filters chunks to that document at SQL level
    """
    admin = User(
        id=uuid.uuid4(),
        email="chat_admin@univ.edu",
        password_hash=get_password_hash("AdminPass123!"),
        full_name="Chat Administrator",
        role=UserRole.ADMIN,
        admin_role=AdminRole.MAIN_ADMIN,
    )
    db_session.add(admin)
    db_session.commit()

    kb = KnowledgeBase(id=uuid.uuid4(), name="Database Systems", created_by_id=admin.id)
    db_session.add(kb)
    db_session.commit()

    doc_unindexed = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb.id,
        original_filename="unindexed_doc.pdf",
        storage_key=f"uploads/{kb.id}/unindexed_doc.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size_bytes=200,
        content_hash="unindexed_hash",
        status=DocumentStatus.COMPLETED,
        indexing_status=IndexingStatus.FAILED,
        is_active=False,
    )
    doc_indexed_a = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb.id,
        original_filename="doc_alpha.pdf",
        storage_key=f"uploads/{kb.id}/doc_alpha.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size_bytes=300,
        content_hash="alpha_hash",
        status=DocumentStatus.COMPLETED,
        indexing_status=IndexingStatus.COMPLETED,
        is_active=True,
    )
    doc_indexed_b = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb.id,
        original_filename="doc_beta.pdf",
        storage_key=f"uploads/{kb.id}/doc_beta.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size_bytes=300,
        content_hash="beta_hash",
        status=DocumentStatus.COMPLETED,
        indexing_status=IndexingStatus.COMPLETED,
        is_active=True,
    )
    db_session.add_all([doc_unindexed, doc_indexed_a, doc_indexed_b])
    db_session.commit()

    provider = Mock1024EmbeddingProvider()
    vec_a = [0.0] * 1024
    vec_a[10] = 1.0
    vec_b = [0.0] * 1024
    vec_b[20] = 1.0

    chunk_a = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_indexed_a.id,
        knowledge_base_id=kb.id,
        chunk_index=0,
        text="AlphaSecretKeyword represents the unique alpha document token.",
        token_count=10,
        embedding=vec_a,
    )
    chunk_b = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_indexed_b.id,
        knowledge_base_id=kb.id,
        chunk_index=0,
        text="BetaSecretKeyword represents the unique beta document token.",
        token_count=10,
        embedding=vec_b,
    )
    db_session.add_all([chunk_a, chunk_b])
    db_session.commit()

    api_client.post(
        "/api/v1/auth/login",
        json={"email": "chat_admin@univ.edu", "password": "AdminPass123!"},
    )

    # 1. Query scoped to unindexed doc -> must return HTTP 400 Bad Request
    unindexed_resp = api_client.post(
        "/api/v1/chat/query",
        json={
            "question": "What is in the unindexed document?",
            "scope": "DOCUMENT",
            "knowledge_base_id": str(kb.id),
            "document_id": str(doc_unindexed.id),
        },
    )
    assert unindexed_resp.status_code == 400
    assert "not ready for retrieval" in unindexed_resp.json()["detail"]

    # 2. Direct service verification of VectorRetrievalService with document_id
    vec_service = VectorRetrievalService(provider=provider)
    vec_res = await vec_service.retrieve(
        db=db_session,
        kb_id=kb.id,
        query="AlphaSecretKeyword",
        document_id=doc_indexed_a.id,
    )
    assert len(vec_res.results) == 1
    assert vec_res.results[0].document_id == doc_indexed_a.id
    assert "AlphaSecretKeyword" in vec_res.results[0].text

    # Lexical retrieval service with document_id
    lex_service = LexicalRetrievalService()
    lex_res = lex_service.retrieve(
        db=db_session,
        kb_id=kb.id,
        query="AlphaSecretKeyword",
        document_id=doc_indexed_a.id,
    )
    assert len(lex_res.results) == 1
    assert lex_res.results[0].document_id == doc_indexed_a.id
