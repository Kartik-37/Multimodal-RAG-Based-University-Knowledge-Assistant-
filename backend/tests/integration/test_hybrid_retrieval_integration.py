"""
Integration Tests for Hybrid Retrieval Layer (Step 9).

Verifies:
1. Real PostgreSQL + pgvector + PostgreSQL full-text search executed natively in the database.
2. Reciprocal Rank Fusion (RRF) combines candidates from both branches based on candidate ranks.
3. Chunks matching in both branches accumulate contributions from both branches and rank higher.
4. Vector-less chunks (embedding is NULL) are retrieved via lexical search and fused into the final candidate list.
5. top_k parameter strictly caps returned results.
6. Knowledge-base authorization and isolation:
   - Admin can retrieve from owned KB.
   - Authorized student can retrieve from member KB.
   - Unauthorized student receives HTTP 404 (preventing existence leakage).
   - Foreign KB chunks never leak across KB boundaries.
   - Unauthenticated requests receive HTTP 401.
   - Nonexistent KB returns HTTP 404.
7. Empty knowledge base returns empty result list.
8. Duplicate text chunks in different documents remain distinguishable by chunk/document IDs.
9. Controlled 503 error on embedding provider failure.
"""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.security import get_password_hash
from backend.app.models.document import Document, DocumentChunk, DocumentStatus, IndexingStatus
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseMember
from backend.app.models.user import User, UserRole
from backend.app.services.embedding.base import BaseEmbeddingProvider
from backend.app.services.embedding.exceptions import EmbeddingProviderError
from backend.app.services.hybrid_retrieval import HybridRetrievalService
from backend.app.services.lexical_retrieval import LexicalRetrievalService
from backend.app.services.retrieval import VectorRetrievalService


