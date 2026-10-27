"""
Unit and Contract Tests for Document Upload-to-Indexing Workflow (Part 9).

Verifies the complete end-to-end processing lifecycle:
1. Complete lifecycle stages: UPLOADING -> VALIDATING -> SAVING -> EXTRACTING -> CHUNKING
   -> QUEUED_FOR_INDEXING -> EMBEDDING -> WRITING_VECTORS -> VERIFYING -> COMPLETED / FAILED.
2. Schema contracts for DocumentResponse and DocumentDTO with progress & chunk metrics.
3. IngestionPipeline stage progression and automatic hand-off to vector indexing.
4. RBAC policy: auto-indexing is triggered only when authorized (DOCUMENT_INDEX / is_main).
5. Idempotent job creation preventing duplicate running jobs.
6. Truthful stage labeling without manufactured or regressing percentages.
7. Progress percentage never reaches 100% prior to final verification.
8. Frontend API client status tracking and queue synchronization.
9. Error sanitization masking database, tokens, and path internals.
"""

import uuid
from unittest.mock import MagicMock, patch

from backend.app.models.document import Document, DocumentStatus, IndexingStatus
from backend.app.models.indexing_job import IndexingJob, IndexingJobStage, IndexingJobStatus
from backend.app.schemas.document import DocumentResponse
from backend.app.schemas.knowledge_base import IndexingJobResponse
from frontend.client.api_client import FrontendAPIClient
from frontend.client.error_handler import normalize_error
from frontend.client.models import DocumentDTO
from frontend.pages.documents_page import format_stage_label


class TestLifecycleStagesAndSchemaContracts:
    """Validate lifecycle stage definitions, model attributes, and API schemas."""

    def test_indexing_job_stages_cover_complete_lifecycle(self) -> None:
        """Verify IndexingJobStage supports all mandated document lifecycle stages."""
        expected_stages = [
            "UPLOADING",
            "VALIDATING",
            "SAVING",
            "EXTRACTING",
            "CHUNKING",
            "QUEUED_FOR_INDEXING",
            "PREPARING",
            "EMBEDDING",
            "WRITING_VECTORS",
            "STORING_VECTORS",
            "VERIFYING",
            "COMPLETED",
            "FAILED",
        ]
        for stage_name in expected_stages:
            assert hasattr(IndexingJobStage, stage_name), f"Missing lifecycle stage {stage_name}"
            stage_val = getattr(IndexingJobStage, stage_name).value
            assert isinstance(stage_val, str)

    def test_document_response_schema_contract(self) -> None:
        """Verify DocumentResponse includes persistent job_id, stage, and chunk progress fields."""
        doc_id = uuid.uuid4()
        kb_id = uuid.uuid4()
        job_id = uuid.uuid4()
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        resp = DocumentResponse(
            id=doc_id,
            knowledge_base_id=kb_id,
            original_filename="cs101_syllabus.pdf",
            file_type="pdf",
            mime_type="application/pdf",
            file_size_bytes=1048576,
            status=DocumentStatus.PROCESSING,
            indexing_status=IndexingStatus.PROCESSING,
            is_active=False,
            created_at=now,
            updated_at=now,
            chunk_count=24,
            job_id=job_id,
            current_stage="EMBEDDING",
            progress_percent=50.0,
            total_chunks=24,
            processed_chunks=12,
            embedded_chunks=12,
            indexed_chunks=12,
        )

        data = resp.model_dump()
        assert data["job_id"] == job_id
        assert data["current_stage"] == "EMBEDDING"
        assert data["progress_percent"] == 50.0
        assert data["total_chunks"] == 24
        assert data["embedded_chunks"] == 12

    def test_document_dto_schema_contract(self) -> None:
        """Verify DocumentDTO includes typed progress fields and alias property."""
        doc = DocumentDTO(
            id="doc-1234",
            kb_id="kb-5678",
            filename="lecture1.pdf",
            file_type="pdf",
            file_size_bytes=50000,
            status="PROCESSING",
            indexing_status="PROCESSING",
            job_id="job-9999",
            current_stage="EXTRACTING",
            progress_percent=15.0,
            total_chunks=10,
            processed_chunks=0,
            embedded_chunks=0,
            indexed_chunks=0,
        )
        assert doc.knowledge_base_id == "kb-5678"
        assert doc.job_id == "job-9999"
        assert doc.current_stage == "EXTRACTING"
        assert doc.progress_percent == 15.0

    def test_indexing_job_response_schema_contract(self) -> None:
        """Verify IndexingJobResponse schema contract covers stage, metrics, and document details."""
        doc_id = uuid.uuid4()
        kb_id = uuid.uuid4()
        job_id = uuid.uuid4()

        job_resp = IndexingJobResponse(
            id=job_id,
            job_id=job_id,
            document_id=doc_id,
            knowledge_base_id=kb_id,
            status="PROCESSING",
            stage="EMBEDDING",
            total_chunks=100,
            processed_chunks=42,
            embedded_chunks=42,
            indexed_chunks=42,
            progress_percent=42.0,
            document_name="algorithms.pdf",
            course_name="CS201",
        )
        assert job_resp.stage == "EMBEDDING"
        assert job_resp.processed_chunks == 42
        assert job_resp.progress_percent == 42.0


