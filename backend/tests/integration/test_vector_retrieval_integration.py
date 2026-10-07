"""
Integration Tests for Vector Retrieval Layer (Step 7).

Verifies:
1. Exact PostgreSQL + pgvector cosine similarity search executed in the database.
2. Chunks ordered by lowest cosine distance / highest similarity.
3. top_k parameter strictly enforced.
4. NULL embeddings strictly excluded.
5. Knowledge-base authorization and isolation:
   - Admin can retrieve from owned KB.
   - Authorized student can retrieve from member KB.
   - Unauthorized student receives HTTP 404 (preventing existence leakage).
   - Foreign KB chunks never leak across KB boundaries.
   - Unauthenticated requests receive HTTP 401.
   - Nonexistent KB returns HTTP 404.
6. Empty or unindexed KB returns empty result list [].
7. Duplicate text chunks remain distinguishable by chunk/document IDs.
8. Unicode search queries work correctly.
9. Deterministic tie-breaking on equal vector distances.
10. Controlled 503 error on embedding provider failure.
"""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.security import get_password_hash
from backend.app.models.document import Document, DocumentChunk, DocumentStatus, IndexingStatus
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseMember
from backend.app.models.user import User, UserRole
from backend.app.services.embedding.base import BaseEmbeddingProvider
from backend.app.services.embedding.exceptions import EmbeddingProviderError
from backend.app.services.retrieval import VectorRetrievalService


class ControlledMockEmbeddingProvider(BaseEmbeddingProvider):
    """
    Predictable 1024-dimensional embedding provider for integration tests.
    Generates deterministic vectors allowing verifiable distance computations.
    """

    def __init__(self, dimension: int = 1024, fail: bool = False) -> None:
        self._dim = dimension
        self.fail = fail

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return "mock-qwen3-embedding"

    def _make_vector(self, text_val: str) -> list[float]:
        """Produce deterministic normalized-like float vector based on content."""
        base = [0.0] * self._dim
        # Use first characters of text to place weights in specific dimensions
        for i, char in enumerate(text_val[:10]):
            idx = (ord(char) * 17 + i * 31) % self._dim
            base[idx] = 1.0
        # Add slight magnitude so norm is non-zero
        base[0] += 0.5
        return base

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if self.fail:
            raise EmbeddingProviderError("Simulated embedding provider failure.")
        return [self._make_vector(t) for t in texts]

    async def embed_query(self, query: str) -> list[float]:
        if self.fail:
            raise EmbeddingProviderError("Simulated embedding provider failure.")
        return self._make_vector(query)


@pytest.fixture(autouse=True)
def clean_database(db_engine) -> Generator[None, None, None]:
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


