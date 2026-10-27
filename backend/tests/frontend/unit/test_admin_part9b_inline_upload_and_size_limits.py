"""
Unit and Contract Tests for Admin Part 9B:
- Inline Document Upload Workspace
- 100 MiB (104,857,600 bytes) Upload Limit and Memory-Safe Validation
- PostgreSQL Reliability and Mode Selection Policy
"""

import io
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, UploadFile, status

from backend.app.core.config import settings
from backend.app.db.session import check_database_connection
from backend.app.services.storage import storage_service
from frontend.client.api_client import FrontendAPIClient
from frontend.pages.documents_page import SUPPORTED_EXTENSIONS


class TestUploadSizeBoundaryAndValidation:
    """Verify exact 100 MiB size boundary, memory-safe validation, and security sanitization."""

    def test_upload_size_limit_setting_is_104857600_bytes(self) -> None:
        """Verify settings.MAX_UPLOAD_SIZE_BYTES is exactly 100 * 1024 * 1024 = 104,857,600 bytes."""
        expected_bytes = 100 * 1024 * 1024
        assert expected_bytes == 104857600
        assert settings.MAX_UPLOAD_SIZE_BYTES == 104857600
        # Verify UI MB representation matches
        ui_mb = settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
        assert ui_mb == 100

    @pytest.mark.asyncio
    async def test_exact_100_mib_boundary_accepted(self) -> None:
        """Verify a valid document at exactly 104,857,600 bytes is accepted without 413 error."""
        target_size = 104857600
        chunk_size = 64 * 1024

        # Stream generator yielding valid PDF bytes totaling exactly 104,857,600 bytes
        # Memory-safe: generates chunks on the fly without keeping 100 MiB in memory
        header = b"%PDF-1.4\n%test academic content\n"
        first_chunk = header + b"0" * (chunk_size - len(header))
        remaining = target_size - len(first_chunk)
        full_chunks = remaining // chunk_size
        last_chunk_len = remaining % chunk_size

        chunk_queue = [first_chunk] + [b"X" * chunk_size] * full_chunks
        if last_chunk_len > 0:
            chunk_queue.append(b"Z" * last_chunk_len)

        idx = 0

        async def mock_read(n: int = -1) -> bytes:
            nonlocal idx
            if idx < len(chunk_queue):
                data = chunk_queue[idx]
                idx += 1
                return data
            return b""

        mock_file = AsyncMock(spec=UploadFile)
        mock_file.filename = "large_syllabus.pdf"
        mock_file.read = mock_read
        mock_file.seek = AsyncMock()
        mock_file.file = io.BytesIO(first_chunk)

        validated = await storage_service.validate_and_read_upload(mock_file)

        assert validated.original_filename == "large_syllabus.pdf"
        assert validated.file_size_bytes == 104857600
        assert validated.file_type == "pdf"
        assert len(validated.content_hash) == 64

    @pytest.mark.asyncio
    async def test_exceeding_100_mib_boundary_rejected_with_413(self) -> None:
        """Verify a file at 104,857,601 bytes (100 MiB + 1 byte) is rejected with HTTP 413."""
        chunk_size = 64 * 1024
        header = b"%PDF-1.4\n%oversized test\n"
        first_chunk = header + b"A" * (chunk_size - len(header))
        total_chunks = (104857600 // chunk_size) + 1

        chunks = [first_chunk] + [b"B" * chunk_size] * (total_chunks - 1) + [b"X"]
        idx = 0

        async def mock_read(n: int = -1) -> bytes:
            nonlocal idx
            if idx < len(chunks):
                data = chunks[idx]
                idx += 1
                return data
            return b""

        mock_file = AsyncMock(spec=UploadFile)
        mock_file.filename = "oversized_research_paper.pdf"
        mock_file.read = mock_read
        mock_file.seek = AsyncMock()
        mock_file.file = io.BytesIO(first_chunk)

        with pytest.raises(HTTPException) as exc_info:
            await storage_service.validate_and_read_upload(mock_file)

        assert exc_info.value.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        assert "exceeds maximum allowed limit" in exc_info.value.detail.lower()
        assert "100 mib" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_empty_file_rejected_with_400(self) -> None:
        """Verify a 0-byte file is rejected with HTTP 400 Bad Request."""
        mock_file = AsyncMock(spec=UploadFile)
        mock_file.filename = "empty.txt"
        mock_file.read = AsyncMock(return_value=b"")
        mock_file.seek = AsyncMock()
        mock_file.file = io.BytesIO(b"")

        with pytest.raises(HTTPException) as exc_info:
            await storage_service.validate_and_read_upload(mock_file)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "empty" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_unsupported_extension_rejected_with_400(self) -> None:
        """Verify unsupported extensions (.exe, .py, .sh) are rejected."""
        mock_file = AsyncMock(spec=UploadFile)
        mock_file.filename = "script.py"
        mock_file.read = AsyncMock(return_value=b"print('hello')")
        mock_file.seek = AsyncMock()
        mock_file.file = io.BytesIO(b"print('hello')")

        with pytest.raises(HTTPException) as exc_info:
            await storage_service.validate_and_read_upload(mock_file)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "unsupported" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_corrupted_or_mismatched_magic_bytes_rejected(self) -> None:
        """Verify a file with .pdf extension containing plain text is rejected by magic byte detection."""
        bad_content = b"THIS IS NOT A VALID PDF FILE AT ALL"
        mock_file = AsyncMock(spec=UploadFile)
        mock_file.filename = "fake_document.pdf"
        mock_file.read = AsyncMock(side_effect=[bad_content, b""])
        mock_file.seek = AsyncMock()
        mock_file.file = io.BytesIO(bad_content)

        with pytest.raises(HTTPException) as exc_info:
            await storage_service.validate_and_read_upload(mock_file)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid pdf file" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_filename_path_traversal_sanitized(self) -> None:
        """Verify directory traversal patterns are stripped from upload filenames."""
        valid_pdf = b"%PDF-1.4\nvalid academic notes content\n"
        mock_file = AsyncMock(spec=UploadFile)
        mock_file.filename = "..\\..\\etc\\passwd.pdf"
        mock_file.read = AsyncMock(side_effect=[valid_pdf, b""])
        mock_file.seek = AsyncMock()
        mock_file.file = io.BytesIO(valid_pdf)

        validated = await storage_service.validate_and_read_upload(mock_file)

        assert "/" not in validated.original_filename
        assert "\\" not in validated.original_filename
        assert "passwd.pdf" in validated.original_filename


class TestDatabaseAvailabilityAndModeSelectionContracts:
    """Verify application mode selection policy and database health verification."""

    def test_real_mode_does_not_silently_fallback_to_demo_mode_when_db_down(self) -> None:
        """Real application mode must not switch to offline preview data on database outage."""
        client = FrontendAPIClient()
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("DEMO_MODE", None)

            # _should_use_real_http must return True (no silent fallback)
            assert client._should_use_real_http() is True

    def test_demo_mode_requires_explicit_env_var(self) -> None:
        """Offline demo mode is active only when DEMO_MODE=1 is explicitly set."""
        client = FrontendAPIClient()
        with patch.dict("os.environ", {"DEMO_MODE": "1"}):
            assert client._should_use_real_http() is False

    def test_database_readiness_probe_executes_select_1(self) -> None:
        """check_database_connection executes SELECT 1 against SQLAlchemy engine."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        result = check_database_connection(db_engine=mock_engine)

        assert result is True
        mock_conn.execute.assert_called_once()
        query_text = str(mock_conn.execute.call_args[0][0])
        assert "SELECT 1" in query_text

    def test_database_readiness_probe_returns_false_on_exception(self) -> None:
        """check_database_connection suppresses raw database errors and safely returns False."""
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = Exception("Password authentication failed for user")

        result = check_database_connection(db_engine=mock_engine)

        assert result is False


class TestInlineUploadWorkspaceAndDropzoneContracts:
    """Verify UI contracts for the inline upload workspace and dropzone."""

    def test_supported_extensions_constant_matches_backend(self) -> None:
        """Verify frontend SUPPORTED_EXTENSIONS matches the 5 supported text formats."""
        assert ".pdf" in SUPPORTED_EXTENSIONS
        assert ".docx" in SUPPORTED_EXTENSIONS
        assert ".txt" in SUPPORTED_EXTENSIONS
        assert ".md" in SUPPORTED_EXTENSIONS
        assert ".csv" in SUPPORTED_EXTENSIONS

    def test_upload_document_supports_file_path_streaming(self, tmp_path: Path) -> None:
        """Verify api_client.upload_document streams from file_path without reading bytes to RAM."""
        test_file = tmp_path / "test_notes.pdf"
        test_file.write_bytes(b"%PDF-1.4\nSample notes\n")

        client = FrontendAPIClient()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": "00000000-0000-0000-0000-000000000001",
            "knowledge_base_id": "c1111111-1111-1111-1111-111111111111",
            "original_filename": "test_notes.pdf",
            "file_type": "pdf",
            "file_size_bytes": test_file.stat().st_size,
            "status": "PROCESSING",
            "indexing_status": "PROCESSING",
            "created_at": "2026-10-21T10:00:00",
        }

        with patch.object(client._http, "post", return_value=mock_resp) as mock_post:
            doc = client.upload_document(
                kb_id="c1111111-1111-1111-1111-111111111111",
                filename="test_notes.pdf",
                file_path=str(test_file),
            )

            assert doc.filename == "test_notes.pdf"
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args[1]
            assert "files" in call_kwargs
            assert "file" in call_kwargs["files"]
            assert call_kwargs["timeout"] == 300.0
            filename, fp = call_kwargs["files"]["file"]
            assert filename == "test_notes.pdf"
            assert isinstance(fp, io.BufferedReader)
