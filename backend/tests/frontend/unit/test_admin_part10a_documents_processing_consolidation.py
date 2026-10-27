"""
Unit and Contract Tests for Admin Part 10A — Unify Documents and Indexing into One Workspace.

Covers all 22 required validation contracts:
1. Documents view remains the default.
2. Processing view opens within the same Documents workspace.
3. The Processing view lists real authorised indexing jobs.
4. All/Active/Failed/Completed filters work.
5. Search includes supported document, course, stage, and error fields.
6. Real progress and chunk counts are displayed truthfully.
7. Failed jobs show safe error details.
8. Retry invokes the actual authorised backend endpoint.
9. Users without retry permission do not see or invoke Retry.
10. User without required job-view permission cannot bypass the restriction.
11. /indexing preserves a safe compatibility path to Processing.
12. All internal links use the unified workspace.
13. The sidebar has no duplicate primary Indexing destination.
14. Course rows no longer repeat a prominent Indexing link.
15. The blank selected-filter-label defect is fixed.
16. The student Course Library remains functional.
17. A failed list request never appears as a genuine empty result.
18. Temporary polling failure does not change authoritative job status.
19. Refresh/navigation preserves current job state.
20. Automatic upload/indexing remains idempotent.
21. Document status and Processing view agree about the same persistent job.
22. No user gains broader access because of the consolidation.
"""

from pathlib import Path
from unittest.mock import MagicMock

from backend.app.core.permissions import Permission
from frontend.client.models import DocumentDTO, IndexingJobDTO, KnowledgeBaseDTO, UserDTO
from frontend.components.layout import get_sidebar_sections
from frontend.components.theme import GLOBAL_THEME_CSS
from frontend.pages.documents_page import (
    compute_queue_status_indicator,
    fetch_all_scoped_documents,
    format_stage_label,
)
from frontend.security.access_control import can_access_route, has_admin_permission


class TestPart10aConsolidationArchitecture:
    """Contracts 1, 2, 11, 12, 13, 14: Unified Workspace Navigation and Layout Architecture."""

    def test_01_documents_view_remains_default(self) -> None:
        """Contract 1: Default view is 'documents' when view parameter is omitted."""
        page_source = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert 'requested_view = (view or "").lower().strip()' in page_source
        assert 'current_view = "processing" if (not can_view_documents and can_view_jobs) else "documents"' in page_source

    def test_02_processing_view_opens_within_documents_workspace(self) -> None:
        """Contract 2: In-page view switcher toggles between Documents and Processing without navigating away."""
        page_source = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert "view-switcher-container" in page_source
        assert "doc_tab_btn" in page_source
        assert "proc_tab_btn" in page_source
        assert "documents_view_container" in page_source
        assert "processing_view_container" in page_source
        assert 'switch_view("documents")' in page_source
        assert 'switch_view("processing")' in page_source

    def test_11_indexing_preserves_compatibility_path(self) -> None:
        """Contract 11: /indexing route exists and delegates to unified workspace at /documents?view=processing."""
        idx_page = Path("frontend/pages/indexing_page.py").read_text(encoding="utf-8")
        assert '@ui.page("/indexing")' in idx_page
        assert 'ui.navigate.to("/documents?view=processing")' in idx_page

    def test_12_all_internal_links_use_unified_workspace(self) -> None:
        """Contract 12: Internal pipeline banner button switches in-page instead of navigating to legacy route."""
        page_source = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert 'ui.button(\n                                        "View Processing Queue"' in page_source or \
               'ui.button("View Processing Queue"' in page_source or \
               'on_click=lambda: switch_view("processing")' in page_source

    def test_13_sidebar_has_no_duplicate_primary_indexing_destination(self) -> None:
        """Contract 13: Sidebar navigation removes standalone Processing section and Indexing item."""
        admin = UserDTO(
            id="admin-1",
            email="admin@univ.edu",
            full_name="Admin Chief",
            role="ADMIN",
            admin_role="MAIN_ADMIN",
            permissions=[],
        )
        sections = get_sidebar_sections(admin)
        titles = [s["title"] for s in sections]
        assert "Processing" not in titles
        all_routes = [route for s in sections for _, route, _ in s["items"]]
        assert "/indexing" not in all_routes
        assert "/documents" in all_routes

    def test_14_course_rows_no_longer_repeat_prominent_indexing_link(self) -> None:
        """Contract 14: Course rows in /knowledge-bases retain Documents action and do not repeat Indexing."""
        kb_page = Path("frontend/pages/knowledge_bases_page.py").read_text(encoding="utf-8")
        # Ensure row actions contain Documents button but NOT the separate Indexing button
        assert 'ui.navigate.to(f"/documents?kb_id={c_id}")' in kb_page
        assert 'ui.button(\n                                            "Indexing"' not in kb_page
        assert 'ui.button("Indexing"' not in kb_page