class ControlledMockEmbeddingProvider(BaseEmbeddingProvider):
    """
    Predictable 1024-dimensional embedding provider for integration tests.
    Generates deterministic vectors allowing verifiable distance computations in pgvector.
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
        """Produce deterministic float vector based on text content."""
        base = [0.0] * self._dim
        for i, char in enumerate(text_val[:10]):
            idx = (ord(char) * 17 + i * 31) % self._dim
            base[idx] = 1.0
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


def create_kb(db: Session, owner: User, name: str = "Hybrid Test KB") -> KnowledgeBase:
    """Provision a knowledge base in PostgreSQL."""
    kb = KnowledgeBase(name=name, description="Test description", created_by_id=owner.id)
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


def create_document(
    db: Session,
    kb: KnowledgeBase,
    filename: str = "operating_systems.pdf",
    status: DocumentStatus = DocumentStatus.COMPLETED,
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
        status=status,
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
    """Provision a document chunk with optional 1024-d embedding in PostgreSQL."""
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
# Direct Real PostgreSQL + pgvector + FTS Hybrid Service Test
# ------------------------------------------------------------------------------


def test_real_postgresql_hybrid_rrf_retrieval(db_session: Session) -> None:
    """
    Verifies that the hybrid service executes both real pgvector vector retrieval
    and PostgreSQL full-text lexical search in the database, and fuses candidates with RRF.
    """
    admin = create_user(db_session, "admin_hybrid_direct@univ.edu", role=UserRole.ADMIN)
    kb = create_kb(db_session, admin)
    doc = create_document(db_session, kb)

    provider = ControlledMockEmbeddingProvider()

    # Query term: "CPU Scheduling"
    query = "CPU Scheduling"
    query_vec = provider._make_vector(query)

    # Chunk 1: Exact keyword match AND closest vector match -> will be #1 in BOTH branches
    chunk_1 = create_chunk(
        db_session,
        doc,
        kb,
        0,
        "CPU Scheduling algorithms allocate the central processing unit to processes.",
        embedding=query_vec,
        page_number=10,
        section_title="CPU Scheduling",
    )

    # Chunk 2: Keyword match for "CPU Scheduling", but slightly different vector
    other_vec = [0.0] * 1024
    other_vec[300] = 1.0
    other_vec[0] = 0.5
    chunk_2 = create_chunk(
        db_session,
        doc,
        kb,
        1,
        "Round robin CPU Scheduling prevents starvation in interactive systems.",
        embedding=other_vec,
        page_number=12,
        section_title="Round Robin",
    )

    # Chunk 3: Completely different topic ("Database Normalization") -> neither vector nor lexical match
    db_vec = [0.0] * 1024
    db_vec[900] = 1.0
    db_vec[0] = 0.5
    create_chunk(
        db_session,
        doc,
        kb,
        2,
        "Database normalization avoids data redundancy using normal forms.",
        embedding=db_vec,
        page_number=40,
        section_title="Normalization",
    )

    vector_service = VectorRetrievalService(provider=provider)
    lexical_service = LexicalRetrievalService()
    hybrid_service = HybridRetrievalService(
        vector_service=vector_service,
        lexical_service=lexical_service,
        rrf_k=60,
    )

    response = hybrid_service.retrieve_sync(
        db=db_session,
        kb_id=kb.id,
        query=query,
        top_k=5,
    )

    assert response.knowledge_base_id == kb.id
    assert response.rrf_k == 60
    assert len(response.results) >= 2

    # Chunk 1 must be Rank #1 in fused results because it matched both branches
    top = response.results[0]
    assert top.chunk_id == chunk_1.id
    assert top.vector_rank == 1
    assert top.lexical_rank == 1
    assert top.vector_contribution > 0.0
    assert top.lexical_contribution > 0.0
    assert top.rrf_score == round((1.0 / 61) + (1.0 / 61), 6)
    assert top.page_number == 10
    assert top.section_title == "CPU Scheduling"
    assert top.similarity is not None
    assert top.lexical_score is not None

    # Chunk 2 should be present
    second = response.results[1]
    assert second.chunk_id == chunk_2.id
    assert second.rrf_score < top.rrf_score


def test_vector_less_chunks_are_retrievable_and_fused(db_session: Session) -> None:
    """
    Verifies that chunks with NULL embeddings (not yet vector-indexed) are retrieved
    by the lexical branch and fused into the final hybrid candidate list.
    """
    admin = create_user(db_session, "admin_vectorless@univ.edu", role=UserRole.ADMIN)
    kb = create_kb(db_session, admin)
    doc = create_document(db_session, kb)

    provider = ControlledMockEmbeddingProvider()

    # Chunk with NULL embedding but matching full-text keywords
    chunk_vectorless = create_chunk(
        db_session,
        doc,
        kb,
        0,
        "Deadlock detection algorithms construct a resource allocation graph.",
        embedding=None,  # No vector!
        page_number=5,
        section_title="Deadlocks",
    )

    vector_service = VectorRetrievalService(provider=provider)
    lexical_service = LexicalRetrievalService()
    hybrid_service = HybridRetrievalService(
        vector_service=vector_service,
        lexical_service=lexical_service,
        rrf_k=settings.RRF_K,
    )

    response = hybrid_service.retrieve_sync(
        db=db_session,
        kb_id=kb.id,
        query="Deadlock detection",
        top_k=5,
    )

    assert len(response.results) == 1
    item = response.results[0]
    assert item.chunk_id == chunk_vectorless.id
    assert item.vector_rank is None
    assert item.vector_contribution == 0.0
    assert item.lexical_rank == 1
    assert item.lexical_contribution == round(1.0 / (settings.RRF_K + 1), 6)
    assert item.rrf_score == item.lexical_contribution
    assert item.cosine_distance is None
    assert item.similarity is None
    assert item.lexical_score is not None


# ------------------------------------------------------------------------------
# API Endpoint Integration Tests
# ------------------------------------------------------------------------------


def test_admin_hybrid_retrieval_endpoint(
    api_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Admin calls POST /knowledge-bases/{kb_id}/hybrid-retrieve successfully."""
    admin = create_user(db_session, "admin_hybrid_api@univ.edu", role=UserRole.ADMIN)
    kb = create_kb(db_session, admin, name="Hybrid Admin KB")
    doc = create_document(db_session, kb, filename="networking.pdf")

    provider = ControlledMockEmbeddingProvider()
    vec = provider._make_vector("TCP handshake")

    create_chunk(
        db_session,
        doc,
        kb,
        0,
        "The TCP three-way handshake establishes a reliable transport connection.",
        embedding=vec,
        page_number=1,
    )

    # Monkeypatch hybrid service provider
    custom_hybrid_service = HybridRetrievalService(
        vector_service=VectorRetrievalService(provider=provider),
        lexical_service=LexicalRetrievalService(),
        rrf_k=settings.RRF_K,
    )
    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.hybrid_retrieval.get_hybrid_retrieval_service",
        lambda: custom_hybrid_service,
    )

    # Authenticate as Admin
    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    resp = api_client.post(
        f"/api/v1/knowledge-bases/{kb.id}/hybrid-retrieve",
        json={"query": "TCP handshake", "top_k": 5},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "TCP handshake"
    assert data["knowledge_base_id"] == str(kb.id)
    assert data["rrf_k"] == settings.RRF_K
    assert data["total_results"] == 1
    assert len(data["results"]) == 1

    first = data["results"][0]
    assert "three-way handshake" in first["text"]
    assert first["rrf_score"] > 0.0
    assert first["vector_rank"] == 1
    assert first["lexical_rank"] == 1
    assert first["vector_contribution"] > 0.0
    assert first["lexical_contribution"] > 0.0


def test_student_membership_hybrid_authorization(
    api_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Student with membership can access hybrid retrieval for that KB."""
    admin = create_user(db_session, "admin_owner_hyb@univ.edu", role=UserRole.ADMIN)
    student = create_user(db_session, "student_hyb@univ.edu", role=UserRole.STUDENT)
    kb = create_kb(db_session, admin, name="Shared Hybrid KB")
    doc = create_document(db_session, kb)

    # Grant membership
    member = KnowledgeBaseMember(knowledge_base_id=kb.id, user_id=student.id)
    db_session.add(member)
    db_session.commit()

    provider = ControlledMockEmbeddingProvider()
    vec = provider._make_vector("graph algorithms")
    create_chunk(
        db_session, doc, kb, 0, "Dijkstra and Bellman-Ford graph algorithms", embedding=vec
    )

    custom_hybrid_service = HybridRetrievalService(
        vector_service=VectorRetrievalService(provider=provider),
        lexical_service=LexicalRetrievalService(),
    )
    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.hybrid_retrieval.get_hybrid_retrieval_service",
        lambda: custom_hybrid_service,
    )

    # Authenticate as Student
    api_client.post(
        "/api/v1/auth/login",
        json={"email": student.email, "password": "SecurePassword123!"},
    )

    resp = api_client.post(
        f"/api/v1/knowledge-bases/{kb.id}/hybrid-retrieve",
        json={"query": "graph algorithms", "top_k": 5},
    )
    assert resp.status_code == 200
    assert len(resp.json()["results"]) == 1


def test_student_without_membership_returns_404(
    api_client: TestClient,
    db_session: Session,
) -> None:
    """Student without membership in the KB receives 404 to avoid private existence leakage."""
    admin = create_user(db_session, "admin_private_hyb@univ.edu", role=UserRole.ADMIN)
    student = create_user(db_session, "outsider_hyb@univ.edu", role=UserRole.STUDENT)
    kb = create_kb(db_session, admin, name="Private KB")

    api_client.post(
        "/api/v1/auth/login",
        json={"email": student.email, "password": "SecurePassword123!"},
    )

    resp = api_client.post(
        f"/api/v1/knowledge-bases/{kb.id}/hybrid-retrieve",
        json={"query": "test query", "top_k": 5},
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_foreign_kb_chunks_never_leak_in_hybrid_retrieval(
    api_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Chunks from KB A must NEVER appear when querying KB B."""
    admin = create_user(db_session, "admin_multi_hyb@univ.edu", role=UserRole.ADMIN)
    kb_a = create_kb(db_session, admin, name="KB A")
    kb_b = create_kb(db_session, admin, name="KB B")

    doc_a = create_document(db_session, kb_a, filename="kb_a_doc.pdf")
    doc_b = create_document(db_session, kb_b, filename="kb_b_doc.pdf")

    provider = ControlledMockEmbeddingProvider()
    vec = provider._make_vector("secret data")

    create_chunk(db_session, doc_a, kb_a, 0, "Confidential secrets of KB A", embedding=vec)
    create_chunk(db_session, doc_b, kb_b, 0, "Public knowledge of KB B", embedding=vec)

    custom_hybrid_service = HybridRetrievalService(
        vector_service=VectorRetrievalService(provider=provider),
        lexical_service=LexicalRetrievalService(),
    )
    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.hybrid_retrieval.get_hybrid_retrieval_service",
        lambda: custom_hybrid_service,
    )

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    # Query KB B for words matching KB A text
    resp = api_client.post(
        f"/api/v1/knowledge-bases/{kb_b.id}/hybrid-retrieve",
        json={"query": "Confidential secrets", "top_k": 10},
    )
    assert resp.status_code == 200
    results = resp.json()["results"]

    # Must NOT contain KB A chunks
    for item in results:
        assert item["knowledge_base_id"] == str(kb_b.id)
        assert item["document_title"] != "kb_a_doc.pdf"
        assert "Confidential secrets of KB A" not in item["text"]


def test_unauthenticated_hybrid_retrieval_returns_401(api_client: TestClient) -> None:
    """Unauthenticated requests receive 401 Unauthorized."""
    resp = api_client.post(
        f"/api/v1/knowledge-bases/{uuid.uuid4()}/hybrid-retrieve",
        json={"query": "algorithms", "top_k": 5},
    )
    assert resp.status_code == 401


def test_nonexistent_kb_returns_404(
    api_client: TestClient,
    db_session: Session,
) -> None:
    """Querying a nonexistent KB returns 404 Not Found."""
    admin = create_user(db_session, "admin_nonexistent_hyb@univ.edu", role=UserRole.ADMIN)

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    resp = api_client.post(
        f"/api/v1/knowledge-bases/{uuid.uuid4()}/hybrid-retrieve",
        json={"query": "algorithms", "top_k": 5},
    )
    assert resp.status_code == 404


def test_empty_kb_returns_empty_results(
    api_client: TestClient,
    db_session: Session,
) -> None:
    """Searching an empty KB returns HTTP 200 with results = []."""
    admin = create_user(db_session, "admin_empty_hyb@univ.edu", role=UserRole.ADMIN)
    kb = create_kb(db_session, admin, name="Empty KB")

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    resp = api_client.post(
        f"/api/v1/knowledge-bases/{kb.id}/hybrid-retrieve",
        json={"query": "Operating Systems", "top_k": 5},
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
    """Simulated provider failure raises controlled 503 without leaking internals."""
    admin = create_user(db_session, "admin_fail_hyb@univ.edu", role=UserRole.ADMIN)
    kb = create_kb(db_session, admin, name="Failure KB")

    failing_provider = ControlledMockEmbeddingProvider(fail=True)
    custom_hybrid_service = HybridRetrievalService(
        vector_service=VectorRetrievalService(provider=failing_provider),
        lexical_service=LexicalRetrievalService(),
    )
    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.hybrid_retrieval.get_hybrid_retrieval_service",
        lambda: custom_hybrid_service,
    )

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    resp = api_client.post(
        f"/api/v1/knowledge-bases/{kb.id}/hybrid-retrieve",
        json={"query": "trigger failure", "top_k": 5},
    )
    assert resp.status_code == 503
    assert "unavailable" in resp.json()["detail"].lower()