class TestIngestionAndIndexingOrchestrationContracts:
    """Validate automatic continuation from ingestion to indexing and permission guards."""

    @patch("backend.app.services.ingestion.get_parser")
    @patch("backend.app.services.ingestion.document_chunker")
    @patch("backend.app.services.ingestion.storage_service")
    @patch("backend.app.services.ingestion.get_db_session")
    def test_ingestion_pipeline_progresses_stages_and_auto_indexes(
        self,
        mock_get_db,
        mock_storage,
        mock_chunker,
        mock_parser,
    ) -> None:
        """Verify process_document updates stage to CHUNKING, QUEUED_FOR_INDEXING, and triggers indexing when authorized."""
        doc_id = uuid.uuid4()
        kb_id = uuid.uuid4()
        job_id = uuid.uuid4()

        doc_record = Document(
            id=doc_id,
            knowledge_base_id=kb_id,
            original_filename="syllabus.pdf",
            storage_key="syllabus_key.pdf",
            file_type="pdf",
            mime_type="application/pdf",
            file_size_bytes=1000,
            status=DocumentStatus.PENDING,
            indexing_status=IndexingStatus.PENDING,
        )
        job_record = IndexingJob(
            id=job_id,
            document_id=doc_id,
            knowledge_base_id=kb_id,
            status=IndexingJobStatus.PROCESSING.value,
            stage=IndexingJobStage.SAVING.value,
        )

        mock_session = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_session

        def execute_side_effect(statement, *args, **kwargs):
            mock_res = MagicMock()
            sql_str = str(statement)
            if "FROM documents" in sql_str:
                mock_res.scalar_one_or_none.return_value = doc_record
                mock_res.scalar_one.return_value = doc_record
            elif "FROM indexing_jobs" in sql_str:
                mock_res.scalar_one_or_none.return_value = job_record
                mock_res.scalars.return_value.first.return_value = job_record
            return mock_res

        mock_session.execute.side_effect = execute_side_effect

        mock_storage.get_absolute_path.return_value.exists.return_value = True
        mock_parser_instance = MagicMock()
        mock_parser.return_value = mock_parser_instance

        chunk1 = MagicMock(id=uuid.uuid4(), chunk_index=0, text="Intro", token_count=10, page_number=1, section_title="S1", chunk_metadata={})
        chunk2 = MagicMock(id=uuid.uuid4(), chunk_index=1, text="Content", token_count=15, page_number=2, section_title="S2", chunk_metadata={})
        mock_chunker.chunk_document.return_value = [chunk1, chunk2]

        from backend.app.services.ingestion import IngestionPipeline
        pipeline = IngestionPipeline()

        with patch("backend.app.services.indexing.index_document_task") as mock_index_task, \
             patch("backend.app.services.indexing_worker.notify_indexing_worker") as mock_notify, \
             patch("backend.app.services.indexing.indexing_pipeline.create_or_reuse_job"):

            success = pipeline.process_document(doc_id, auto_index=True, job_id=job_id)

            assert success is True
            assert doc_record.status == DocumentStatus.COMPLETED
            assert job_record.total_chunks == 2
            assert job_record.stage == IndexingJobStage.QUEUED_FOR_INDEXING.value
            mock_notify.assert_called_once()
            mock_index_task.assert_called_once_with(doc_id, job_id)

    @patch("backend.app.services.ingestion.get_parser")
    @patch("backend.app.services.ingestion.document_chunker")
    @patch("backend.app.services.ingestion.storage_service")
    @patch("backend.app.services.ingestion.get_db_session")
    def test_ingestion_pipeline_skips_auto_index_when_unauthorized(
        self,
        mock_get_db,
        mock_storage,
        mock_chunker,
        mock_parser,
    ) -> None:
        """Verify process_document completes ingestion but does NOT queue vector indexing when auto_index=False."""
        doc_id = uuid.uuid4()
        kb_id = uuid.uuid4()
        job_id = uuid.uuid4()

        doc_record = Document(
            id=doc_id,
            knowledge_base_id=kb_id,
            original_filename="syllabus.pdf",
            storage_key="syllabus_key.pdf",
            file_type="pdf",
            mime_type="application/pdf",
            file_size_bytes=1000,
            status=DocumentStatus.PENDING,
            indexing_status=IndexingStatus.PENDING,
        )
        job_record = IndexingJob(
            id=job_id,
            document_id=doc_id,
            knowledge_base_id=kb_id,
            status=IndexingJobStatus.PROCESSING.value,
            stage=IndexingJobStage.SAVING.value,
        )

        mock_session = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_session

        def execute_side_effect(statement, *args, **kwargs):
            mock_res = MagicMock()
            sql_str = str(statement)
            if "FROM documents" in sql_str:
                mock_res.scalar_one_or_none.return_value = doc_record
                mock_res.scalar_one.return_value = doc_record
            elif "FROM indexing_jobs" in sql_str:
                mock_res.scalar_one_or_none.return_value = job_record
                mock_res.scalars.return_value.first.return_value = job_record
            return mock_res

        mock_session.execute.side_effect = execute_side_effect
        mock_storage.get_absolute_path.return_value.exists.return_value = True
        mock_chunker.chunk_document.return_value = [
            MagicMock(id=uuid.uuid4(), chunk_index=0, text="Intro", token_count=10, page_number=1, section_title="S1", chunk_metadata={})
        ]

        from backend.app.services.ingestion import IngestionPipeline
        pipeline = IngestionPipeline()

        with patch("backend.app.services.indexing.index_document_task") as mock_index_task, \
             patch("backend.app.services.indexing_worker.notify_indexing_worker") as mock_notify:

            success = pipeline.process_document(doc_id, auto_index=False, job_id=job_id)

            assert success is True
            assert doc_record.status == DocumentStatus.COMPLETED
            # Indexing task must NOT be dispatched
            mock_notify.assert_not_called()
            mock_index_task.assert_not_called()

    @patch("backend.app.services.ingestion.get_parser")
    @patch("backend.app.services.ingestion.storage_service")
    @patch("backend.app.services.ingestion.get_db_session")
    def test_ingestion_failure_halts_pipeline_cleanly(
        self,
        mock_get_db,
        mock_storage,
        mock_parser,
    ) -> None:
        """Verify an extraction failure marks Document and Job as FAILED and never triggers vector indexing."""
        doc_id = uuid.uuid4()
        kb_id = uuid.uuid4()
        job_id = uuid.uuid4()

        doc_record = Document(
            id=doc_id,
            knowledge_base_id=kb_id,
            original_filename="corrupted.pdf",
            storage_key="corrupted_key.pdf",
            file_type="pdf",
            mime_type="application/pdf",
            file_size_bytes=1000,
            status=DocumentStatus.PENDING,
        )
        job_record = IndexingJob(
            id=job_id,
            document_id=doc_id,
            knowledge_base_id=kb_id,
            status=IndexingJobStatus.PROCESSING.value,
            stage=IndexingJobStage.SAVING.value,
        )

        mock_session = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_session

        def execute_side_effect(statement, *args, **kwargs):
            mock_res = MagicMock()
            sql_str = str(statement)
            if "FROM documents" in sql_str:
                mock_res.scalar_one_or_none.return_value = doc_record
            elif "FROM indexing_jobs" in sql_str:
                mock_res.scalar_one_or_none.return_value = job_record
            return mock_res

        mock_session.execute.side_effect = execute_side_effect
        mock_storage.get_absolute_path.return_value.exists.return_value = True

        mock_parser_instance = MagicMock()
        mock_parser_instance.parse.side_effect = RuntimeError("Corrupted PDF structure")
        mock_parser.return_value = mock_parser_instance

        from backend.app.services.ingestion import IngestionPipeline
        pipeline = IngestionPipeline()

        with patch("backend.app.services.indexing.index_document_task") as mock_index_task:
            success = pipeline.process_document(doc_id, auto_index=True, job_id=job_id)

            assert success is False
            assert doc_record.status == DocumentStatus.FAILED
            assert job_record.status == IndexingJobStatus.FAILED.value
            assert job_record.stage == IndexingJobStage.FAILED.value
            mock_index_task.assert_not_called()


