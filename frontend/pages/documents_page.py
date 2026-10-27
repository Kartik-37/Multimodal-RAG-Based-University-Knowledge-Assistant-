"""
Documents & Processing Management Workspace.

Unified operational workspace for university administrators:
- In-page View Switcher: "Documents" (file management) and "Processing" (vectorization queue)
- Preserves the approved sequential two-step upload workspace (Part 9F)
- Full document lifecycle: read in source viewer, chunk inspection, safe deletion
- Progressive disclosure: inline expandable document details with stage, vector metrics, and retry
- Complete operational vectorization queue with filtering (All, Active, Needs Attention, Completed), search, attempt counts, and authorized retry
- Live polling for active jobs without losing search, filter, or disclosure state
- Guaranteed text visibility on selected filter pills with high-contrast Ivory/Navy tokens
"""

import asyncio
import html
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from nicegui import events, ui

from backend.app.core.config import settings
from backend.app.core.permissions import Permission
from frontend.client.api_client import api_client
from frontend.client.error_handler import normalize_error
from frontend.client.models import DocumentDTO, IndexingJobDTO, KnowledgeBaseDTO
from frontend.components.layout import has_admin_permission, page_layout
from frontend.components.source_viewer import open_source_viewer
from frontend.components.ui_kit import (
    render_alert,
    render_empty_state,
    render_section_heading,
    render_status_badge,
)
from frontend.state.app_state import state

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".txt", ".md", ".csv"]


def format_stage_label(
    stage: str | None,
    processed: int = 0,
    total: int = 0,
    percent: float = 0.0,
    status: str = "PROCESSING",
) -> str:
    """Return concise, truthful human-readable stage descriptions."""
    if status == "FAILED" or stage == "FAILED":
        return "Failed during processing"
    if status == "COMPLETED" or stage == "COMPLETED":
        if total > 0:
            return f"Ready · {total} chunks indexed"
        return "Ready · Indexed & verified"
    if not stage:
        return "Processing document..."
    s = stage.upper()
    if s == "UPLOADING":
        return "Uploading document..."
    if s in ("VALIDATING", "SAVING"):
        return "Saving document..."
    if s == "EXTRACTING":
        return "Reading document..."
    if s == "CHECKING_VISUALS":
        return "Checking visual pages..."
    if s == "EXTRACTING_VISUALS":
        return "Reading visual content..."
    if s == "CHUNKING":
        return "Preparing searchable text..."
    if s in ("QUEUED_FOR_INDEXING", "QUEUED", "PREPARING"):
        return "Waiting for vector indexing..."
    if s == "EMBEDDING":
        if total > 0 and processed > 0:
            return f"Creating embeddings · {processed} of {total} chunks"
        return "Creating embeddings..."
    if s in ("WRITING_VECTORS", "STORING_VECTORS"):
        if total > 0:
            return f"Saving vectors · {total} chunks"
        return "Saving vectors..."
    if s == "VERIFYING":
        return "Verifying indexed vectors..."
    return s.replace("_", " ").title()


