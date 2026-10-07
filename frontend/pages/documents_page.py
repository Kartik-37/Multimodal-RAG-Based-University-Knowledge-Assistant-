"""
Documents Management Page.

Provides complete university course document lifecycle management:
- Upload documents (PDF, DOCX, TXT, MD, CSV, max 20MB) with clear validation.
- Clean document table with human-readable status, chunk counts, and file formats.
- Focused evidence reading via canonical Source Viewer (same-origin, no query tokens).
- Chunk inspection dialog and safe document deletion with confirmation guards.
"""

from nicegui import events, ui

from backend.app.core.config import settings
from backend.app.core.permissions import Permission
from frontend.client.api_client import api_client
from frontend.client.error_handler import normalize_error
from frontend.components.layout import has_admin_permission, page_layout
from frontend.components.source_viewer import open_source_viewer
from frontend.components.ui_kit import render_alert, render_empty_state
from frontend.state.app_state import state

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
            "Upload, index, and manage learning material versions with complete lifecycle visibility."
            if selected_course
            else "Select a university course to view and manage its learning materials."
        )

        crumbs = (
            [
                ("Dashboard", "/dashboard"),
                ("Courses", "/knowledge-bases"),
                (f"{selected_course.name} Documents", None),
            ]
            if selected_course
            else [
                ("Dashboard", "/dashboard"),
                ("Courses", "/knowledge-bases"),
                ("Course Documents", None),
            ]
        )

        with page_layout(
            title=page_title,
            subtitle=page_subtitle,
            active_route="/documents",
            require_auth=True,
            breadcrumbs=crumbs,
        ):
            # ------------------------------------------------------------------
            # COURSE SELECTION PROMPT (When no course is selected in URL)
            # ------------------------------------------------------------------
            if not selected_course:
                with ui.card().classes(
                    "academic-card w-full p-6 sm:p-8 bg-white border border-slate-200 rounded-xl shadow-xs"
                ):
                    with ui.row().classes("items-center gap-2 mb-2"):
                        with ui.element("div").classes(
                            "w-8 h-8 rounded-lg bg-blue-50 text-blue-700 flex items-center justify-center font-bold"
                        ):
                            ui.icon("folder_open", size="18px")
                        ui.label("Select a Course Knowledge Base").classes(
                            "text-base font-bold text-slate-900"
                        )
                    ui.label(
                        "Choose a course below to upload syllabi, inspect indexed documents, and monitor vector status."
                    ).classes("text-xs text-slate-600 mb-5")

                    if not all_courses:
                        render_empty_state(
                            icon="school",
                            title="No Courses Available",
                            description="You do not have access to manage documents in any courses.",
                        )
                    else:
                        with ui.element("div").classes(
                            "w-full grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"
                        ):
                            for c in all_courses:
                                with ui.card().classes(
                                    "p-4 bg-white border border-slate-200 rounded-lg shadow-2xs hover:border-blue-400 transition-colors flex flex-col justify-between"
                                ):
                                    with ui.column().classes("gap-1"):
                                        ui.label(c.name).classes(
                                            "text-sm font-bold text-slate-900 truncate"
                                        )
                                        if c.description:
                                            ui.label(c.description).classes(
                                                "text-xs text-slate-500 line-clamp-2"
                                            )
                                    ui.button(
                                        "Manage Documents",
                                        icon="arrow_forward",
                                        on_click=lambda c_id=c.id: ui.navigate.to(
                                            f"/documents?kb_id={c_id}"
                                        ),
                                    ).props("no-caps dense").classes(
                                        "w-full mt-3 text-xs font-medium !bg-blue-700 hover:!bg-blue-800 !text-white rounded-lg"
                                    )
                return

            # ------------------------------------------------------------------
            # COURSE CONTEXT BAR
            # ------------------------------------------------------------------
            with ui.card().classes(
                "academic-card w-full p-5 bg-white border border-slate-200 rounded-xl shadow-xs"
            ):
                with ui.row().classes("w-full justify-between items-center gap-3 flex-wrap"):
                    with ui.row().classes("items-center gap-3"):
                        with ui.element("div").classes(
                            "w-9 h-9 rounded-lg bg-blue-50 text-blue-700 flex items-center justify-center font-bold"
                        ):
                            ui.icon("school", size="18px")
                        with ui.column().classes("gap-0.5"):
                            with ui.row().classes("items-center gap-2"):
                                ui.label(selected_course.name).classes(
                                    "text-base font-bold text-slate-900 tracking-tight"
                                )
                                ui.badge("Active Course", color="blue-1").props("text-color=blue-9").classes(
                                    "text-[10px] font-mono px-1.5 py-0.5 border border-blue-200"
                                )
                            if selected_course.description:
                                ui.label(selected_course.description).classes(
                                    "text-xs text-slate-500 line-clamp-1"
                                )

                    with ui.row().classes("items-center gap-2"):
                        ui.button(
                            "Switch Course",
                            icon="swap_horiz",
                            on_click=lambda: ui.navigate.to("/documents"),
                        ).props("outline dense no-caps").classes(
                            "text-xs border-slate-300 text-slate-700 hover:bg-slate-50 px-3 py-1.5 rounded-lg font-medium transition-colors"
                        )
                        ui.button(
                            "Open Chat",
                            icon="chat",
                            on_click=lambda: ui.navigate.to(f"/chat?kb_id={selected_course.id}"),
                        ).props("flat dense no-caps").classes(
                            "text-xs text-blue-700 hover:text-blue-900 font-medium px-2 py-1"
                        )

            # ------------------------------------------------------------------
            # UPLOAD COURSE MATERIAL PANEL
            # ------------------------------------------------------------------
            if can_upload_documents:
                max_upload_bytes = settings.MAX_UPLOAD_SIZE_BYTES
                max_mb = max_upload_bytes // (1024 * 1024)

                with ui.card().classes(
                    "academic-card w-full p-5 sm:p-6 bg-white border border-slate-200 rounded-xl shadow-xs gap-3"
                ):
                    with ui.row().classes("w-full justify-between items-center pb-2.5 border-b border-slate-100"):
                        with ui.row().classes("items-center gap-2"):
                            with ui.element("div").classes(
                                "w-7 h-7 rounded-lg bg-blue-50 text-blue-700 flex items-center justify-center font-bold"
                            ):
                                ui.icon("upload_file", size="16px")
                            ui.label("Upload Course Material").classes(
                                "text-sm font-bold text-slate-900"
                            )
                        with ui.row().classes("items-center gap-1.5 text-xs text-slate-500 font-mono"):
                            ui.label("Supported: PDF, DOCX, TXT, MD, CSV")
                            ui.label("•")
                            ui.label(f"Max: {max_mb} MB")

                    ui.label(
                        f"Upload learning materials directly into '{selected_course.name}'. "
                        "Ingestion validates format, parses text, and chunks content in the background."
                    ).classes("text-xs text-slate-600 leading-relaxed")

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
                                render_alert(f"Failed to read file: {read_err}", level="negative")
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
                                    f"'{doc.filename}' uploaded successfully ({format_bytes(size)}). Processing started.",
                                    level="info",
                                )
                            ui.notify(f"Uploaded '{doc.filename}'.", type="positive")
                            refresh_doc_list()
                            poll_timer.activate()
                        except ValueError as err:
                            with upload_alert:
                                render_alert(normalize_error(err, context="document"), level="negative")

                    ui.upload(
                        label=f"Drop course files here or click to browse (up to {max_mb} MB)",
                        on_upload=handle_upload,
                        auto_upload=True,
                        max_file_size=max_upload_bytes,
                    ).props('accept=".pdf,.docx,.txt,.md,.csv"').classes("w-full")

            # ------------------------------------------------------------------
            # DOCUMENTS TABLE & INSPECTION
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

            poll_timer = ui.timer(2.5, poll_check, active=False)

            def open_chunk_inspection_dialog(doc_id: str, doc_name: str) -> None:
                """Open inspection dialog inside with dialog: to prevent ghost DOM elements."""
                try:
                    chunks = api_client.get_document_chunks(
                        kb_id=selected_course.id, document_id=doc_id
                    )
                except Exception:
                    chunks = []

                with (
                    ui.dialog() as chunk_dlg,
                    ui.card().classes(
                        "w-full max-w-2xl p-6 bg-white border border-slate-200 rounded-xl shadow-xl gap-3"
                    ),
                ):
                    with ui.row().classes("w-full justify-between items-center pb-2.5 border-b border-slate-100"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("segment", size="18px").classes("text-blue-700")
                            ui.label(f"Chunks — {doc_name}").classes(
                                "text-sm font-bold text-slate-900"
                            )
                        ui.button(icon="close", on_click=chunk_dlg.close).props(
                            "flat round dense"
                        ).classes("text-slate-400 hover:text-slate-700")

                    ui.label(f"Total: {len(chunks)} indexed vector chunk(s)").classes(
                        "text-xs text-slate-500 font-mono"
                    )

                    if not chunks:
                        ui.label("No chunks generated for this document yet.").classes(
                            "text-xs text-slate-500 py-4"
                        )
                    else:
                        with ui.column().classes("w-full gap-2.5 max-h-80 overflow-y-auto pr-1"):
                            for i, chk in enumerate(chunks, 1):
                                with ui.card().classes(
                                    "w-full p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs"
                                ):
                                    with ui.row().classes("w-full justify-between items-center mb-1 text-[11px] text-slate-500 font-mono"):
                                        ui.label(f"Chunk #{i} • Page {chk.get('page_number', 'N/A')}")
                                        ui.label(f"{chk.get('token_count', 0)} tokens")
                                    ui.label(chk.get("content", "")).classes(
                                        "italic text-slate-700 line-clamp-3 select-text"
                                    )

                    with ui.row().classes("w-full justify-end pt-2 border-t border-slate-100"):
                        ui.button("Close", on_click=chunk_dlg.close).props(
                            "flat dense no-caps"
                        ).classes("text-xs text-slate-600")

                chunk_dlg.open()

            def confirm_delete_document(doc_id: str, doc_name: str) -> None:
                """Open confirmation dialog inside with dialog: to prevent ghost DOM elements."""
                with (
                    ui.dialog() as del_dlg,
                    ui.card().classes("w-full max-w-sm p-5 bg-white border border-slate-200 rounded-xl shadow-lg gap-3"),
                ):
                    ui.label("Delete Document?").classes("text-base font-bold text-slate-900")
                    ui.label(
                        f"Are you sure you want to delete '{doc_name}'? "
                        "All associated vector embeddings and chunks will be removed from pgvector."
                    ).classes("text-xs text-slate-600 leading-relaxed")

                    def do_delete() -> None:
                        del_dlg.close()
                        try:
                            api_client.delete_document(selected_course.id, doc_id)
                            ui.notify(f"Deleted '{doc_name}'.", type="positive")
                            refresh_doc_list()
                        except ValueError as err:
                            ui.notify(f"Delete failed: {err}", type="negative")

                    with ui.row().classes("w-full justify-end gap-2 pt-2 border-t border-slate-100"):
                        ui.button("Cancel", on_click=del_dlg.close).props("flat dense no-caps").classes("text-xs text-slate-600")
                        ui.button("Delete", icon="delete", on_click=do_delete).props("no-caps dense").classes("text-xs px-3 py-1.5 !bg-rose-600 !text-white rounded-lg")

                del_dlg.open()

            def render_documents_view() -> None:
                try:
                    docs = api_client.get_documents(selected_course.id)
                except ValueError as err:
                    render_alert(f"Failed to load documents: {err}", level="negative")
                    return

                q = search_state["query"].lower().strip()
                cat = search_state["filter"]
                filtered_docs = docs
                if q:
                    filtered_docs = [d for d in filtered_docs if q in d.filename.lower()]
                if cat == "READY":
                    filtered_docs = [
                        d for d in filtered_docs if d.indexing_status == "COMPLETED"
                    ]
                elif cat == "INDEXING":
                    filtered_docs = [
                        d for d in filtered_docs if d.indexing_status in ("QUEUED", "PROCESSING")
                    ]
                elif cat == "FAILED":
                    filtered_docs = [
                        d for d in filtered_docs if d.indexing_status == "FAILED" or d.status == "FAILED"
                    ]

                with ui.card().classes(
                    "academic-card w-full p-5 sm:p-6 bg-white border border-slate-200 rounded-xl shadow-xs gap-4"
                ):
                    # Table Toolbar
                    with ui.row().classes("w-full justify-between items-center gap-3 flex-wrap pb-3 border-b border-slate-100"):
                        with ui.row().classes("items-center gap-2 flex-1 max-w-sm"):
                            s_in = (
                                ui.input(placeholder="Search by filename...", value=search_state["query"])
                                .props("outlined dense clearable")
                                .classes("w-full text-xs minimalist-input")
                            )

                            def update_q(val: str | None) -> None:
                                search_state["query"] = val or ""
                                refresh_doc_list()

                            s_in.on_value_change(lambda e: update_q(e.value))

                        with ui.row().classes("items-center gap-1.5 flex-wrap"):
                            filters = [
                                ("ALL", f"All ({len(docs)})"),
                                ("READY", "Ready"),
                                ("INDEXING", "Indexing"),
                                ("FAILED", "Failed"),
                            ]
                            for f_key, f_label in filters:
                                is_sel = search_state["filter"] == f_key
                                btn_cls = (
                                    "!bg-slate-900 !text-white"
                                    if is_sel
                                    else "border border-slate-200 text-slate-600 hover:bg-slate-50"
                                )

                                def set_cat(k=f_key) -> None:
                                    search_state["filter"] = k
                                    refresh_doc_list()

                                ui.button(f_label, on_click=set_cat).props("dense no-caps").classes(
                                    f"text-xs px-2.5 py-1 rounded-md {btn_cls} transition-colors"
                                )

                            ui.button(icon="refresh", on_click=refresh_doc_list).props("flat round dense").classes("text-slate-400 hover:text-slate-700")

                    if not filtered_docs:
                        render_empty_state(
                            icon="description",
                            title="No Documents Found" if q else "No Documents Uploaded",
                            description=(
                                f"No files match '{q}'."
                                if q
                                else f"No learning materials have been uploaded to '{selected_course.name}' yet."
                            ),
                        )
                        return

                    # Clean Accessible Documents Table
                    with ui.element("div").classes("w-full responsive-table-wrapper"):
                        with ui.element("table").classes("w-full text-left text-xs border-collapse"):
                            with ui.element("thead"):
                                with ui.element("tr").classes("border-b border-slate-200 text-slate-500 font-mono text-[11px]"):
                                    ui.element("th").classes("py-2.5 px-3 font-semibold").text = "DOCUMENT"
                                    ui.element("th").classes("py-2.5 px-2 font-semibold").text = "FORMAT"
                                    ui.element("th").classes("py-2.5 px-2 font-semibold").text = "SIZE"
                                    ui.element("th").classes("py-2.5 px-2 font-semibold").text = "STATUS"
                                    ui.element("th").classes("py-2.5 px-2 font-semibold").text = "CHUNKS"
                                    ui.element("th").classes("py-2.5 px-2 font-semibold").text = "UPLOADED"
                                    ui.element("th").classes("py-2.5 px-3 font-semibold text-right").text = "ACTIONS"

                            with ui.element("tbody"):
                                for d in filtered_docs:
                                    with ui.element("tr").classes("border-b border-slate-100 hover:bg-slate-50/70 transition-colors"):
                                        # Document name with icon
                                        with ui.element("td").classes("py-3 px-3"):
                                            with ui.row().classes("items-center gap-2 min-w-0"):
                                                is_pdf = d.filename.lower().endswith(".pdf")
                                                ui.icon("picture_as_pdf" if is_pdf else "description", size="18px").classes(
                                                    "text-rose-600" if is_pdf else "text-blue-600"
                                                )
                                                ui.label(d.filename).classes("font-semibold text-slate-900 truncate max-w-xs")

                                        # Format
                                        with ui.element("td").classes("py-3 px-2 font-mono text-[11px] text-slate-500"):
                                            ui.badge(d.file_type.upper(), color="slate-1").props("text-color=slate-7").classes("text-[10px] px-1.5 py-0.5 border border-slate-200")

                                        # Size
                                        with ui.element("td").classes("py-3 px-2 font-mono text-[11px] text-slate-600"):
                                            ui.label(format_bytes(d.file_size_bytes or 0))

                                        # Status Badge
                                        with ui.element("td").classes("py-3 px-2"):
                                            if d.indexing_status == "COMPLETED":
                                                ui.badge("Ready", color="emerald-1").props("text-color=emerald-9").classes("text-[10px] font-semibold px-2 py-0.5 border border-emerald-200")
                                            elif d.indexing_status in ("QUEUED", "PROCESSING") or d.status == "PROCESSING":
                                                ui.badge("Indexing", color="amber-1").props("text-color=amber-9").classes("text-[10px] font-semibold px-2 py-0.5 border border-amber-200")
                                            elif d.indexing_status == "FAILED" or d.status == "FAILED":
                                                ui.badge("Failed", color="rose-1").props("text-color=rose-9").classes("text-[10px] font-semibold px-2 py-0.5 border border-rose-200")
                                            else:
                                                ui.badge(d.status.title(), color="slate-1").props("text-color=slate-7").classes("text-[10px] font-semibold px-2 py-0.5 border border-slate-200")

                                        # Chunks
                                        with ui.element("td").classes("py-3 px-2 font-mono text-[11px] text-slate-600"):
                                            ui.label(str(d.chunk_count or 0))

                                        # Uploaded date
                                        with ui.element("td").classes("py-3 px-2 font-mono text-[11px] text-slate-400"):
                                            ui.label(str(d.created_at)[:10] if d.created_at else "—")

                                        # Actions
                                        with ui.element("td").classes("py-3 px-3 text-right"):
                                            with ui.row().classes("justify-end items-center gap-1"):
                                                # Read in Source Viewer
                                                ui.button(
                                                    icon="visibility",
                                                    on_click=lambda doc=d: open_source_viewer(
                                                        document_id=str(doc.id),
                                                        document_name=doc.filename,
                                                        kb_id=str(selected_course.id),
                                                        course_name=selected_course.name,
                                                    ),
                                                ).props("flat round dense size=sm").classes(
                                                    "text-slate-600 hover:text-blue-700"
                                                ).tooltip("Read original document")

                                                # Inspect Chunks
                                                ui.button(
                                                    icon="segment",
                                                    on_click=lambda doc=d: open_chunk_inspection_dialog(
                                                        doc_id=str(doc.id),
                                                        doc_name=doc.filename,
                                                    ),
                                                ).props("flat round dense size=sm").classes(
                                                    "text-slate-600 hover:text-blue-700"
                                                ).tooltip("Inspect vector chunks")

                                                # Delete Document
                                                if can_delete_documents:
                                                    ui.button(
                                                        icon="delete",
                                                        on_click=lambda doc=d: confirm_delete_document(
                                                            doc_id=str(doc.id),
                                                            doc_name=doc.filename,
                                                        ),
                                                    ).props("flat round dense size=sm").classes(
                                                        "text-slate-400 hover:text-rose-600"
                                                    ).tooltip("Delete document")

            # Initial render
            refresh_doc_list()
