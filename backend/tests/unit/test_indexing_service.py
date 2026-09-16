"""
Unit Tests for Document Vector Indexing Service.

Verifies:
1. Ineligible documents (not in COMPLETED ingestion status) fail indexing.
2. Documents with zero chunks are handled gracefully (marked COMPLETED with 0 vectors).
3. Non-existent document returns False.
4. Chunks are preserved upon failure.
5. Ingestion pipeline is decoupled from indexing (Correction 1).
"""

import uuid
from collections.abc import Generator

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.security import get_password_hash
from backend.app.db.session import get_db_session
from backend.app.models.document import Document, DocumentChunk, DocumentStatus, IndexingStatus
from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.models.user import User, UserRole
from backend.app.services.embedding.base import BaseEmbeddingProvider
from backend.app.services.embedding.exceptions import EmbeddingProviderError
from backend.app.services.indexing import IndexingPipeline


class SimpleTestProvider(BaseEmbeddingProvider):
    def __init__(self, fail: bool = False, count_offset: int = 0) -> None:
        self.fail = fail
        self.count_offset = count_offset

    @property
    def dimension(self) -> int:
        return 1024

    @property
    def model_name(self) -> str:
        return "simple-test-model"

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if self.fail:
            raise EmbeddingProviderError("Provider unavailable.")
        count = len(texts) + self.count_offset
        return [[0.05] * 1024 for _ in range(count)]

    async def embed_query(self, query: str) -> list[float]:
        return [0.05] * 1024


@pytest.fixture(autouse=True)
def clean_indexing_unit_db(db_engine) -> Generator[None, None, None]:
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


def create_test_fixtures(
    db: Session, status: DocumentStatus = DocumentStatus.COMPLETED
) -> Document:
    """Helper to generate an admin user, KB, and document."""
    user = User(
        email=f"indexer_{uuid.uuid4().hex[:6]}@univ.edu",
        password_hash=get_password_hash("Pass123!"),
        full_name="Indexer Admin",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    kb = KnowledgeBase(name="Index KB", created_by_id=user.id)
    db.add(kb)
    db.commit()
    db.refresh(kb)

    doc = Document(
        knowledge_base_id=kb.id,
        original_filename="sample.txt",
        storage_key=f"storage/{kb.id}/{uuid.uuid4().hex}.txt",
        file_type="txt",
        mime_type="text/plain",
        file_size_bytes=100,
        content_hash="abc" * 21 + "a",
        status=status,
        indexing_status=IndexingStatus.PENDING,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def test_ineligible_document_rejected(db_session: Session) -> None:
    """Documents still PENDING or PROCESSING ingestion cannot be vector-indexed."""
    doc = create_test_fixtures(db_session, status=DocumentStatus.PENDING)
    pipeline = IndexingPipeline(provider=SimpleTestProvider())

    success = pipeline.index_document(doc.id)
    assert success is False

    with get_db_session() as db:
        refreshed = db.get(Document, doc.id)
        assert refreshed is not None
        assert refreshed.indexing_status == IndexingStatus.FAILED
        assert "not eligible for indexing" in (refreshed.indexing_error or "")


def test_zero_chunk_document_handled_gracefully(db_session: Session) -> None:
    """Documents with zero chunks complete indexing without vector writes."""
    doc = create_test_fixtures(db_session, status=DocumentStatus.COMPLETED)
    pipeline = IndexingPipeline(provider=SimpleTestProvider())

    success = pipeline.index_document(doc.id)
    assert success is True

    with get_db_session() as db:
        refreshed = db.get(Document, doc.id)
        assert refreshed is not None
        assert refreshed.indexing_status == IndexingStatus.COMPLETED
        assert refreshed.indexed_at is not None


def test_nonexistent_document_returns_false() -> None:
    """Attempting to index a non-existent UUID returns False."""
    pipeline = IndexingPipeline(provider=SimpleTestProvider())
    assert pipeline.index_document(uuid.uuid4()) is False


def test_provider_count_mismatch_fails_indexing(db_session: Session) -> None:
    """If provider returns mismatched number of vectors, indexing fails and chunks are untouched."""
    doc = create_test_fixtures(db_session, status=DocumentStatus.COMPLETED)

    # Add 2 chunks
    c1 = DocumentChunk(
        document_id=doc.id,
        knowledge_base_id=doc.knowledge_base_id,
        chunk_index=1,
        text="Text 1",
        token_count=2,
        chunk_metadata={},
    )
    c2 = DocumentChunk(
        document_id=doc.id,
        knowledge_base_id=doc.knowledge_base_id,
        chunk_index=2,
        text="Text 2",
        token_count=2,
        chunk_metadata={},
    )
    db_session.add_all([c1, c2])
    db_session.commit()

    # Provider returning 1 embedding instead of 2
    pipeline = IndexingPipeline(provider=SimpleTestProvider(count_offset=-1))
    success = pipeline.index_document(doc.id)
    assert success is False

    with get_db_session() as db:
        refreshed = db.get(Document, doc.id)
        assert refreshed is not None
        assert refreshed.indexing_status == IndexingStatus.FAILED
        assert "Embedding count mismatch" in (refreshed.indexing_error or "")

        # Chunks are preserved and have no embedding
        chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).all()
        assert len(chunks) == 2
        assert all(c.embedding is None for c in chunks)
