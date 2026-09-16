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
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select

from backend.app.db.session import get_db_session
from backend.app.models.document import Document, DocumentChunk, DocumentStatus
from backend.app.services.chunking import document_chunker
from backend.app.services.parsers.factory import get_parser
from backend.app.services.storage import storage_service

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """
    Coordinates the document ingestion lifecycle: parsing -> chunking -> atomic DB insertion.
    """

    def process_document(self, document_id: uuid.UUID) -> bool:
        """
        Process an uploaded document through the complete ingestion pipeline.

        Args:
            document_id: UUID of the document record to process.

        Returns:
            True if ingestion succeeded (COMPLETED), False if failed (FAILED).
        """
        logger.info("Starting ingestion processing for document: %s", document_id)

        # 1. Mark document as PROCESSING in an initial transaction
        with get_db_session() as db:
            doc = db.execute(
                select(Document).where(Document.id == document_id)
            ).scalar_one_or_none()
            if not doc:
                logger.error("Ingestion failed: Document %s not found in database.", document_id)
                return False

            storage_key = str(doc.storage_key)
            file_type = str(doc.file_type)

            doc.status = DocumentStatus.PROCESSING
            doc.error_message = None
            doc.updated_at = datetime.now(UTC)
            db.commit()

        # 2. Parse and chunk the document (untrusted data boundary)
        try:
            abs_file_path = storage_service.get_absolute_path(storage_key)
            if not abs_file_path.exists():
                raise FileNotFoundError(f"Source file not found on disk at {abs_file_path}")

            # Instantiate format-specific parser
            parser = get_parser(file_type)
            parsed_doc = parser.parse(abs_file_path)

            # Generate token-estimated, metadata-preserving chunks
            generated_chunks = document_chunker.chunk_document(parsed_doc)

            if not generated_chunks:
                raise ValueError("Document yielded no extractable textual content or valid chunks.")

            # 3. Atomically persist chunks and update status to COMPLETED
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
                doc_record.error_message = None
                doc_record.updated_at = datetime.now(UTC)
                db.commit()

            logger.info(
                "Ingestion completed for document %s: Generated %d chunks.",
                document_id,
                len(generated_chunks),
            )
            return True

        except Exception as exc:
            logger.exception("Ingestion failed for document %s: %s", document_id, exc)
            safe_error = str(exc)[:500]

            # 4. In case of failure: update status to FAILED and record diagnostic message
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
                        doc_fail.error_message = safe_error
                        doc_fail.updated_at = datetime.now(UTC)
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


def process_document_task(document_id: uuid.UUID) -> None:
    """
    BackgroundTasks entry point for asynchronous document ingestion.
    """
    ingestion_pipeline.process_document(document_id)
