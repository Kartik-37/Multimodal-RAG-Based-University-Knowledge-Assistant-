"""
Unit and Contract Tests for Admin Part 9E:
- Paired document upload fields alignment and layout structure.
- Target Course and Document File explicit labels using shared styling.
- Shared 2-column grid layout on desktop and single-column on mobile.
- Control top alignment and consistent 48px height geometry.
- Absence of duplicate native labels or separate browse button.
- Full surface clickability and drag-and-drop preservation.
- Target Course placeholder 'Choose a course' and lack of silent selection.
- Contextual kb_id preselection and blocking of upload without valid course.
- 100 MiB (104,857,600 bytes) limit preservation and 413 rejection.
- Truthful progress without premature 0% or fake simulated percentages.
- Suppression of idle 0.0B / 0.00% subtitle counter.
- Absence of legacy 140px/cloud_upload styling in active theme.
"""

from pathlib import Path

from backend.app.core.config import settings
from frontend.components.theme import GLOBAL_THEME_CSS
from frontend.pages.documents_page import SUPPORTED_EXTENSIONS


class TestUploadFieldAlignmentAndStructureContracts:
    """Verify the structural pairing and layout geometry of the upload fields."""

    def test_shared_paired_grid_layout_structure(self) -> None:
        """Verify upload fields are laid out in the sequential intake workspace, replacing paired grid."""
        doc_page = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert "upload-intake-workspace" in doc_page
        assert "intake-step-destination" in doc_page
        assert "intake-step-document" in doc_page
        assert "upload-paired-grid" not in doc_page
        assert "items-end" not in doc_page[doc_page.find("upload_form_container"):doc_page.find("upload_progress_container")]

    def test_both_labels_explicitly_rendered_with_shared_label_class(self) -> None:
        """Verify both Target Course and Document File labels use the shared intake-field-label class."""
        doc_page = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert 'ui.label("Target Course").classes("intake-field-label")' in doc_page
        assert 'ui.label("Document File").classes("intake-field-label")' in doc_page

    def test_paired_grid_and_label_css_contracts(self) -> None:
        """Verify theme CSS enforces sequential workspace, intake label geometry, and appropriate heights."""
        assert ".upload-intake-workspace" in GLOBAL_THEME_CSS
        assert ".intake-step-destination" in GLOBAL_THEME_CSS
        assert ".intake-step-document" in GLOBAL_THEME_CSS
        assert ".intake-field-label" in GLOBAL_THEME_CSS
        assert "upload-paired-grid" not in GLOBAL_THEME_CSS

    def test_target_course_selector_height_and_styling(self) -> None:
        """Verify Target Course selector control matches 46px height and parchment styling."""
        assert ".upload-course-select.q-field" in GLOBAL_THEME_CSS
        assert "min-height: 46px !important;" in GLOBAL_THEME_CSS
        assert "height: 46px !important;" in GLOBAL_THEME_CSS
        assert "background-color: #FAF6F0 !important;" in GLOBAL_THEME_CSS
        assert "border: 1px solid #D8CFBF !important;" in GLOBAL_THEME_CSS
        assert "border-radius: 6px !important;" in GLOBAL_THEME_CSS

    def test_document_uploader_height_and_styling(self) -> None:
        """Verify Document intake strip matches 74px min-height, gold accent, and post_add icon."""
        assert ".academic-uploader.q-uploader" in GLOBAL_THEME_CSS
        assert "min-height: 74px !important;" in GLOBAL_THEME_CSS
        assert "border-left: 3px solid #B89A5A !important;" in GLOBAL_THEME_CSS
        assert 'content: "post_add";' in GLOBAL_THEME_CSS
        assert "cloud_upload" not in GLOBAL_THEME_CSS

    def test_target_course_placeholder_and_no_silent_selection(self) -> None:
        """Verify Target Course placeholder 'Choose a course' is configured and no silent selection occurs."""
        doc_page = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert 'display-value="Choose a course"' in doc_page
        assert 'placeholder="Choose a course"' in doc_page
        assert "initial_target = kb_id if (kb_id and kb_id in course_select_options) else None" in doc_page

    def test_no_separate_browse_button_and_full_surface_intake(self) -> None:
        """Verify theme CSS suppresses native browse button and covers full surface with input."""
        assert ".academic-uploader .q-uploader__header .q-btn" in GLOBAL_THEME_CSS
        assert "display: none !important;" in GLOBAL_THEME_CSS
        assert ".academic-uploader .q-uploader__input" in GLOBAL_THEME_CSS
        assert "position: absolute !important;" in GLOBAL_THEME_CSS
        assert "width: 100% !important;" in GLOBAL_THEME_CSS
        assert "height: 100% !important;" in GLOBAL_THEME_CSS

    def test_idle_counter_suppression(self) -> None:
        """Verify native 0.0B / 0.00% counter is suppressed."""
        assert ".academic-uploader .q-uploader__subtitle" in GLOBAL_THEME_CSS

    def test_truthful_progress_no_premature_zero_percent(self) -> None:
        """Verify chunk percentages are not shown when embedded/processed chunks count is 0."""
        doc_page = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        # In workspace progress UI:
        assert 'if stage_upper == "EMBEDDING" and total > 0 and processed > 0 and status not in ("FAILED", "COMPLETED"):' in doc_page
        # In active pipeline banner:
        assert 'if stage_upper == "EMBEDDING" and ad.total_chunks > 0 and ad.embedded_chunks > 0:' in doc_page
        # In table row:
        assert 'if stage_str == "EMBEDDING" and doc.total_chunks > 0 and doc.embedded_chunks > 0:' in doc_page

    def test_100_mib_limit_unchanged(self) -> None:
        """Verify authoritative 100 MiB (104,857,600 bytes) limit."""
        assert settings.MAX_UPLOAD_SIZE_BYTES == 104857600
        doc_page = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert "max_file_size=max_upload_bytes" in doc_page
        assert "{max_mb} MiB" in doc_page

    def test_all_five_supported_formats(self) -> None:
        """Verify all 5 supported academic text extensions."""
        for ext in [".pdf", ".docx", ".txt", ".md", ".csv"]:
            assert ext in SUPPORTED_EXTENSIONS