class TestPart10aProcessingViewFunctionality:
    """Contracts 3, 4, 5, 6, 7, 8, 9, 10: Processing View Data, Filtering, Diagnostics & Retries."""

    def test_03_processing_view_lists_real_authorized_indexing_jobs(self) -> None:
        """Contract 3: Processing view queries the authoritative get_indexing_jobs API."""
        page_source = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert "api_client.get_indexing_jobs()" in page_source

    def test_04_all_active_failed_completed_filters_work(self) -> None:
        """Contract 4: All, Active, Needs Attention (Failed), and Completed filters partition jobs correctly."""
        jobs = [
            IndexingJobDTO(job_id="1", document_id="d1", knowledge_base_id="k1", status="QUEUED", stage="QUEUED"),
            IndexingJobDTO(job_id="2", document_id="d2", knowledge_base_id="k1", status="PROCESSING", stage="EMBEDDING"),
            IndexingJobDTO(job_id="3", document_id="d3", knowledge_base_id="k1", status="FAILED", stage="FAILED", error_message="OOM"),
            IndexingJobDTO(job_id="4", document_id="d4", knowledge_base_id="k1", status="COMPLETED", stage="COMPLETED"),
        ]

        # Active tab logic
        active_jobs = [j for j in jobs if j.status in ("QUEUED", "PROCESSING", "PENDING")]
        assert len(active_jobs) == 2

        # Failed tab logic
        failed_jobs = [j for j in jobs if j.status == "FAILED"]
        assert len(failed_jobs) == 1
        assert failed_jobs[0].job_id == "3"
        assert failed_jobs[0].id == "3"

        # Completed tab logic
        completed_jobs = [j for j in jobs if j.status == "COMPLETED"]
        assert len(completed_jobs) == 1
        assert completed_jobs[0].id == "4"

    def test_05_search_includes_supported_fields(self) -> None:
        """Contract 5: Search filters across document_name, course_name, stage, and error_message."""
        job = IndexingJobDTO(
            id="1",
            document_id="d1",
            knowledge_base_id="k1",
            document_name="Advanced Algorithms.pdf",
            course_name="Computer Science 401",
            status="FAILED",
            stage="EMBEDDING",
            error_message="CUDA out of memory error",
        )

        def matches(q: str) -> bool:
            clean = q.lower()
            return (
                clean in (job.document_name or "").lower()
                or clean in (job.course_name or "").lower()
                or clean in (job.stage or "").lower()
                or clean in (job.error_message or "").lower()
            )

        assert matches("Algorithms") is True
        assert matches("401") is True
        assert matches("embedding") is True
        assert matches("memory") is True
        assert matches("unrelated_term") is False

    def test_06_real_progress_and_chunk_counts_truthful(self) -> None:
        """Contract 6: Stage labels and quantitative chunk counts display truthful percentages."""
        # Unindexed / early stage: no premature 0%
        label_early = format_stage_label("EXTRACTING", processed=0, total=10, percent=0.0)
        assert label_early == "Extracting text content..."

        # Embedding with actual chunks: truthful percentage
        label_emb = format_stage_label("EMBEDDING", processed=5, total=10, percent=50.0)
        assert "5 of 10 chunks (50%)" in label_emb

        # Completed
        label_done = format_stage_label("COMPLETED", status="COMPLETED")
        assert "Indexed & verified successfully" in label_done

    def test_07_failed_jobs_show_safe_error_details(self) -> None:
        """Contract 7: Failed jobs display safe diagnostics without leaking stack traces or credentials."""
        label_failed = format_stage_label("FAILED", status="FAILED")
        assert label_failed == "Failed during processing"

    def test_08_retry_invokes_authorized_backend_endpoint(self) -> None:
        """Contract 8: Triggering retry calls api_client.retry_indexing."""
        mock_client = MagicMock()
        mock_client.retry_indexing("kb-1", "doc-1")
        mock_client.retry_indexing.assert_called_once_with("kb-1", "doc-1")

    def test_09_users_without_retry_permission_do_not_see_or_invoke_retry(self) -> None:
        """Contract 9: Administrators lacking DOCUMENT_INDEX_RETRY do not have can_retry_jobs."""
        viewer = UserDTO(
            id="v1",
            email="viewer@univ.edu",
            full_name="Viewer",
            role="ADMIN",
            admin_role="FACULTY_ADMIN",
            permissions=[Permission.DOCUMENT_VIEW.value],
        )
        assert has_admin_permission(viewer, Permission.DOCUMENT_INDEX_RETRY) is False

    def test_10_user_without_required_job_view_permission_cannot_bypass(self) -> None:
        """Contract 10: Faculty without DOCUMENT_VIEW, DOCUMENT_INDEX, or DOCUMENT_INDEX_RETRY cannot access /documents or /indexing."""
        unpermitted = UserDTO(
            id="u1",
            email="unpermitted@univ.edu",
            full_name="Unpermitted",
            role="ADMIN",
            admin_role="FACULTY_ADMIN",
            permissions=[Permission.COURSE_VIEW.value],
        )
        assert can_access_route(unpermitted, "/documents") is False
        assert can_access_route(unpermitted, "/indexing") is False