def create_user(
    db: Session,
    email: str,
    password: str = "SecurePassword123!",
    role: UserRole = UserRole.ADMIN,
) -> User:
    """Provision a user in PostgreSQL."""
    user = User(
        email=email.strip().lower(),
        password_hash=get_password_hash(password),
        full_name="Integration Test User",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_kb(db: Session, owner: User, name: str = "Retrieval Test KB") -> KnowledgeBase:
    """Provision a knowledge base in PostgreSQL."""
    kb = KnowledgeBase(name=name, description="Test description", created_by_id=owner.id)
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


def create_document(
    db: Session,
    kb: KnowledgeBase,
    filename: str = "curriculum.pdf",
    indexing_status: IndexingStatus = IndexingStatus.COMPLETED,
) -> Document:
    """Provision a document in PostgreSQL."""
    doc = Document(
        knowledge_base_id=kb.id,
        original_filename=filename,
        storage_key=f"storage/{kb.id}/{uuid.uuid4().hex}_{filename}",
        file_type="pdf",
        mime_type="application/pdf",
        file_size_bytes=4096,
        content_hash=uuid.uuid4().hex + uuid.uuid4().hex,
        status=DocumentStatus.COMPLETED,
        indexing_status=indexing_status,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def create_chunk(
    db: Session,
    doc: Document,
    kb: KnowledgeBase,
    chunk_index: int,
    text_content: str,
    embedding: list[float] | None = None,
    page_number: int | None = 1,
    section_title: str | None = "Section 1",
) -> DocumentChunk:
    """Provision a document chunk with optional 1024-d embedding."""
    chunk = DocumentChunk(
        document_id=doc.id,
        knowledge_base_id=kb.id,
        chunk_index=chunk_index,
        text=text_content,
        token_count=len(text_content.split()),
        page_number=page_number,
        section_title=section_title,
        chunk_metadata={"test": True},
        embedding=embedding,
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)
    return chunk


# ------------------------------------------------------------------------------
# PostgreSQL + pgvector Direct Vector Search Test
# ------------------------------------------------------------------------------


def test_real_pgvector_cosine_distance_query_execution(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Verifies that the vector search query actually executes in PostgreSQL using
    pgvector's `<=>` cosine distance operator and orders by distance ascending.
    """
    admin = create_user(db_session, "admin_direct@univ.edu", role=UserRole.ADMIN)
    kb = create_kb(db_session, admin)
    doc = create_document(db_session, kb)

    # Chunk A: text "algorithms"
    vec_a = [0.0] * 1024
    vec_a[10] = 1.0
    vec_a[0] = 0.5
    chunk_a = create_chunk(
        db_session, doc, kb, 0, "Algorithms analysis and Big O notation", embedding=vec_a
    )

    # Chunk B: text "databases"
    vec_b = [0.0] * 1024
    vec_b[500] = 1.0
    vec_b[0] = 0.5
    chunk_b = create_chunk(
        db_session, doc, kb, 1, "Relational databases and SQL normalization", embedding=vec_b
    )

    # Chunk C: unindexed chunk (embedding is NULL)
    create_chunk(db_session, doc, kb, 2, "Unindexed draft section", embedding=None)

    # Create mock provider that will return a query vector identical to vec_a
    class ExactMatchProvider(BaseEmbeddingProvider):
        @property
        def dimension(self) -> int:
            return 1024

        @property
        def model_name(self) -> str:
            return "exact-match"

        async def embed_texts(self, texts: list[str]) -> list[list[float]]:
            return [vec_a]

        async def embed_query(self, query: str) -> list[float]:
            return vec_a

    service = VectorRetrievalService(provider=ExactMatchProvider())

    # Execute vector retrieval via service
    response = service.retrieve_sync(
        db=db_session,
        kb_id=kb.id,
        query="algorithms",
        top_k=10,
    )

    # NULL embedding must be excluded: only 2 chunks returned
    assert response.total_results == 2
    assert len(response.results) == 2

    # Chunk A (identical vector) must be first with cosine distance ~ 0.0
    top_result = response.results[0]
    assert top_result.chunk_id == chunk_a.id
    assert top_result.cosine_distance < 0.001
    assert top_result.similarity > 0.999
    assert top_result.document_title == "curriculum.pdf"

    # Chunk B must be second
    second_result = response.results[1]
    assert second_result.chunk_id == chunk_b.id
    assert second_result.cosine_distance > top_result.cosine_distance
    assert second_result.similarity < top_result.similarity


# ------------------------------------------------------------------------------
# API Endpoint Integration Tests
# ------------------------------------------------------------------------------


def test_admin_vector_retrieval_success(
    api_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Admin retrieves vector-matched chunks from their own knowledge base."""
    admin = create_user(db_session, "admin_retrieval@univ.edu", role=UserRole.ADMIN)
    kb = create_kb(db_session, admin, name="CS Core")
    doc = create_document(db_session, kb, filename="syllabus.pdf")

    provider = ControlledMockEmbeddingProvider()
    vec1 = provider._make_vector("data structures")
    vec2 = provider._make_vector("web development")

    create_chunk(db_session, doc, kb, 0, "Binary search trees and AVL trees", embedding=vec1)
    create_chunk(db_session, doc, kb, 1, "HTML CSS JavaScript fundamentals", embedding=vec2)

    # Override default retrieval service provider
    custom_service = VectorRetrievalService(provider=provider)
    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.retrieval.get_retrieval_service",
        lambda: custom_service,
    )

    # Authenticate as Admin
    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    resp = api_client.post(
        f"/api/v1/knowledge-bases/{kb.id}/retrieve",
        json={"query": "data structures", "top_k": 5},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "data structures"
    assert data["knowledge_base_id"] == str(kb.id)
    assert data["total_results"] == 2
    assert len(data["results"]) == 2

    first = data["results"][0]
    assert "Binary search trees" in first["text"]
    assert first["document_title"] == "syllabus.pdf"
    assert "cosine_distance" in first
    assert "similarity" in first
    # Direct mathematical conversion without clamping
    assert abs(first["similarity"] - (1.0 - first["cosine_distance"])) < 1e-5


def test_top_k_parameter_limits_returned_chunks(
    api_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """top_k limit restricts returned chunks to requested count."""
    admin = create_user(db_session, "admin_topk@univ.edu", role=UserRole.ADMIN)
    kb = create_kb(db_session, admin)
    doc = create_document(db_session, kb)

    provider = ControlledMockEmbeddingProvider()
    for i in range(5):
        vec = provider._make_vector(f"chunk number {i}")
        create_chunk(db_session, doc, kb, i, f"Content for chunk {i}", embedding=vec)

    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.retrieval.get_retrieval_service",
        lambda: VectorRetrievalService(provider=provider),
    )

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    # Request top_k=2 out of 5 chunks
    resp = api_client.post(
        f"/api/v1/knowledge-bases/{kb.id}/retrieve",
        json={"query": "chunk", "top_k": 2},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_results"] == 2
    assert len(data["results"]) == 2


def test_student_membership_retrieval_authorization(
    api_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Verifies knowledge-base authorization and isolation:
    - Student with membership can retrieve chunks (HTTP 200).
    - Student without membership receives HTTP 404 (preventing existence leakage).
    """
    admin = create_user(db_session, "admin_kb_owner@univ.edu", role=UserRole.ADMIN)
    student = create_user(db_session, "student_access@univ.edu", role=UserRole.STUDENT)

    kb_authorized = create_kb(db_session, admin, name="Enrolled Course")
    kb_private = create_kb(db_session, admin, name="Faculty Private")
    kb_private.is_student_visible = False
    db_session.commit()
    db_session.refresh(kb_private)

    # Grant student membership to kb_authorized only
    membership = KnowledgeBaseMember(
        knowledge_base_id=kb_authorized.id,
        user_id=student.id,
    )
    db_session.add(membership)
    db_session.commit()

    doc_auth = create_document(db_session, kb_authorized)
    doc_priv = create_document(db_session, kb_private)

    provider = ControlledMockEmbeddingProvider()
    create_chunk(
        db_session,
        doc_auth,
        kb_authorized,
        0,
        "Public course syllabus",
        embedding=provider._make_vector("syllabus"),
    )
    create_chunk(
        db_session,
        doc_priv,
        kb_private,
        0,
        "Private exam answers",
        embedding=provider._make_vector("exam"),
    )

    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.retrieval.get_retrieval_service",
        lambda: VectorRetrievalService(provider=provider),
    )

    # Log in as Student
    api_client.post(
        "/api/v1/auth/login",
        json={"email": student.email, "password": "SecurePassword123!"},
    )

    # 1. Authorized KB search succeeds
    resp_auth = api_client.post(
        f"/api/v1/knowledge-bases/{kb_authorized.id}/retrieve",
        json={"query": "syllabus", "top_k": 5},
    )
    assert resp_auth.status_code == 200
    assert resp_auth.json()["total_results"] == 1

    # 2. Unauthorized KB search returns 404 (existence leakage protection)
    resp_priv = api_client.post(
        f"/api/v1/knowledge-bases/{kb_private.id}/retrieve",
        json={"query": "exam", "top_k": 5},
    )
    assert resp_priv.status_code == 404
    assert "Knowledge base not found" in resp_priv.json()["detail"]


def test_foreign_kb_chunks_never_leak(
    api_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Verifies that chunks from another knowledge base are never returned, even if their
    vectors are an identical match to the search query.
    """
    admin_a = create_user(db_session, "admin_a@univ.edu", role=UserRole.ADMIN)
    admin_b = create_user(db_session, "admin_b@univ.edu", role=UserRole.ADMIN)

    kb_a = create_kb(db_session, admin_a, name="KB A")
    kb_b = create_kb(db_session, admin_b, name="KB B")

    doc_a = create_document(db_session, kb_a, filename="doc_a.pdf")
    doc_b = create_document(db_session, kb_b, filename="doc_b.pdf")

    provider = ControlledMockEmbeddingProvider()
    identical_vector = provider._make_vector("secret data")

    # Add chunk to KB A and identical chunk to KB B
    chunk_a = create_chunk(db_session, doc_a, kb_a, 0, "Data in KB A", embedding=identical_vector)
    create_chunk(db_session, doc_b, kb_b, 0, "Data in KB B", embedding=identical_vector)

    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.retrieval.get_retrieval_service",
        lambda: VectorRetrievalService(provider=provider),
    )

    # Admin A logs in and retrieves from KB A
    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin_a.email, "password": "SecurePassword123!"},
    )

    resp = api_client.post(
        f"/api/v1/knowledge-bases/{kb_a.id}/retrieve",
        json={"query": "secret data", "top_k": 10},
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 1
    assert results[0]["chunk_id"] == str(chunk_a.id)
    assert results[0]["knowledge_base_id"] == str(kb_a.id)


def test_unauthenticated_retrieval_returns_401(api_client: TestClient) -> None:
    """Unauthenticated retrieval requests return HTTP 401 Unauthorized."""
    api_client.cookies.clear()
    fake_kb_id = uuid.uuid4()
    resp = api_client.post(
        f"/api/v1/knowledge-bases/{fake_kb_id}/retrieve",
        json={"query": "test query"},
    )
    assert resp.status_code == 401


def test_nonexistent_kb_returns_404(
    api_client: TestClient,
    db_session: Session,
) -> None:
    """Request for nonexistent knowledge base returns HTTP 404."""
    admin = create_user(db_session, "admin_nonexistent@univ.edu", role=UserRole.ADMIN)
    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    resp = api_client.post(
        f"/api/v1/knowledge-bases/{uuid.uuid4()}/retrieve",
        json={"query": "test query"},
    )
    assert resp.status_code == 404


def test_empty_knowledge_base_returns_empty_results(
    api_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Knowledge base with no indexed documents returns empty results list []."""
    admin = create_user(db_session, "admin_empty@univ.edu", role=UserRole.ADMIN)
    kb = create_kb(db_session, admin, name="Empty KB")

    provider = ControlledMockEmbeddingProvider()
    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.retrieval.get_retrieval_service",
        lambda: VectorRetrievalService(provider=provider),
    )

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    resp = api_client.post(
        f"/api/v1/knowledge-bases/{kb.id}/retrieve",
        json={"query": "any query"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_results"] == 0
    assert data["results"] == []


def test_provider_failure_returns_controlled_503(
    api_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Embedding provider failure returns HTTP 503 without leaking stack traces or credentials."""
    admin = create_user(db_session, "admin_fail@univ.edu", role=UserRole.ADMIN)
    kb = create_kb(db_session, admin)

    # Provider configured to fail
    failing_provider = ControlledMockEmbeddingProvider(fail=True)
    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.retrieval.get_retrieval_service",
        lambda: VectorRetrievalService(provider=failing_provider),
    )

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    resp = api_client.post(
        f"/api/v1/knowledge-bases/{kb.id}/retrieve",
        json={"query": "test query"},
    )
    assert resp.status_code == 503
    assert "Embedding provider unavailable" in resp.json()["detail"]


def test_duplicate_chunk_text_remains_distinguishable(
    api_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Two chunks with identical text content remain distinguishable by
    chunk_id and chunk_index.
    """
    admin = create_user(db_session, "admin_dups@univ.edu", role=UserRole.ADMIN)
    kb = create_kb(db_session, admin)
    doc = create_document(db_session, kb)

    provider = ControlledMockEmbeddingProvider()
    vec = provider._make_vector("duplicate text")

    chunk1 = create_chunk(db_session, doc, kb, 0, "Duplicate sentence.", embedding=vec)
    chunk2 = create_chunk(db_session, doc, kb, 1, "Duplicate sentence.", embedding=vec)

    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.retrieval.get_retrieval_service",
        lambda: VectorRetrievalService(provider=provider),
    )

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    resp = api_client.post(
        f"/api/v1/knowledge-bases/{kb.id}/retrieve",
        json={"query": "duplicate text", "top_k": 5},
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 2

    # Verify both chunks are distinct
    ids = {r["chunk_id"] for r in results}
    assert ids == {str(chunk1.id), str(chunk2.id)}
    indices = [r["chunk_index"] for r in results]
    # Deterministic secondary ordering: index 0 before index 1
    assert indices == [0, 1]


def test_unicode_query_handling(
    api_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unicode query text is supported and retrieves indexed chunks."""
    admin = create_user(db_session, "admin_unicode@univ.edu", role=UserRole.ADMIN)
    kb = create_kb(db_session, admin)
    doc = create_document(db_session, kb)

    provider = ControlledMockEmbeddingProvider()
    unicode_content = "Graph theory: ∀ v ∈ V, deg(v) ≥ δ(G) vertex analysis."
    vec = provider._make_vector(unicode_content)

    chunk = create_chunk(db_session, doc, kb, 0, unicode_content, embedding=vec)

    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.retrieval.get_retrieval_service",
        lambda: VectorRetrievalService(provider=provider),
    )

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    resp = api_client.post(
        f"/api/v1/knowledge-bases/{kb.id}/retrieve",
        json={"query": "Graph theory: ∀ v ∈ V", "top_k": 5},
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 1
    assert results[0]["chunk_id"] == str(chunk.id)
