"""
Unit and Contract Tests for Admin Part 9C:
- Documents Upload UX Correction (immediate visibility, no header toggle, no browsing course dropdown)
- Removal of idle '0.0B / 0.00%' framework text via theme CSS
- Removal of hardcoded 0.85 progress simulation
- Target course selection requirement and validation
- Real PDF parsing integrity: valid PDF parsing vs. truncated stream failure diagnosis
"""

import io
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, UploadFile, status

from backend.app.core.config import settings
from backend.app.services.chunking import document_chunker
from backend.app.services.parsers.pdf_parser import PDFParser
from backend.app.services.storage import storage_service
from frontend.components.theme import GLOBAL_THEME_CSS
from frontend.pages.documents_page import SUPPORTED_EXTENSIONS, format_stage_label


def generate_minimal_valid_pdf(text_content: str = "Academic test lecture notes.") -> bytes:
    """Generate a minimal syntactically valid PDF 1.4 document in memory."""
    # Build valid PDF objects
    stream_bytes = f"BT /F1 12 Tf 72 712 Td ({text_content}) Tj ET".encode("latin-1")
    stream_len = len(stream_bytes)

    objects = [
        # 1: Catalog
        b"<< /Type /Catalog /Pages 2 0 R >>",
        # 2: Pages
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        # 3: Page
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        # 4: Contents
        f"<< /Length {stream_len} >>\nstream\n".encode("latin-1") + stream_bytes + b"\nendstream",
        # 5: Font
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []

    for i, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode("latin-1"))
        out.extend(obj)
        out.extend(b"\nendobj\n")

    xref_offset = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets:
        out.extend(f"{off:010d} 00000 n \n".encode("latin-1"))

    out.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(
            "latin-1"
        )
    )
    return bytes(out)


class TestUploadLayoutAndUXContracts:
    """Verify layout simplification, removal of toggle, removal of course dropdown, and CSS rules."""

    def test_no_hardcoded_85_percent_progress_in_documents_page(self) -> None:
        """Verify documents_page.py contains zero occurrences of hardcoded 0.85 progress."""
        doc_page_path = Path("frontend/pages/documents_page.py")
        content = doc_page_path.read_text(encoding="utf-8")
        assert "value=0.85" not in content
        assert "linear_progress(value=0.85)" not in content

    def test_no_course_select_dropdown_in_browsing_toolbar(self) -> None:
        """Verify the 'All Accessible Courses' dropdown was removed from the document ledger toolbar."""
        doc_page_path = Path("frontend/pages/documents_page.py")
        content = doc_page_path.read_text(encoding="utf-8")
        assert 'course_options = {"ALL": "All Accessible Courses"' not in content
        assert "current_course_filter" not in content
        assert "on_course_change" not in content

    def test_search_documents_by_filename_placeholder_exists(self) -> None:
        """Verify filename search input is the primary document browsing control."""
        doc_page_path = Path("frontend/pages/documents_page.py")
        content = doc_page_path.read_text(encoding="utf-8")
        assert 'placeholder="Search documents by filename..."' in content

    def test_academic_uploader_subtitle_hidden_in_theme_css(self) -> None:
        """Verify theme CSS hides .academic-uploader .q-uploader__subtitle to eliminate idle 0.0B / 0.00% text."""
        assert ".academic-uploader .q-uploader__subtitle" in GLOBAL_THEME_CSS
        assert "display: none !important;" in GLOBAL_THEME_CSS

    def test_supported_extensions_remain_intact(self) -> None:
        """Verify supported extensions list contains all 5 text/document formats."""
        for ext in [".pdf", ".docx", ".txt", ".md", ".csv"]:
            assert ext in SUPPORTED_EXTENSIONS


