"""
Document Ingestion Pipeline Service.

Executes parsing, normalization, token-aware chunking, and atomic database persistence
for uploaded documents within the modular monolith architecture.

Reliability Invariants (Addressing Correction #2):
1. Atomic Persistence: Chunks and status transitions are committed within database transactions.
   If chunk insertion or parsing fails midway, chunks are rolled back; partial chunks are never persisted.
2. Failure Transparency: Exceptions transition the document record to FAILED with safe diagnostic
   error details recorded for administrator inspection. Documents do not remain stranded in PROCESSING.
3. Safe Retries: Documents in PENDING or FAILED states can be reprocessed cleanly. Any preexisting
   chunks are cleared prior to re-chunking.
4. Untrusted Content: All parsed content is treated as untrusted text data; it is never executed
   or evaluated as application instructions.
"""

import logging
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select

from backend.app.core.config import settings
from backend.app.db.session import get_db_session
from backend.app.models.document import Document, DocumentChunk, DocumentStatus, IndexingStatus
from backend.app.models.indexing_job import IndexingJob, IndexingJobStage, IndexingJobStatus
from backend.app.services.chunking import document_chunker
from backend.app.services.ocr import ocr_service
from backend.app.services.parsers.base import ParsedSection
from backend.app.services.parsers.factory import get_parser
from backend.app.services.storage import storage_service
from backend.app.services.vision import get_vision_provider, pdf_visual_extractor

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """
    Coordinates the document ingestion lifecycle: parsing -> chunking -> atomic DB insertion
    -> automatic progression to vector indexing.
    """

    def process_document(
        self,
        document_id: uuid.UUID,
        auto_index: bool = True,
        job_id: uuid.UUID | None = None,
    ) -> bool:
        """
        Process an uploaded document through the complete ingestion pipeline.

        Args:
            document_id: UUID of the document record to process.
            auto_index: Whether to automatically queue and initiate vector indexing upon successful ingestion.
            job_id: Optional UUID of a persistent IndexingJob tracking this operation.

        Returns:
            True if ingestion succeeded (COMPLETED), False if failed (FAILED).
        """
        logger.info(
            "Starting ingestion processing for document: %s (auto_index=%s, job_id=%s)",
            document_id,
            auto_index,
            job_id,
        )

        now = datetime.now(UTC)
        t_start = time.monotonic()

        # 1. Mark document and persistent job as PROCESSING / EXTRACTING
        with get_db_session() as db:
            doc = db.execute(
                select(Document).where(Document.id == document_id)
            ).scalar_one_or_none()
            if not doc:
                logger.error("Ingestion failed: Document %s not found in database.", document_id)
                return False

            storage_key = str(doc.storage_key)
            file_type = str(doc.file_type)
            kb_id = doc.knowledge_base_id

            doc.status = DocumentStatus.PROCESSING
            doc.error_message = None
            doc.updated_at = now

            # Locate or create persistent job record for stage tracking
            job = None
            if job_id:
                job = db.execute(select(IndexingJob).where(IndexingJob.id == job_id)).scalar_one_or_none()
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

            if job:
                job.status = IndexingJobStatus.PROCESSING.value
                job.stage = IndexingJobStage.EXTRACTING.value
                job.error_message = None
                job.updated_at = now
            else:
                job = IndexingJob(
                    id=uuid.uuid4(),
                    document_id=document_id,
                    knowledge_base_id=kb_id,
                    status=IndexingJobStatus.PROCESSING.value,
                    stage=IndexingJobStage.EXTRACTING.value,
                    started_at=now,
                    attempt_number=1,
                )
                db.add(job)

            db.commit()
            active_job_id = job.id

        # 2. Parse and chunk the document (untrusted data boundary)
        try:
            abs_file_path = storage_service.get_absolute_path(storage_key)
            if not abs_file_path.exists():
                raise FileNotFoundError(f"Source file not found on disk at {abs_file_path}")

            # Stage: Text Parsing
            t_parse = time.monotonic()
            parser = get_parser(file_type)
            parsed_doc = parser.parse(abs_file_path)
            parse_duration_ms = (time.monotonic() - t_parse) * 1000
            logger.info(
                "Ingestion stage text_parsing completed: doc_id=%s, duration_ms=%.1f, sections=%d",
                document_id,
                parse_duration_ms,
                len(parsed_doc.sections),
            )

            # Phase 11A: Multimodal PDF Visual Content Analysis
            visual_note: str | None = None
            vis_detect_duration_ms = 0.0
            vis_infer_duration_ms = 0.0
            if file_type.lower() == "pdf" and settings.VISION_PROCESSING_ENABLED:
                t_vis_detect = time.monotonic()
                candidates = pdf_visual_extractor.detect_candidates(abs_file_path)
                vis_detect_duration_ms = (time.monotonic() - t_vis_detect) * 1000
                logger.info(
                    "Ingestion stage visual_detection completed: doc_id=%s, duration_ms=%.1f, candidates=%d",
                    document_id,
                    vis_detect_duration_ms,
                    len(candidates),
                )

                if candidates:
                    vision_provider = get_vision_provider()
                    if vision_provider.is_available():
                        with get_db_session() as db:
                            j_vis = db.execute(
                                select(IndexingJob).where(IndexingJob.id == active_job_id)
                            ).scalar_one_or_none()
                            if j_vis:
                                j_vis.stage = IndexingJobStage.EXTRACTING_VISUALS.value
                                j_vis.updated_at = datetime.now(UTC)
                                db.commit()

                        processed_count = 0
                        failed_count = 0
                        t_vis_infer = time.monotonic()
                        for cand in candidates:
                            try:
                                img_bytes = pdf_visual_extractor.render_page(abs_file_path, cand.page_number)

                                # Optional selective OCR context hint if OCR is available
                                ocr_hint = None
                                if ocr_service.is_available()[0]:
                                    try:
                                        import pymupdf
                                        with pymupdf.open(str(abs_file_path)) as fdoc:
                                            fpage = fdoc[cand.page_number - 1]
                                            ocr_text = ocr_service.ocr_page(fpage, cand.page_number, cache_key=str(abs_file_path))
                                            if ocr_text:
                                                ocr_hint = f"OCR legible text: {ocr_text[:300]}"
                                    except Exception as ocr_err:
                                        logger.debug("Selective OCR on visual page %d skipped: %s", cand.page_number, ocr_err)

                                res = vision_provider.analyze_image_sync(img_bytes, cand.page_number, context_hint=ocr_hint)
                                if res.is_success:
                                    visual_section = ParsedSection(
                                        text=res.to_section_text(),
                                        page_number=cand.page_number,
                                        section_title=f"Visual Evidence — Page {cand.page_number}: {res.visual_type.title()}",
                                        metadata={
                                            "source_modality": "visual",
                                            "visual_type": res.visual_type,
                                            "model_name": res.model_name,
                                            "page": cand.page_number,
                                            "reasons": cand.reasons,
                                            "visual_summary": res.summary,
                                        },
                                    )
                                    parsed_doc.sections.append(visual_section)
                                    processed_count += 1
                                else:
                                    failed_count += 1
                                    logger.warning(
                                        "Visual analysis failed on Page %d: %s",
                                        cand.page_number,
                                        res.error,
                                    )
                            except Exception as exc:
                                failed_count += 1
                                logger.warning(
                                    "Exception during visual processing of Page %d: %s",
                                    cand.page_number,
                                    exc,
                                )

                        vis_infer_duration_ms = (time.monotonic() - t_vis_infer) * 1000
                        logger.info(
                            "Ingestion stage visual_inference completed: doc_id=%s, duration_ms=%.1f, processed=%d, failed=%d",
                            document_id,
                            vis_infer_duration_ms,
                            processed_count,
                            failed_count,
                        )

                        total_detected = pdf_visual_extractor.last_scan_total_detected or len(candidates)
                        skipped_due_to_cap = pdf_visual_extractor.last_scan_skipped_count

                        if failed_count > 0:
                            visual_note = f"Visual analysis partial: {processed_count}/{total_detected} visual pages analyzed ({failed_count} failed)."
                        elif skipped_due_to_cap > 0:
                            visual_note = f"Visual analysis partial: {processed_count}/{total_detected} visual pages analyzed ({skipped_due_to_cap} skipped due to page limit)."
                        else:
                            visual_note = f"Visual analysis complete: {processed_count} visual pages analyzed."
                    else:
                        visual_note = f"Visual analysis skipped: Vision model ({settings.OLLAMA_VISION_MODEL}) not installed/reachable. Text indexed."
                        logger.info("Vision model unavailable; proceeding with text extraction only.")

            # Update stage to CHUNKING
            with get_db_session() as db:
                j_chunk = db.execute(
                    select(IndexingJob).where(IndexingJob.id == active_job_id)
                ).scalar_one_or_none()
                if j_chunk:
                    j_chunk.stage = IndexingJobStage.CHUNKING.value
                    if visual_note:
                        j_chunk.error_message = visual_note
                    j_chunk.updated_at = datetime.now(UTC)
                    db.commit()

            # Stage: Token-estimated, metadata-preserving chunking
            t_chunk = time.monotonic()
            generated_chunks = document_chunker.chunk_document(parsed_doc)
            chunk_duration_ms = (time.monotonic() - t_chunk) * 1000

            if not generated_chunks:
                raise ValueError("Document yielded no extractable textual content or valid chunks.")

            total_chunks = len(generated_chunks)
            logger.info(
                "Ingestion stage chunking completed: doc_id=%s, duration_ms=%.1f, chunks=%d",
                document_id,
                chunk_duration_ms,
                total_chunks,
            )

            # 3. Atomically persist chunks and update status to COMPLETED
            t_persist = time.monotonic()
            with get_db_session() as db:
                doc_record = db.execute(
                    select(Document).where(Document.id == document_id)
                ).scalar_one()

                # Clean up any preexisting chunks (safe idempotency for retries)
                db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))

                # Bulk insert generated chunks
                chunk_entities = [
                    DocumentChunk(
                        id=chunk.id,
                        document_id=doc_record.id,
                        knowledge_base_id=doc_record.knowledge_base_id,
                        chunk_index=chunk.chunk_index,
                        text=chunk.text,
                        token_count=chunk.token_count,
                        page_number=chunk.page_number,
                        section_title=chunk.section_title,
                        chunk_metadata=chunk.chunk_metadata,
                        created_at=datetime.now(UTC),
                    )
                    for chunk in generated_chunks
                ]
                db.add_all(chunk_entities)

                # Finalize document state
                doc_record.status = DocumentStatus.COMPLETED
                if visual_note:
                    doc_record.error_message = visual_note
                doc_record.updated_at = datetime.now(UTC)

                # Update job with chunk counts
                j_update = db.execute(
                    select(IndexingJob).where(IndexingJob.id == active_job_id)
                ).scalar_one_or_none()
                if j_update:
                    j_update.total_chunks = total_chunks
                    j_update.stage = (
                        IndexingJobStage.QUEUED_FOR_INDEXING.value
                        if auto_index
                        else IndexingJobStage.QUEUED_FOR_INDEXING.value
                    )
                    if visual_note:
                        j_update.error_message = visual_note
                    j_update.status = IndexingJobStatus.QUEUED.value
                    j_update.updated_at = datetime.now(UTC)

                db.commit()

            persist_duration_ms = (time.monotonic() - t_persist) * 1000
            total_duration_ms = (time.monotonic() - t_start) * 1000
            logger.info(
                "Ingestion completed for document %s: generated %d chunks (persist=%.1fms, total=%.1fms).",
                document_id,
                total_chunks,
                persist_duration_ms,
                total_duration_ms,
            )

            # 4. Automatically queue indexing when authorized
            if auto_index:
                from backend.app.services.indexing import index_document_task, indexing_pipeline
                from backend.app.services.indexing_worker import notify_indexing_worker

                # Ensure job is primed in QUEUED state
                indexing_pipeline.create_or_reuse_job(document_id, kb_id)
                notify_indexing_worker()
                index_document_task(document_id, active_job_id)

            return True

        except Exception as exc:
            logger.exception("Ingestion failed for document %s: %s", document_id, exc)
            safe_error = str(exc)[:500]

            # 5. In case of failure: update status to FAILED and record diagnostic message
            try:
                with get_db_session() as db:
                    doc_fail = db.execute(
                        select(Document).where(Document.id == document_id)
                    ).scalar_one_or_none()
                    if doc_fail:
                        # Ensure no partial chunks are left persisted
                        db.execute(
                            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
                        )
                        doc_fail.status = DocumentStatus.FAILED
                        doc_fail.indexing_status = IndexingStatus.FAILED
                        doc_fail.error_message = safe_error
                        doc_fail.updated_at = datetime.now(UTC)

                    # Update indexing job record to FAILED
                    j_fail = db.execute(
                        select(IndexingJob).where(IndexingJob.id == active_job_id)
                    ).scalar_one_or_none()
                    if j_fail:
                        j_fail.status = IndexingJobStatus.FAILED.value
                        j_fail.stage = IndexingJobStage.FAILED.value
                        j_fail.error_message = safe_error
                        j_fail.completed_at = datetime.now(UTC)
                        j_fail.updated_at = datetime.now(UTC)

                    db.commit()
            except Exception as update_err:
                logger.error(
                    "Failed to record FAILED status for document %s: %s",
                    document_id,
                    update_err,
                )

            return False


# Singleton ingestion pipeline instance
ingestion_pipeline = IngestionPipeline()


def process_document_task(
    document_id: uuid.UUID,
    auto_index: bool = True,
    job_id: uuid.UUID | None = None,
) -> None:
    """
    BackgroundTasks entry point for asynchronous document ingestion and automatic indexing.
    """
    ingestion_pipeline.process_document(document_id, auto_index=auto_index, job_id=job_id)