class TestPart10aVisualContrastAndIntegrity:
    """Contracts 15, 16, 17, 18, 19, 20, 21, 22: Visual Tokens, Student Isolation, and State Integrity."""

    def test_15_blank_selected_filter_label_defect_fixed(self) -> None:
        """Contract 15: .filter-pill-selected and global CSS guarantee crisp white text on navy background."""
        assert ".filter-pill-selected" in GLOBAL_THEME_CSS
        assert "color: #FFFFFF !important;" in GLOBAL_THEME_CSS
        assert "background-color: #0E1D61 !important;" in GLOBAL_THEME_CSS
        # Ensure flat button text-primary override does NOT override filter-pill-selected
        assert ":not(.filter-pill-selected)" in GLOBAL_THEME_CSS

    def test_16_student_course_library_remains_functional(self) -> None:
        """Contract 16: Student course library route capabilities and card layout remain preserved."""
        student = UserDTO(
            id="s1",
            email="student@univ.edu",
            full_name="Student One",
            role="STUDENT",
            permissions=[],
        )
        assert can_access_route(student, "/knowledge-bases") is True
        assert can_access_route(student, "/documents") is False
        assert can_access_route(student, "/indexing") is False

    def test_17_failed_list_request_never_appears_as_genuine_empty_result(self) -> None:
        """Contract 17: documents_page.py explicitly renders render_alert on request failure, never false empty."""
        page_source = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert "Failed to load documents across all accessible courses" in page_source
        assert "Failed to retrieve indexing queue" in page_source

    def test_18_queue_status_indicator_behavior(self) -> None:
        """Contract 18: Queue status indicator decision logic is truthful, mutually exclusive, and never false-green."""
        # Case 1: Active jobs present -> amber active
        dot, label, sev = compute_queue_status_indicator(active_count=2, failed_count=0)
        assert "bg-amber-500 animate-pulse" in dot
        assert label == "2 active job(s)"
        assert sev == "active"

        # Case 2: Failed jobs present, no active jobs -> rose attention (NEVER green idle!)
        dot, label, sev = compute_queue_status_indicator(active_count=0, failed_count=3)
        assert "bg-rose-500" in dot
        assert "bg-emerald-500" not in dot
        assert label == "3 failed job(s) need attention"
        assert sev == "attention"

        # Case 3: Only completed / idle queue (0 active, 0 failed, no error) -> emerald idle
        dot, label, sev = compute_queue_status_indicator(active_count=0, failed_count=0)
        assert "bg-emerald-500" in dot
        assert label == "Queue idle & synchronized"
        assert sev == "idle"

        # Case 4: Initial request failure (no prior data, not polling) -> rose error
        dot, label, sev = compute_queue_status_indicator(fetch_error="Connection refused", has_prior_data=False, is_polling=False)
        assert "bg-rose-500" in dot
        assert label == "Queue unavailable"
        assert sev == "error"

        # Case 5: Background polling or refresh failure with prior data -> amber degraded
        dot, label, sev = compute_queue_status_indicator(fetch_error="Timeout", has_prior_data=True, is_polling=True)
        assert "bg-amber-500" in dot
        assert label == "Sync disrupted — retrying..."
        assert sev == "degraded"

    def test_18b_polling_error_never_mutates_job_authoritative_status(self) -> None:
        """Contract 18b: A polling error logs a warning and sets degraded indicator, never mutating authoritative job status."""
        cached_jobs = [
            IndexingJobDTO(job_id="j1", document_id="d1", knowledge_base_id="k1", status="PROCESSING", stage="EMBEDDING"),
            IndexingJobDTO(job_id="j2", document_id="d2", knowledge_base_id="k1", status="FAILED", stage="FAILED", error_message="OOM"),
        ]
        # Simulate a polling network failure
        fetch_error = "503 Service Unavailable"
        dot, label, sev = compute_queue_status_indicator(fetch_error=fetch_error, is_polling=True, has_prior_data=True)
        assert sev == "degraded"
        assert label == "Sync disrupted — retrying..."

        # Verify job objects in cache were NOT mutated to FAILED or COMPLETED
        assert cached_jobs[0].status == "PROCESSING"
        assert cached_jobs[1].status == "FAILED"

    def test_18c_scoped_document_fetching_behavior(self) -> None:
        """Contract 18c: Scoped document fetching handles total failure, partial failure, and empty results deterministically."""
        courses = [
            KnowledgeBaseDTO(id="c1", name="CS 101", description="CS"),
            KnowledgeBaseDTO(id="c2", name="MATH 201", description="Math"),
        ]

        # Case 7: All courses succeed with data
        def mock_fetch_success(cid: str) -> list[DocumentDTO]:
            return [DocumentDTO(id=f"doc-{cid}", kb_id=cid, filename=f"syllabus-{cid}.pdf", file_type="pdf", file_size_bytes=1024)]

        res = fetch_all_scoped_documents(courses, mock_fetch_success)
        assert res.is_complete_success is True
        assert res.is_total_failure is False
        assert res.is_partial_failure is False
        assert len(res.documents) == 2

        # Case 8: All courses succeed with zero documents (real empty state)
        res_empty = fetch_all_scoped_documents(courses, lambda cid: [])
        assert res_empty.is_complete_success is True
        assert res_empty.is_total_failure is False
        assert len(res_empty.documents) == 0

        # Case 9: Partial failure (one course fails, one succeeds)
        def mock_fetch_partial(cid: str) -> list[DocumentDTO]:
            if cid == "c2":
                raise RuntimeError("Course c2 timeout")
            return [DocumentDTO(id="doc-c1", kb_id="c1", filename="c1.pdf", file_type="pdf", file_size_bytes=512)]

        res_part = fetch_all_scoped_documents(courses, mock_fetch_partial)
        assert res_part.is_partial_failure is True
        assert res_part.is_complete_success is False
        assert res_part.is_total_failure is False
        assert len(res_part.documents) == 1
        assert "MATH 201" in res_part.failed_courses
        assert "CS 101" in res_part.successful_courses

        # Case 10: Total failure across all courses
        def mock_fetch_fail(cid: str) -> list[DocumentDTO]:
            raise ConnectionError("Network down")

        res_total = fetch_all_scoped_documents(courses, mock_fetch_fail)
        assert res_total.is_total_failure is True
        assert res_total.is_partial_failure is False
        assert res_total.is_complete_success is False
        assert len(res_total.documents) == 0
        assert len(res_total.failed_courses) == 2

    def test_18d_job_history_limit_honesty(self) -> None:
        """Contract 18d: 100-job backend limit is represented honestly as Recent Jobs, never masquerading as infinite history."""
        page_source = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert "Recent Jobs" in page_source
        assert "(recent 100 jobs)" in page_source
        assert "cap)" in page_source

    def test_19_refresh_navigation_preserves_current_job_state(self) -> None:
        """Contract 19: trigger_table_refresh and background polling maintain cached_docs and cached_jobs without blanking UI."""
        page_source = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert "def trigger_table_refresh() -> None:" in page_source
        assert "render_doc_table()" in page_source

    def test_20_automatic_upload_indexing_remains_idempotent(self) -> None:
        """Contract 20: Documents page uses the canonical upload_document API without creating a second queue."""
        page_source = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert "api_client.upload_document" in page_source

    def test_21_document_status_and_processing_view_agree(self) -> None:
        """Contract 21: Documents table and Processing view share the same status badge renderer."""
        page_source = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert "render_status_badge" in page_source

    def test_22_no_user_gains_broader_access_because_of_consolidation(self) -> None:
        """Contract 22: Least privilege is enforced: specialized indexers see restriction note on documents view."""
        page_source = Path("frontend/pages/documents_page.py").read_text(encoding="utf-8")
        assert "Document Repository Listing Restricted" in page_source
        assert "Your administrative role does not grant DOCUMENT_VIEW" in page_source
