"""
Unit and Contract Tests for Admin Part 9D:
- Editorial document intake design (compact strip, left-aligned, post_add icon, no giant cloud or dashed box).
- Target Course selector visibility, 'Choose a course' placeholder, and absence of silent selection.
- Valid contextual kb_id preselection and blocking of upload without target course.
- Deduplication of active upload progress (primary workspace only, suppressed from active pipeline banner).
- Concise status badge in document table row.
- 100 MiB (104,857,600 bytes) limit preservation and rejection of oversized files.
- Truthful progress without fixed 85% simulation.
- Multi-upload lifecycle: resetting workspace after completion without page reload.
- Full surface click and drag-drop support without separate browse button.
- Real PDF parsing and chunking integrity.
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


def generate_minimal_valid_pdf(text_content: str = "Academic test lecture notes for Part 9D.") -> bytes:
    """Generate a minimal syntactically valid PDF 1.4 document in memory."""
    stream_bytes = f"BT /F1 12 Tf 72 712 Td ({text_content}) Tj ET".encode("latin-1")
    stream_len = len(stream_bytes)

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {stream_len} >>\nstream\n".encode("latin-1") + stream_bytes + b"\nendstream",
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


class TestEditorialIntakeDesignContracts:
    """Verify the structural composition of the editorial document intake strip."""

    def test_upload_workspace_directly_visible_without_toggle(self) -> None:
        """Verify upload workspace is mounted directly on /documents without header toggle."""
        doc_page = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert "toggle_upload_workspace" not in doc_page
        assert "header_upload_btn" not in doc_page
        assert "show_upload_workspace" not in doc_page

    def test_document_browsing_toolbar_has_no_course_dropdown(self) -> None:
        """Verify browsing toolbar does not contain an 'All Accessible Courses' dropdown."""
        doc_page = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert 'course_options = {"ALL": "All Accessible Courses"' not in doc_page
        assert "current_course_filter" not in doc_page

    def test_target_course_selector_present_with_visible_placeholder(self) -> None:
        """Verify Target Course selector is present and configured with 'Choose a course' placeholder."""
        doc_page = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert "Target Course" in doc_page
        assert 'placeholder="Choose a course"' in doc_page
        assert 'display-value="Choose a course"' in doc_page

    def test_target_course_not_silently_selected(self) -> None:
        """Verify initial_target defaults to None when no course query param is provided."""
        doc_page = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert "initial_target = kb_id if (kb_id and kb_id in course_select_options) else None" in doc_page

    def test_no_separate_browse_file_button(self) -> None:
        """Verify theme CSS suppresses Quasar's native Browse File button."""
        assert ".academic-uploader .q-uploader__header .q-btn" in GLOBAL_THEME_CSS
        assert "display: none !important;" in GLOBAL_THEME_CSS

    def test_full_surface_intake_strip_click_and_drag(self) -> None:
        """Verify native file input covers 100% of the intake strip for click and drag-drop."""
        assert ".academic-uploader .q-uploader__input" in GLOBAL_THEME_CSS
        assert "position: absolute !important;" in GLOBAL_THEME_CSS
        assert "width: 100% !important;" in GLOBAL_THEME_CSS
        assert "height: 100% !important;" in GLOBAL_THEME_CSS

    def test_idle_native_progress_counter_suppressed(self) -> None:
        """Verify theme CSS hides the idle 0.0B / 0.00% framework counter."""
        assert ".academic-uploader .q-uploader__subtitle" in GLOBAL_THEME_CSS

    def test_academic_uploader_compact_editorial_styling(self) -> None:
        """Verify compact architectural styling with gold accent and post_add icon."""
        assert "min-height: 74px !important;" in GLOBAL_THEME_CSS
        assert "border-left: 3px solid #B89A5A !important;" in GLOBAL_THEME_CSS
        assert 'content: "post_add";' in GLOBAL_THEME_CSS
        assert "cloud_upload" not in GLOBAL_THEME_CSS

    def test_supported_extensions_remain_intact(self) -> None:
        """Verify all 5 academic text formats are supported."""
        for ext in [".pdf", ".docx", ".txt", ".md", ".csv"]:
            assert ext in SUPPORTED_EXTENSIONS


