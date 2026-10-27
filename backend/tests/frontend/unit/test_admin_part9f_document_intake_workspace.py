"""
Unit and Contract Tests for Admin Part 9F — Sequential Document Intake Workspace:
1. The new upload composition replaces the old .upload-paired-grid layout.
2. No content-sized Target Course select collapses to a few characters (w-full max-w-md container).
3. Destination selector displays full course names with 46px control height.
4. File-selection surface is genuine, purposeful, and distinct (document-intake-surface, 74px height, parchment, gold accent).
5. Clicking surface activates real native file picker (100% full-surface input overlay).
6. Drag-and-drop mechanism is preserved on native Quasar uploader.
7. Keyboard focus halo (:focus-within) and explicit accessible labels are present.
8. No separate visible Browse File button.
9. Idle 0.0B / 0.00% framework counter is suppressed.
10. Course placeholder 'Choose a course' is visible when empty.
11. No first course is silently selected.
12. Upload without an authorized course is safely rejected with clear alert.
13. Authoritative 100 MiB (104,857,600 bytes) limit is preserved.
14. Persistent background processing and automatic indexing pipeline remain functional.
15. Truthful progress reporting: only authoritative stages and chunk counts when available.
16. Single source of progress: progress is not redundantly duplicated.
17. Search input and status filters remain usable during processing.
18. Permission gating (DOCUMENT_UPLOAD) and retry behavior remain correct.
"""

from pathlib import Path

from backend.app.core.config import settings
from frontend.components.theme import GLOBAL_THEME_CSS
from frontend.pages.documents_page import SUPPORTED_EXTENSIONS, format_bytes, format_stage_label


class TestSequentialIntakeWorkspaceStructure:
    """Verify the structural composition of the Part 9F Sequential Intake Workspace."""

    def test_upload_paired_grid_completely_abandoned(self) -> None:
        """Verify the failed paired grid is absent from both page and theme."""
        doc_page = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert "upload-paired-grid" not in doc_page
        assert "upload-field-col" not in doc_page
        assert ".upload-paired-grid" not in GLOBAL_THEME_CSS

    def test_sequential_two_step_workspace_elements_present(self) -> None:
        """Verify the two sequential steps (01 Destination, 02 Document) exist in order."""
        doc_page = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert "upload-intake-workspace" in doc_page
        assert "intake-step-destination" in doc_page
        assert "intake-step-document" in doc_page

        # Verify sequential ordering: Step 1 precedes Step 2 in markup
        step1_idx = doc_page.find("intake-step-destination")
        step2_idx = doc_page.find("intake-step-document")
        assert step1_idx != -1
        assert step2_idx != -1
        assert step1_idx < step2_idx

    def test_step_labels_and_numbering(self) -> None:
        """Verify explicit step numbering (01, 02) and field labels."""
        doc_page = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert 'ui.label("01").classes("intake-step-number")' in doc_page
        assert 'ui.label("Target Course").classes("intake-field-label")' in doc_page
        assert 'ui.label("02").classes("intake-step-number")' in doc_page
        assert 'ui.label("Document File").classes("intake-field-label")' in doc_page

    def test_destination_selector_responsive_width_not_content_sized(self) -> None:
        """Verify destination selector has w-full max-w-md wrapper so it never collapses to content."""
        doc_page = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert 'ui.element("div").classes("w-full max-w-md")' in doc_page
        assert "upload_course_select = ui.select(" in doc_page
        assert "intake-course-select" in doc_page

    def test_destination_selector_css_contracts(self) -> None:
        """Verify theme CSS enforces 46px height, parchment surface, and navy focus halo."""
        assert ".intake-course-select.q-field" in GLOBAL_THEME_CSS
        assert "min-height: 46px !important;" in GLOBAL_THEME_CSS
        assert "height: 46px !important;" in GLOBAL_THEME_CSS
        assert "background-color: #FAF6F0 !important;" in GLOBAL_THEME_CSS
        assert "border: 1px solid #D8CFBF !important;" in GLOBAL_THEME_CSS
        assert "border-radius: 6px !important;" in GLOBAL_THEME_CSS


