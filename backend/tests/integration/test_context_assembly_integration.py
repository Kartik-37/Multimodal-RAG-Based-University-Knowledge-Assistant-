"""
Integration Tests for Context Assembly Layer (Step 12).

Verifies:
1. End-to-end integration: Step 11 Query Processing -> Steps 7-9 Hybrid Retrieval ->
   Step 10 CrossEncoder Reranking -> Step 12 Context Assembly with real PostgreSQL + pgvector.
2. Provenance preservation end-to-end (document title, page, section, scores, ranks, metadata).
3. Evidence integrity: exact chunk text preserved without mutation, truncation, or rewriting.
4. Independent preservation of original query and processed query.
5. Token budget enforcement and candidate selection with real DB-seeded chunks.
6. Knowledge base integrity check with actual retrieved chunks.
"""

import uuid
from collections.abc import Generator

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.security import get_password_hash
from backend.app.models.document import Document, DocumentChunk, DocumentStatus, IndexingStatus
from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.models.user import User, UserRole
from backend.app.services.context_assembly import get_context_assembler
from backend.app.services.embedding.base import BaseEmbeddingProvider
from backend.app.services.hybrid_retrieval import HybridRetrievalService
from backend.app.services.lexical_retrieval import LexicalRetrievalService
from backend.app.services.query_processing import get_query_processor
from backend.app.services.reranking.base import BaseRerankerProvider
from backend.app.services.reranking.service import RerankingService
from backend.app.services.retrieval import VectorRetrievalService


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Predictable 1024-d embedding provider for integration testing."""

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
    """Predictable mock provider returning float scores based on relevance keywords."""

    @property
    def model_name(self) -> str:
        return "mock-reranker"

    async def compute_scores(self, query: str, texts: list[str]) -> list[float]:
        scores = []
        for t in texts:
            score = 0.5
            if "primary" in t.lower() or "first" in t.lower():
                score += 0.4
            if "secondary" in t.lower() or "second" in t.lower():
                score += 0.2
            scores.append(score)
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
    email: str = "assembly_user@university.edu",
    password: str = "SecurePassword123!",
    role: UserRole = UserRole.STUDENT,
) -> User:
    user = User(
        email=email.strip().lower(),
        password_hash=get_password_hash(password),
        full_name="Assembly Test User",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.mark.asyncio
async def test_end_to_end_context_assembly_pipeline(db_session: Session) -> None:
    """
    Verifies complete end-to-end integration:
    QueryProcessor (Step 11) -> Retrieval & Reranking (Steps 7-10) -> ContextAssembler (Step 12).
    """
    user = create_user(db_session, "pipeline_assembly@univ.edu")

    # Create knowledge base
    kb = KnowledgeBase(
        name="Operating Systems KB",
        description="OS concepts for BCA",
        created_by_id=user.id,
    )
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)

    # Create document
    doc = Document(
        knowledge_base_id=kb.id,
        original_filename="operating_systems_notes.pdf",
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
    vec1 = embed_provider._make_vector("scheduling primary")
    vec2 = embed_provider._make_vector("scheduling secondary")

    chunk_text_1 = (
        "   Primary scheduling algorithms include First-Come, First-Served (FCFS) "
        "and Shortest Job First (SJF). Special symbols: C++, CPU-bound, I/O-bound!   "
    )
    chunk_text_2 = (
        "Secondary scheduling algorithms incorporate priority and multi-level feedback queues. "
        "Round Robin ensures fair CPU time distribution."
    )

    chunk1 = DocumentChunk(
        document_id=doc.id,
        knowledge_base_id=kb.id,
        chunk_index=0,
        text=chunk_text_1,
        token_count=18,
        page_number=12,
        section_title="CPU Scheduling",
        chunk_metadata={"source": "lecture_3", "author": "Professor Smith"},
        embedding=vec1,
    )
    chunk2 = DocumentChunk(
        document_id=doc.id,
        knowledge_base_id=kb.id,
        chunk_index=1,
        text=chunk_text_2,
        token_count=20,
        page_number=14,
        section_title="Advanced Scheduling",
        chunk_metadata={"source": "lecture_4", "author": "Professor Smith"},
        embedding=vec2,
    )
    db_session.add_all([chunk1, chunk2])
    db_session.commit()

    # 1. Step 11: Query Processing
    raw_query = "   \t What are primary   CPU   scheduling   algorithms???   \n  "
    processor = get_query_processor()
    processed_query_res = processor.process(raw_query)
    processed_query = processed_query_res.processed_query

    # 2. Step 7 & 8: Retrieval services
    vector_service = VectorRetrievalService(provider=embed_provider)
    lexical_service = LexicalRetrievalService()

    # 3. Step 9: Hybrid Retrieval
    hybrid_service = HybridRetrievalService(
        vector_service=vector_service,
        lexical_service=lexical_service,
    )

    # 4. Step 10: Reranking Service
    reranker_provider = MockRerankerProvider()
    rerank_service = RerankingService(
        hybrid_service=hybrid_service,
        reranker_provider=reranker_provider,
    )

    rerank_resp = await rerank_service.rerank(
        db=db_session,
        kb_id=kb.id,
        query=processed_query,
        candidate_limit=10,
        top_k=5,
    )

    assert len(rerank_resp.results) == 2
    # Verify reranker ordering: chunk1 has "primary" -> score 0.9, chunk2 has "secondary" -> score 0.7
    assert rerank_resp.results[0].chunk_id == chunk1.id
    assert rerank_resp.results[1].chunk_id == chunk2.id

    # 5. Step 12: Context Assembler
    assembler = get_context_assembler()
    assembly_result = assembler.assemble_from_candidates(
        query=processed_query,
        candidates=rerank_resp.results,
        original_query=raw_query,
        token_budget=1000,
        max_items=5,
        knowledge_base_id=kb.id,
    )

    # Verify query preservation
    assert assembly_result.query == processed_query
    assert assembly_result.original_query == raw_query

    # Verify items and ordering
    assert assembly_result.total_items == 2
    assert len(assembly_result.items) == 2
    assert assembly_result.candidates_received == 2
    assert assembly_result.items_skipped_budget == 0
    assert assembly_result.items_deduplicated == 0

    item1 = assembly_result.items[0]
    assert item1.source_id == "source_1"
    assert item1.chunk_id == chunk1.id
    assert item1.document_title == "operating_systems_notes.pdf"
    assert item1.page_number == 12
    assert item1.section_title == "CPU Scheduling"
    assert item1.chunk_metadata == {"source": "lecture_3", "author": "Professor Smith"}
    assert item1.reranker_rank == 1

    # STRICT EVIDENCE INTEGRITY: Exact text character-by-character
    assert item1.text == chunk_text_1
    assert item1.text.startswith("   Primary")
    assert item1.text.endswith("!   ")

    item2 = assembly_result.items[1]
    assert item2.source_id == "source_2"
    assert item2.chunk_id == chunk2.id
    assert item2.text == chunk_text_2
    assert item2.reranker_rank == 2

    # Token accounting
    assert assembly_result.total_estimated_tokens == item1.estimated_tokens + item2.estimated_tokens
    assert (
        assembly_result.metadata["remaining_tokens"]
        == 1000 - assembly_result.total_estimated_tokens
    )


@pytest.mark.asyncio
async def test_pipeline_token_budget_skipping(db_session: Session) -> None:
    """
    Verifies that when token budget is constrained on real retrieval candidates:
    1. Oversized candidate is skipped without truncation.
    2. Subsequent candidate fitting within remaining budget is selected.
    """
    user = create_user(db_session, "budget_assembly@univ.edu")
    kb = KnowledgeBase(name="Budget KB", created_by_id=user.id)
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)

    doc = Document(
        knowledge_base_id=kb.id,
        original_filename="budget_doc.pdf",
        storage_key=f"storage/{kb.id}/doc.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        content_hash=uuid.uuid4().hex + uuid.uuid4().hex,
        status=DocumentStatus.COMPLETED,
        indexing_status=IndexingStatus.COMPLETED,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    embed_provider = MockEmbeddingProvider()
    vec1 = embed_provider._make_vector("large")
    vec2 = embed_provider._make_vector("small")

    # Large chunk (~35 words / tokens)
    large_text = (
        "Primary memory allocation strategies in modern multi-programmed operating systems "
        "rely heavily on paging, segmentation, virtual memory management, page replacement algorithms, "
        "and inverted page tables to optimize physical RAM utilization."
    )
    # Small chunk (~6 words / tokens)
    small_text = "Secondary caching accelerates disk block retrieval."

    chunk_large = DocumentChunk(
        document_id=doc.id,
        knowledge_base_id=kb.id,
        chunk_index=0,
        text=large_text,
        token_count=35,
        embedding=vec1,
    )
    chunk_small = DocumentChunk(
        document_id=doc.id,
        knowledge_base_id=kb.id,
        chunk_index=1,
        text=small_text,
        token_count=6,
        embedding=vec2,
    )
    db_session.add_all([chunk_large, chunk_small])
    db_session.commit()

    vector_service = VectorRetrievalService(provider=embed_provider)
    lexical_service = LexicalRetrievalService()
    hybrid_service = HybridRetrievalService(
        vector_service=vector_service, lexical_service=lexical_service
    )
    rerank_service = RerankingService(
        hybrid_service=hybrid_service,
        reranker_provider=MockRerankerProvider(),
    )

    rerank_resp = await rerank_service.rerank(
        db=db_session, kb_id=kb.id, query="memory caching", top_k=5
    )
    assert len(rerank_resp.results) == 2

    assembler = get_context_assembler()
    estimator = assembler.token_estimator
    large_tokens = estimator.estimate_tokens(large_text)
    small_tokens = estimator.estimate_tokens(small_text)

    # Set budget to fit only small_text (large_text > budget, small_text <= budget)
    tight_budget = small_tokens + 2
    assert large_tokens > tight_budget

    assembly_result = assembler.assemble_from_candidates(
        query="memory caching",
        candidates=rerank_resp.results,
        token_budget=tight_budget,
        knowledge_base_id=kb.id,
    )

    # Candidate 1 (large) was skipped because it exceeded the budget
    # Candidate 2 (small) was selected because it fit into the remaining budget!
    assert assembly_result.total_items == 1
    assert assembly_result.items_skipped_budget == 1
    assert assembly_result.items[0].chunk_id == chunk_small.id
    assert assembly_result.items[0].source_id == "source_1"
    assert assembly_result.items[0].text == small_text


@pytest.mark.asyncio
async def test_pipeline_isolation_integrity_check(db_session: Session) -> None:
    """
    Verifies that ContextAssembler rejects candidates with mismatched knowledge_base_id
    when knowledge_base_id is supplied for integrity verification.
    """
    user = create_user(db_session, "isolation_assembly@univ.edu")
    kb1 = KnowledgeBase(name="KB One", created_by_id=user.id)
    kb2 = KnowledgeBase(name="KB Two", created_by_id=user.id)
    db_session.add_all([kb1, kb2])
    db_session.commit()

    doc = Document(
        knowledge_base_id=kb1.id,
        original_filename="doc1.pdf",
        storage_key=f"storage/{kb1.id}/doc1.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        content_hash=uuid.uuid4().hex + uuid.uuid4().hex,
        status=DocumentStatus.COMPLETED,
        indexing_status=IndexingStatus.COMPLETED,
    )
    db_session.add(doc)
    db_session.commit()

    embed_provider = MockEmbeddingProvider()
    vec = embed_provider._make_vector("content")
    chunk = DocumentChunk(
        document_id=doc.id,
        knowledge_base_id=kb1.id,
        chunk_index=0,
        text="Content belonging to KB One.",
        token_count=5,
        embedding=vec,
    )
    db_session.add(chunk)
    db_session.commit()

    vector_service = VectorRetrievalService(provider=embed_provider)
    lexical_service = LexicalRetrievalService()
    hybrid_service = HybridRetrievalService(
        vector_service=vector_service, lexical_service=lexical_service
    )
    rerank_service = RerankingService(
        hybrid_service=hybrid_service,
        reranker_provider=MockRerankerProvider(),
    )

    rerank_resp = await rerank_service.rerank(db=db_session, kb_id=kb1.id, query="content", top_k=5)
    assert len(rerank_resp.results) == 1

    assembler = get_context_assembler()

    # Mismatched target KB ID raises ValueError
    with pytest.raises(ValueError, match="does not match expected target knowledge base"):
        assembler.assemble_from_candidates(
            query="content",
            candidates=rerank_resp.results,
            knowledge_base_id=kb2.id,  # Target is kb2, but chunk is from kb1
        )