class TestProgressUnificationAndDeduplication:
    """Verify progress deduplication and truthful status reporting."""

    def test_no_hardcoded_85_percent_progress(self) -> None:
        """Verify zero simulated 85% progress bars exist."""
        doc_page = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert "value=0.85" not in doc_page
        assert "linear_progress(value=0.85)" not in doc_page

    def test_active_upload_deduplication_in_pipeline_banner(self) -> None:
        """Verify render_active_pipeline filters out the actively uploading document."""
        doc_page = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert "if uploading_doc_id:" in doc_page
        assert "str(d.id) != str(uploading_doc_id)" in doc_page

    def test_format_stage_label_truthfulness(self) -> None:
        """Verify format_stage_label produces truthful, accurate human descriptions."""
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

    def test_upload_another_document_resets_workspace(self) -> None:
        """Verify reset_upload_workspace clears uploading state and restores intake form."""
        doc_page = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert "uploading_doc_id = None" in doc_page
        assert "upload_form_container.visible = True" in doc_page
        assert "upload_progress_container.visible = False" in doc_page


class TestUploadSizeLimitsAndStorageValidation:
    """Verify 100 MiB limit enforcement and storage validation integrity."""

    def test_exact_100_mib_boundary(self) -> None:
        """Verify settings.MAX_UPLOAD_SIZE_BYTES is exactly 104,857,600 bytes."""
        assert settings.MAX_UPLOAD_SIZE_BYTES == 104857600
        assert settings.MAX_UPLOAD_SIZE_BYTES == 100 * 1024 * 1024

    @pytest.mark.asyncio
    async def test_oversize_upload_rejected_with_413(self) -> None:
        """Verify file exceeding 104,857,600 bytes is rejected with HTTP 413."""
        chunk_size = 64 * 1024
        header = b"%PDF-1.4\n"
        first_chunk = header + b"X" * (chunk_size - len(header))
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
        mock_file.filename = "oversized_lecture.pdf"
        mock_file.read = mock_read
        mock_file.seek = AsyncMock()
        mock_file.file = io.BytesIO(first_chunk)

        with pytest.raises(HTTPException) as exc_info:
            await storage_service.validate_and_read_upload(mock_file)

        assert exc_info.value.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE

    def test_valid_pdf_parsing_and_chunking(self, tmp_path: Path) -> None:
        """Verify valid PDF document parses and chunks with complete provenance."""
        valid_bytes = generate_minimal_valid_pdf("Advanced Distributed Algorithms: Paxos and Raft.")
        pdf_file = tmp_path / "paxos_notes.pdf"
        pdf_file.write_bytes(valid_bytes)

        parser = PDFParser()
        parsed = parser.parse(pdf_file)
        assert parsed.metadata["total_pages"] == 1
        assert "Paxos and Raft" in parsed.raw_text

        chunks = document_chunker.chunk_document(parsed)
        assert len(chunks) >= 1
        assert chunks[0].page_number == 1
        assert "Paxos and Raft" in chunks[0].text

    def test_truncated_pdf_stream_error_handled(self, tmp_path: Path) -> None:
        """Verify truncated synthetic stream raises ValueError gracefully."""
        truncated_bytes = b"%PDF-1.4\n1 0 obj\n<< /Title (Incomplete) >>\nendobj\n"
        bad_file = tmp_path / "truncated.pdf"
        bad_file.write_bytes(truncated_bytes)

        parser = PDFParser()
        with pytest.raises(ValueError) as exc_info:
            parser.parse(bad_file)
        assert "stream has ended unexpectedly" in str(exc_info.value).lower()