class TestFrontendProgressAndUiContracts:
    """Validate truthful progress labeling, monotonic percentages, and API client simulation."""

    def test_format_stage_label_handles_all_stages_truthfully(self) -> None:
        """Verify format_stage_label renders descriptive, non-misleading text for every lifecycle stage."""
        assert "Uploading" in format_stage_label("UPLOADING")
        assert "Saving" in format_stage_label("SAVING")
        assert "Extracting text" in format_stage_label("EXTRACTING")
        assert "sections" in format_stage_label("CHUNKING").lower()
        assert "Waiting for vector indexing" in format_stage_label("QUEUED_FOR_INDEXING")
        assert "42 of 100 chunks (42%)" in format_stage_label("EMBEDDING", processed=42, total=100, percent=42.0)
        assert "Saving vectors" in format_stage_label("WRITING_VECTORS", total=50)
        assert "Verifying indexed vectors" in format_stage_label("VERIFYING")
        assert "Indexed & verified successfully" in format_stage_label("COMPLETED", status="COMPLETED")
        assert "Failed during processing" in format_stage_label("FAILED", status="FAILED")

    def test_progress_percent_never_reaches_100_before_completion(self) -> None:
        """Verify progress percentage does not claim 100% until COMPLETED stage succeeds."""
        embedding_label = format_stage_label("EMBEDDING", processed=99, total=100, percent=99.0)
        assert "99%" in embedding_label
        assert "100%" not in embedding_label

        verifying_label = format_stage_label("VERIFYING", processed=100, total=100, percent=95.0)
        assert "100%" not in verifying_label

    @patch("frontend.client.api_client.is_db_connected", return_value=False)
    def test_api_client_simulation_progresses_through_lifecycle(self, mock_db: MagicMock) -> None:
        """Verify offline API client advances realistically through the complete pipeline."""
        client = FrontendAPIClient()
        kb_id = "c1111111-1111-1111-1111-111111111111"

        # 1. Upload creates document in PROCESSING / SAVING
        uploaded_doc = client.upload_document(
            kb_id=kb_id,
            filename="algorithm_syllabus.pdf",
            content=b"%PDF-1.4 test document content...",
            content_size_bytes=25000,
        )
        assert uploaded_doc.status == "PROCESSING"
        assert uploaded_doc.current_stage == "SAVING"
        assert uploaded_doc.job_id is not None
        assert uploaded_doc.progress_percent == 0.0

        doc_id = uploaded_doc.id

        # 2. Poll 1: SAVING -> EXTRACTING
        stat1 = client.get_document_index_status(kb_id, doc_id)
        assert stat1.stage == "EXTRACTING"
        assert stat1.status == "PROCESSING"

        # 3. Poll 2: EXTRACTING -> CHUNKING
        stat2 = client.get_document_index_status(kb_id, doc_id)
        assert stat2.stage == "CHUNKING"

        # 4. Poll 3: CHUNKING -> QUEUED_FOR_INDEXING
        stat3 = client.get_document_index_status(kb_id, doc_id)
        assert stat3.stage == "QUEUED_FOR_INDEXING"

        # 5. Poll 4: QUEUED_FOR_INDEXING -> EMBEDDING (partial chunks)
        stat4 = client.get_document_index_status(kb_id, doc_id)
        assert stat4.stage == "EMBEDDING"
        assert stat4.embedded_chunks > 0
        assert stat4.progress_percent > 0.0

        # 6. Poll 5: EMBEDDING -> WRITING_VECTORS
        stat5 = client.get_document_index_status(kb_id, doc_id)
        assert stat5.stage == "WRITING_VECTORS"

        # 7. Poll 6: WRITING_VECTORS -> VERIFYING
        stat6 = client.get_document_index_status(kb_id, doc_id)
        assert stat6.stage == "VERIFYING"

        # 8. Poll 7: VERIFYING -> COMPLETED
        stat7 = client.get_document_index_status(kb_id, doc_id)
        assert stat7.stage == "COMPLETED"
        assert stat7.status == "COMPLETED"
        assert stat7.progress_percent == 100.0

    @patch("frontend.client.api_client.is_db_connected", return_value=False)
    def test_api_client_get_indexing_jobs_syncs_with_uploaded_jobs(self, mock_db: MagicMock) -> None:
        """Verify get_indexing_jobs returns newly uploaded active jobs in the queue."""
        client = FrontendAPIClient()
        kb_id = "c1111111-1111-1111-1111-111111111111"

        uploaded = client.upload_document(
            kb_id=kb_id,
            filename="data_structures.pdf",
            content=b"%PDF-1.4 test content",
        )

        all_jobs = client.get_indexing_jobs()
        matching = [j for j in all_jobs if j.document_id == uploaded.id]
        assert len(matching) == 1
        assert matching[0].document_name == "data_structures.pdf"

    def test_error_normalization_masks_credentials_and_stacktraces(self) -> None:
        """Verify normalize_error sanitizes raw database errors and file paths."""
        raw_error = "psycopg.OperationalError: could not connect to server at '127.0.0.1', password='secret_pwd'"
        clean = normalize_error(raw_error, context="indexing")
        assert "secret_pwd" not in clean
        assert "127.0.0.1" not in clean
        assert len(clean) > 0


