"""
Document Vector Indexing Service and Background Worker.

Coordinates generating dense vector embeddings for ingested document chunks,
persisting incremental progress to the indexing_jobs table, validating vector cardinality
and dimensionality, and atomically persisting vectors in PostgreSQL using pgvector.

Architectural Invariants:
1. Stage Separation: Step 5 ingestion (parsing/chunking) and Step 6 vector indexing
   are strictly separate. Ingestion sets status=COMPLETED and indexing_status=PENDING.
2. External Isolation: Embedding generation via the configured provider (Ollama)
   occurs in small, non-blocking batches outside prolonged PostgreSQL database locks.
3. Live Observability: Each batch completion commits progress (stage, processed_chunks,
   embedded_chunks, progress_percent) to indexing_jobs in PostgreSQL, enabling truthful
   polling from the frontend.
4. Non-Destructive Failure: If vector generation fails or times out, chunks remain intact.
   indexing_jobs and documents transition to FAILED with a safe, human-readable reason.
5. Idempotent Retry: Re-indexing updates existing chunk embeddings without creating duplicate
   records or corrupting vector spaces.
6. Strict Cardinality Verification: A job only transitions to COMPLETED after verifying
   that count(chunk.embedding IS NOT NULL) == total_chunks and all match EMBEDDING_DIM.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select

from backend.app.core.config import settings
from backend.app.db.session import get_db_session
from backend.app.models.document import Document, DocumentChunk, DocumentStatus, IndexingStatus
from backend.app.models.indexing_job import IndexingJob, IndexingJobStage, IndexingJobStatus
from backend.app.services.embedding.base import BaseEmbeddingProvider
from backend.app.services.embedding.service import get_embedding_service

logger = logging.getLogger(__name__)


def sanitize_indexing_error(exc: Exception) -> str:
    """Produce a safe, actionable error message concealing secrets and tracebacks."""
    err_str = str(exc)
    err_lower = err_str.lower()

    if "timeout" in err_lower or "timed out" in err_lower:
        return (
            f"Embedding service timed out ({settings.OLLAMA_EMBED_TIMEOUT}s). "
            "Please verify Ollama is running and responsive, then retry."
        )
    if "connect" in err_lower or "connection" in err_lower:
        return (
            f"Unable to connect to embedding service at {settings.OLLAMA_BASE_URL}. "
            "Please ensure Ollama is running locally ('ollama serve')."
        )
    if "dimension" in err_lower:
        return f"Embedding dimension mismatch: {err_str[:120]}"

    # Fallback to sanitized prefix
    clean = err_str.split("\n")[0].strip()
    return (
        f"Vector indexing failed: {clean[:150]}"
        if clean
        else "Vector indexing failed unexpectedly."
    )


class IndexingPipeline:
    """
    Coordinates dense vector indexing of document chunks into PostgreSQL/pgvector
    with persistent job tracking and batch-level progress updates.
    """

    def __init__(self, provider: BaseEmbeddingProvider | None = None) -> None:
        self._custom_provider = provider

    def _get_provider(self) -> BaseEmbeddingProvider:
        if self._custom_provider is not None:
            return self._custom_provider
        return get_embedding_service().provider

    def create_or_reuse_job(
        self,
        document_id: uuid.UUID,
        knowledge_base_id: uuid.UUID,
    ) -> IndexingJob:
        """
        Create a new indexing job or prepare an existing one for retry.
        Prevents starting duplicate jobs if one is actively running.
        """
        with get_db_session() as db:
            # Check for existing job
            job = (
                db.execute(
                    select(IndexingJob)
                    .where(IndexingJob.document_id == document_id)
                    .order_by(IndexingJob.created_at.desc())
                )
                .scalars()
                .first()
            )

            now = datetime.now(UTC)

            if job and job.status in (
                IndexingJobStatus.QUEUED.value,
                IndexingJobStatus.PROCESSING.value,
            ):
                # Active job already in progress; return it
                db.expunge(job)
                return job

            # Count total chunks
            total_chunks = db.execute(
                select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == document_id)
            ).scalar_one()

            if job:
                # Reuse/retry existing job record
                job.status = IndexingJobStatus.QUEUED.value
                job.stage = IndexingJobStage.PREPARING.value
                job.total_chunks = total_chunks
                job.processed_chunks = 0
                job.embedded_chunks = 0
                job.indexed_chunks = 0
                job.progress_percent = 0.0
                job.started_at = now
                job.completed_at = None
                job.error_message = None
                job.attempt_number += 1
                job.updated_at = now
            else:
                job = IndexingJob(
                    id=uuid.uuid4(),
                    document_id=document_id,
                    knowledge_base_id=knowledge_base_id,
                    status=IndexingJobStatus.QUEUED.value,
                    stage=IndexingJobStage.PREPARING.value,
                    total_chunks=total_chunks,
                    processed_chunks=0,
                    embedded_chunks=0,
                    indexed_chunks=0,
                    progress_percent=0.0,
                    started_at=now,
                    completed_at=None,
                    error_message=None,
                    attempt_number=1,
                )
                db.add(job)

            # Ensure document reflects processing indexing state
            doc = db.execute(
                select(Document).where(Document.id == document_id)
            ).scalar_one_or_none()
            if doc:
                doc.indexing_status = IndexingStatus.PROCESSING
                doc.indexing_error = None
                doc.updated_at = now

            db.commit()
            db.refresh(job)
            db.expunge(job)
            return job

    async def index_document_async(
        self,
        document_id: uuid.UUID,
        job_id: uuid.UUID | None = None,
    ) -> bool:
        """
        Asynchronously generate embeddings in small batches, save progress,
        and verify stored vector cardinality in PostgreSQL.
        """
        logger.info(
            "Starting persistent vector indexing for document: %s (job: %s)", document_id, job_id
        )
        provider = self._get_provider()
        batch_size = max(1, settings.OLLAMA_EMBED_BATCH_SIZE)

        # 1. Verification and Transition to PROCESSING
        with get_db_session() as db:
            doc = db.execute(
                select(Document).where(Document.id == document_id)
            ).scalar_one_or_none()
            if not doc:
                logger.error("Indexing failed: Document %s not found.", document_id)
                self._record_failure(document_id, job_id, "Document not found in database.")
                return False

            if doc.status != DocumentStatus.COMPLETED:
                msg = (
                    f"Document is not eligible for indexing. Ingestion status is '{doc.status}' "
                    "(must be COMPLETED)."
                )
                logger.warning(msg)
                self._record_failure(document_id, job_id, msg)
                return False

            # Load or resolve job
            job = None
            if job_id:
                job = db.execute(
                    select(IndexingJob).where(IndexingJob.id == job_id)
                ).scalar_one_or_none()
            if not job:
                job = (
                    db.execute(
                        select(IndexingJob)
                        .where(IndexingJob.document_id == document_id)
                        .order_by(IndexingJob.created_at.desc())
                    )
                    .scalars()
                    .first()
                )

            now = datetime.now(UTC)
            if job:
                job.status = IndexingJobStatus.PROCESSING.value
                job.stage = IndexingJobStage.PREPARING.value
                job.started_at = job.started_at or now
                job.error_message = None
                job.updated_at = now

            doc.indexing_status = IndexingStatus.PROCESSING
            doc.indexing_error = None
            doc.updated_at = now
            db.commit()

        # 2. Fetch chunks ordered by chunk_index
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
            chunk_data = [(c.id, c.text, c.chunk_index) for c in chunks]

        total_chunks = len(chunk_data)

        # Handle zero-chunk documents
        if total_chunks == 0:
            logger.info("Document %s has 0 chunks to index. Marking COMPLETED.", document_id)
            with get_db_session() as db:
                doc = db.execute(
                    select(Document).where(Document.id == document_id)
                ).scalar_one_or_none()
                if doc:
                    doc.indexing_status = IndexingStatus.COMPLETED
                    doc.indexed_at = datetime.now(UTC)
                    doc.indexing_error = None
                if job_id:
                    j = db.execute(
                        select(IndexingJob).where(IndexingJob.id == job_id)
                    ).scalar_one_or_none()
                    if j:
                        j.status = IndexingJobStatus.COMPLETED.value
                        j.stage = IndexingJobStage.COMPLETED.value
                        j.progress_percent = 100.0
                        j.completed_at = datetime.now(UTC)
                db.commit()
            return True

        # Update job with total chunks
        with get_db_session() as db:
            if job_id:
                j = db.execute(
                    select(IndexingJob).where(IndexingJob.id == job_id)
                ).scalar_one_or_none()
                if j:
                    j.total_chunks = total_chunks
                    j.stage = IndexingJobStage.EMBEDDING.value
                    db.commit()

        # 3. Process chunks in configurable batches with live progress persistence
        processed_count = 0
        try:
            for start_idx in range(0, total_chunks, batch_size):
                batch = chunk_data[start_idx : start_idx + batch_size]
                batch_texts = [text for _, text, _ in batch]

                # Generate dense vectors via embedding provider
                embeddings = await provider.embed_texts(batch_texts)

                # Validate count and dimensions
                if len(embeddings) != len(batch):
                    raise ValueError(
                        f"Embedding count mismatch: Expected {len(batch)}, received {len(embeddings)}."
                    )
                for emb in embeddings:
                    if len(emb) != provider.dimension:
                        raise ValueError(
                            f"Embedding dimension mismatch: Expected {provider.dimension}, got {len(emb)}."
                        )

                # Commit batch vectors and incremental progress atomically
                with get_db_session() as db:
                    for (c_id, _, _), emb in zip(batch, embeddings, strict=True):
                        c_row = db.execute(
                            select(DocumentChunk).where(DocumentChunk.id == c_id)
                        ).scalar_one()
                        c_row.embedding = emb

                    processed_count += len(batch)
                    pct = round((processed_count / total_chunks) * 100.0, 1)

                    if job_id:
                        j = db.execute(
                            select(IndexingJob).where(IndexingJob.id == job_id)
                        ).scalar_one_or_none()
                        if j:
                            j.embedded_chunks = processed_count
                            j.indexed_chunks = processed_count
                            j.processed_chunks = processed_count
                            j.progress_percent = pct
                            j.updated_at = datetime.now(UTC)

                    db.commit()

                logger.info(
                    "Indexed batch %d-%d / %d (%.1f%%) for document %s",
                    start_idx + 1,
                    start_idx + len(batch),
                    total_chunks,
                    round((processed_count / total_chunks) * 100.0, 1),
                    document_id,
                )

            # 4. Verification Stage
            with get_db_session() as db:
                if job_id:
                    j = db.execute(
                        select(IndexingJob).where(IndexingJob.id == job_id)
                    ).scalar_one_or_none()
                    if j:
                        j.stage = IndexingJobStage.VERIFYING.value
                        db.commit()

                # Verify all chunk vectors exist in PostgreSQL
                stored_vectors = db.execute(
                    select(func.count(DocumentChunk.id)).where(
                        DocumentChunk.document_id == document_id,
                        DocumentChunk.embedding.is_not(None),
                    )
                ).scalar_one()

                if stored_vectors != total_chunks:
                    raise ValueError(
                        f"Vector verification mismatch: Expected {total_chunks} vectors, but found {stored_vectors}."
                    )

                # 5. Success Completion
                now = datetime.now(UTC)
                doc = db.execute(select(Document).where(Document.id == document_id)).scalar_one()
                doc.indexing_status = IndexingStatus.COMPLETED
                doc.indexed_at = now
                doc.indexing_error = None
                doc.updated_at = now

                if job_id:
                    j = db.execute(select(IndexingJob).where(IndexingJob.id == job_id)).scalar_one()
                    j.status = IndexingJobStatus.COMPLETED.value
                    j.stage = IndexingJobStage.COMPLETED.value
                    j.progress_percent = 100.0
                    j.embedded_chunks = total_chunks
                    j.indexed_chunks = total_chunks
                    j.processed_chunks = total_chunks
                    j.completed_at = now
                    j.updated_at = now

                db.commit()

            logger.info(
                "Successfully completed and verified vector indexing for document %s.", document_id
            )
            return True

        except Exception as exc:
            logger.error("Vector indexing failed for document %s: %s", document_id, exc)
            safe_error = sanitize_indexing_error(exc)
            self._record_failure(document_id, job_id, safe_error)
            return False

    def index_document(
        self,
        document_id: uuid.UUID,
        job_id: uuid.UUID | None = None,
    ) -> bool:
        """Synchronous wrapper for vector indexing."""
        return asyncio.run(self.index_document_async(document_id, job_id=job_id))

    def _record_failure(
        self,
        document_id: uuid.UUID,
        job_id: uuid.UUID | None,
        error_message: str,
    ) -> None:
        """Record FAILED status and error details in a fresh database session."""
        try:
            now = datetime.now(UTC)
            with get_db_session() as db:
                doc = db.execute(
                    select(Document).where(Document.id == document_id)
                ).scalar_one_or_none()
                if doc:
                    doc.indexing_status = IndexingStatus.FAILED
                    doc.indexing_error = error_message
                    doc.updated_at = now

                if job_id:
                    j = db.execute(
                        select(IndexingJob).where(IndexingJob.id == job_id)
                    ).scalar_one_or_none()
                    if j:
                        j.status = IndexingJobStatus.FAILED.value
                        j.stage = IndexingJobStage.FAILED.value
                        j.error_message = error_message
                        j.completed_at = now
                        j.updated_at = now

                db.commit()
        except Exception as db_err:
            logger.error(
                "Failed to record indexing failure for document %s: %s", document_id, db_err
            )


indexing_pipeline = IndexingPipeline()


def index_document_task(
    document_id: uuid.UUID,
    job_id: uuid.UUID | None = None,
    provider: BaseEmbeddingProvider | None = None,
) -> None:
    """
    BackgroundTasks / Worker entry point for asynchronous document vector indexing.
    Creates and closes its own fresh database session.
    """
    pipeline = IndexingPipeline(provider=provider) if provider else indexing_pipeline
    pipeline.index_document(document_id, job_id=job_id)