def format_bytes(num_bytes: int) -> str:
    """Format file size into human-readable text."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.2f} MB"


def get_file_type_icon(filename: str) -> str:
    """Return appropriate Material icon for file extension."""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return "picture_as_pdf"
    if lower.endswith((".docx", ".doc")):
        return "description"
    if lower.endswith(".csv"):
        return "table_chart"
    if lower.endswith((".md", ".txt")):
        return "article"
    return "insert_drive_file"


def compute_queue_status_indicator(
    *,
    fetch_error: str | None = None,
    active_count: int = 0,
    failed_count: int = 0,
    has_prior_data: bool = False,
    is_polling: bool = False,
) -> tuple[str, str, str]:
    """
    Decides the global queue status indicator dot class, label text, and status severity.

    Mutually exclusive state decision:
    1. If an error occurred:
       - If we have prior data or this is an ongoing background poll:
         ("w-2 h-2 rounded-full bg-amber-500 shrink-0", "Sync disrupted — retrying...", "degraded")
       - If initial request failed with no prior data:
         ("w-2 h-2 rounded-full bg-rose-500 shrink-0", "Queue unavailable", "error")
    2. If active jobs exist:
       ("w-2 h-2 rounded-full bg-amber-500 animate-pulse shrink-0", f"{active_count} active job(s)", "active")
    3. If no active jobs, but failed jobs exist (never show green idle!):
       label = f"{failed_count} failed job(s) need attention" if failed_count > 1 else "1 failed job needs attention"
       return ("w-2 h-2 rounded-full bg-rose-500 shrink-0", label, "attention")
    4. If no active or failed jobs (idle queue / only completed jobs):
       ("w-2 h-2 rounded-full bg-emerald-500 shrink-0", "Queue idle & synchronized", "idle")
    """
    if fetch_error:
        if has_prior_data or is_polling:
            return ("w-2 h-2 rounded-full bg-amber-500 shrink-0", "Sync disrupted — retrying...", "degraded")
        return ("w-2 h-2 rounded-full bg-rose-500 shrink-0", "Queue unavailable", "error")

    if active_count > 0:
        return ("w-2 h-2 rounded-full bg-amber-500 animate-pulse shrink-0", f"{active_count} active job(s)", "active")

    if failed_count > 0:
        label = f"{failed_count} failed job(s) need attention" if failed_count > 1 else "1 failed job needs attention"
        return ("w-2 h-2 rounded-full bg-rose-500 shrink-0", label, "attention")

    return ("w-2 h-2 rounded-full bg-emerald-500 shrink-0", "Queue idle & synchronized", "idle")


@dataclass
class DocumentFetchResult:
    documents: list[DocumentDTO]
    successful_courses: list[str]
    failed_courses: list[str]
    is_total_failure: bool
    is_partial_failure: bool
    is_complete_success: bool


def fetch_all_scoped_documents(
    courses: list[KnowledgeBaseDTO],
    fetch_fn: Callable[[str], list[DocumentDTO]],
) -> DocumentFetchResult:
    all_docs: list[DocumentDTO] = []
    success_courses: list[str] = []
    failed_courses: list[str] = []

    for c in courses:
        try:
            c_docs = fetch_fn(c.id)
            all_docs.extend(c_docs)
            success_courses.append(c.name)
        except Exception as err:
            failed_courses.append(c.name)
            logger.warning(f"Failed to fetch documents for course {c.name} ({c.id}): {err}")

    total_courses = len(courses)
    is_total_failure = (total_courses > 0 and len(failed_courses) == total_courses)
    is_partial_failure = (len(failed_courses) > 0 and not is_total_failure)
    is_complete_success = (len(failed_courses) == 0)

    return DocumentFetchResult(
        documents=all_docs,
        successful_courses=success_courses,
        failed_courses=failed_courses,
        is_total_failure=is_total_failure,
        is_partial_failure=is_partial_failure,
        is_complete_success=is_complete_success,
    )


def register_documents_page() -> None:
    @ui.page("/documents")
    def documents_page(kb_id: str | None = None, view: str | None = None) -> None:
        user = state.current_user
        is_admin = bool(user and user.role == "ADMIN")
        is_main = bool(user and user.admin_role == "MAIN_ADMIN")

        can_view_documents = has_admin_permission(user, Permission.DOCUMENT_VIEW)
        can_view_jobs = (
            is_main
            or has_admin_permission(user, Permission.DOCUMENT_VIEW)
            or has_admin_permission(user, Permission.DOCUMENT_INDEX)
            or has_admin_permission(user, Permission.DOCUMENT_INDEX_RETRY)
        )
        can_upload_documents = has_admin_permission(user, Permission.DOCUMENT_UPLOAD)
        can_delete_documents = has_admin_permission(user, Permission.DOCUMENT_DELETE)
        can_retry_jobs = has_admin_permission(user, Permission.DOCUMENT_INDEX_RETRY)

        if not is_admin or not (can_view_documents or can_view_jobs):
            with page_layout(
                title="Documents & Processing",
                subtitle="Permission-aware course material access.",
                active_route="/documents",
                require_auth=True,
            ):
                render_empty_state(
                    icon="lock",
                    title="Document Management Unavailable",
                    description="You do not have permission to view course documents or processing operations.",
                )
            return

        # Determine initial in-page view
        requested_view = (view or "").lower().strip()
        if requested_view in ("documents", "processing"):
            current_view = requested_view
        else:
            current_view = "processing" if (not can_view_documents and can_view_jobs) else "documents"

        # Load accessible courses if permitted to view documents
        all_courses: list[KnowledgeBaseDTO] = []
        course_map: dict[str, str] = {}
        if can_view_documents:
            try:
                all_courses = api_client.get_document_scope_courses()
                course_map = {c.id: c.name for c in all_courses}
            except Exception as err:
                with page_layout(
                    title="Documents & Processing",
                    subtitle="Permission-aware course material access.",
                    active_route="/documents",
                    require_auth=True,
                ):
                    render_alert(
                        f"Unable to load accessible courses: {normalize_error(err, context='course')}",
                        "negative",
                    )
                return

        with page_layout(
            title="Documents & Processing",
            subtitle="Curate course materials, inspect text vectorization, and recover indexing jobs.",
            active_route="/documents",
            require_auth=True,
        ):
            # -----------------------------------------------------------------
            # Shared State Across In-Page Views
            # -----------------------------------------------------------------
            cached_docs: list[DocumentDTO] = []
            cached_jobs: list[IndexingJobDTO] = []
            expanded_doc_ids: set[str] = set()

            doc_search_query = ""
            doc_status_filter = "ALL"  # ALL | READY | INDEXING | FAILED

            proc_active_tab = "ALL"  # ALL | ACTIVE | FAILED | COMPLETED
            proc_search_query = ""

            poll_timer: ui.timer | None = None

            # -----------------------------------------------------------------
            # In-Page View Switcher Bar (Responsive & Compact)
            # -----------------------------------------------------------------
            with ui.row().classes("w-full justify-between items-center mb-3 sm:mb-5 flex-wrap sm:flex-nowrap gap-2 sm:gap-4"):
                with ui.element("div").classes("view-switcher-container"):
                    doc_tab_btn = ui.button(
                        "Documents",
                        icon="description",
                        on_click=lambda: switch_view("documents"),
                    ).props("flat dense no-caps")

                    proc_tab_btn = ui.button(
                        "Processing",
                        icon="sync",
                        on_click=lambda: switch_view("processing"),
                    ).props("flat dense no-caps")

                # Right side: Scope badge / Refresh indicator (composed cleanly on single row on mobile)
                with ui.row().classes("items-center justify-between sm:justify-end gap-2 sm:gap-3 w-full sm:w-auto flex-nowrap"):
                    live_indicator_row = ui.row().classes("items-center gap-1.5 text-xs text-secondary-navy flex-nowrap min-w-0")
                    with live_indicator_row:
                        live_dot = ui.element("div").classes("w-2 h-2 rounded-full bg-emerald-500 shrink-0")
                        live_status_label = ui.label("Queue idle & synchronized").classes("text-xs leading-none truncate")

                    ui.button("Refresh Workspace", icon="refresh", on_click=lambda: refresh_all_data()).props(
                        "outline dense no-caps"
                    ).classes(
                        "text-xs font-bold text-primary-navy border border-subtle px-2.5 py-1 rounded hover:bg-surface shrink-0"
                    ).tooltip("Refresh course documents and vectorization status")

            def update_live_indicator(fetch_error: str | None = None, is_polling: bool = False) -> None:
                active_count = sum(1 for j in cached_jobs if j.status in ("QUEUED", "PROCESSING", "PENDING"))
                failed_count = sum(1 for j in cached_jobs if j.status == "FAILED")
                dot_cls, label_text, _ = compute_queue_status_indicator(
                    fetch_error=fetch_error,
                    active_count=active_count,
                    failed_count=failed_count,
                    has_prior_data=bool(cached_jobs),
                    is_polling=is_polling,
                )
                live_dot.classes(replace=dot_cls)
                live_status_label.text = label_text

            def update_switcher_classes() -> None:
                if current_view == "documents":
                    doc_tab_btn.classes(replace="view-switcher-pill view-switcher-pill-active")
                    proc_tab_btn.classes(replace="view-switcher-pill")
                else:
                    doc_tab_btn.classes(replace="view-switcher-pill")
                    proc_tab_btn.classes(replace="view-switcher-pill view-switcher-pill-active")

                # Update badge labels
                doc_tab_btn.text = f"Documents ({len(cached_docs)})" if cached_docs else "Documents"

                failed_jobs_count = sum(1 for j in cached_jobs if j.status == "FAILED")
                active_jobs_count = sum(1 for j in cached_jobs if j.status in ("QUEUED", "PROCESSING", "PENDING"))
                if failed_jobs_count > 0:
                    proc_tab_btn.text = f"Processing ({len(cached_jobs)} • {failed_jobs_count} alert)"
                elif active_jobs_count > 0:
                    proc_tab_btn.text = f"Processing ({len(cached_jobs)} • {active_jobs_count} active)"
                elif cached_jobs:
                    proc_tab_btn.text = f"Processing ({len(cached_jobs)})"
                else:
                    proc_tab_btn.text = "Processing"

            def switch_view(target_view: str) -> None:
                nonlocal current_view
                current_view = target_view
                update_switcher_classes()

                if current_view == "documents":
                    documents_view_container.visible = True
                    processing_view_container.visible = False
                else:
                    documents_view_container.visible = False
                    processing_view_container.visible = True
                    if not cached_jobs:
                        refresh_processing_queue()

                # Update browser address query without triggering a destructive full page reload
                kb_part = f"&kb_id={kb_id}" if kb_id else ""
                ui.run_javascript(
                    f'window.history.replaceState(null, "", "/documents?view={target_view}{kb_part}");'
                )

            # Containers for the two views
            documents_view_container = ui.column().classes("w-full gap-0")
            processing_view_container = ui.column().classes("w-full gap-0")

            documents_view_container.visible = (current_view == "documents")
            processing_view_container.visible = (current_view == "processing")

            # =================================================================
            # VIEW 1: DOCUMENTS VIEW
            # =================================================================
            with documents_view_container:
                if not can_view_documents:
                    with ui.card().classes(
                        "w-full p-8 bg-surface-elevated border border-subtle rounded-lg items-center text-center gap-3"
                    ):
                        ui.icon("lock", size="2rem").classes("text-secondary-navy")
                        ui.label("Document Repository Listing Restricted").classes(
                            "text-base font-bold text-primary-navy font-editorial"
                        )
                        ui.label(
                            "Your administrative role does not grant DOCUMENT_VIEW permissions to list stored course materials. "
                            "You have operational permission to monitor and retry background vectorization jobs in the Processing queue."
                        ).classes("text-xs text-secondary-navy max-w-md leading-relaxed")
                        ui.button(
                            "Go to Processing Queue",
                            icon="sync",
                            on_click=lambda: switch_view("processing"),
                        ).props("no-caps dense").classes("bg-surface-navy text-inverted font-bold text-xs px-4 py-2 rounded mt-2")
                else:
                    # -------------------------------------------------------------
                    # Inline Upload Workspace Configuration & State (Part 9F)
                    # -------------------------------------------------------------
                    max_upload_bytes = settings.MAX_UPLOAD_SIZE_BYTES
                    max_mb = max_upload_bytes // (1024 * 1024)

                    upload_form_container: ui.column | None = None
                    upload_progress_container: ui.column | None = None
                    inline_upload_alert: ui.column | None = None
                    upload_course_select: ui.select | None = None

                    uploading_doc_id: str | None = None
                    uploading_kb_id: str | None = None
                    uploaded_filename: str = ""
                    uploaded_filesize: int = 0

                    def reset_upload_workspace() -> None:
                        nonlocal uploading_doc_id, uploading_kb_id, uploaded_filename, uploaded_filesize
                        uploading_doc_id = None
                        uploading_kb_id = None
                        uploaded_filename = ""
                        uploaded_filesize = 0
                        if inline_upload_alert:
                            inline_upload_alert.clear()
                        if upload_progress_container:
                            upload_progress_container.clear()
                            upload_progress_container.visible = False
                        if upload_form_container:
                            upload_form_container.visible = True

                    def update_workspace_progress_ui(
                        filename: str,
                        course_name: str,
                        file_size: int,
                        stage: str,
                        status: str,
                        processed: int = 0,
                        total: int = 0,
                        pct: float = 0.0,
                        error_msg: str | None = None,
                    ) -> None:
                        if not upload_progress_container:
                            return
                        upload_progress_container.clear()
                        with upload_progress_container:
                            with ui.card().classes("w-full p-4 bg-surface-elevated border border-subtle rounded-lg shadow-none gap-2"):
                                with ui.row().classes("w-full justify-between items-start gap-2"):
                                    with ui.column().classes("gap-0 min-w-0 flex-1"):
                                        ui.label(filename).classes("text-sm font-bold text-primary-navy truncate font-sans")
                                        ui.label(f"{course_name} • {format_bytes(file_size)}").classes("text-xs text-secondary-navy")
                                    with ui.row().classes("items-center shrink-0"):
                                        render_status_badge(
                                            "completed" if status == "COMPLETED" else ("failed" if status == "FAILED" else "indexing"),
                                            "Ready" if status == "COMPLETED" else ("Failed" if status == "FAILED" else (stage.replace("_", " ").title() if stage else "Processing")),
                                        )

                                stage_upper = (stage or "").upper()
                                is_embedding_prog = (stage_upper == "EMBEDDING" and total > 0 and processed > 0 and status not in ("FAILED", "COMPLETED"))

                                if status == "COMPLETED":
                                    ui.linear_progress(value=1.0).props('rounded color="emerald" size="6px"').classes("w-full my-2")
                                elif status == "FAILED":
                                    ui.linear_progress(value=1.0).props('rounded color="negative" size="6px"').classes("w-full my-2")
                                elif is_embedding_prog:
                                    actual_frac = min(processed / total, 0.99)
                                    ui.linear_progress(value=actual_frac).props('rounded color="primary" size="6px"').classes("w-full my-2")
                                else:
                                    ui.linear_progress(value=None).props('indeterminate rounded color="primary" size="6px"').classes("w-full my-2")

                                stage_text = format_stage_label(stage, processed, total, pct, status)
                                with ui.row().classes("w-full justify-between items-center text-xs"):
                                    ui.label(stage_text).classes(
                                        "font-medium text-rose-700" if status == "FAILED" else ("text-emerald-800" if status == "COMPLETED" else "text-primary-navy")
                                    )
                                    if is_embedding_prog:
                                        pct_chk = round((processed / total) * 100.0)
                                        ui.label(f"{pct_chk}%").classes("font-mono text-secondary-navy font-semibold")
                                    elif status == "COMPLETED" and total > 0:
                                        ui.label(f"{total} chunks indexed").classes("font-mono text-emerald-700")

                                if error_msg and status == "FAILED":
                                    render_alert(error_msg, level="negative")

                                with ui.row().classes("w-full justify-end items-center gap-2 pt-2 border-t border-subtle mt-1"):
                                    if status == "COMPLETED":
                                        ui.button("Upload Another Document", icon="add", on_click=reset_upload_workspace).props("outline dense no-caps").classes(
                                            "text-xs font-semibold text-primary-navy px-3 py-1.5"
                                        )
                                    elif status == "FAILED":
                                        ui.button("Try Again", icon="refresh", on_click=reset_upload_workspace).props("outline dense no-caps").classes(
                                            "text-xs font-semibold text-primary-navy px-3 py-1.5"
                                        )
                                    else:
                                        ui.label("Processing continues automatically in background").classes("text-[11px] text-secondary-navy italic")

                    async def handle_file_upload(e: events.UploadEventArguments) -> None:
                        nonlocal uploading_doc_id, uploading_kb_id, uploaded_filename, uploaded_filesize
                        if inline_upload_alert:
                            inline_upload_alert.clear()
                        file_obj = e.file
                        fname = file_obj.name.strip()
                        lower_fname = fname.lower()
                        target_kb = upload_course_select.value if upload_course_select else None

                        if not target_kb:
                            if inline_upload_alert:
                                with inline_upload_alert:
                                    render_alert("Please select a target course for upload.", level="warning")
                            return

                        if not any(lower_fname.endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                            if inline_upload_alert:
                                with inline_upload_alert:
                                    render_alert(f"Unsupported file format '{fname}'. Please upload a PDF, DOCX, TXT, MD, or CSV file.", level="negative")
                            return

                        size = file_obj.size() if hasattr(file_obj, "size") and callable(file_obj.size) else 0
                        file_path = None
                        content = None
                        if hasattr(file_obj, "_path") and file_obj._path:
                            file_path = str(file_obj._path)
                        else:
                            try:
                                content = await file_obj.read()
                                if size == 0:
                                    size = len(content)
                            except Exception as read_err:
                                if inline_upload_alert:
                                    with inline_upload_alert:
                                        render_alert(f"Failed to read file: {read_err}", level="negative")
                                return

                        if size > max_upload_bytes:
                            if inline_upload_alert:
                                with inline_upload_alert:
                                    render_alert(f"File '{fname}' exceeds the maximum allowed size of {max_mb} MiB ({format_bytes(size)}).", level="negative")
                            return

                        if upload_form_container:
                            upload_form_container.visible = False
                        if upload_progress_container:
                            upload_progress_container.visible = True

                        uploading_kb_id = target_kb
                        uploaded_filename = fname
                        uploaded_filesize = size
                        selected_course_name = course_map.get(target_kb, "Course")

                        update_workspace_progress_ui(
                            filename=fname,
                            course_name=selected_course_name,
                            file_size=size,
                            stage="UPLOADING",
                            status="PROCESSING",
                        )

                        try:
                            doc = await asyncio.to_thread(
                                api_client.upload_document,
                                target_kb,
                                fname,
                                content=content,
                                content_size_bytes=size,
                                file_path=file_path,
                            )
                            uploading_doc_id = str(doc.id)

                            update_workspace_progress_ui(
                                filename=fname,
                                course_name=selected_course_name,
                                file_size=size,
                                stage=doc.current_stage or "SAVING",
                                status=doc.status,
                                processed=doc.processed_chunks,
                                total=doc.total_chunks,
                                pct=doc.progress_percent,
                            )

                            if poll_timer:
                                poll_timer.activate()
                            background_poll_tick()
                        except Exception as err:
                            update_workspace_progress_ui(
                                filename=fname,
                                course_name=selected_course_name,
                                file_size=size,
                                stage="FAILED",
                                status="FAILED",
                                error_msg=normalize_error(err, context="document"),
                            )

                    # -------------------------------------------------------------
                    # Chunk Inspection Dialog
                    # -------------------------------------------------------------
                    chunk_dialog = ui.dialog()
                    with chunk_dialog, ui.card().classes(
                        "w-full max-w-2xl p-6 bg-surface-elevated border border-subtle rounded-lg shadow-none gap-4"
                    ):
                        with ui.row().classes("w-full items-center justify-between pb-3 border-b border-subtle"):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon("segment", size="1.25rem").classes("text-primary-navy")
                                chunk_dialog_title = ui.label("Document Chunks").classes(
                                    "text-base sm:text-lg font-bold text-primary-navy font-editorial truncate"
                                )
                            ui.button(icon="close", on_click=chunk_dialog.close).props("flat round dense").classes(
                                "text-secondary-navy hover:text-primary-navy"
                            )

                        chunk_dialog_content = ui.column().classes("w-full max-h-96 overflow-y-auto")

                        with ui.row().classes("w-full justify-end pt-3 border-t border-subtle"):
                            ui.button("Close", on_click=chunk_dialog.close).props("outline no-caps dense").classes(
                                "text-xs font-semibold text-primary-navy border border-subtle px-4 py-1.5"
                            )

                    def open_chunk_dialog(doc_id: str, doc_name: str, doc_kb_id: str) -> None:
                        chunk_dialog_title.text = f"Vector Chunks — {doc_name}"
                        chunk_dialog_content.clear()
                        with chunk_dialog_content:
                            with ui.row().classes("w-full py-6 justify-center items-center gap-2"):
                                ui.spinner(size="sm", color="primary")
                                ui.label("Loading chunk vectors...").classes("text-xs text-secondary-navy")

                        chunk_dialog.open()

                        chunk_error: str | None = None
                        chunks: list[dict[str, Any]] = []
                        try:
                            chunks = api_client.get_document_chunks(kb_id=doc_kb_id, document_id=doc_id)
                        except Exception as ex:
                            chunk_error = normalize_error(ex, context="document")

                        chunk_dialog_content.clear()
                        with chunk_dialog_content:
                            if chunk_error:
                                render_alert(
                                    f"Failed to inspect chunk vectors: {chunk_error}",
                                    level="negative",
                                    action_label="Retry",
                                    on_action=lambda: open_chunk_dialog(doc_id, doc_name, doc_kb_id),
                                )
                            elif not chunks:
                                ui.label("No vector chunks generated yet for this document.").classes(
                                    "text-xs text-secondary-navy italic py-4 text-center w-full"
                                )
                            else:
                                ui.label(f"Total: {len(chunks)} indexed vector chunk(s)").classes(
                                    "text-xs font-semibold text-secondary-navy mb-2"
                                )
                                with ui.column().classes("w-full gap-2.5"):
                                    for i, chk in enumerate(chunks, 1):
                                        with ui.card().classes("w-full p-3 bg-canvas border border-subtle rounded text-xs shadow-none gap-1"):
                                            with ui.row().classes("w-full justify-between items-center font-bold text-secondary-navy uppercase text-[10px]"):
                                                ui.label(f"Chunk #{i} • Page {chk.get('page_number', 'N/A')}")
                                                ui.label(f"{chk.get('token_count', 0)} tokens")
                                            ui.label(chk.get("content", "")).classes(
                                                "text-primary-navy leading-relaxed select-text font-serif mt-1"
                                            )

                    # -------------------------------------------------------------
                    # Delete Confirmation Dialog
                    # -------------------------------------------------------------
                    delete_dialog = ui.dialog()
                    pending_delete: dict[str, str] = {}
                    delete_dialog_msg: ui.label | None = None

                    with delete_dialog, ui.card().classes(
                        "w-full max-w-sm p-6 bg-surface-elevated border border-subtle rounded-lg shadow-none gap-4"
                    ):
                        ui.label("Delete Course Material?").classes("text-lg font-bold text-primary-navy font-editorial")
                        delete_dialog_msg = ui.label("").classes("text-xs sm:text-sm text-secondary-navy leading-relaxed")

                        def execute_delete() -> None:
                            delete_dialog.close()
                            target_kb = pending_delete.get("kb_id")
                            target_doc = pending_delete.get("doc_id")
                            fname = pending_delete.get("filename", "document")
                            if target_kb and target_doc:
                                try:
                                    api_client.delete_document(target_kb, target_doc)
                                    ui.notify(f"Deleted '{fname}'.", type="positive")
                                    refresh_documents()
                                except Exception as ex:
                                    ui.notify(f"Delete failed: {normalize_error(ex, context='document')}", type="negative")

                        def cancel_delete() -> None:
                            delete_dialog.close()
                            if delete_dialog_msg:
                                delete_dialog_msg.text = ""

                        with ui.row().classes("w-full justify-end gap-3 pt-3 border-t border-subtle"):
                            ui.button("Cancel", on_click=cancel_delete).props("flat dense no-caps").classes(
                                "text-xs font-semibold text-secondary-navy"
                            )
                            ui.button("Delete", icon="delete", on_click=execute_delete).props("dense no-caps").classes(
                                "text-xs font-bold px-3 py-1.5 bg-rose-700 text-inverted rounded"
                            )

                    def confirm_delete(doc_id: str, doc_name: str, doc_kb_id: str) -> None:
                        pending_delete["kb_id"] = doc_kb_id
                        pending_delete["doc_id"] = doc_id
                        pending_delete["filename"] = doc_name
                        if delete_dialog_msg:
                            delete_dialog_msg.text = (
                                f"Are you sure you want to delete '{doc_name}'? "
                                "All associated text vectors will be removed permanently."
                            )
                        delete_dialog.open()

                    # -------------------------------------------------------------
                    # Inline Upload Workspace (Sequential Two-Step Intake)
                    # -------------------------------------------------------------
                    if can_upload_documents:
                        with ui.column().classes("w-full mb-4 sm:mb-6 gap-2.5 sm:gap-3 upload-intake-workspace"):
                            with ui.row().classes("w-full items-baseline justify-between gap-2 pb-2 border-b border-subtle/60"):
                                ui.label("Add Course Material").classes(
                                    "text-sm font-bold text-primary-navy font-editorial"
                                )
                                ui.label("Sequential Intake").classes(
                                    "text-[11px] font-semibold text-gold font-mono tracking-wider uppercase"
                                )

                            inline_upload_alert = ui.column().classes("w-full")
                            upload_form_container = ui.column().classes("w-full gap-4")
                            upload_progress_container = ui.column().classes("w-full gap-3")
                            upload_progress_container.visible = False

                            with upload_form_container:
                                # Step 1: Destination
                                with ui.element("div").classes("intake-step-destination"):
                                    with ui.row().classes("items-center gap-1.5"):
                                        ui.label("01").classes("intake-step-number")
                                        ui.label("Target Course").classes("intake-field-label")
                                        ui.label("*").classes("text-primary-navy font-bold text-xs")

                                    course_select_options = {c.id: c.name for c in all_courses}
                                    initial_target = kb_id if (kb_id and kb_id in course_select_options) else None

                                    with ui.element("div").classes("w-full max-w-md"):
                                        upload_course_select = ui.select(
                                            options=course_select_options,
                                            value=initial_target,
                                        ).props('outlined dense options-dense').classes(
                                            f"w-full text-sm upload-course-select intake-course-select {'is-unselected' if not initial_target else ''}"
                                        )
                                        if not initial_target:
                                            upload_course_select.props('display-value="Choose a course" placeholder="Choose a course"')
                                        else:
                                            upload_course_select.props('placeholder="Choose a course"')

                                        def on_course_select_change(e: Any) -> None:
                                            if upload_course_select:
                                                if e.value:
                                                    upload_course_select.props(remove="display-value")
                                                    upload_course_select.classes(remove="is-unselected")
                                                else:
                                                    upload_course_select.props('display-value="Choose a course"')
                                                    upload_course_select.classes("is-unselected")
                                                upload_course_select.update()

                                        upload_course_select.on_value_change(on_course_select_change)

                                # Step 2: Document Intake Surface
                                with ui.element("div").classes("intake-step-document"):
                                    with ui.row().classes("items-center gap-1.5"):
                                        ui.label("02").classes("intake-step-number")
                                        ui.label("Document File").classes("intake-field-label")
                                        ui.label("*").classes("text-primary-navy font-bold text-xs")

                                    ui.upload(
                                        label="Drop a document here, or click to choose a file",
                                        on_upload=handle_file_upload,
                                        auto_upload=True,
                                        max_file_size=max_upload_bytes,
                                    ).props('flat accept=".pdf,.docx,.txt,.md,.csv"').classes(
                                        "document-intake-surface academic-uploader w-full"
                                    )

                    # -------------------------------------------------------------
                    # Documents Toolbar: Search Input & Status Filter Pills
                    # -------------------------------------------------------------
                    with ui.column().classes("w-full gap-2.5 sm:gap-3 mb-4 sm:mb-6"):
                        with ui.row().classes("w-full items-center justify-between gap-4 flex-wrap"):
                            doc_search_box = (
                                ui.input(placeholder="Search documents by filename...", value=doc_search_query)
                                .props("outlined dense clearable")
                                .classes("w-full sm:w-80 md:w-96 text-sm minimalist-input")
                            )

                        with ui.row().classes("w-full items-center justify-between gap-3 flex-wrap pt-1 border-t border-subtle/50"):
                            doc_status_pills_container = ui.row().classes("items-center gap-2 flex-wrap")
                            ui.button("Refresh List", icon="refresh", on_click=lambda: refresh_documents()).props(
                                "flat dense no-caps"
                            ).classes("text-xs font-semibold text-secondary-navy hover:text-primary-navy")

                    # Active Ingestion Banner
                    active_pipeline_container = ui.column().classes("w-full mb-4 gap-2")

                    # Documents Table Container
                    doc_table_container = ui.column().classes("w-full min-h-[220px]")

                    def render_active_pipeline() -> None:
                        active_pipeline_container.clear()
                        active_docs = [
                            d
                            for d in cached_docs
                            if d.indexing_status in ("QUEUED", "PROCESSING")
                            or d.status in ("PROCESSING", "PENDING")
                        ]
                        if uploading_doc_id:
                            active_docs = [d for d in active_docs if str(d.id) != str(uploading_doc_id)]

                        if not active_docs:
                            active_pipeline_container.visible = False
                            return

                        active_pipeline_container.visible = True
                        with active_pipeline_container:
                            with ui.card().classes(
                                "w-full p-4 bg-surface-elevated border border-gold/40 rounded-lg shadow-none gap-3"
                            ):
                                with ui.row().classes("w-full justify-between items-center"):
                                    with ui.row().classes("items-center gap-2"):
                                        ui.spinner(size="xs", color="primary")
                                        ui.label("Active Ingestion & Indexing Pipeline").classes(
                                            "text-xs font-bold uppercase tracking-wider text-primary-navy font-sans"
                                        )
                                    ui.button(
                                        "View Processing Queue",
                                        icon="arrow_forward",
                                        on_click=lambda: switch_view("processing"),
                                    ).props("flat dense no-caps").classes(
                                        "text-xs text-secondary-navy hover:text-primary-navy font-semibold"
                                    )

                                for ad in active_docs:
                                    kb_name = course_map.get(ad.kb_id, "Course")
                                    stage_text = format_stage_label(
                                        ad.current_stage,
                                        ad.embedded_chunks,
                                        ad.total_chunks,
                                        ad.progress_percent,
                                        ad.indexing_status,
                                    )
                                    with ui.column().classes("w-full p-3 bg-canvas border border-subtle rounded gap-2"):
                                        with ui.row().classes("w-full justify-between items-center gap-2"):
                                            with ui.column().classes("gap-0 min-w-0 flex-1"):
                                                ui.label(ad.filename).classes("text-xs font-bold text-primary-navy truncate font-sans")
                                                ui.label(kb_name).classes("text-[10px] text-secondary-navy truncate")
                                            with ui.row().classes("items-center gap-2 shrink-0"):
                                                render_status_badge("indexing", ad.current_stage or "Processing")

                                        stage_upper = (ad.current_stage or "").upper()
                                        is_embedding_prog = (stage_upper == "EMBEDDING" and ad.total_chunks > 0 and ad.embedded_chunks > 0)
                                        if is_embedding_prog:
                                            emb_pct = min(ad.embedded_chunks / ad.total_chunks, 0.99)
                                            ui.linear_progress(value=emb_pct).props(
                                                'rounded color="primary" size="6px"'
                                            ).classes("w-full")
                                        else:
                                            ui.linear_progress(value=None).props(
                                                'indeterminate rounded color="primary" size="6px"'
                                            ).classes("w-full")

                                        with ui.row().classes("w-full justify-between items-center text-[11px]"):
                                            ui.label(stage_text).classes("font-medium text-primary-navy truncate")
                                            if is_embedding_prog:
                                                pct_disp = round((ad.embedded_chunks / ad.total_chunks) * 100.0)
                                                ui.label(f"{pct_disp}%").classes("font-mono text-secondary-navy font-semibold shrink-0")

                    def render_doc_table(
                        partial_warning: str | None = None,
                        error_banner: str | None = None,
                    ) -> None:
                        doc_table_container.clear()
                        doc_status_pills_container.clear()

                        # Status pill definitions
                        total_cnt = len(cached_docs)
                        ready_cnt = sum(1 for d in cached_docs if d.indexing_status == "COMPLETED")
                        indexing_cnt = sum(
                            1
                            for d in cached_docs
                            if d.indexing_status in ("QUEUED", "PROCESSING")
                            or d.status in ("PROCESSING", "PENDING")
                        )
                        failed_cnt = sum(
                            1
                            for d in cached_docs
                            if d.indexing_status == "FAILED" or d.status == "FAILED"
                        )

                        with doc_status_pills_container:
                            filters = [
                                ("ALL", f"All ({total_cnt})"),
                                ("READY", f"Ready ({ready_cnt})"),
                                ("INDEXING", f"Indexing ({indexing_cnt})"),
                                ("FAILED", f"Failed ({failed_cnt})"),
                            ]
                            for f_key, f_label in filters:
                                is_sel = doc_status_filter == f_key
                                btn_cls = (
                                    "bg-primary-navy !text-white font-bold filter-pill-selected shadow-none"
                                    if is_sel
                                    else "bg-surface text-secondary-navy hover:bg-surface-subtle font-medium"
                                )

                                def make_pill_handler(k=f_key):
                                    nonlocal doc_status_filter
                                    doc_status_filter = k
                                    render_doc_table()

                                ui.button(f_label, on_click=make_pill_handler).props("flat dense no-caps").classes(
                                    f"px-2.5 py-1 text-xs rounded-full border border-subtle transition-colors {btn_cls}"
                                )

                        # Filter documents by search and status
                        q = doc_search_query.strip().lower()
                        filtered = cached_docs

                        if q:
                            filtered = [d for d in filtered if q in d.filename.lower()]

                        if doc_status_filter == "READY":
                            filtered = [d for d in filtered if d.indexing_status == "COMPLETED"]
                        elif doc_status_filter == "INDEXING":
                            filtered = [
                                d
                                for d in filtered
                                if d.indexing_status in ("QUEUED", "PROCESSING")
                                or d.status in ("PROCESSING", "PENDING")
                            ]
                        elif doc_status_filter == "FAILED":
                            filtered = [
                                d
                                for d in filtered
                                if d.indexing_status == "FAILED" or d.status == "FAILED"
                            ]

                        with doc_table_container:
                            if error_banner:
                                with ui.row().classes(
                                    "w-full items-center justify-between p-3 bg-amber-50 border border-amber-300 rounded mb-3 flex-wrap gap-2"
                                ):
                                    with ui.row().classes("items-center gap-2"):
                                        ui.icon("warning", size="1.25rem").classes("text-amber-800 shrink-0")
                                        ui.label(error_banner).classes("text-xs text-amber-900 leading-snug")
                                    ui.button("Retry", icon="refresh", on_click=lambda: refresh_documents()).props(
                                        "outline dense no-caps"
                                    ).classes("text-xs font-bold text-amber-900 border border-amber-400 hover:bg-amber-100 px-2.5 py-1 rounded")

                            if partial_warning:
                                render_alert(partial_warning, level="warning")

                            if not cached_docs and not error_banner:
                                render_empty_state(
                                    icon="description",
                                    title="No Documents Available",
                                    description="No documents are available across your accessible courses.",
                                )
                                return

                            if not filtered:
                                def clear_doc_filters() -> None:
                                    nonlocal doc_search_query, doc_status_filter
                                    doc_search_query = ""
                                    doc_status_filter = "ALL"
                                    doc_search_box.value = ""
                                    render_doc_table()

                                render_empty_state(
                                    icon="search_off",
                                    title="No Documents Found",
                                    description=f'No documents match "{q}" with the active filter.'
                                    if q
                                    else "No documents match the active filter.",
                                    action_label="Clear Filters",
                                    on_action=clear_doc_filters,
                                    action_icon="clear",
                                )
                                return

                            # Document Management Table with Progressive Disclosure
                            with ui.column().classes(
                                "w-full bg-surface-elevated border border-subtle rounded-lg overflow-hidden shadow-none"
                            ):
                                # Table Header
                                with ui.row().classes(
                                    "w-full px-5 py-3 border-b border-subtle text-xs font-bold text-secondary-navy uppercase tracking-wider items-center justify-between bg-surface/30"
                                ):
                                    ui.label("Document Material").classes("flex-1 min-w-[200px]")
                                    ui.label("Course").classes("w-40 text-left hidden md:block")
                                    ui.label("Size & Format").classes("w-28 text-left hidden sm:block")
                                    ui.label("Pipeline & Indexing").classes("w-48 text-left")
                                    ui.label("Actions").classes("w-40 text-right")

                                # Table Rows
                                for idx, doc in enumerate(filtered):
                                    doc_id_str = str(doc.id)
                                    is_expanded = doc_id_str in expanded_doc_ids
                                    is_last = idx == len(filtered) - 1 and not is_expanded
                                    border_b = "" if is_last else "border-b border-subtle"
                                    kb_id_val = str(getattr(doc, "kb_id", getattr(doc, "knowledge_base_id", "")))
                                    doc_kb_name = course_map.get(kb_id_val, "Course")

                                    with ui.column().classes(f"w-full {border_b}"):
                                        with ui.row().classes(
                                            "w-full px-5 py-3.5 items-center justify-between hover:bg-surface/50 transition-colors gap-4"
                                        ):
                                            # Left: Expand Toggle + Icon + Document Title
                                            with ui.row().classes("items-center gap-2 flex-1 min-w-[200px]"):
                                                def toggle_row(did=doc_id_str):
                                                    if did in expanded_doc_ids:
                                                        expanded_doc_ids.remove(did)
                                                    else:
                                                        expanded_doc_ids.add(did)
                                                    render_doc_table()

                                                chevron_icon = "expand_less" if is_expanded else "expand_more"
                                                ui.button(
                                                    icon=chevron_icon,
                                                    on_click=toggle_row,
                                                ).props('flat round dense aria-label="Toggle details"').classes(
                                                    "text-secondary-navy hover:text-primary-navy shrink-0 -ml-2"
                                                ).tooltip("Hide details" if is_expanded else "Inspect stage details & retry")

                                                ui.icon(get_file_type_icon(doc.filename), size="18px").classes(
                                                    "text-primary-navy shrink-0"
                                                )
                                                with ui.column().classes("gap-0 min-w-0 flex-1"):
                                                    ui.label(doc.filename).classes(
                                                        "text-xs sm:text-sm font-semibold text-primary-navy truncate font-sans"
                                                    ).props(f'title="{html.escape(doc.filename, quote=True)}"')
                                                    ui.label(f"{doc_kb_name} • {format_bytes(doc.file_size_bytes)}").classes(
                                                        "text-[10px] text-secondary-navy block sm:hidden truncate"
                                                    )

                                            # Course Name
                                            with ui.row().classes("w-40 items-center hidden md:flex"):
                                                ui.label(doc_kb_name).classes(
                                                    "text-xs text-secondary-navy truncate font-medium"
                                                ).props(f'title="{html.escape(doc_kb_name, quote=True)}"')

                                            # Size & Format
                                            with ui.row().classes(
                                                "w-28 items-center gap-1.5 hidden sm:flex font-mono text-xs text-secondary-navy"
                                            ):
                                                ui.label(doc.file_type.upper()).classes(
                                                    "font-bold text-[10px] px-1.5 py-0.5 rounded bg-surface border border-subtle"
                                                )
                                                ui.label(format_bytes(doc.file_size_bytes)).classes("text-[11px]")

                                            # Pipeline & Indexing Status Cell
                                            with ui.column().classes("w-48 gap-1 justify-center"):
                                                if doc.indexing_status == "COMPLETED" or (
                                                    doc.status == "COMPLETED"
                                                    and doc.indexing_status in (None, "", "COMPLETED", "INDEXED")
                                                ):
                                                    with ui.row().classes("items-center gap-2"):
                                                        render_status_badge("completed", "Ready")
                                                        if doc.chunk_count > 0:
                                                            ui.label(f"{doc.chunk_count} vectors").classes(
                                                                "text-[10px] font-mono text-secondary-navy"
                                                            )
                                                    if doc.error_message and doc.error_message.startswith("Visual analysis"):
                                                        with ui.row().classes("items-center gap-1 text-[10px] text-secondary-navy"):
                                                            ui.icon("info", size="12px").classes("text-accent-gold")
                                                            ui.label(doc.error_message).classes("truncate max-w-[180px]").props(
                                                                f'title="{html.escape(doc.error_message, quote=True)}"'
                                                            )
                                                elif doc.indexing_status in ("QUEUED", "PROCESSING") or doc.status in (
                                                    "PROCESSING",
                                                    "PENDING",
                                                ):
                                                    stage_str = (doc.current_stage or "Processing").upper()
                                                    badge_label = "Queued" if stage_str in ("QUEUED_FOR_INDEXING", "QUEUED") else (doc.current_stage or "Processing").title()
                                                    render_status_badge("indexing", badge_label)

                                                    if stage_str == "EMBEDDING" and doc.total_chunks > 0 and doc.embedded_chunks > 0:
                                                        actual_frac = min(doc.embedded_chunks / doc.total_chunks, 0.99)
                                                        ui.linear_progress(
                                                            value=actual_frac
                                                        ).props('rounded color="primary" size="4px"').classes("w-full")
                                                        with ui.row().classes("w-full justify-between text-[10px] text-secondary-navy font-mono"):
                                                            ui.label(f"{doc.embedded_chunks}/{doc.total_chunks} chunks")
                                                            ui.label(f"{int(actual_frac * 100)}%")
                                                    else:
                                                        ui.linear_progress(value=None).props(
                                                            'indeterminate rounded color="primary" size="4px"'
                                                        ).classes("w-full")
                                                        with ui.row().classes("w-full justify-between text-[10px] text-secondary-navy"):
                                                            label_text = "Saving vectors to database..." if stage_str in ("WRITING_VECTORS", "STORING_VECTORS") else format_stage_label(doc.current_stage, status=doc.indexing_status)
                                                            ui.label(label_text).classes("truncate")
                                                elif doc.indexing_status == "FAILED" or doc.status == "FAILED":
                                                    with ui.column().classes("gap-0.5 w-full"):
                                                        render_status_badge("failed", "Failed")
                                                        err_txt = doc.indexing_error or doc.error_message or "Processing error"
                                                        ui.label(err_txt).classes(
                                                            "text-[10px] text-rose-700 truncate font-mono max-w-[180px]"
                                                        ).props(f'title="{html.escape(err_txt, quote=True)}"')
                                                else:
                                                    render_status_badge("inactive", "Unindexed")

                                            # Actions Column
                                            with ui.row().classes("w-40 justify-end items-center gap-1.5 shrink-0"):
                                                # Read Document
                                                ui.button(
                                                    icon="visibility",
                                                    on_click=lambda d=doc, kbid=kb_id_val, kbn=doc_kb_name: open_source_viewer(
                                                        document_id=str(d.id),
                                                        document_name=d.filename,
                                                        kb_id=kbid,
                                                        course_name=kbn,
                                                        return_to=f"/documents?kb_id={kbid}",
                                                    ),
                                                ).props('flat round dense aria-label="Read in Viewer"').classes(
                                                    "text-secondary-navy hover:text-primary-navy"
                                                ).tooltip("Read in Viewer")

                                                # Inspect Chunks
                                                ui.button(
                                                    icon="segment",
                                                    on_click=lambda d=doc, kbid=kb_id_val: open_chunk_dialog(
                                                        str(d.id), d.filename, kbid
                                                    ),
                                                ).props('flat round dense aria-label="Inspect Chunks"').classes(
                                                    "text-secondary-navy hover:text-primary-navy"
                                                ).tooltip("Inspect Chunks")

                                                # Delete Document
                                                if can_delete_documents:
                                                    ui.button(
                                                        icon="delete_outline",
                                                        on_click=lambda d=doc, kbid=kb_id_val: confirm_delete(
                                                            str(d.id), d.filename, kbid
                                                        ),
                                                    ).props('flat round dense aria-label="Delete Document"').classes(
                                                        "text-secondary-navy hover:text-rose-700"
                                                    ).tooltip("Delete Document")

                                        # Progressive Disclosure: Inline Expanded Details
                                        if is_expanded:
                                            with ui.row().classes(
                                                "w-full px-6 py-4 doc-details-pane items-start justify-between flex-wrap gap-4"
                                            ):
                                                with ui.column().classes("gap-1.5 min-w-[280px] flex-1"):
                                                    with ui.row().classes("items-center gap-2"):
                                                        ui.label("Processing Lifecycle & Diagnostics").classes(
                                                            "text-xs font-bold text-primary-navy font-editorial"
                                                        )
                                                        render_status_badge(
                                                            doc.indexing_status or doc.status or "PENDING",
                                                            doc.current_stage or "Status",
                                                        )
                                                        attempt_num = getattr(doc, "attempt_number", 1) or 1
                                                        if attempt_num > 1:
                                                            ui.badge(
                                                                f"Attempt #{attempt_num}",
                                                                color="canvas",
                                                            ).props("text-color=secondary-navy").classes(
                                                                "text-[10px] px-1.5 py-0 border border-subtle"
                                                            )

                                                    stage_desc = format_stage_label(
                                                        doc.current_stage,
                                                        doc.embedded_chunks,
                                                        doc.total_chunks,
                                                        doc.progress_percent,
                                                        doc.indexing_status,
                                                    )
                                                    ui.label(stage_desc).classes("text-xs text-secondary-navy")

                                                    # Diagnostic / failure note
                                                    if doc.indexing_status == "FAILED" or doc.status == "FAILED":
                                                        err_msg = doc.indexing_error or doc.error_message or "Vectorization halted unexpectedly."
                                                        with ui.row().classes("items-start gap-2 p-2.5 rounded bg-rose-50 border border-rose-200 mt-1 w-full"):
                                                            ui.icon("error_outline", size="15px").classes("text-rose-700 shrink-0 mt-0.5")
                                                            ui.label(err_msg).classes("text-xs text-rose-800 font-mono leading-relaxed break-all")
                                                    elif doc.indexing_status == "COMPLETED" or doc.status == "COMPLETED":
                                                        ui.label("Synchronized with pgvector storage. Fully indexed for semantic search grounding.").classes(
                                                            "text-xs text-emerald-800 font-sans"
                                                        )

                                                # Metrics & Contextual Retry Action
                                                with ui.column().classes("items-end gap-2 shrink-0"):
                                                    with ui.row().classes("items-center gap-3 text-xs font-mono text-secondary-navy"):
                                                        if doc.total_chunks > 0:
                                                            ui.label(f"Chunks: {doc.embedded_chunks or doc.chunk_count}/{doc.total_chunks}")
                                                        if doc.chunk_count > 0:
                                                            ui.label(f"Vectors: {doc.chunk_count}")

                                                    if (doc.indexing_status == "FAILED" or doc.status == "FAILED") and can_retry_jobs:
                                                        def handle_doc_retry(kbid=kb_id_val, docid=doc_id_str, docname=doc.filename):
                                                            try:
                                                                api_client.retry_indexing(kbid, docid)
                                                                ui.notify(f"Dispatched retry for '{docname}'.", type="positive")
                                                                trigger_table_refresh()
                                                                refresh_processing_queue()
                                                            except Exception as ex:
                                                                ui.notify(normalize_error(ex, context="indexing"), type="negative")

                                                        ui.button(
                                                            "Retry Indexing",
                                                            icon="refresh",
                                                            on_click=lambda k=kb_id_val, d=doc_id_str, n=doc.filename: handle_doc_retry(k, d, n),
                                                        ).props("outline dense no-caps").classes(
                                                            "text-xs font-bold text-rose-700 border-rose-700 hover:bg-rose-50 px-3 py-1 rounded"
                                                        )

                    def refresh_documents() -> None:
                        nonlocal cached_docs
                        doc_table_container.clear()
                        with doc_table_container:
                            with ui.row().classes("w-full py-12 justify-center items-center gap-2"):
                                ui.spinner(size="md", color="primary")
                                ui.label("Loading course documents...").classes("text-xs text-secondary-navy")

                        res = fetch_all_scoped_documents(all_courses, api_client.get_documents)
                        if res.is_total_failure:
                            if cached_docs:
                                # Preserve last known data and show error banner + retry
                                render_doc_table(
                                    error_banner="Failed to refresh course documents. Showing last known documents."
                                )
                                update_live_indicator(fetch_error="Course documents fetch failed")
                            else:
                                # Initial load total failure: show error state, not false empty state
                                doc_table_container.clear()
                                with doc_table_container:
                                    render_alert(
                                        "Failed to load documents across all accessible courses. Please retry or check network access.",
                                        level="negative",
                                        action_label="Retry",
                                        on_action=refresh_documents,
                                    )
                                update_live_indicator(fetch_error="Course documents fetch failed")
                            return

                        cached_docs = res.documents
                        partial_warning = None
                        if res.is_partial_failure:
                            partial_warning = f"Notice: Could not load documents for: {', '.join(res.failed_courses)}. Results may be incomplete."

                        render_doc_table(partial_warning=partial_warning)
                        render_active_pipeline()
                        update_switcher_classes()

                    def trigger_table_refresh() -> None:
                        nonlocal cached_docs
                        res = fetch_all_scoped_documents(all_courses, api_client.get_documents)
                        if res.is_total_failure:
                            logger.warning("Background document refresh failed across all accessible courses.")
                            render_doc_table(
                                error_banner="Background refresh failed across courses. Showing last known documents."
                            )
                            update_live_indicator(fetch_error="Background sync disrupted", is_polling=True)
                            return

                        cached_docs = res.documents
                        partial_warning = None
                        if res.is_partial_failure:
                            partial_warning = f"Notice: Background refresh incomplete for: {', '.join(res.failed_courses)}."

                        render_doc_table(partial_warning=partial_warning)
                        render_active_pipeline()
                        update_switcher_classes()

                    def on_doc_search_change(e: Any) -> None:
                        nonlocal doc_search_query
                        doc_search_query = e.value or ""
                        render_doc_table()

                    doc_search_box.on_value_change(on_doc_search_change)

            # =================================================================
            # VIEW 2: PROCESSING VIEW (Unified Vectorization Queue)
            # =================================================================
            with processing_view_container:
                # Top Header Bar
                with ui.row().classes("w-full justify-between items-center mb-4 flex-wrap gap-4"):
                    render_section_heading(
                        title="Vectorization Queue",
                        caption="Persistent job ledger tracking parsing, chunking, embedding, and pgvector storage across courses (recent 100 jobs).",
                    )
                    with ui.row().classes("items-center gap-3"):
                        ui.button("Refresh Queue", icon="refresh", on_click=lambda: refresh_processing_queue()).props(
                            "outline dense no-caps"
                        ).classes(
                            "text-xs font-bold text-primary-navy border border-subtle px-3 py-1.5 rounded hover:bg-surface"
                        )

                # Attention / Degradation Banner container
                proc_attention_container = ui.column().classes("w-full mb-4 gap-2")

                # Filter Toolbar Container
                proc_toolbar_container = ui.row().classes(
                    "w-full justify-between items-center flex-wrap gap-4 p-4 bg-surface-elevated border border-subtle rounded mb-4"
                )

                # Main Queue Content Container
                proc_queue_container = ui.column().classes("w-full gap-4 min-h-[220px]")

                def render_proc_toolbar() -> None:
                    proc_toolbar_container.clear()
                    with proc_toolbar_container:
                        proc_search_input = (
                            ui.input(
                                placeholder="Filter by document, course, or error...",
                                value=proc_search_query,
                            )
                            .props("outlined dense clearable")
                            .classes("w-full md:w-80 text-sm minimalist-input")
                        )

                        def on_proc_search(e: Any) -> None:
                            nonlocal proc_search_query
                            proc_search_query = (e.value or "").strip()
                            render_proc_queue_table()

                        proc_search_input.on("update:model-value", on_proc_search)

                        failed_count = sum(1 for j in cached_jobs if j.status == "FAILED")
                        active_count = sum(1 for j in cached_jobs if j.status in ("QUEUED", "PROCESSING", "PENDING"))
                        completed_count = sum(1 for j in cached_jobs if j.status == "COMPLETED")
                        total_count = len(cached_jobs)

                        with ui.row().classes("items-center gap-2 flex-wrap"):
                            all_tab_label = f"Recent Jobs ({total_count})" if total_count < 100 else f"Recent Jobs ({total_count} cap)"
                            tabs = [
                                ("ALL", all_tab_label, None),
                                ("ACTIVE", f"Active ({active_count})", "amber" if active_count > 0 else None),
                                ("FAILED", f"Needs Attention ({failed_count})", "rose" if failed_count > 0 else None),
                                ("COMPLETED", f"Completed ({completed_count})", None),
                            ]

                            for tab_key, tab_label, alert_tone in tabs:
                                is_selected = proc_active_tab == tab_key

                                if is_selected:
                                    btn_cls = "bg-primary-navy !text-white font-bold filter-pill-selected shadow-none"
                                elif alert_tone == "rose" and failed_count > 0:
                                    btn_cls = "bg-rose-50 text-rose-700 border border-rose-300 font-bold"
                                elif alert_tone == "amber" and active_count > 0:
                                    btn_cls = "bg-amber-50 text-amber-800 border border-amber-300 font-bold"
                                else:
                                    btn_cls = "bg-canvas text-secondary-navy border border-subtle hover:bg-surface font-medium"

                                def make_tab_handler(k=tab_key):
                                    return lambda: switch_proc_tab(k)

                                ui.button(tab_label, on_click=make_tab_handler()).props("no-caps dense").classes(
                                    f"text-xs px-3 py-1.5 rounded {btn_cls} transition-colors"
                                )

                def switch_proc_tab(tab_name: str) -> None:
                    nonlocal proc_active_tab
                    proc_active_tab = tab_name
                    render_proc_toolbar()
                    render_proc_queue_table()

                def trigger_proc_retry(job: IndexingJobDTO) -> None:
                    try:
                        api_client.retry_indexing(job.knowledge_base_id, job.document_id)
                        ui.notify(f"Dispatched retry for {job.document_name or 'document'}.", type="positive")
                        refresh_processing_queue()
                        if can_view_documents:
                            trigger_table_refresh()
                    except Exception as ex:
                        ui.notify(normalize_error(ex, context="indexing"), type="negative")

                def render_proc_queue_table() -> None:
                    proc_queue_container.clear()
                    with proc_queue_container:
                        filtered = list(cached_jobs)

                        # Filter by tab
                        if proc_active_tab == "ACTIVE":
                            filtered = [j for j in filtered if j.status in ("QUEUED", "PROCESSING", "PENDING")]
                        elif proc_active_tab == "FAILED":
                            filtered = [j for j in filtered if j.status == "FAILED"]
                        elif proc_active_tab == "COMPLETED":
                            filtered = [j for j in filtered if j.status == "COMPLETED"]

                        # Filter by search
                        if proc_search_query:
                            q = proc_search_query.lower()
                            filtered = [
                                j for j in filtered
                                if q in (j.document_name or "").lower()
                                or q in (j.course_name or "").lower()
                                or q in (j.stage or "").lower()
                                or q in (j.error_message or "").lower()
                            ]

                        if not filtered:
                            if not cached_jobs:
                                render_empty_state(
                                    "done_all",
                                    "Indexing Queue Empty",
                                    "No indexing jobs have been scheduled or processed yet.",
                                )
                            else:
                                render_empty_state(
                                    "filter_list_off",
                                    "No Jobs Match Active Filter",
                                    f"No jobs found matching '{proc_search_query}' in '{proc_active_tab.title()}' tab.",
                                    action_label="Reset Filters",
                                    on_action=lambda: switch_proc_tab("ALL"),
                                )
                            return

                        # High-density operational table
                        with ui.card().classes(
                            "w-full p-0 bg-surface-elevated border border-subtle rounded shadow-none overflow-hidden"
                        ):
                            with ui.element("div").classes("w-full overflow-x-auto"):
                                with ui.element("table").classes("w-full text-left text-sm border-collapse"):
                                    with ui.element("thead"):
                                        with ui.element("tr").classes(
                                            "border-b border-subtle bg-canvas text-secondary-navy font-bold text-xs uppercase tracking-wider"
                                        ):
                                            ui.element("th").classes("py-3.5 px-4").text = "Document Material"
                                            ui.element("th").classes("py-3.5 px-4").text = "Course"
                                            ui.element("th").classes("py-3.5 px-4").text = "Status"
                                            ui.element("th").classes("py-3.5 px-4").text = "Stage & Vectors"
                                            ui.element("th").classes("py-3.5 px-4").text = "Diagnostic Details"
                                            ui.element("th").classes("py-3.5 px-4 text-right").text = "Actions"

                                    with ui.element("tbody"):
                                        for job in filtered:
                                            status_val = (job.status or "PENDING").upper()
                                            is_running = status_val in ("PROCESSING", "QUEUED")
                                            is_failed = status_val == "FAILED"

                                            row_bg = "hover:bg-surface transition-colors border-b border-subtle"
                                            if is_failed:
                                                row_bg += " bg-rose-50/40"

                                            with ui.element("tr").classes(row_bg):
                                                # Document Material
                                                with ui.element("td").classes("py-3.5 px-4"):
                                                    with ui.column().classes("gap-0.5"):
                                                        doc_title = job.document_name or f"Document {job.document_id[:8]}"
                                                        ui.label(doc_title).classes(
                                                            "font-bold text-primary-navy text-sm font-sans"
                                                        )
                                                        with ui.row().classes("items-center gap-2 text-xs text-secondary-navy font-mono"):
                                                            ui.label(f"ID: {job.document_id[:8]}")
                                                            if job.attempt_number and job.attempt_number > 1:
                                                                ui.badge(
                                                                    f"Attempt #{job.attempt_number}",
                                                                    color="canvas"
                                                                ).props("text-color=secondary-navy").classes(
                                                                    "text-[10px] px-1 py-0 border border-subtle"
                                                                )

                                                # Course
                                                with ui.element("td").classes("py-3.5 px-4"):
                                                    ui.badge(job.course_name or "Course", color="canvas").props(
                                                        "text-color=secondary-navy"
                                                    ).classes("text-xs font-medium px-2 py-0.5 border border-subtle")

                                                # Status Badge
                                                with ui.element("td").classes("py-3.5 px-4"):
                                                    render_status_badge(status_val)

                                                # Stage & Vectors
                                                with ui.element("td").classes("py-3.5 px-4"):
                                                    with ui.column().classes("gap-1 min-w-[140px]"):
                                                        stage_text = format_stage_label(job.stage, job.processed_chunks, job.total_chunks, job.progress_percent, job.status)
                                                        ui.label(stage_text).classes(
                                                            "text-xs font-semibold text-secondary-navy"
                                                        )
                                                        if is_running:
                                                            pct = min(100.0, max(0.0, job.progress_percent))
                                                            if job.total_chunks > 0 and job.processed_chunks > 0:
                                                                with ui.row().classes("items-center justify-between text-xs w-full"):
                                                                    ui.label(f"{job.processed_chunks} / {job.total_chunks} chunks").classes(
                                                                        "font-mono text-amber-800 text-[11px]"
                                                                    )
                                                                    ui.label(f"{pct:.0f}%").classes(
                                                                        "font-mono text-amber-800 font-bold text-[11px]"
                                                                    )
                                                            if pct > 0.0:
                                                                ui.linear_progress(
                                                                    value=pct / 100.0, show_value=False
                                                                ).props("rounded color=amber-7 size=4px").classes("w-full")
                                                            else:
                                                                ui.linear_progress(
                                                                    value=None, show_value=False
                                                                ).props("indeterminate rounded color=amber-7 size=4px").classes("w-full")
                                                        elif status_val == "COMPLETED":
                                                            vec_count = job.indexed_chunks or job.total_chunks
                                                            ui.label(f"Ready · {vec_count} chunks indexed").classes(
                                                                "font-mono text-xs text-emerald-700 font-bold"
                                                            )
                                                        else:
                                                            ui.label(f"{job.total_chunks} chunks").classes(
                                                                "font-mono text-xs text-secondary-navy"
                                                            )

                                                # Diagnostic Details
                                                with ui.element("td").classes("py-3.5 px-4 max-w-[280px]"):
                                                    if is_failed:
                                                        ui.label(job.error_message or "Vectorization halted unexpectedly.").classes(
                                                            "text-xs text-rose-700 leading-snug font-mono truncate"
                                                        ).tooltip(job.error_message or "Error details")
                                                    elif status_val == "COMPLETED":
                                                        if job.error_message and job.error_message.startswith("Visual analysis"):
                                                            ui.label(job.error_message).classes(
                                                                "text-xs text-secondary-navy font-mono truncate"
                                                            ).tooltip(job.error_message)
                                                        else:
                                                            ui.label("Synchronized with pgvector storage").classes(
                                                                "text-xs text-secondary-navy"
                                                            )
                                                    elif is_running:
                                                        ui.label("Asynchronous worker vectorizing chunks...").classes(
                                                            "text-xs text-amber-800 italic"
                                                        )
                                                    else:
                                                        ui.label("Pending scheduler assignment").classes(
                                                            "text-xs text-secondary-navy italic"
                                                        )

                                                # Actions (inline Retry)
                                                with ui.element("td").classes("py-3.5 px-4 text-right"):
                                                    if is_failed and can_retry_jobs:
                                                        ui.button(
                                                            "Retry",
                                                            icon="refresh",
                                                            on_click=lambda _, j=job: trigger_proc_retry(j),
                                                        ).props("outline dense no-caps").classes(
                                                            "text-xs text-rose-700 border-rose-700 hover:bg-rose-50 px-2.5 py-1 font-bold rounded"
                                                        )
                                                    elif is_running:
                                                        ui.spinner(size="xs", color="amber-700")
                                                    else:
                                                        ui.label("—").classes("text-secondary-navy text-xs")

                def refresh_processing_queue() -> None:
                    nonlocal cached_jobs
                    proc_attention_container.clear()

                    try:
                        cached_jobs = api_client.get_indexing_jobs()
                    except Exception as err:
                        logger.warning(f"Failed to retrieve indexing queue: {err}")
                        with proc_attention_container:
                            render_alert(
                                f"Failed to retrieve indexing queue: {normalize_error(err, context='indexing')}",
                                level="negative",
                                action_label="Retry Request",
                                on_action=lambda: refresh_processing_queue(),
                            )
                        update_live_indicator(fetch_error=str(err))
                        render_proc_toolbar()
                        if not cached_jobs:
                            proc_queue_container.clear()
                        return

                    active_count = sum(1 for j in cached_jobs if j.status in ("QUEUED", "PROCESSING", "PENDING"))
                    failed_count = sum(1 for j in cached_jobs if j.status == "FAILED")

                    # Live indicator update using mutually exclusive truthful status logic
                    update_live_indicator()
                    if active_count > 0 and poll_timer and not poll_timer.active:
                        poll_timer.activate()

                    # Attention alert for failed jobs
                    if failed_count > 0:
                        with proc_attention_container:
                            with ui.row().classes(
                                "w-full items-center justify-between p-3.5 bg-rose-50 border border-rose-300 rounded"
                            ):
                                with ui.row().classes("items-center gap-2.5"):
                                    ui.icon("warning", size="1.25rem").classes("text-rose-700")
                                    with ui.column().classes("gap-0"):
                                        ui.label(
                                            f"Attention: {failed_count} vectorization job(s) failed."
                                        ).classes("text-sm font-bold text-rose-900")
                                        ui.label(
                                            "Inspection or retry is required to ensure complete semantic search grounding."
                                        ).classes("text-xs text-rose-700")
                                ui.button(
                                    "View Failed Jobs",
                                    icon="filter_list",
                                    on_click=lambda: switch_proc_tab("FAILED"),
                                ).props("outline dense no-caps").classes(
                                    "text-xs font-bold text-rose-700 border border-rose-300 hover:bg-rose-100 px-3 py-1.5 rounded"
                                )

                    render_proc_toolbar()
                    render_proc_queue_table()
                    update_switcher_classes()

            # -----------------------------------------------------------------
            # Unified Polling & Initialization
            # -----------------------------------------------------------------
            def refresh_all_data() -> None:
                if can_view_documents:
                    refresh_documents()
                refresh_processing_queue()

            def poll_check() -> None:
                has_active_docs = any(
                    d.indexing_status in ("QUEUED", "PROCESSING")
                    or d.status in ("PROCESSING", "PENDING")
                    for d in cached_docs
                )
                has_active_jobs = any(
                    j.status in ("QUEUED", "PROCESSING", "PENDING")
                    for j in cached_jobs
                )

                # Check actively uploading document
                if uploading_doc_id and can_view_documents:
                    try:
                        job_stat = api_client.get_document_index_status(
                            uploading_kb_id or "", uploading_doc_id
                        )
                        sel_course = course_map.get(uploading_kb_id or "", "Course")
                        update_workspace_progress_ui(
                            filename=uploaded_filename or job_stat.document_name or "Document",
                            course_name=sel_course,
                            file_size=uploaded_filesize,
                            stage=job_stat.stage,
                            status=job_stat.status,
                            processed=job_stat.embedded_chunks or job_stat.processed_chunks,
                            total=job_stat.total_chunks,
                            pct=job_stat.progress_percent,
                            error_msg=job_stat.error_message,
                        )
                    except Exception as upload_poll_err:
                        logger.warning(f"Error polling upload progress: {upload_poll_err}")

                if not has_active_docs and not has_active_jobs and not uploading_doc_id:
                    if poll_timer and poll_timer.active:
                        poll_timer.deactivate()
                    return

                # Silently refresh data
                if can_view_documents:
                    trigger_table_refresh()
                try:
                    cached_j = api_client.get_indexing_jobs()
                    cached_jobs.clear()
                    cached_jobs.extend(cached_j)
                    update_live_indicator()
                    if current_view == "processing":
                        render_proc_toolbar()
                        render_proc_queue_table()
                    update_switcher_classes()
                except Exception as poll_err:
                    logger.warning(f"Error polling indexing queue: {poll_err}")
                    update_live_indicator(fetch_error=str(poll_err), is_polling=True)

            def background_poll_tick() -> None:
                poll_check()

            poll_timer = ui.timer(3.0, poll_check, active=False)

            # Initial Load
            update_switcher_classes()
            if can_view_documents:
                refresh_documents()
            refresh_processing_queue()
