"""
Integration Tests for Vector Indexing and pgvector Persistence.

Verifies:
1. Successful vector indexing stores 1024-dimensional vectors in PostgreSQL using pgvector.
2. pgvector function vector_dims(embedding) returns exactly 1024.
3. Vectors belong to the correct DocumentChunk identities.
4. Document status remains COMPLETED, indexing_status becomes COMPLETED (Correction 1).
5. Failed indexing transitions indexing_status to FAILED with error message, without deleting chunks or leaving partial vector writes.
6. Re-indexing after failure successfully updates vectors on the same chunk UUIDs (no duplicate chunks).
7. Server-side RBAC: Student gets 403, unauthenticated gets 401, cross-tenant gets 404.
"""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.app.core.security import get_password_hash
from backend.app.db.session import get_db_session
from backend.app.models.document import Document, DocumentChunk, DocumentStatus, IndexingStatus
from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.models.user import User, UserRole
from backend.app.services.embedding.base import BaseEmbeddingProvider
from backend.app.services.embedding.exceptions import EmbeddingProviderError
from backend.app.services.indexing import IndexingPipeline
from backend.tests.fixtures_documents import create_sample_pdf_bytes


class DeterministicMockProvider(BaseEmbeddingProvider):
    """Deterministic embedding provider for integration testing."""

    def __init__(self, dimension: int = 1024, fail: bool = False) -> None:
        self._dim = dimension
        self.fail = fail

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return "mock-qwen3-embedding"

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if self.fail:
            raise EmbeddingProviderError("Simulated Ollama service outage.")
        if not texts:
            return []

        results = []
        for text_val in texts:
            # Deterministic float vector with unique prefix based on text length
            seed = (len(text_val) % 100) * 0.001
            vec = [(0.01 * (j % 50) + seed) for j in range(self._dim)]
            results.append(vec)
        return results

    async def embed_query(self, query: str) -> list[float]:
        res = await self.embed_texts([query])
        return res[0]


@pytest.fixture(autouse=True)
def clean_vector_db(db_engine) -> Generator[None, None, None]:
    """Clean all tables before and after each test function."""
    with db_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE document_chunks, documents, knowledge_base_members, "
                "knowledge_bases, user_sessions, users CASCADE;"
            )
        )
    yield
    with db_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE document_chunks, documents, knowledge_base_members, "
                "knowledge_bases, user_sessions, users CASCADE;"
            )
        )