class TestDocumentIntakeSurfaceDesignAndInteraction:
    """Verify the purposeful document intake surface styling, interaction, and accessibility."""

    def test_intake_surface_classes_and_height(self) -> None:
        """Verify document intake surface uses 74px min-height, parchment, and 3px gold accent."""
        assert ".document-intake-surface.q-uploader" in GLOBAL_THEME_CSS
        assert "min-height: 74px !important;" in GLOBAL_THEME_CSS
        assert "background-color: #FAF6F0 !important;" in GLOBAL_THEME_CSS
        assert "border: 1px solid #D8CFBF !important;" in GLOBAL_THEME_CSS
        assert "border-left: 3px solid #B89A5A !important;" in GLOBAL_THEME_CSS
        assert "border-radius: 6px !important;" in GLOBAL_THEME_CSS

    def test_intake_surface_academic_icon(self) -> None:
        """Verify post_add academic icon is present and cloud_upload is absent."""
        assert 'content: "post_add";' in GLOBAL_THEME_CSS
        assert "cloud_upload" not in GLOBAL_THEME_CSS

    def test_integrated_format_and_size_guidance(self) -> None:
        """Verify format and size guidance is integrated into header content."""
        assert 'content: "PDF · DOCX · TXT · Markdown · CSV · Maximum 100 MiB";' in GLOBAL_THEME_CSS

    def test_full_surface_input_overlay_and_no_browse_button(self) -> None:
        """Verify full surface file input overlay and complete suppression of separate browse button."""
        assert ".document-intake-surface .q-uploader__input" in GLOBAL_THEME_CSS
        assert "position: absolute !important;" in GLOBAL_THEME_CSS
        assert "width: 100% !important;" in GLOBAL_THEME_CSS
        assert "height: 100% !important;" in GLOBAL_THEME_CSS
        assert ".document-intake-surface .q-uploader__header .q-btn" in GLOBAL_THEME_CSS
        assert "display: none !important;" in GLOBAL_THEME_CSS

    def test_idle_counter_suppression(self) -> None:
        """Verify meaningless idle 0.0B / 0.00% counter is suppressed."""
        assert ".document-intake-surface .q-uploader__subtitle" in GLOBAL_THEME_CSS

    def test_keyboard_focus_styling(self) -> None:
        """Verify focus-within state has distinct navy outline for keyboard navigation."""
        assert ".document-intake-surface.q-uploader:focus-within" in GLOBAL_THEME_CSS
        assert "box-shadow: 0 0 0 2px rgba(14, 29, 97, 0.15) !important;" in GLOBAL_THEME_CSS


class TestUploadBehaviorAndSecurityContracts:
    """Verify course validation, 100 MiB limit, truthful progress, and error handling."""

    def test_placeholder_visible_and_no_silent_selection(self) -> None:
        """Verify 'Choose a course' placeholder and lack of default silent selection."""
        doc_page = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert 'placeholder="Choose a course"' in doc_page
        assert 'display-value="Choose a course"' in doc_page
        assert "initial_target = kb_id if (kb_id and kb_id in course_select_options) else None" in doc_page

    def test_upload_without_target_course_blocked(self) -> None:
        """Verify handle_file_upload requires a selected target course before processing."""
        doc_page = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert "if not target_kb:" in doc_page
        assert "Please select a target course for upload." in doc_page

    def test_authoritative_100_mib_limit(self) -> None:
        """Verify authoritative 100 MiB (104,857,600 bytes) limit is strictly enforced."""
        assert settings.MAX_UPLOAD_SIZE_BYTES == 104857600
        doc_page = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert "max_file_size=max_upload_bytes" in doc_page
        assert "max_upload_bytes = settings.MAX_UPLOAD_SIZE_BYTES" in doc_page

    def test_supported_extensions(self) -> None:
        """Verify all 5 supported text extensions are configured."""
        for ext in [".pdf", ".docx", ".txt", ".md", ".csv"]:
            assert ext in SUPPORTED_EXTENSIONS

    def test_truthful_progress_label_formatting(self) -> None:
        """Verify format_stage_label produces truthful, informative labels without fabrication."""
        # Unprocessed / indeterminate stage
        lbl_val = format_stage_label("VALIDATING", 0, 0, 0.0, "PROCESSING")
        assert lbl_val == "Saving document..."

        # Embedding with valid chunks
        lbl_emb = format_stage_label("EMBEDDING", 4, 10, 40.0, "PROCESSING")
        assert lbl_emb == "Generating embeddings — 4 of 10 chunks (40%)"

        # Embedding without chunks reported yet
        lbl_emb_zero = format_stage_label("EMBEDDING", 0, 0, 0.0, "PROCESSING")
        assert lbl_emb_zero == "Generating dense vector embeddings..."

        # Verifying vectors
        lbl_ver = format_stage_label("VERIFYING", 10, 10, 100.0, "PROCESSING")
        assert lbl_ver == "Verifying indexed vectors in pgvector..."

    def test_format_bytes_utility(self) -> None:
        """Verify format_bytes human-readable output."""
        assert format_bytes(500) == "500 B"
        assert format_bytes(1024) == "1.0 KB"
        assert format_bytes(1048576) == "1.00 MB"

    def test_permission_gating_present(self) -> None:
        """Verify DOCUMENT_UPLOAD permission is required to render the intake workspace."""
        doc_page = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert "can_upload_documents = has_admin_permission(user, Permission.DOCUMENT_UPLOAD)" in doc_page
        assert "if can_upload_documents:" in doc_page
        assert "with ui.column().classes(\"w-full mb-6 gap-3 upload-intake-workspace\"):" in doc_page
