"""
Integration Tests for Query Processing Layer (Step 11).

Verifies:
1. POST /api/v1/query/process endpoint with authenticated user session.
2. Unauthenticated request rejection with HTTP 401.
3. Validation errors (e.g. whitespace-only queries) return HTTP 422.
4. Smoke test: raw query normalized via QueryProcessor flows seamlessly through
   vector retrieval (Step 7), lexical retrieval (Step 8), hybrid RRF (Step 9),
   and CrossEncoder reranking (Step 10) without pipeline disruption.
"""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.security import get_password_hash
from backend.app.models.document import Document, DocumentChunk, DocumentStatus, IndexingStatus
from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.models.user import User, UserRole
from backend.app.services.embedding.base import BaseEmbeddingProvider
from backend.app.services.hybrid_retrieval import HybridRetrievalService
from backend.app.services.lexical_retrieval import LexicalRetrievalService
from backend.app.services.query_processing import get_query_processor
from backend.app.services.reranking.base import BaseRerankerProvider
from backend.app.services.reranking.service import RerankingService
from backend.app.services.retrieval import VectorRetrievalService


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Predictable 1024-d embedding provider for integration test."""

    @property
    def dimension(self) -> int:
        return 1024

    @property
    def model_name(self) -> str:
        return "mock-embed"

    def _make_vector(self, text_val: str) -> list[float]:
        base = [0.0] * 1024
        for i, char in enumerate(text_val[:10]):
            idx = (ord(char) * 17 + i * 31) % 1024
            base[idx] = 1.0
        base[0] += 0.5
        return base

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._make_vector(t) for t in texts]

    async def embed_query(self, query: str) -> list[float]:
        return self._make_vector(query)


class MockRerankerProvider(BaseRerankerProvider):
    """Predictable mock provider returning float scores."""

    @property
    def model_name(self) -> str:
        return "mock-reranker"

    async def compute_scores(self, query: str, texts: list[str]) -> list[float]:
        return [float(len(t)) for t in texts]


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
    email: str = "query_user@university.edu",
    password: str = "SecurePassword123!",
    role: UserRole = UserRole.STUDENT,
) -> User:
    user = User(
        email=email.strip().lower(),
        password_hash=get_password_hash(password),
        full_name="Query Test User",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ------------------------------------------------------------------------------
# API Endpoint Tests
# ------------------------------------------------------------------------------


def test_api_query_process_authenticated(api_client: TestClient, db_session: Session) -> None:
    """Authenticated user successfully processes a raw query via HTTP endpoint."""
    user = create_user(db_session, "auth_query@univ.edu")

    api_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "SecurePassword123!"},
    )

    raw_query = "   \t What   are   the   main   BCA   Sem-4   C++   topics?  \n "
    resp = api_client.post(
        "/api/v1/query/process",
        json={"query": raw_query},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["original_query"] == raw_query
    assert data["processed_query"] == "What are the main BCA Sem-4 C++ topics?"
    assert data["character_count"] == len(data["processed_query"])
    assert data["token_estimate"] > 0
    assert data["has_technical_tokens"] is True


def test_api_query_process_unauthenticated_returns_401(api_client: TestClient) -> None:
    """Unauthenticated requests to /query/process must return 401."""
    resp = api_client.post(
        "/api/v1/query/process",
        json={"query": "test query"},
    )
    assert resp.status_code == 401


def test_api_query_process_whitespace_returns_422(
    api_client: TestClient, db_session: Session
) -> None:
    """Whitespace-only query returns 422."""
    user = create_user(db_session, "ws_query@univ.edu")
    api_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "SecurePassword123!"},
    )

    resp = api_client.post(
        "/api/v1/query/process",
        json={"query": "   \t\n  "},
    )
    assert resp.status_code == 422


# ------------------------------------------------------------------------------
# Pipeline Flow Integration Test
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_processed_query_flows_into_retrieval_and_reranking(
    db_session: Session,
) -> None:
    """
    Verifies that a raw query, when processed by QueryProcessor, successfully flows into
    VectorRetrievalService (Step 7), LexicalRetrievalService (Step 8),
    HybridRetrievalService (Step 9), and RerankingService (Step 10) without any errors.
    """
    admin = create_user(db_session, "admin_pipeline@univ.edu", role=UserRole.ADMIN)
    kb = KnowledgeBase(name="Pipeline KB", created_by_id=admin.id)
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)

    doc = Document(
        knowledge_base_id=kb.id,
        original_filename="os_concepts.pdf",
        storage_key=f"storage/{kb.id}/{uuid.uuid4().hex}_os.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size_bytes=2048,
        content_hash=uuid.uuid4().hex + uuid.uuid4().hex,
        status=DocumentStatus.COMPLETED,
        indexing_status=IndexingStatus.COMPLETED,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    embed_provider = MockEmbeddingProvider()
    doc_vec = embed_provider._make_vector("scheduling")

    chunk = DocumentChunk(
        document_id=doc.id,
        knowledge_base_id=kb.id,
        chunk_index=0,
        text="First process scheduling algorithms allocate CPU execution slices to active tasks.",
        token_count=13,
        embedding=doc_vec,
    )
    db_session.add(chunk)
    db_session.commit()

    # 1. Raw user query with messy spacing and Unicode ligatures
    raw_query = "   \t ﬁrst   CPU   scheduling   algorithms   \n\r  "

    # 2. Step 11 Query Processing
    processor = get_query_processor()
    processed_result = processor.process(raw_query)

    assert processed_result.original_query == raw_query
    assert processed_result.processed_query == "first CPU scheduling algorithms"
    query_for_retrieval = processed_result.processed_query

    # 3. Vector Retrieval (Step 7) accepts processed query
    vector_service = VectorRetrievalService(provider=embed_provider)
    vector_resp = await vector_service.retrieve(
        db=db_session, kb_id=kb.id, query=query_for_retrieval, top_k=5
    )
    assert vector_resp.query == query_for_retrieval
    assert len(vector_resp.results) == 1

    # 4. Lexical Retrieval (Step 8) accepts processed query
    lexical_service = LexicalRetrievalService()
    lexical_resp = lexical_service.retrieve(
        db=db_session, kb_id=kb.id, query=query_for_retrieval, top_k=5
    )
    assert lexical_resp.query == query_for_retrieval
    assert len(lexical_resp.results) == 1

    # 5. Hybrid Retrieval (Step 9) accepts processed query
    hybrid_service = HybridRetrievalService(
        vector_service=vector_service,
        lexical_service=lexical_service,
    )
    hybrid_resp = await hybrid_service.retrieve(
        db=db_session, kb_id=kb.id, query=query_for_retrieval, top_k=5
    )
    assert hybrid_resp.query == query_for_retrieval
    assert len(hybrid_resp.results) == 1
    assert hybrid_resp.results[0].chunk_id == chunk.id

    # 6. Reranking Service (Step 10) accepts processed query
    reranker_provider = MockRerankerProvider()
    rerank_service = RerankingService(
        hybrid_service=hybrid_service,
        reranker_provider=reranker_provider,
    )
    rerank_resp = await rerank_service.rerank(
        db=db_session, kb_id=kb.id, query=query_for_retrieval, top_k=5
    )
    assert rerank_resp.query == query_for_retrieval
    assert len(rerank_resp.results) == 1
    assert rerank_resp.results[0].chunk_id == chunk.id
    assert rerank_resp.results[0].reranker_rank == 1