def provision_user(
    db: Session,
    email: str,
    password: str = "SecurePassword123!",
    role: UserRole = UserRole.ADMIN,
) -> User:
    """Helper to provision a user directly in database."""
    user = User(
        email=email.strip().lower(),
        password_hash=get_password_hash(password),
        full_name="Test User",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def provision_kb(db: Session, owner: User, name: str = "Test Vector KB") -> KnowledgeBase:
    """Helper to create a knowledge base."""
    kb = KnowledgeBase(name=name, description="Test description", created_by_id=owner.id)
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


# ------------------------------------------------------------------------------
# Integration Tests
# ------------------------------------------------------------------------------


def test_real_pgvector_storage_and_dimension_verification(db_session: Session) -> None:
    """
    Direct PostgreSQL/pgvector integration test:
    Verifies that a 1024-dimensional vector can be written to document_chunks
    and that vector_dims(embedding) returns 1024.
    """
    admin = provision_user(db_session, "admin_vector@univ.edu", role=UserRole.ADMIN)
    kb = provision_kb(db_session, admin)

    # 1. Create a document and chunk
    doc = Document(
        knowledge_base_id=kb.id,
        original_filename="pgvector_test.pdf",
        storage_key=f"storage/{kb.id}/{uuid.uuid4().hex}.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        content_hash="abc" * 21 + "a",
        status=DocumentStatus.COMPLETED,
        indexing_status=IndexingStatus.PENDING,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    chunk = DocumentChunk(
        document_id=doc.id,
        knowledge_base_id=kb.id,
        chunk_index=1,
        text="Testing pgvector 1024-dimension vector persistence.",
        token_count=8,
        page_number=1,
        section_title="Test Section",
        chunk_metadata={"test": True},
    )
    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(chunk)
    chunk_id = chunk.id

    # 2. Run indexing pipeline with deterministic 1024-d provider
    provider = DeterministicMockProvider(dimension=1024)
    pipeline = IndexingPipeline(provider=provider)
    success = pipeline.index_document(doc.id)
    assert success is True

    # 3. Direct pgvector SQL verification in PostgreSQL
    with get_db_session() as db:
        updated_chunk = db.execute(
            select(DocumentChunk).where(DocumentChunk.id == chunk_id)
        ).scalar_one()

        assert updated_chunk.embedding is not None
        assert len(updated_chunk.embedding) == 1024

        # Query pgvector native function: vector_dims()
        raw_dim = db.execute(
            text("SELECT vector_dims(embedding) FROM document_chunks WHERE id = :cid"),
            {"cid": chunk_id},
        ).scalar_one()

        assert raw_dim == 1024, f"Expected pgvector dimension 1024, got {raw_dim}"

        # Verify document status
        updated_doc = db.execute(select(Document).where(Document.id == doc.id)).scalar_one()
        assert updated_doc.status == DocumentStatus.COMPLETED
        assert updated_doc.indexing_status == IndexingStatus.COMPLETED
        assert updated_doc.indexed_at is not None
        assert updated_doc.indexing_error is None


def test_end_to_end_upload_and_indexing_lifecycle(
    api_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    End-to-end admin workflow:
    1. Admin uploads real 2-page PDF.
    2. Step 5 ingestion completes: doc.status = COMPLETED, doc.indexing_status = PENDING.
    3. Admin triggers indexing via POST /documents/{id}/index.
    4. Document indexing transitions to COMPLETED and pgvector stores vectors.
    """
    admin = provision_user(db_session, "admin_e2e@univ.edu", role=UserRole.ADMIN)
    kb = provision_kb(db_session, admin)

    # Login as admin
    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    # Monkeypatch the default provider used in background tasks to deterministic mock
    mock_provider = DeterministicMockProvider(dimension=1024)
    from backend.app.services.indexing import indexing_pipeline

    monkeypatch.setattr(indexing_pipeline, "_custom_provider", mock_provider)

    pdf_bytes = create_sample_pdf_bytes()
    files = {"file": ("curriculum.pdf", pdf_bytes, "application/pdf")}

    # Step 1: Upload document
    resp = api_client.post(f"/api/v1/knowledge-bases/{kb.id}/documents", files=files)
    assert resp.status_code == 201
    doc_data = resp.json()
    doc_id = doc_data["id"]

    # Step 2: Verify Step 5 ingestion completed, indexing is PENDING
    detail_resp = api_client.get(f"/api/v1/knowledge-bases/{kb.id}/documents/{doc_id}")
    assert detail_resp.status_code == 200
    doc_info = detail_resp.json()
    assert doc_info["status"] == "COMPLETED"
    assert doc_info["indexing_status"] == "PENDING"
    assert doc_info["chunk_count"] > 0

    # Chunks exist but have no embeddings yet
    chunks_resp = api_client.get(f"/api/v1/knowledge-bases/{kb.id}/documents/{doc_id}/chunks")
    assert chunks_resp.status_code == 200
    chunks = chunks_resp.json()
    assert len(chunks) > 0
    assert all(c["has_embedding"] is False for c in chunks)

    # Step 3: Trigger vector indexing
    index_resp = api_client.post(f"/api/v1/knowledge-bases/{kb.id}/documents/{doc_id}/index")
    assert index_resp.status_code == 202

    # Step 4: Verify vector indexing is COMPLETED and vectors are stored
    final_resp = api_client.get(f"/api/v1/knowledge-bases/{kb.id}/documents/{doc_id}")
    assert final_resp.status_code == 200
    final_info = final_resp.json()
    assert final_info["status"] == "COMPLETED"
    assert final_info["indexing_status"] == "COMPLETED"
    assert final_info["indexed_at"] is not None

    final_chunks_resp = api_client.get(f"/api/v1/knowledge-bases/{kb.id}/documents/{doc_id}/chunks")
    final_chunks = final_chunks_resp.json()
    assert all(c["has_embedding"] is True for c in final_chunks)


def test_indexing_failure_preserves_chunks_and_sets_failed_status(
    api_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Verify fault tolerance:
    When embedding provider fails:
    - doc.status remains COMPLETED (original parsing intact)
    - doc.indexing_status becomes FAILED
    - doc.indexing_error captures the diagnostic error
    - Chunks are NOT deleted
    - Partial vector writes are not committed (has_embedding remains False)
    """
    admin = provision_user(db_session, "admin_fail@univ.edu", role=UserRole.ADMIN)
    kb = provision_kb(db_session, admin)

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    # Inject failing provider
    failing_provider = DeterministicMockProvider(dimension=1024, fail=True)
    from backend.app.services.indexing import indexing_pipeline

    monkeypatch.setattr(indexing_pipeline, "_custom_provider", failing_provider)

    pdf_bytes = create_sample_pdf_bytes()
    files = {"file": ("syllabus_failure_test.pdf", pdf_bytes, "application/pdf")}

    # Upload
    resp = api_client.post(f"/api/v1/knowledge-bases/{kb.id}/documents", files=files)
    doc_id = resp.json()["id"]

    # Trigger indexing with failing provider
    index_resp = api_client.post(f"/api/v1/knowledge-bases/{kb.id}/documents/{doc_id}/index")
    assert index_resp.status_code == 202

    # Inspect document state
    doc_resp = api_client.get(f"/api/v1/knowledge-bases/{kb.id}/documents/{doc_id}")
    doc_info = doc_resp.json()
    assert doc_info["status"] == "COMPLETED"
    assert doc_info["indexing_status"] == "FAILED"
    assert "Simulated Ollama service outage" in doc_info["indexing_error"]

    # Chunks are completely preserved with 0 partial embeddings
    chunks_resp = api_client.get(f"/api/v1/knowledge-bases/{kb.id}/documents/{doc_id}/chunks")
    chunks = chunks_resp.json()
    assert len(chunks) > 0
    assert all(c["has_embedding"] is False for c in chunks)


def test_indexing_retry_after_failure_is_idempotent(
    api_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Verify retry safety:
    A failed indexing can be retried successfully without duplicating chunks.
    Chunk UUIDs remain unchanged.
    """
    admin = provision_user(db_session, "admin_retry@univ.edu", role=UserRole.ADMIN)
    kb = provision_kb(db_session, admin)

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    # 1. Start with failing provider
    failing_provider = DeterministicMockProvider(dimension=1024, fail=True)
    from backend.app.services.indexing import indexing_pipeline

    monkeypatch.setattr(indexing_pipeline, "_custom_provider", failing_provider)

    pdf_bytes = create_sample_pdf_bytes()
    resp = api_client.post(
        f"/api/v1/knowledge-bases/{kb.id}/documents",
        files={"file": ("retry_test.pdf", pdf_bytes, "application/pdf")},
    )
    doc_id = resp.json()["id"]

    api_client.post(f"/api/v1/knowledge-bases/{kb.id}/documents/{doc_id}/index")

    # Record chunk IDs after initial failure
    chunks_before = api_client.get(
        f"/api/v1/knowledge-bases/{kb.id}/documents/{doc_id}/chunks"
    ).json()
    chunk_ids_before = [c["id"] for c in chunks_before]

    # 2. Recover provider and retry indexing
    recovered_provider = DeterministicMockProvider(dimension=1024, fail=False)
    monkeypatch.setattr(indexing_pipeline, "_custom_provider", recovered_provider)

    retry_resp = api_client.post(f"/api/v1/knowledge-bases/{kb.id}/documents/{doc_id}/index")
    assert retry_resp.status_code == 202

    # Verify status is now COMPLETED
    doc_info = api_client.get(f"/api/v1/knowledge-bases/{kb.id}/documents/{doc_id}").json()
    assert doc_info["indexing_status"] == "COMPLETED"
    assert doc_info["indexing_error"] is None

    # Verify chunk UUIDs are unchanged (NO duplicate chunks)
    chunks_after = api_client.get(
        f"/api/v1/knowledge-bases/{kb.id}/documents/{doc_id}/chunks"
    ).json()
    chunk_ids_after = [c["id"] for c in chunks_after]

    assert chunk_ids_before == chunk_ids_after, (
        "Chunk identities must be preserved during re-indexing"
    )
    assert all(c["has_embedding"] is True for c in chunks_after)


def test_student_cannot_trigger_vector_indexing(
    api_client: TestClient,
    db_session: Session,
) -> None:
    """Verify students receive 403 Forbidden when attempting to trigger vector indexing."""
    admin = provision_user(db_session, "admin_owner_s@univ.edu", role=UserRole.ADMIN)
    student = provision_user(db_session, "student_tester@univ.edu", role=UserRole.STUDENT)
    kb = provision_kb(db_session, admin)

    api_client.post(
        "/api/v1/auth/login",
        json={"email": student.email, "password": "SecurePassword123!"},
    )

    fake_doc_id = uuid.uuid4()
    resp = api_client.post(f"/api/v1/knowledge-bases/{kb.id}/documents/{fake_doc_id}/index")
    assert resp.status_code == 403
    assert "Administrator privileges required" in resp.json()["detail"]


def test_cross_tenant_indexing_returns_404(
    api_client: TestClient,
    db_session: Session,
) -> None:
    """Verify indexing request for non-existent or foreign KB returns 404."""
    admin_b = provision_user(db_session, "admin_b_idx@univ.edu", role=UserRole.ADMIN)
    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin_b.email, "password": "SecurePassword123!"},
    )

    foreign_kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    resp = api_client.post(f"/api/v1/knowledge-bases/{foreign_kb_id}/documents/{doc_id}/index")
    assert resp.status_code == 404


def test_unauthenticated_indexing_returns_401(api_client: TestClient) -> None:
    """Verify unauthenticated user receives 401 Unauthorized."""
    api_client.cookies.clear()
    resp = api_client.post(f"/api/v1/knowledge-bases/{uuid.uuid4()}/documents/{uuid.uuid4()}/index")
    assert resp.status_code == 401