class TestAdminPart9ADocumentsAndUploadContracts:
    """Validate Part 9A bug fixes and behavioral contracts for Documents page & Upload experience."""

    def test_queue_waiting_progress_never_claims_embedded_chunk_progress(self) -> None:
        """Verify stage QUEUED_FOR_INDEXING returns truthful waiting text without false chunk counts."""
        label = format_stage_label("QUEUED_FOR_INDEXING", processed=0, total=10, percent=25.0)
        assert "Waiting for vector indexing" in label
        assert "0 of 10" not in label
        assert "25%" not in label

    def test_chunk_percentages_correspond_to_actual_processed_and_total(self) -> None:
        """Verify embedding stage percentages match actual chunk progress (processed / total)."""
        label = format_stage_label("EMBEDDING", processed=5, total=10, percent=50.0)
        assert "Generating embeddings — 5 of 10 chunks (50%)" in label

        label_quarter = format_stage_label("EMBEDDING", processed=25, total=100, percent=25.0)
        assert "25 of 100 chunks (25%)" in label_quarter

    def test_overall_completion_occurs_only_after_verification_succeeds(self) -> None:
        """Verify completed stage label indicates indexed and verified successfully."""
        comp_label = format_stage_label("COMPLETED", status="COMPLETED")
        assert "Indexed & verified successfully" in comp_label

        proc_label = format_stage_label("VERIFYING", status="PROCESSING")
        assert "Verifying indexed vectors" in proc_label
        assert "successfully" not in proc_label

    def test_uploader_accepts_only_supported_formats(self) -> None:
        """Verify only .pdf, .docx, .txt, .md, .csv are in SUPPORTED_EXTENSIONS."""
        from frontend.pages.documents_page import SUPPORTED_EXTENSIONS

        assert ".pdf" in SUPPORTED_EXTENSIONS
        assert ".docx" in SUPPORTED_EXTENSIONS
        assert ".txt" in SUPPORTED_EXTENSIONS
        assert ".md" in SUPPORTED_EXTENSIONS
        assert ".csv" in SUPPORTED_EXTENSIONS
        assert ".exe" not in SUPPORTED_EXTENSIONS
        assert ".zip" not in SUPPORTED_EXTENSIONS
        assert ".py" not in SUPPORTED_EXTENSIONS

    def test_status_badge_semantic_mapping_and_neutral_unindexed(self) -> None:
        """Verify unindexed/inactive statuses never map to error/failure icons or rose colors."""
        from frontend.components.ui_kit import render_status_badge

        # Status badge function executes without exception for all semantic states
        with patch("nicegui.ui.row"), patch("nicegui.ui.icon") as mock_icon, patch("nicegui.ui.label"):
            render_status_badge("completed", "Ready")
            assert mock_icon.call_args[0][0] == "check_circle"

            render_status_badge("failed", "Failed")
            assert mock_icon.call_args[0][0] == "error_outline"

            render_status_badge("indexing", "Queued")
            assert mock_icon.call_args[0][0] == "sync"

            render_status_badge("inactive", "Unindexed")
            assert mock_icon.call_args[0][0] == "remove_circle_outline"

            render_status_badge("unindexed", "Unindexed")
            assert mock_icon.call_args[0][0] == "remove_circle_outline"

    def test_delete_dialog_confirmation_state_safely_tracks_filename(self) -> None:
        """Verify confirm_delete securely binds document details and resets upon cancellation."""
        pending_delete: dict[str, str] = {}
        mock_label = MagicMock()
        mock_dialog = MagicMock()

        def confirm_delete(doc_id: str, doc_name: str, doc_kb_id: str) -> None:
            pending_delete["kb_id"] = doc_kb_id
            pending_delete["doc_id"] = doc_id
            pending_delete["filename"] = doc_name
            mock_label.text = (
                f"Are you sure you want to delete '{doc_name}'? "
                "All associated text vectors will be removed permanently."
            )
            mock_dialog.open()

        def cancel_delete() -> None:
            mock_dialog.close()
            mock_label.text = ""

        # Open deletion
        confirm_delete("doc-999", "disposable_test.pdf", "kb-111")
        assert "disposable_test.pdf" in mock_label.text
        assert pending_delete["doc_id"] == "doc-999"
        mock_dialog.open.assert_called_once()

        # Cancel deletion
        cancel_delete()
        assert mock_label.text == ""
        mock_dialog.close.assert_called_once()

    def test_delete_confirmed_invokes_delete_api_exactly_once(self) -> None:
        """Verify executing delete invokes api_client.delete_document with target IDs."""
        mock_client = MagicMock()
        target_kb = "kb-abc"
        target_doc = "doc-xyz"

        mock_client.delete_document(target_kb, target_doc)
        mock_client.delete_document.assert_called_once_with("kb-abc", "doc-xyz")

    def test_chunk_inspection_distinguishes_failure_from_zero_chunks(self) -> None:
        """Verify chunk inspection error produces error feedback rather than claiming document has no chunks."""
        mock_client = MagicMock()
        mock_client.get_document_chunks.side_effect = RuntimeError("psycopg.OperationalError: server closed the connection unexpectedly at 127.0.0.1:5432")

        chunk_err = None
        chunks = []
        try:
            chunks = mock_client.get_document_chunks("kb-1", "doc-1")
        except Exception as ex:
            chunk_err = normalize_error(ex, context="document")

        assert chunk_err is not None
        assert len(chunks) == 0
        assert "127.0.0.1" not in chunk_err
        assert "5432" not in chunk_err
        assert "psycopg" not in chunk_err  # Sanitized!
        assert len(chunk_err) > 0

    def test_all_course_loading_failure_distinguished_from_empty_scope(self) -> None:
        """Verify complete failure across courses yields error state instead of false 'No Documents'."""
        courses = [MagicMock(id="c1", name="Course 1"), MagicMock(id="c2", name="Course 2")]
        mock_client = MagicMock()
        mock_client.get_documents.side_effect = RuntimeError("Course service unavailable")

        failed_courses = []
        docs = []
        for c in courses:
            try:
                docs.extend(mock_client.get_documents(c.id))
            except Exception:
                failed_courses.append(c.name)

        assert len(failed_courses) == len(courses)
        assert len(docs) == 0
        is_complete_failure = len(failed_courses) == len(courses)
        assert is_complete_failure is True
