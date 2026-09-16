"""
Document Vector Indexing Service.

Coordinates generating dense vector embeddings for ingested document chunks,
validating dimensionality and cardinality, and atomically persisting vectors in
PostgreSQL using pgvector.

Architectural Invariants:
1. Stage Separation: Step 5 ingestion (parsing/chunking) and Step 6 vector indexing
   are strictly separate. Ingestion sets status=COMPLETED and indexing_status=PENDING.
2. External Isolation: Embedding generation via the configured provider (Ollama)
   occurs outside PostgreSQL database transactions.
3. Transactional Safety: Chunks' embeddings and the document's indexing_status
   are updated together in a single atomic transaction. Failures roll back; partial
   vector updates are never committed.
4. Non-Destructive Failure: If vector generation or persistence fails, original
   document text and chunks remain intact. indexing_status transitions to FAILED
   with diagnostic details, enabling future retry without re-parsing or re-chunking.
5. Idempotent Retry: Re-indexing updates the embedding column on existing chunk UUIDs
   without duplicating chunks or creating orphaned records.
6. Independent Session: Background tasks instantiate a fresh database session via
   get_db_session() rather than reusing request-scoped sessions.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from backend.app.db.session import get_db_session
from backend.app.models.document import Document, DocumentChunk, DocumentStatus, IndexingStatus
from backend.app.services.embedding.base import BaseEmbeddingProvider
from backend.app.services.embedding.service import get_embedding_service

logger = logging.getLogger(__name__)


class IndexingPipeline:
    """
    Coordinates dense vector indexing of document chunks into PostgreSQL/pgvector.
    """

    def __init__(self, provider: BaseEmbeddingProvider | None = None) -> None:
        self._custom_provider = provider

    def _get_provider(self) -> BaseEmbeddingProvider:
        if self._custom_provider is not None:
            return self._custom_provider
        return get_embedding_service().provider

    async def index_document_async(self, document_id: uuid.UUID) -> bool:
        """
        Asynchronously generate embeddings and update document chunks in pgvector.

        Returns True on success, False on failure.
        """
        logger.info("Starting vector indexing for document: %s", document_id)

        # 1. Eligibility check and transition to PROCESSING
        with get_db_session() as db:
            doc = db.execute(
                select(Document).where(Document.id == document_id)
            ).scalar_one_or_none()
            if not doc:
                logger.error("Indexing failed: Document %s not found.", document_id)
                return False

            if doc.status != DocumentStatus.COMPLETED:
                msg = (
                    f"Document {document_id} is not eligible for indexing. "
                    f"Current ingestion status: {doc.status} (must be COMPLETED)."
                )
                logger.warning(msg)
                doc.indexing_status = IndexingStatus.FAILED
                doc.indexing_error = msg
                db.commit()
                return False

            doc.indexing_status = IndexingStatus.PROCESSING
            doc.indexing_error = None
            db.commit()

        # 2. Fetch chunks (read-only)
        with get_db_session() as db:
            chunks = (
                db.execute(
                    select(DocumentChunk)
                    .where(DocumentChunk.document_id == document_id)
                    .order_by(DocumentChunk.chunk_index)
                )
                .scalars()
                .all()
            )
            chunk_ids = [c.id for c in chunks]
            chunk_texts = [c.text for c in chunks]

        # If document has zero chunks
        if not chunk_ids:
            logger.info("Document %s has 0 chunks to index. Marking COMPLETED.", document_id)
            with get_db_session() as db:
                doc = db.execute(
                    select(Document).where(Document.id == document_id)
                ).scalar_one_or_none()
                if doc:
                    doc.indexing_status = IndexingStatus.COMPLETED
                    doc.indexed_at = datetime.now(UTC)
                    doc.indexing_error = None
                    db.commit()
            return True

        # 3. Generate embeddings OUTSIDE database transaction
        provider = self._get_provider()
        try:
            embeddings = await provider.embed_texts(chunk_texts)
        except Exception as exc:
            logger.error("Embedding generation failed for document %s: %s", document_id, exc)
            self._record_failure(document_id, f"Embedding generation failed: {exc}")
            return False

        # 4. Strict cardinality & validation check (Correction 3)
        if len(embeddings) != len(chunk_ids):
            err_msg = (
                f"Embedding count mismatch: {len(chunk_ids)} chunks requested, "
                f"but received {len(embeddings)} embeddings."
            )
            logger.error(err_msg)
            self._record_failure(document_id, err_msg)
            return False

        # 5. Atomic PostgreSQL persistence
        try:
            with get_db_session() as db:
                doc = db.execute(select(Document).where(Document.id == document_id)).scalar_one()
                db_chunks = (
                    db.execute(
                        select(DocumentChunk)
                        .where(DocumentChunk.document_id == document_id)
                        .order_by(DocumentChunk.chunk_index)
                    )
                    .scalars()
                    .all()
                )

                for chunk, emb in zip(db_chunks, embeddings, strict=True):
                    chunk.embedding = emb

                doc.indexing_status = IndexingStatus.COMPLETED
                doc.indexed_at = datetime.now(UTC)
                doc.indexing_error = None
                db.commit()

            logger.info(
                "Successfully indexed %d chunks for document %s with %d-d vectors.",
                len(embeddings),
                document_id,
                provider.dimension,
            )
            return True

        except Exception as exc:
            logger.error(
                "Failed to commit vectors to database for document %s: %s", document_id, exc
            )
            self._record_failure(document_id, f"Database vector persistence failed: {exc}")
            return False

    def index_document(self, document_id: uuid.UUID) -> bool:
        """Synchronous wrapper for vector indexing."""
        return asyncio.run(self.index_document_async(document_id))

    def _record_failure(self, document_id: uuid.UUID, error_message: str) -> None:
        """Record FAILED status and error details in a fresh database session."""
        try:
            with get_db_session() as db:
                doc = db.execute(
                    select(Document).where(Document.id == document_id)
                ).scalar_one_or_none()
                if doc:
                    doc.indexing_status = IndexingStatus.FAILED
                    doc.indexing_error = error_message
                    doc.updated_at = datetime.now(UTC)
                    db.commit()
        except Exception as db_err:
            logger.error(
                "Failed to record indexing failure for document %s: %s", document_id, db_err
            )


indexing_pipeline = IndexingPipeline()


def index_document_task(
    document_id: uuid.UUID, provider: BaseEmbeddingProvider | None = None
) -> None:
    """
    BackgroundTasks entry point for asynchronous document vector indexing.
    Creates and closes its own fresh database session.
    """
    pipeline = IndexingPipeline(provider=provider) if provider else indexing_pipeline
    pipeline.index_document(document_id)
