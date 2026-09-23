"""
Documents Management Page.

Provides course-specific document management:
- Upload documents (PDF, DOCX, TXT, MD, CSV) with real-time lifecycle tracking.
- Distinct states: Uploading/Uploaded, Ingestion (PENDING, PROCESSING, COMPLETED, FAILED),
  and Retrieval Publication (ACTIVE, INACTIVE).
- Document-level publication controls (Activate / Deactivate) for version management.
- Dynamic polling while any document is in PENDING or PROCESSING.
- Strictly replaces dynamic content in a single container to guarantee rendering integrity.
"""

from nicegui import events, ui

from backend.app.core.config import settings
from frontend.client.api_client import api_client
from frontend.components.layout import page_layout
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

        all_courses = api_client.get_knowledge_bases() if user else []

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
            "Upload and manage learning material, activate versions for retrieval, and track processing status."
            if selected_course
            else "Select a university course to view and manage its learning materials."
        )

        with page_layout(
            title=page_title,
            subtitle=page_subtitle,
            active_route="/documents",
            require_auth=True,
        ):
            # If no course is selected, display clear course selection state (no silent defaults)
            if not selected_course:
                with ui.card().classes(
                    "w-full max-w-2xl mx-auto p-6 bg-white border border-slate-200 rounded-lg shadow-xs text-center items-center"
                ):
                    ui.icon("menu_book", size="3rem").classes("text-blue-600 mb-2")
                    ui.label("Select a Course").classes("text-lg font-bold text-slate-900 mb-1")
                    ui.label(
                        "Please choose a course below to manage its documents and learning materials."
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
                                        "w-full items-center justify-between p-3 bg-slate-50 hover:bg-blue-50/50 border border-slate-200 rounded-lg cursor-pointer transition-colors"
                                    )
                                    .on(
                                        "click",
                                        lambda course_id=c.id: ui.navigate.to(
                                            f"/documents?kb_id={course_id}"
                                        ),
                                    )
                                ):
                                    with ui.row().classes("items-center gap-3"):
                                        ui.icon("school", size="sm").classes("text-blue-600")
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

            # Course Context & Supported Formats Banner
            with ui.card().classes(
                "w-full p-4 bg-white border border-slate-200 rounded-lg shadow-xs"
            ):
                with ui.row().classes("w-full justify-between items-center gap-3 flex-wrap"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("school", size="sm").classes("text-blue-600")
                        ui.label(f"Course: {selected_course.name}").classes(
                            "text-sm font-bold text-slate-900"
                        )
                        ui.button(
                            "Switch Course",
                            icon="swap_horiz",
                            on_click=lambda: ui.navigate.to("/documents"),
                        ).props("flat dense no-caps").classes("text-xs text-blue-600 ml-2")

                    with ui.row().classes("items-center gap-2"):
                        ui.label("Supported:").classes("text-xs font-semibold text-slate-500")
                        formats = [
                            ("PDF", "rose-700"),
                            ("DOCX", "blue-700"),
                            ("TXT", "slate-700"),
                            ("MD", "purple-700"),
                            ("CSV", "emerald-700"),
                        ]
                        for fmt_label, fmt_color in formats:
                            ui.badge(fmt_label, color=fmt_color).classes(
                                "text-[10px] font-mono px-1.5 py-0.5"
                            )
                        ui.label("• Max 20 MB").classes("text-xs text-slate-400 font-mono")

            # Upload Course Material Section (Admin Only)
            if is_admin:
                max_upload_bytes = settings.MAX_UPLOAD_SIZE_BYTES
                max_mb = max_upload_bytes // (1024 * 1024)

                with ui.card().classes(
                    "w-full p-5 bg-white border border-slate-200 rounded-lg shadow-xs"
                ):
                    with ui.row().classes("items-center justify-between mb-1"):
                        ui.label("Upload Course Material").classes(
                            "text-sm font-bold text-slate-900"
                        )
                        ui.label(f"Maximum File Size: {max_mb} MB").classes(
                            "text-xs text-slate-500 font-mono"
                        )

                    ui.label(
                        f"Upload syllabus, lecture notes, or textbooks directly into '{selected_course.name}'. "
                        "Ingestion pipeline automatically performs parsing, normalization, semantic chunking, and indexing."
                    ).classes("text-xs text-slate-500 mb-3")

                    upload_alert = ui.column().classes("w-full mb-2")

                    async def handle_upload(e: events.UploadEventArguments) -> None:
                        upload_alert.clear()
                        # Use current NiceGUI FileUpload API directly
                        file_obj = e.file
                        fname = file_obj.name.strip()
                        lower_fname = fname.lower()
                        if not any(lower_fname.endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                            with upload_alert:
                                render_alert(
                                    f"Unsupported file format for '{fname}'. Supported formats: PDF, DOCX, TXT, MD, CSV.",
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
                            ui.notify(
                                f"Uploaded '{doc.filename}'. Processing initiated in background.",
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
            # Stable Dynamic Document List Container (Guarantees Single Table)
            # ------------------------------------------------------------------
            doc_container = ui.column().classes("w-full gap-4")

            def refresh_doc_list() -> None:
                """Rebuild document list strictly inside doc_container."""
                doc_container.clear()
                with doc_container:
                    render_documents_view()

            def poll_check() -> None:
                """Periodic poll to update document processing state."""
                docs = api_client.get_documents(selected_course.id)
                has_active_processing = any(
                    d.status in ("PENDING", "PROCESSING") or d.indexing_status == "PROCESSING"
                    for d in docs
                )
                refresh_doc_list()
                if not has_active_processing:
                    poll_timer.deactivate()

            poll_timer = ui.timer(2.0, poll_check, active=False)

            def render_documents_view() -> None:
                docs = api_client.get_documents(selected_course.id)

                # Check if any documents are currently processing or queued
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

                with ui.card().classes(
                    "w-full p-5 bg-white border border-slate-200 rounded-lg shadow-xs"
                ):
                    with ui.row().classes(
                        "w-full justify-between items-center mb-3 pb-2 border-b border-slate-100"
                    ):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("library_books", size="sm").classes("text-slate-600")
                            ui.label(f"{len(docs)} Document(s) Ingested").classes(
                                "text-sm font-bold text-slate-800"
                            )
                            if active_processing:
                                with ui.row().classes(
                                    "items-center gap-1 text-xs text-blue-600 font-medium ml-2"
                                ):
                                    ui.spinner(size="xs")
                                    ui.label("Indexing / Processing in background...")

                        ui.button(icon="refresh", on_click=refresh_doc_list).props(
                            "flat round dense"
                        ).classes("text-slate-500 hover:text-slate-800").tooltip(
                            "Refresh Document Status"
                        )

                    if not docs:
                        render_empty_state(
                            icon="description",
                            title="No Documents Uploaded",
                            description=f"No learning materials have been uploaded to '{selected_course.name}' yet.",
                        )
                        return

                    # Responsive Document Table
                    with ui.element("div").classes("responsive-table-wrapper"):
                        with ui.element("table").classes(
                            "w-full text-left text-xs border-collapse"
                        ):
                            with ui.element("thead").classes(
                                "bg-slate-50 text-slate-600 uppercase font-semibold border-b border-slate-200"
                            ):
                                with ui.element("tr"):
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Document")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Retrieval")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Format")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Size")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Processing")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Vectors")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Chunks")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Uploaded")
                                    if is_admin:
                                        with ui.element("th").classes("py-2.5 px-3 text-right"):
                                            ui.label("Actions")

                            with ui.element("tbody").classes(
                                "divide-y divide-slate-100 text-slate-800"
                            ):
                                for doc in docs:
                                    with ui.element("tr").classes(
                                        "hover:bg-slate-50 transition-colors"
                                    ):
                                        # Filename & Ingestion failure
                                        with ui.element("td").classes("py-2.5 px-3 font-medium"):
                                            with ui.column().classes("gap-0"):
                                                ui.label(doc.filename).classes(
                                                    "truncate max-w-[220px] font-semibold text-slate-900"
                                                )
                                                if doc.error_message and doc.status == "FAILED":
                                                    ui.label(f"Error: {doc.error_message}").classes(
                                                        "text-[10px] text-rose-600 truncate max-w-[200px]"
                                                    ).tooltip(doc.error_message)

                                        # Retrieval Publication State (Active / Inactive / Not Ready)
                                        with ui.element("td").classes("py-2.5 px-3"):
                                            if doc.indexing_status != "COMPLETED":
                                                ui.badge("NOT READY", color="amber-700").classes(
                                                    "text-[10px] font-bold"
                                                ).tooltip(
                                                    "Not ready: Vector indexing has not completed successfully."
                                                )
                                            elif doc.is_active:
                                                ui.badge("ACTIVE", color="emerald-700").classes(
                                                    "text-[10px] font-bold"
                                                ).tooltip("Active: Included in student queries")
                                            else:
                                                ui.badge("INACTIVE", color="slate-500").classes(
                                                    "text-[10px] font-bold"
                                                ).tooltip(
                                                    "Inactive: Historical version excluded from retrieval"
                                                )

                                        # Format
                                        with ui.element("td").classes("py-2.5 px-3 font-mono"):
                                            ui.badge(
                                                doc.file_type.upper(), color="slate-600"
                                            ).classes("text-[10px]")

                                        # Size
                                        with ui.element("td").classes("py-2.5 px-3 font-mono"):
                                            ui.label(format_bytes(doc.file_size_bytes))

                                        # Processing Status
                                        with ui.element("td").classes("py-2.5 px-3"):
                                            render_status_badge(doc.status)

                                        # Vectors Status & Live Progress
                                        with ui.element("td").classes("py-2.5 px-3"):
                                            with ui.column().classes("gap-0.5"):
                                                if doc.indexing_status in ("QUEUED", "PROCESSING"):
                                                    render_indexing_status_badge(doc.indexing_status)
                                                    try:
                                                        job = api_client.get_document_index_status(
                                                            selected_course.id, doc.id
                                                        )
                                                        ui.label(
                                                            f"{job.processed_chunks} / {job.total_chunks} chunks ({job.progress_percent:.0f}%)"
                                                        ).classes(
                                                            "text-[10px] font-mono text-blue-700 font-semibold"
                                                        )
                                                        stage_clean = job.stage.replace(
                                                            "_", " "
                                                        ).title()
                                                        ui.label(
                                                            f"Stage: {stage_clean}"
                                                        ).classes("text-[9px] text-slate-500")
                                                    except Exception:
                                                        pass
                                                elif doc.indexing_status == "COMPLETED":
                                                    render_indexing_status_badge("COMPLETED")
                                                    ui.label(
                                                        f"{doc.chunk_count} / {doc.chunk_count} vectors verified"
                                                    ).classes(
                                                        "text-[10px] font-mono text-emerald-700"
                                                    )
                                                elif doc.indexing_status == "FAILED":
                                                    render_indexing_status_badge("FAILED")
                                                    err_text = (
                                                        doc.indexing_error or "Indexing failed"
                                                    )
                                                    ui.label(err_text).classes(
                                                        "text-[10px] text-rose-600 truncate max-w-[180px]"
                                                    ).tooltip(err_text)
                                                else:
                                                    render_indexing_status_badge(
                                                        doc.indexing_status
                                                    )

                                        # Chunks
                                        with ui.element("td").classes("py-2.5 px-3 font-mono"):
                                            ui.label(str(doc.chunk_count))

                                        # Uploaded Date
                                        with ui.element("td").classes(
                                            "py-2.5 px-3 font-mono text-slate-500"
                                        ):
                                            ui.label(doc.created_at)

                                        # Admin Actions
                                        if is_admin:
                                            with ui.element("td").classes("py-2.5 px-3 text-right"):
                                                with ui.row().classes(
                                                    "items-center justify-end gap-1"
                                                ):
                                                    # Version Activation / Deactivation Toggle
                                                    if doc.is_active:

                                                        def trigger_deactivate(
                                                            d_id=doc.id, d_name=doc.filename
                                                        ) -> None:
                                                            try:
                                                                api_client.deactivate_document(
                                                                    selected_course.id, d_id
                                                                )
                                                                ui.notify(
                                                                    f"Deactivated '{d_name}'. Excluded from retrieval.",
                                                                    type="info",
                                                                )
                                                                refresh_doc_list()
                                                            except ValueError as err:
                                                                ui.notify(str(err), type="negative")

                                                        ui.button(
                                                            "Deactivate",
                                                            icon="pause_circle",
                                                            on_click=trigger_deactivate,
                                                        ).props(
                                                            "outline dense no-caps color=warning"
                                                        ).classes(
                                                            "text-[11px] px-2 py-0.5"
                                                        ).tooltip(
                                                            "Deactivate to exclude from search while preserving file"
                                                        )
                                                    elif doc.indexing_status == "COMPLETED":

                                                        def trigger_activate(
                                                            d_id=doc.id, d_name=doc.filename
                                                        ) -> None:
                                                            try:
                                                                api_client.activate_document(
                                                                    selected_course.id, d_id
                                                                )
                                                                ui.notify(
                                                                    f"Activated '{d_name}'. Available for retrieval.",
                                                                    type="positive",
                                                                )
                                                                refresh_doc_list()
                                                            except ValueError as err:
                                                                ui.notify(str(err), type="negative")

                                                        ui.button(
                                                            "Activate",
                                                            icon="play_circle",
                                                            on_click=trigger_activate,
                                                        ).props(
                                                            "outline dense no-caps color=positive"
                                                        ).classes(
                                                            "text-[11px] px-2 py-0.5"
                                                        ).tooltip("Activate to include in search")
                                                    else:
                                                        ui.button(
                                                            "Activate",
                                                            icon="play_circle",
                                                        ).props(
                                                            "outline dense no-caps disable"
                                                        ).classes(
                                                            "text-[11px] px-2 py-0.5 opacity-50"
                                                        ).tooltip("Vector indexing must complete before activating")

                                                    # Vector Indexing Trigger (Index vs Retry)
                                                    if doc.indexing_status == "FAILED":

                                                        def trigger_retry(d_id=doc.id) -> None:
                                                            try:
                                                                api_client.index_document(
                                                                    selected_course.id, d_id
                                                                )
                                                                ui.notify(
                                                                    "Indexing retry initiated in background.",
                                                                    type="positive",
                                                                )
                                                                refresh_doc_list()
                                                                poll_timer.activate()
                                                            except ValueError as err:
                                                                ui.notify(str(err), type="negative")

                                                        ui.button(
                                                            "Retry Indexing",
                                                            icon="refresh",
                                                            on_click=trigger_retry,
                                                        ).props(
                                                            "outline dense no-caps color=warning"
                                                        ).classes("text-[11px] px-2 py-0.5")

                                                    elif (
                                                        doc.status == "COMPLETED"
                                                        and doc.indexing_status
                                                        not in ("COMPLETED", "PROCESSING", "QUEUED")
                                                    ):

                                                        def trigger_index(d_id=doc.id) -> None:
                                                            try:
                                                                api_client.index_document(
                                                                    selected_course.id, d_id
                                                                )
                                                                ui.notify(
                                                                    "Indexing task initiated in background.",
                                                                    type="positive",
                                                                )
                                                                refresh_doc_list()
                                                                poll_timer.activate()
                                                            except ValueError as err:
                                                                ui.notify(str(err), type="negative")

                                                        ui.button(
                                                            "Index",
                                                            icon="storage",
                                                            on_click=trigger_index,
                                                        ).props(
                                                            "outline dense no-caps color=primary"
                                                        ).classes("text-[11px] px-2 py-0.5")

                                                    elif doc.indexing_status in (
                                                        "QUEUED",
                                                        "PROCESSING",
                                                    ):
                                                        with ui.row().classes(
                                                            "items-center gap-1 text-[11px] text-blue-600 font-medium px-1"
                                                        ):
                                                            ui.spinner(size="xs")
                                                            ui.label("Indexing...")

                                                    # Delete Action
                                                    def trigger_delete(
                                                        d_id=doc.id, d_name=doc.filename
                                                    ) -> None:
                                                        try:
                                                            api_client.delete_document(
                                                                selected_course.id, d_id
                                                            )
                                                            ui.notify(
                                                                f"Deleted '{d_name}'", type="info"
                                                            )
                                                            refresh_doc_list()
                                                        except ValueError as err:
                                                            ui.notify(str(err), type="negative")

                                                    ui.button(
                                                        icon="delete_outline",
                                                        on_click=trigger_delete,
                                                    ).props("flat round dense").classes(
                                                        "text-slate-400 hover:text-rose-600"
                                                    ).tooltip("Delete Document")

            # Strictly execute initial render inside doc_container via refresh_doc_list
            refresh_doc_list()
