"""
Local Background Indexing Worker.

Provides a robust, local-friendly background worker for document vector indexing:
- Operates on the persistent `indexing_jobs` table in PostgreSQL.
- Survives independent of client connections or page refreshes.
- Picks up QUEUED jobs and executes them via IndexingPipeline.
- Interrupted jobs from server restart are safely marked FAILED so they can be retried.
- Wakes up immediately via an asyncio.Event when new jobs are enqueued,
  or periodically every 5 seconds.
"""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from backend.app.db.session import get_db_session
from backend.app.models.document import Document, IndexingStatus
from backend.app.models.indexing_job import IndexingJob, IndexingJobStage, IndexingJobStatus
from backend.app.services.indexing import indexing_pipeline

logger = logging.getLogger(__name__)

_worker_event: asyncio.Event | None = None


def notify_indexing_worker() -> None:
    """Notify the background indexing worker that a new job has been queued."""
    global _worker_event
    if _worker_event is not None:
        try:
            _worker_event.set()
        except RuntimeError:
            pass


async def run_indexing_worker() -> None:
    """
    Continuous background worker loop for processing queued vector indexing jobs.
    Runs inside the FastAPI lifespan context.
    """
    global _worker_event
    _worker_event = asyncio.Event()
    logger.info("Background indexing worker started.")

    # 1. Server-restart recovery: Mark any orphaned 'PROCESSING' jobs as FAILED with retry message
    try:
        with get_db_session() as db:
            orphaned_jobs = (
                db.execute(
                    select(IndexingJob).where(IndexingJob.status == IndexingJobStatus.PROCESSING.value)
                )
                .scalars()
                .all()
            )
            now = datetime.now(UTC)
            for j in orphaned_jobs:
                j.status = IndexingJobStatus.FAILED.value
                j.stage = IndexingJobStage.FAILED.value
                j.error_message = "Indexing was interrupted by a server restart. Please retry."
                j.completed_at = now
                j.updated_at = now

                # Also update document status
                doc = db.execute(select(Document).where(Document.id == j.document_id)).scalar_one_or_none()
                if doc:
                    doc.indexing_status = IndexingStatus.FAILED
                    doc.indexing_error = j.error_message
                    doc.is_active = False
                    doc.updated_at = now

            if orphaned_jobs:
                db.commit()
                logger.info("Recovered %d orphaned indexing jobs from previous server run.", len(orphaned_jobs))
    except Exception as exc:
        logger.error("Error during indexing worker startup recovery: %s", exc)

    # 2. Main processing loop
    while True:
        try:
            # Look for the next queued job
            next_job_id = None
            next_doc_id = None

            with get_db_session() as db:
                job = (
                    db.execute(
                        select(IndexingJob)
                        .where(IndexingJob.status == IndexingJobStatus.QUEUED.value)
                        .order_by(IndexingJob.created_at.asc())
                    )
                    .scalars()
                    .first()
                )
                if job:
                    next_job_id = job.id
                    next_doc_id = job.document_id

            if next_job_id and next_doc_id:
                logger.info("Indexing worker processing job %s for document %s", next_job_id, next_doc_id)
                try:
                    await indexing_pipeline.index_document_async(next_doc_id, job_id=next_job_id)
                except Exception as exc:
                    logger.exception("Unexpected error executing indexing job %s: %s", next_job_id, exc)
                # Immediately loop to check for more queued jobs
                continue

            # No job found; wait for notification or 5 second timeout
            try:
                if _worker_event is not None:
                    await asyncio.wait_for(_worker_event.wait(), timeout=5.0)
                    _worker_event.clear()
                else:
                    await asyncio.sleep(5.0)
            except TimeoutError:
                pass

        except asyncio.CancelledError:
            logger.info("Background indexing worker received cancellation. Shutting down gracefully.")
            break
        except Exception as exc:
            logger.exception("Unexpected error in indexing worker loop: %s", exc)
            await asyncio.sleep(2.0)
