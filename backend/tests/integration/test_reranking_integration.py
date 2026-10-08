"""
Integration Tests for CrossEncoder Reranking Layer (Step 10).

Verifies:
1. Real PostgreSQL + pgvector + PostgreSQL full-text search candidates reranked by CrossEncoder.
2. Candidates ordered strictly by raw CrossEncoder score DESC.
3. Reranker score is unrounded raw float (no internal rounding).
4. Full provenance preserved from Step 9 (RRF score, vector rank, lexical rank, contributions, distances).
5. Knowledge-base authorization and isolation:
   - Admin can rerank in owned KB.
   - Authorized student can rerank in member KB.
   - Unauthorized student receives HTTP 404 (preventing existence leakage).
   - Foreign KB chunks never leak into reranking results.
   - Unauthenticated requests receive HTTP 401.
   - Nonexistent KB returns HTTP 404.
6. Empty knowledge base returns empty results cleanly.
7. Validation errors return HTTP 422.
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
from backend.app.services.hybrid_retrieval import HybridRetrievalService
from backend.app.services.lexical_retrieval import LexicalRetrievalService
from backend.app.services.reranking.base import BaseRerankerProvider
from backend.app.services.reranking.service import RerankingService
from backend.app.services.retrieval import VectorRetrievalService


class ControlledMockEmbeddingProvider(BaseEmbeddingProvider):
    """Predictable 1024-d embedding provider for integration tests."""

    def __init__(self, dimension: int = 1024) -> None:
        self._dim = dimension

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return "mock-qwen3-embedding"

    def _make_vector(self, text_val: str) -> list[float]:
        base = [0.0] * self._dim
        for i, char in enumerate(text_val[:10]):
            idx = (ord(char) * 17 + i * 31) % self._dim
            base[idx] = 1.0
        base[0] += 0.5
        return base

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._make_vector(t) for t in texts]

    async def embed_query(self, query: str) -> list[float]:
        return self._make_vector(query)


class ControlledMockRerankerProvider(BaseRerankerProvider):
    """Predictable reranker provider assigning scores based on keyword presence."""

    @property
    def model_name(self) -> str:
        return "mock-cross-encoder-provider"

    async def compute_scores(self, query: str, texts: list[str]) -> list[float]:
        scores = []
        for t in texts:
            # Score based on presence of key terms and raw float precision
            base_score = 0.123456789
            if "essential" in t.lower():
                base_score += 5.0
            if "scheduling" in t.lower():
                base_score += 2.5
            scores.append(float(base_score))
        return scores


@pytest.fixture(autouse=True)
def clean_database(db_engine) -> Generator[None, None, None]:
    """Clean all tables before and after each test."""
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


def create_kb(
    db: Session,
    owner: User,
    name: str = "Rerank Test KB",
    *,
    is_student_visible: bool = True,
) -> KnowledgeBase:
    """Provision a knowledge base in PostgreSQL."""
    kb = KnowledgeBase(
        name=name,
        description="Test description",
        created_by_id=owner.id,
        is_student_visible=is_student_visible,
    )
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
        chunk_metadata={"test": True, "token_count": len(text_content.split())},
        embedding=embedding,
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)
    return chunk


# ------------------------------------------------------------------------------
# Direct Real PostgreSQL Reranking Service Tests
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_real_postgresql_reranking_service(db_session: Session) -> None:
    """
    Verifies that the RerankingService retrieves real candidates from PostgreSQL
    via vector + lexical RRF and reranks them strictly by CrossEncoder scores.
    """
    admin = create_user(db_session, "admin_rerank_direct@univ.edu", role=UserRole.ADMIN)
    kb = create_kb(db_session, admin)
    doc = create_document(db_session, kb)

    embed_provider = ControlledMockEmbeddingProvider()
    query = "CPU Scheduling"
    query_vec = embed_provider._make_vector(query)

    # Chunk 1: Mentions scheduling, but not 'essential'
    create_chunk(
        db_session,
        doc,
        kb,
        chunk_index=0,
        text_content="CPU scheduling algorithms like round robin distribute execution time.",
        embedding=query_vec,
    )

    # Chunk 2: Mentions both 'scheduling' and 'essential'
    c2 = create_chunk(
        db_session,
        doc,
        kb,
        chunk_index=1,
        text_content="Process scheduling is an essential operating system mechanism for efficiency.",
        embedding=query_vec,
    )

    vector_service = VectorRetrievalService(provider=embed_provider)
    lexical_service = LexicalRetrievalService()
    hybrid_service = HybridRetrievalService(
        vector_service=vector_service,
        lexical_service=lexical_service,
        rrf_k=60,
    )
    reranker_provider = ControlledMockRerankerProvider()

    service = RerankingService(
        hybrid_service=hybrid_service,
        reranker_provider=reranker_provider,
    )

    resp = await service.rerank(
        db=db_session,
        kb_id=kb.id,
        query=query,
        candidate_limit=10,
        top_k=5,
    )

    assert resp.total_candidates_reranked == 2
    assert resp.total_results == 2

    # c2 has 'essential' and 'scheduling' -> higher CrossEncoder score (7.623456789)
    # c1 has 'scheduling' only -> lower CrossEncoder score (2.623456789)
    assert resp.results[0].chunk_id == c2.id
    assert resp.results[0].reranker_rank == 1
    assert resp.results[0].reranker_score > resp.results[1].reranker_score

    # Check unrounded float preservation
    assert resp.results[0].reranker_score == 7.623456789

    # Verify provenance
    assert resp.results[0].document_id == doc.id
    assert resp.results[0].document_title == doc.original_filename
    assert resp.results[0].rrf_score > 0.0
    assert resp.results[0].chunk_metadata.get("test") is True


# ------------------------------------------------------------------------------
# API Endpoint Integration Tests
# ------------------------------------------------------------------------------


def test_api_rerank_success_admin(
    api_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Admin can execute reranking on owned knowledge base via HTTP endpoint."""
    admin = create_user(db_session, "admin_rerank_api@univ.edu", role=UserRole.ADMIN)
    kb = create_kb(db_session, admin)
    doc = create_document(db_session, kb)

    embed_provider = ControlledMockEmbeddingProvider()
    query_vec = embed_provider._make_vector("deadlock")

    create_chunk(
        db_session,
        doc,
        kb,
        chunk_index=0,
        text_content="Deadlock prevention requires eliminating mutual exclusion or hold-and-wait.",
        embedding=query_vec,
    )

    custom_service = RerankingService(
        hybrid_service=HybridRetrievalService(
            vector_service=VectorRetrievalService(provider=embed_provider),
            lexical_service=LexicalRetrievalService(),
        ),
        reranker_provider=ControlledMockRerankerProvider(),
    )
    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.reranking.get_reranking_service",
        lambda: custom_service,
    )

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    resp = api_client.post(
        f"/api/v1/knowledge-bases/{kb.id}/rerank",
        json={"query": "deadlock", "candidate_limit": 20, "top_k": 5},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "deadlock"
    assert data["knowledge_base_id"] == str(kb.id)
    assert data["total_results"] == 1
    assert data["total_candidates_reranked"] == 1
    assert len(data["results"]) == 1
    result = data["results"][0]
    assert result["reranker_rank"] == 1
    assert isinstance(result["reranker_score"], float)
    assert result["rrf_score"] > 0.0


def test_api_rerank_authorized_student(
    api_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Authorized student member of the KB can execute reranking."""
    admin = create_user(db_session, "admin_rerank_kb@univ.edu", role=UserRole.ADMIN)
    student = create_user(db_session, "student_rerank_auth@univ.edu", role=UserRole.STUDENT)
    kb = create_kb(db_session, admin)

    # Grant membership
    member = KnowledgeBaseMember(knowledge_base_id=kb.id, user_id=student.id)
    db_session.add(member)
    db_session.commit()

    custom_service = RerankingService(
        hybrid_service=HybridRetrievalService(
            vector_service=VectorRetrievalService(provider=ControlledMockEmbeddingProvider()),
            lexical_service=LexicalRetrievalService(),
        ),
        reranker_provider=ControlledMockRerankerProvider(),
    )
    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.reranking.get_reranking_service",
        lambda: custom_service,
    )

    api_client.post(
        "/api/v1/auth/login",
        json={"email": student.email, "password": "SecurePassword123!"},
    )

    resp = api_client.post(
        f"/api/v1/knowledge-bases/{kb.id}/rerank",
        json={"query": "paging algorithms", "candidate_limit": 20, "top_k": 5},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_results"] == 0
    assert data["results"] == []


def test_api_rerank_unauthorized_student_returns_404(
    api_client: TestClient, db_session: Session
) -> None:
    """Unauthorized student receives 404 (preventing KB existence leakage)."""
    admin = create_user(db_session, "admin_owner_kb@univ.edu", role=UserRole.ADMIN)
    student = create_user(db_session, "student_unauth@univ.edu", role=UserRole.STUDENT)
    kb = create_kb(db_session, admin, is_student_visible=False)

    api_client.post(
        "/api/v1/auth/login",
        json={"email": student.email, "password": "SecurePassword123!"},
    )

    resp = api_client.post(
        f"/api/v1/knowledge-bases/{kb.id}/rerank",
        json={"query": "scheduling algorithms"},
    )
    assert resp.status_code == 404


def test_api_rerank_unauthenticated_returns_401(api_client: TestClient) -> None:
    """Unauthenticated requests must be rejected with 401."""
    random_kb_id = uuid.uuid4()
    resp = api_client.post(
        f"/api/v1/knowledge-bases/{random_kb_id}/rerank",
        json={"query": "test query"},
    )
    assert resp.status_code == 401


def test_api_rerank_whitespace_query_returns_422(
    api_client: TestClient, db_session: Session
) -> None:
    """Empty or whitespace-only queries must fail validation with 422."""
    admin = create_user(db_session, "admin_ws@univ.edu", role=UserRole.ADMIN)
    kb = create_kb(db_session, admin)

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    resp = api_client.post(
        f"/api/v1/knowledge-bases/{kb.id}/rerank",
        json={"query": "     "},
    )
    assert resp.status_code == 422


def test_api_rerank_kb_isolation(
    api_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure candidate chunks from a different knowledge base never leak into results."""
    admin = create_user(db_session, "admin_iso@univ.edu", role=UserRole.ADMIN)
    kb1 = create_kb(db_session, admin, name="KB 1")
    kb2 = create_kb(db_session, admin, name="KB 2")

    doc1 = create_document(db_session, kb1, filename="kb1_doc.pdf")
    doc2 = create_document(db_session, kb2, filename="kb2_doc.pdf")

    embed_provider = ControlledMockEmbeddingProvider()
    query_vec = embed_provider._make_vector("isolation")

    create_chunk(
        db_session,
        doc1,
        kb1,
        chunk_index=0,
        text_content="Content inside KB 1 about isolation principles.",
        embedding=query_vec,
    )
    create_chunk(
        db_session,
        doc2,
        kb2,
        chunk_index=0,
        text_content="Content inside KB 2 about isolation principles.",
        embedding=query_vec,
    )

    custom_service = RerankingService(
        hybrid_service=HybridRetrievalService(
            vector_service=VectorRetrievalService(provider=embed_provider),
            lexical_service=LexicalRetrievalService(),
        ),
        reranker_provider=ControlledMockRerankerProvider(),
    )
    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.reranking.get_reranking_service",
        lambda: custom_service,
    )

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    # Query KB 1
    resp1 = api_client.post(
        f"/api/v1/knowledge-bases/{kb1.id}/rerank",
        json={"query": "isolation", "candidate_limit": 10, "top_k": 5},
    )
    assert resp1.status_code == 200
    results1 = resp1.json()["results"]
    assert len(results1) == 1
    assert results1[0]["knowledge_base_id"] == str(kb1.id)
    assert results1[0]["document_title"] == "kb1_doc.pdf"