class TestPDFParserAndIntegrityDiagnosis:
    """Diagnose the 'Stream has ended unexpectedly' failure mode and verify valid PDF processing."""

    def test_valid_pdf_parses_completely_without_stream_ended_error(self, tmp_path: Path) -> None:
        """Verify a syntactically valid PDF is parsed without 'Stream has ended unexpectedly'."""
        valid_bytes = generate_minimal_valid_pdf("Distributed Systems lecture: consensus and replication.")
        pdf_file = tmp_path / "valid_lecture.pdf"
        pdf_file.write_bytes(valid_bytes)

        parser = PDFParser()
        parsed = parser.parse(pdf_file)

        assert parsed.metadata["total_pages"] == 1
        assert len(parsed.sections) == 1
        assert "Distributed Systems" in parsed.sections[0].text
        assert "consensus and replication" in parsed.raw_text

    def test_truncated_or_malformed_dummy_string_reproduces_stream_ended_error(self, tmp_path: Path) -> None:
        """
        Reproduce root cause from Part 9B:
        A synthetic dummy string without PDF xref/trailer/EOF triggers 'Stream has ended unexpectedly'.
        """
        fake_content = (
            b"%PDF-1.4\n%Academic Reference Material\n1 0 obj\n"
            b"<< /Title (CS101 Distributed Systems Overview) >>\nendobj\n"
        )
        fake_file = tmp_path / "fake_doc.pdf"
        fake_file.write_bytes(fake_content)

        parser = PDFParser()
        with pytest.raises(ValueError) as exc_info:
            parser.parse(fake_file)

        assert "stream has ended unexpectedly" in str(exc_info.value).lower()

    def test_valid_pdf_end_to_end_chunking(self, tmp_path: Path) -> None:
        """Verify a valid parsed PDF generates valid text chunks with provenance metadata."""
        valid_bytes = generate_minimal_valid_pdf("Introduction to Database Normalization: 1NF, 2NF, and 3NF.")
        pdf_file = tmp_path / "db_notes.pdf"
        pdf_file.write_bytes(valid_bytes)

        parser = PDFParser()
        parsed = parser.parse(pdf_file)

        chunks = document_chunker.chunk_document(parsed)
        assert len(chunks) >= 1
        assert chunks[0].page_number == 1
        assert "Database Normalization" in chunks[0].text


class TestUploadSizeLimitsAndTruthfulProgress:
    """Verify 100 MiB limit enforcement and truthful progress reporting."""

    def test_exact_100_mib_boundary_accepted(self) -> None:
        """Verify settings.MAX_UPLOAD_SIZE_BYTES is exactly 104,857,600 bytes."""
        assert settings.MAX_UPLOAD_SIZE_BYTES == 104857600
        assert settings.MAX_UPLOAD_SIZE_BYTES == 100 * 1024 * 1024

    @pytest.mark.asyncio
    async def test_oversize_upload_rejected_with_413(self) -> None:
        """Verify file exceeding 104,857,600 bytes is rejected with HTTP 413."""
        chunk_size = 64 * 1024
        header = b"%PDF-1.4\n"
        first_chunk = header + b"X" * (chunk_size - len(header))
        # Total size: 104,857,601 bytes
        total_chunks = (104857600 // chunk_size) + 1
        chunks = [first_chunk] + [b"Y" * chunk_size] * (total_chunks - 1) + [b"Z"]
        idx = 0

        async def mock_read(n: int = -1) -> bytes:
            nonlocal idx
            if idx < len(chunks):
                data = chunks[idx]
                idx += 1
                return data
            return b""

        mock_file = AsyncMock(spec=UploadFile)
        mock_file.filename = "oversized.pdf"
        mock_file.read = mock_read
        mock_file.seek = AsyncMock()
        mock_file.file = io.BytesIO(first_chunk)

        with pytest.raises(HTTPException) as exc_info:
            await storage_service.validate_and_read_upload(mock_file)

        assert exc_info.value.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE

    def test_format_stage_label_truthfulness(self) -> None:
        """Verify format_stage_label produces truthful, accurate human descriptions."""
        # Unindexed / idle
        assert format_stage_label("EXTRACTING") == "Extracting text content..."
        assert format_stage_label("CHUNKING") == "Splitting text into sections..."
        assert format_stage_label("QUEUED_FOR_INDEXING") == "Waiting for vector indexing..."
        assert format_stage_label("STORING_VECTORS") == "Saving vectors to database..."
        assert format_stage_label("VERIFYING") == "Verifying indexed vectors in pgvector..."
        assert format_stage_label("COMPLETED", status="COMPLETED") == "Indexed & verified successfully"
        assert format_stage_label("FAILED", status="FAILED") == "Failed during processing"

        # Embedding shows quantitative chunk progress
        label = format_stage_label("EMBEDDING", processed=5, total=10)
        assert "5 of 10 chunks (50%)" in label
