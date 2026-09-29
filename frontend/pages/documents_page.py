"""
Documents Management Page.

Provides complete university course document lifecycle management:
- Upload documents (PDF, DOCX, TXT, MD, CSV, max 20MB) with clear validation & lifecycle.
- Full lifecycle visualization: Uploaded -> Parsed -> Chunked -> Embedded -> Indexed -> Verified -> Ready.
- Document-level publication controls (Activate / Deactivate) with confirmation guards.
- Truthful, persistent indexing progress tracking (chunks, vectors, stages, and error reasons).
- Interactive document detail dialog with pipeline state inspection.
- Filter, search, and dynamic polling without page reloading.
"""

from nicegui import events, ui

from backend.app.core.config import settings
from backend.app.core.permissions import Permission
from frontend.client.api_client import api_client
from frontend.client.models import DocumentDTO, IndexingJobDTO
from frontend.components.layout import has_admin_permission, page_layout
from frontend.components.status_badge import render_indexing_status_badge, render_status_badge
from frontend.components.ui_kit import render_alert, render_empty_state
from frontend.state.app_state import state

# Supported formats per specification
SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".txt", ".md", ".csv"]


def format_bytes(num_bytes: int) -> str:
    """Format byte size into human-readable representation."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.2f} MB"


def register_documents_page() -> None:
    """Register /documents route with NiceGUI."""

    @ui.page("/documents")
    def documents_page(kb_id: str | None = None) -> None:
        user = state.current_user
        is_admin = bool(user and user.role == "ADMIN")
        can_view_documents = has_admin_permission(user, Permission.DOCUMENT_VIEW)
        can_upload_documents = has_admin_permission(user, Permission.DOCUMENT_UPLOAD)
        can_publish_documents = has_admin_permission(user, Permission.DOCUMENT_PUBLISH)
        can_index_documents = has_admin_permission(user, Permission.DOCUMENT_INDEX)
        can_retry_indexing = has_admin_permission(user, Permission.DOCUMENT_INDEX_RETRY)
        can_delete_documents = has_admin_permission(user, Permission.DOCUMENT_DELETE)

        if not is_admin or not can_view_documents:
            with page_layout(
                title="Course Documents",
                subtitle="Permission-aware course material access.",
                active_route="/documents",
                require_auth=True,
            ):
                render_empty_state(
                    icon="lock",
                    title="Document Management Unavailable",
                    description="You do not have permission to view course documents.",
                )
            return

        try:
            all_courses = api_client.get_document_scope_courses()
        except ValueError as err:
            with page_layout(
                title="Course Documents",
                subtitle="Permission-aware course material access.",
                active_route="/documents",
                require_auth=True,
            ):
                render_alert(f"Unable to load courses. {err}", "negative")
            return

        # Resolve selected course strictly from kb_id parameter
        selected_course = None
        if kb_id:
            for c in all_courses:
                if c.id == kb_id:
                    selected_course = c
                    break

        page_title = (
            f"Documents — {selected_course.name}" if selected_course else "Course Documents"
        )
        page_subtitle = (
            "Upload, vectorize, and manage learning material versions with complete lifecycle visibility."
            if selected_course
            else "Select a university course to view and manage its learning materials."
        )

        with page_layout(
            title=page_title,
            subtitle=page_subtitle,
            active_route="/documents",
            require_auth=True,
        ):
            # If no course is selected, display course selection list
            if not selected_course:
                with ui.card().classes(
                    "w-full max-w-2xl mx-auto p-6 bg-white border border-slate-200 rounded-lg shadow-xs text-center items-center"
                ):
                    ui.icon("menu_book", size="3rem").classes("text-blue-600 mb-2")
                    ui.label("Select a Course").classes("text-lg font-bold text-slate-900 mb-1")
                    ui.label(
                        "Please choose an authorized university course below to view, upload, and index materials."
                    ).classes("text-xs text-slate-500 mb-5 max-w-md")

                    if not all_courses:
                        render_empty_state(
                            icon="folder_off",
                            title="No Courses Available",
                            description="No courses are currently available. Create a course first to upload materials.",
                            action_label="Manage Courses" if is_admin else None,
                            on_action=lambda: ui.navigate.to("/knowledge-bases"),
                        )
                    else:
                        with ui.column().classes("w-full gap-2 text-left"):
                            for c in all_courses:
                                with (
                                    ui.row()
                                    .classes(
                                        "w-full items-center justify-between p-3.5 bg-slate-50 hover:bg-blue-50/50 border border-slate-200 rounded-lg cursor-pointer transition-colors"
                                    )
                                    .on(
                                        "click",
                                        lambda course_id=c.id: ui.navigate.to(
                                            f"/documents?kb_id={course_id}"
                                        ),
                                    )
                                ):
                                    with ui.row().classes("items-center gap-3"):
                                        with ui.element("div").classes(
                                            "w-9 h-9 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-sm"
                                        ):
                                            ui.icon("school", size="xs")
                                        with ui.column().classes("gap-0"):
                                            ui.label(c.name).classes(
                                                "text-sm font-bold text-slate-900"
                                            )
                                            if c.description:
                                                ui.label(c.description).classes(
                                                    "text-xs text-slate-500 line-clamp-1"
                                                )
                                    ui.button(
                                        "Open Course",
                                        icon="arrow_forward",
                                        on_click=lambda course_id=c.id: ui.navigate.to(
                                            f"/documents?kb_id={course_id}"
                                        ),
                                    ).props("flat dense no-caps color=primary").classes("text-xs")
                return

            # ------------------------------------------------------------------
            # COURSE CONTEXT BAR & SWITCHER
            # ------------------------------------------------------------------
            with ui.card().classes(
                "w-full p-4 bg-white border border-slate-200 rounded-lg shadow-xs"
            ):
                with ui.row().classes("w-full justify-between items-center gap-3 flex-wrap"):
                    with ui.row().classes("items-center gap-2.5"):
                        with ui.element("div").classes(
                            "w-8 h-8 rounded-lg bg-blue-600/20 text-blue-700 flex items-center justify-center"
                        ):
                            ui.icon("school", size="xs")
                        with ui.column().classes("gap-0"):
                            with ui.row().classes("items-center gap-2"):
                                ui.label(selected_course.name).classes(
                                    "text-base font-bold text-slate-900"
                                )
                                ui.badge("Active Context", color="blue-700").classes("text-[10px] font-bold")
                            if selected_course.description:
                                ui.label(selected_course.description).classes(
                                    "text-xs text-slate-500 line-clamp-1"
                                )

                    with ui.row().classes("items-center gap-2"):
                        ui.button(
                            "Switch Course",
                            icon="swap_horiz",
                            on_click=lambda: ui.navigate.to("/documents"),
                        ).props("outline dense no-caps color=primary").classes("text-xs")
                        ui.button(
                            "Open Chat",
                            icon="chat",
                            on_click=lambda: ui.navigate.to(f"/chat?kb_id={selected_course.id}"),
                        ).props("flat dense no-caps").classes("text-xs text-blue-600")

            # ------------------------------------------------------------------
            # UPLOAD COURSE MATERIAL PANEL
            # ------------------------------------------------------------------
            if can_upload_documents:
                max_upload_bytes = settings.MAX_UPLOAD_SIZE_BYTES
                max_mb = max_upload_bytes // (1024 * 1024)

                with ui.card().classes(
                    "w-full p-5 bg-white border border-slate-200 rounded-lg shadow-xs gap-3"
                ):
                    with ui.row().classes("w-full justify-between items-center pb-2 border-b border-slate-100"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("upload_file", size="sm").classes("text-blue-600")
                            ui.label("Upload Course Material").classes(
                                "text-sm font-bold text-slate-900"
                            )
                        with ui.row().classes("items-center gap-2 text-xs text-slate-500 font-mono"):
                            ui.label("Supported: PDF, DOCX, TXT, MD, CSV")
                            ui.label("•")
                            ui.label(f"Max: {max_mb} MB")

                    ui.label(
                        f"Upload syllabi, textbooks, research papers, or lecture notes directly into '{selected_course.name}'. "
                        "Ingestion runs parsing, normalization, and chunking in the background. After chunking, vector indexing can be started."
                    ).classes("text-xs text-slate-500 leading-relaxed")

                    upload_alert = ui.column().classes("w-full")

                    async def handle_upload(e: events.UploadEventArguments) -> None:
                        upload_alert.clear()
                        file_obj = e.file
                        fname = file_obj.name.strip()
                        lower_fname = fname.lower()
                        if not any(lower_fname.endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                            with upload_alert:
                                render_alert(
                                    f"Unsupported file format for '{fname}'. Permitted: PDF, DOCX, TXT, MD, CSV.",
                                    level="negative",
                                )
                            return

                        try:
                            content = await file_obj.read()
                            size = (
                                file_obj.size()
                                if hasattr(file_obj, "size") and callable(file_obj.size)
                                else len(content)
                            )
                        except Exception as read_err:
                            with upload_alert:
                                render_alert(
                                    f"Failed to read file: {read_err}",
                                    level="negative",
                                )
                            return

                        try:
                            doc = api_client.upload_document(
                                kb_id=selected_course.id,
                                filename=fname,
                                content=content,
                                content_size_bytes=size,
                            )
                            with upload_alert:
                                render_alert(
                                    f"'{doc.filename}' uploaded successfully ({format_bytes(size)}). Processing queued in background.",
                                    level="info",
                                )
                            ui.notify(
                                f"Uploaded '{doc.filename}'. Parsing and chunking initiated.",
                                type="positive",
                            )
                            refresh_doc_list()
                            poll_timer.activate()
                        except ValueError as err:
                            with upload_alert:
                                render_alert(str(err), level="negative")

                    ui.upload(
                        label=f"Drop course files here or click to browse (up to {max_mb} MB)",
                        on_upload=handle_upload,
                        auto_upload=True,
                        max_file_size=max_upload_bytes,
                    ).props('accept=".pdf,.docx,.txt,.md,.csv"').classes("w-full")

            # ------------------------------------------------------------------
            # DOCUMENT DETAIL DIALOG
            # ------------------------------------------------------------------
            detail_dialog = ui.dialog()
            detail_dialog_card = ui.card().classes(
                "w-full max-w-2xl p-6 bg-white border border-slate-200 rounded-lg shadow-lg gap-4"
            )

            def open_document_detail(doc: DocumentDTO) -> None:
                detail_dialog_card.clear()
                with detail_dialog:
                    with detail_dialog_card:
                        # Fetch real indexing job status
                        job: IndexingJobDTO | None = None
                        try:
                            job = api_client.get_document_index_status(selected_course.id, doc.id)
                        except Exception:
                            pass

                        # Dialog Header
                        with ui.row().classes("w-full justify-between items-start pb-3 border-b border-slate-100"):
                            with ui.column().classes("gap-0.5"):
                                with ui.row().classes("items-center gap-2"):
                                    ui.icon("description", size="sm").classes("text-blue-600")
                                    ui.label(doc.filename).classes("text-lg font-bold text-slate-900")
                                ui.label(f"Course: {selected_course.name} • Format: {doc.file_type.upper()} • Size: {format_bytes(doc.file_size_bytes)}").classes("text-xs text-slate-500 font-mono")
                            ui.button(icon="close", on_click=detail_dialog.close).props("flat round dense text-color=grey-7")

                        # Lifecycle Pipeline Visualization
                        ui.label("PROCESSING & RETRIEVAL PIPELINE").classes("text-[10px] font-bold text-slate-400 tracking-wider")
                        with ui.row().classes("w-full items-center justify-between p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs"):
                            # Steps: Uploaded -> Parsed -> Chunked -> Embedded -> Vectors -> Ready
                            steps = [
                                ("Uploaded", True),
                                ("Parsed", doc.status in ("COMPLETED", "PROCESSING")),
                                ("Chunked", doc.chunk_count > 0 or doc.status == "COMPLETED"),
                                ("Embedded", doc.indexing_status in ("PROCESSING", "COMPLETED")),
                                ("Indexed", doc.indexing_status == "COMPLETED"),
                                ("Ready", doc.indexing_status == "COMPLETED" and doc.is_active),
                            ]
                            for label, is_done in steps:
                                with ui.column().classes("items-center gap-1"):
                                    icon_name = "check_circle" if is_done else "radio_button_unchecked"
                                    icon_color = "text-emerald-600" if is_done else "text-slate-300"
                                    ui.icon(icon_name, size="xs").classes(icon_color)
                                    ui.label(label).classes(f"text-[10px] font-semibold {'text-slate-800' if is_done else 'text-slate-400'}")

                        # Metrics Grid
                        with ui.row().classes("w-full grid grid-cols-2 sm:grid-cols-4 gap-3"):
                            with ui.card().classes("p-3 bg-slate-50 border border-slate-200 rounded"):
                                ui.label("TOTAL CHUNKS").classes("text-[10px] font-bold text-slate-400")
                                ui.label(str(doc.chunk_count)).classes("text-xl font-bold font-mono text-slate-800")
                            with ui.card().classes("p-3 bg-slate-50 border border-slate-200 rounded"):
                                ui.label("VECTORS CREATED").classes("text-[10px] font-bold text-slate-400")
                                v_count = doc.chunk_count if doc.indexing_status == "COMPLETED" else (job.indexed_chunks if job else 0)
                                ui.label(f"{v_count} / {doc.chunk_count}").classes("text-xl font-bold font-mono text-blue-700")
                            with ui.card().classes("p-3 bg-slate-50 border border-slate-200 rounded"):
                                ui.label("INDEXING STATUS").classes("text-[10px] font-bold text-slate-400")
                                render_indexing_status_badge(doc.indexing_status)
                            with ui.card().classes("p-3 bg-slate-50 border border-slate-200 rounded"):
                                ui.label("RETRIEVAL ELIGIBLE").classes("text-[10px] font-bold text-slate-400")
                                ret_ready = doc.indexing_status == "COMPLETED" and doc.is_active
                                ui.badge("READY" if ret_ready else "NOT READY", color="emerald-700" if ret_ready else "amber-700").classes("text-[10px] font-bold")

                        # Progress Details if active or failed
                        if job and job.status in ("PROCESSING", "QUEUED"):
                            with ui.card().classes("w-full p-3 bg-blue-50 border border-blue-200 rounded"):
                                with ui.row().classes("w-full justify-between items-center text-xs mb-1"):
                                    ui.label(f"Stage: {job.stage}").classes("font-semibold text-blue-800")
                                    ui.label(f"{job.progress_percent:.0f}%").classes("font-mono font-bold text-blue-700")
                                ui.linear_progress(job.progress_percent / 100.0, show_value=False).props("rounded color=primary")

                        if doc.indexing_error or (job and job.error_message):
                            err_msg = doc.indexing_error or (job.error_message if job else "Indexing failed")
                            with ui.card().classes("w-full p-3 bg-rose-50 border border-rose-200 rounded"):
                                ui.label(f"Error Diagnostic: {err_msg}").classes("text-xs font-semibold text-rose-800")

                        # Timeline details
                        with ui.column().classes("w-full gap-1 text-[11px] text-slate-500 font-mono"):
                            ui.label(f"Uploaded: {doc.created_at}")
                            if doc.indexed_at:
                                ui.label(f"Indexed: {doc.indexed_at}")

                        # Dialog Actions
                        with ui.row().classes("w-full justify-end items-center gap-2 pt-3 border-t border-slate-100"):
                            ui.button("Close", on_click=detail_dialog.close).props("flat dense no-caps")

                detail_dialog.open()

            # ------------------------------------------------------------------
            # CONFIRMATION DIALOGS (Section 21)
            # ------------------------------------------------------------------
            confirm_dialog = ui.dialog()
            confirm_card = ui.card().classes(
                "w-full max-w-md p-6 bg-white border border-slate-200 rounded-lg shadow-lg gap-4"
            )

            def open_confirm_dialog(
                title: str,
                message: str,
                action_label: str,
                action_color: str,
                on_confirm,
            ) -> None:
                confirm_card.clear()
                with confirm_dialog:
                    with confirm_card:
                        ui.label(title).classes("text-base font-bold text-slate-900")
                        ui.label(message).classes("text-xs text-slate-600 leading-relaxed")
                        with ui.row().classes("w-full justify-end gap-2 pt-2 border-t border-slate-100"):
                            ui.button("Cancel", on_click=confirm_dialog.close).props("flat dense no-caps")
                            def _do_action() -> None:
                                confirm_dialog.close()
                                on_confirm()
                            ui.button(
                                action_label,
                                on_click=_do_action,
                            ).props(f"color={action_color} dense no-caps").classes("px-3 py-1 font-semibold")
                confirm_dialog.open()

            # ------------------------------------------------------------------
            # DOCUMENT TABLE & CONTROLS
            # ------------------------------------------------------------------
            doc_container = ui.column().classes("w-full gap-4")

            search_state = {"query": "", "filter": "ALL"}

            def refresh_doc_list() -> None:
                doc_container.clear()
                with doc_container:
                    render_documents_view()

            def poll_check() -> None:
                docs = api_client.get_documents(selected_course.id)
                has_active = any(
                    d.status in ("PENDING", "PROCESSING")
                    or d.indexing_status in ("QUEUED", "PROCESSING")
                    for d in docs
                )
                refresh_doc_list()
                if not has_active:
                    poll_timer.deactivate()

            poll_timer = ui.timer(2.0, poll_check, active=False)

            def render_documents_view() -> None:
                try:
                    docs = api_client.get_documents(selected_course.id)
                except ValueError as err:
                    render_alert(f"Failed to load documents: {err}", level="negative")
                    return

                active_processing = [
                    d
                    for d in docs
                    if d.status in ("PENDING", "PROCESSING")
                    or d.indexing_status in ("QUEUED", "PROCESSING")
                ]
                if active_processing and not poll_timer.active:
                    poll_timer.activate()
                elif not active_processing and poll_timer.active:
                    poll_timer.deactivate()

                # Filter documents by search and category
                q = search_state["query"].lower().strip()
                cat = search_state["filter"]
                filtered_docs = docs
                if q:
                    filtered_docs = [d for d in filtered_docs if q in d.filename.lower()]
                if cat == "ACTIVE":
                    filtered_docs = [d for d in filtered_docs if d.is_active and d.indexing_status == "COMPLETED"]
                elif cat == "INDEXING":
                    filtered_docs = [d for d in filtered_docs if d.indexing_status in ("QUEUED", "PROCESSING")]
                elif cat == "FAILED":
                    filtered_docs = [d for d in filtered_docs if d.indexing_status == "FAILED" or d.status == "FAILED"]
                elif cat == "INACTIVE":
                    filtered_docs = [d for d in filtered_docs if not d.is_active or d.indexing_status != "COMPLETED"]

                with ui.card().classes("w-full p-5 bg-white border border-slate-200 rounded-lg shadow-xs gap-4"):
                    # Top Filter & Search Controls
                    with ui.row().classes("w-full justify-between items-center gap-3 flex-wrap pb-3 border-b border-slate-100"):
                        with ui.row().classes("items-center gap-2 flex-1 max-w-md"):
                            s_input = ui.input(
                                placeholder="Search documents by filename...",
                                value=search_state["query"],
                            ).props("outlined dense clearable").classes("w-full text-xs")
                            s_input.on("input", lambda e: on_search_input(e.value))

                        with ui.row().classes("items-center gap-2"):
                            ui.label("Filter:").classes("text-xs font-semibold text-slate-500")
                            filters = [
                                ("ALL", f"All ({len(docs)})"),
                                ("ACTIVE", "Active"),
                                ("INDEXING", "Indexing"),
                                ("FAILED", "Needs Attention"),
                            ]
                            for f_key, f_label in filters:
                                is_sel = search_state["filter"] == f_key
                                btn_cls = "text-xs px-2.5 py-1 rounded "
                                if is_sel:
                                    btn_cls += "bg-blue-600 text-white font-semibold"
                                else:
                                    btn_cls += "text-slate-600 hover:bg-slate-100"
                                ui.button(
                                    f_label,
                                    on_click=lambda k=f_key: on_filter_change(k),
                                ).props("flat dense no-caps").classes(btn_cls)

                            ui.button(
                                icon="refresh",
                                on_click=refresh_doc_list,
                            ).props("flat round dense").classes("text-slate-500 hover:text-slate-800").tooltip("Refresh List")

                    if not filtered_docs:
                        if search_state["query"] or search_state["filter"] != "ALL":
                            render_empty_state(
                                icon="search_off",
                                title="No Matching Documents",
                                description="No course materials match the current search query or filter.",
                                action_label="Clear Filters",
                                on_action=clear_filters,
                            )
                        else:
                            render_empty_state(
                                icon="description",
                                title="No Documents Uploaded",
                                description=f"No learning materials have been uploaded to '{selected_course.name}' yet.",
                            )
                        return

                    # Redesigned Document Table (Section 5)
                    with ui.element("div").classes("w-full overflow-x-auto"):
                        with ui.element("table").classes("w-full text-left text-xs border-collapse"):
                            with ui.element("thead").classes("bg-slate-50 text-slate-600 uppercase font-semibold border-b border-slate-200"):
                                with ui.element("tr"):
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Document")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Format")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Size")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Processing")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Indexing")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Chunks")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Vectors")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Retrieval")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Updated")
                                    with ui.element("th").classes("py-2.5 px-3 text-right"):
                                        ui.label("Actions")

                            with ui.element("tbody").classes("divide-y divide-slate-100 text-slate-800"):
                                for doc in filtered_docs:
                                    with ui.element("tr").classes("hover:bg-slate-50/70 transition-colors"):
                                        # 1. Document Title
                                        with ui.element("td").classes("py-2.5 px-3 font-medium"):
                                            with ui.row().classes("items-center gap-2"):
                                                ui.icon("description", size="xs").classes("text-slate-400")
                                                with ui.column().classes("gap-0"):
                                                    ui.label(doc.filename).classes("truncate max-w-[200px] font-semibold text-slate-900")
                                                    if doc.error_message and doc.status == "FAILED":
                                                        ui.label(f"Error: {doc.error_message}").classes("text-[10px] text-rose-600 truncate max-w-[180px]")

                                        # 2. Format
                                        with ui.element("td").classes("py-2.5 px-3 font-mono"):
                                            ui.badge(doc.file_type.upper(), color="slate-600").classes("text-[10px]")

                                        # 3. Size
                                        with ui.element("td").classes("py-2.5 px-3 font-mono text-slate-600"):
                                            ui.label(format_bytes(doc.file_size_bytes))

                                        # 4. Processing
                                        with ui.element("td").classes("py-2.5 px-3"):
                                            render_status_badge(doc.status)

                                        # 5. Indexing (Truthful Chunk Progress)
                                        with ui.element("td").classes("py-2.5 px-3"):
                                            if doc.indexing_status in ("QUEUED", "PROCESSING"):
                                                with ui.column().classes("gap-0.5 min-w-[120px]"):
                                                    render_indexing_status_badge(doc.indexing_status)
                                                    try:
                                                        j = api_client.get_document_index_status(selected_course.id, doc.id)
                                                        ui.label(f"{j.processed_chunks} / {j.total_chunks} chunks ({j.progress_percent:.0f}%)").classes("text-[10px] font-mono text-blue-700 font-semibold")
                                                        ui.linear_progress(j.progress_percent / 100.0, show_value=False, size="4px").props("rounded color=primary")
                                                    except Exception:
                                                        pass
                                            elif doc.indexing_status == "COMPLETED":
                                                render_indexing_status_badge("COMPLETED")
                                            elif doc.indexing_status == "FAILED":
                                                render_indexing_status_badge("FAILED")
                                                err_txt = doc.indexing_error or "Indexing failed"
                                                ui.label(err_txt).classes("text-[10px] text-rose-600 truncate max-w-[140px]").tooltip(err_txt)
                                            else:
                                                render_indexing_status_badge(doc.indexing_status)

                                        # 6. Chunks
                                        with ui.element("td").classes("py-2.5 px-3 font-mono text-slate-600"):
                                            ui.label(str(doc.chunk_count))

                                        # 7. Vectors
                                        with ui.element("td").classes("py-2.5 px-3 font-mono"):
                                            if doc.indexing_status == "COMPLETED":
                                                ui.label(f"{doc.chunk_count} / {doc.chunk_count}").classes("text-emerald-700 font-semibold")
                                            elif doc.indexing_status in ("QUEUED", "PROCESSING"):
                                                try:
                                                    j = api_client.get_document_index_status(selected_course.id, doc.id)
                                                    ui.label(f"{j.indexed_chunks} / {j.total_chunks}").classes("text-blue-700 font-semibold")
                                                except Exception:
                                                    ui.label("0 / —").classes("text-slate-400")
                                            else:
                                                ui.label("0 / —").classes("text-slate-400")

                                        # 8. Retrieval Status
                                        with ui.element("td").classes("py-2.5 px-3"):
                                            if doc.indexing_status != "COMPLETED":
                                                ui.badge("NOT READY", color="amber-700").classes("text-[9px] font-bold").tooltip("Vector indexing has not completed.")
                                            elif doc.is_active:
                                                ui.badge("READY", color="emerald-700").classes("text-[9px] font-bold").tooltip("Active: Included in student queries.")
                                            else:
                                                ui.badge("INACTIVE", color="slate-400").classes("text-[9px] font-bold").tooltip("Inactive: Excluded from retrieval.")

                                        # 9. Updated
                                        with ui.element("td").classes("py-2.5 px-3 font-mono text-slate-500"):
                                            ui.label(doc.created_at[:10])

                                        # 10. Actions
                                        with ui.element("td").classes("py-2.5 px-3 text-right"):
                                            with ui.row().classes("items-center justify-end gap-1"):
                                                # View Details
                                                ui.button(
                                                    icon="visibility",
                                                    on_click=lambda d=doc: open_document_detail(d),
                                                ).props("flat round dense").classes("text-slate-500 hover:text-blue-600").tooltip("View Document Details")

                                                # Index trigger
                                                if (
                                                    can_index_documents
                                                    and doc.status == "COMPLETED"
                                                    and doc.indexing_status not in ("COMPLETED", "PROCESSING", "QUEUED")
                                                ):
                                                    def do_index(d_id=doc.id, name=doc.filename):
                                                        try:
                                                            api_client.index_document(selected_course.id, d_id)
                                                            ui.notify(f"Indexing started for '{name}'.", type="positive")
                                                            refresh_doc_list()
                                                            poll_timer.activate()
                                                        except ValueError as err:
                                                            ui.notify(str(err), type="negative")

                                                    ui.button(
                                                        "Index",
                                                        icon="storage",
                                                        on_click=do_index,
                                                    ).props("outline dense no-caps color=primary").classes("text-[11px] px-2 py-0.5")

                                                # Retry Indexing
                                                elif can_retry_indexing and doc.indexing_status == "FAILED":
                                                    def do_retry(d_id=doc.id, name=doc.filename):
                                                        try:
                                                            api_client.retry_indexing(selected_course.id, d_id)
                                                            ui.notify(f"Indexing retry started for '{name}'.", type="positive")
                                                            refresh_doc_list()
                                                            poll_timer.activate()
                                                        except ValueError as err:
                                                            ui.notify(str(err), type="negative")

                                                    ui.button(
                                                        "Retry",
                                                        icon="refresh",
                                                        on_click=do_retry,
                                                    ).props("outline dense no-caps color=amber-9").classes("text-[11px] px-2 py-0.5")

                                                # Deactivate action with confirmation (Section 21)
                                                if can_publish_documents and doc.is_active:
                                                    def request_deactivate(d_id=doc.id, name=doc.filename):
                                                        def execute_deactivate():
                                                            try:
                                                                api_client.deactivate_document(selected_course.id, d_id)
                                                                ui.notify(f"Deactivated '{name}'. Excluded from retrieval.", type="info")
                                                                refresh_doc_list()
                                                            except ValueError as err:
                                                                ui.notify(str(err), type="negative")

                                                        open_confirm_dialog(
                                                            title=f'Deactivate "{name}"?',
                                                            message="This document will no longer be available for student retrieval until reactivated.",
                                                            action_label="Deactivate",
                                                            action_color="warning",
                                                            on_confirm=execute_deactivate,
                                                        )

                                                    ui.button(
                                                        icon="pause_circle",
                                                        on_click=request_deactivate,
                                                    ).props("flat round dense").classes("text-slate-400 hover:text-amber-600").tooltip("Deactivate Document")

                                                # Activate action
                                                elif can_publish_documents and doc.indexing_status == "COMPLETED" and not doc.is_active:
                                                    def do_activate(d_id=doc.id, name=doc.filename):
                                                        try:
                                                            api_client.activate_document(selected_course.id, d_id)
                                                            ui.notify(f"Activated '{name}'. Now available for retrieval.", type="positive")
                                                            refresh_doc_list()
                                                        except ValueError as err:
                                                            ui.notify(str(err), type="negative")

                                                    ui.button(
                                                        icon="check_circle",
                                                        on_click=do_activate,
                                                    ).props("flat round dense").classes("text-slate-400 hover:text-emerald-600").tooltip("Activate for Retrieval")

                                                # Delete action with confirmation (Section 21)
                                                if can_delete_documents:
                                                    def request_delete(d_id=doc.id, name=doc.filename):
                                                        def execute_delete():
                                                            try:
                                                                api_client.delete_document(selected_course.id, d_id)
                                                                ui.notify(f"Deleted '{name}'.", type="info")
                                                                refresh_doc_list()
                                                            except ValueError as err:
                                                                ui.notify(str(err), type="negative")

                                                        open_confirm_dialog(
                                                            title=f'Delete "{name}"?',
                                                            message="This will permanently remove the document and its indexed vectors. This action cannot be undone.",
                                                            action_label="Delete",
                                                            action_color="negative",
                                                            on_confirm=execute_delete,
                                                        )

                                                    ui.button(
                                                        icon="delete_outline",
                                                        on_click=request_delete,
                                                    ).props("flat round dense").classes("text-slate-400 hover:text-rose-600").tooltip("Delete Document")

            def on_search_input(val: str | None) -> None:
                search_state["query"] = val or ""
                refresh_doc_list()

            def on_filter_change(cat: str) -> None:
                search_state["filter"] = cat
                refresh_doc_list()

            def clear_filters() -> None:
                search_state["query"] = ""
                search_state["filter"] = "ALL"
                refresh_doc_list()

            refresh_doc_list()
