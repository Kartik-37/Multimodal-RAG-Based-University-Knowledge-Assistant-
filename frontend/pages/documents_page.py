"""
Documents Management Page.

Provides document upload UI with supported format indicators, lifecycle status
tracking badges, responsive table layout, and role-based action controls.
Upload limits are read dynamically from backend settings (MAX_UPLOAD_SIZE_BYTES).
All operations route through FrontendAPIClient.
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
    def documents_page() -> None:
        with page_layout(
            title="Documents",
            subtitle="Upload and inspect source documents for parsing, chunking, and dense vector indexing.",
            active_route="/documents",
            require_auth=True,
        ):
            user = state.current_user
            is_admin = bool(user and user.role == "ADMIN")
            active_kb = state.active_kb

            if not active_kb:
                render_empty_state(
                    icon="folder_off",
                    title="No Active Knowledge Base Selected",
                    description="Please select or create a knowledge base before uploading or inspecting documents.",
                    action_label="Select Knowledge Base",
                    on_action=lambda: ui.navigate.to("/knowledge-bases"),
                )
                return

            # Active KB Header Card
            with ui.card().classes(
                "w-full p-4 bg-white border border-slate-200 rounded-lg shadow-xs"
            ):
                with ui.row().classes("w-full justify-between items-center gap-2"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("folder", size="sm").classes("text-blue-600")
                        ui.label("Active Target Corpus:").classes(
                            "text-xs font-semibold text-slate-500 uppercase tracking-wider"
                        )
                        ui.label(active_kb.name).classes("text-sm font-bold text-slate-900")

                    with ui.row().classes("items-center gap-1.5"):
                        ui.label("Supported Formats:").classes(
                            "text-xs font-semibold text-slate-500 mr-1"
                        )
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

            # Dynamic document list container
            doc_container = ui.column().classes("w-full gap-4")

            # Document Upload Section (Admin Only)
            if is_admin:
                max_upload_bytes = settings.MAX_UPLOAD_SIZE_BYTES
                max_mb = max_upload_bytes // (1024 * 1024)

                with ui.card().classes(
                    "w-full p-5 bg-white border border-slate-200 rounded-lg shadow-xs"
                ):
                    with ui.row().classes("items-center justify-between mb-1"):
                        ui.label("Upload New Document (Administrator)").classes(
                            "text-sm font-bold text-slate-900"
                        )
                        ui.label(f"Maximum File Size: {max_mb} MB").classes(
                            "text-xs text-slate-500 font-mono"
                        )

                    ui.label(
                        "Upload course documents to initiate automated parsing, metadata extraction, and semantic chunking."
                    ).classes("text-xs text-slate-500 mb-3")

                    upload_alert = ui.column().classes("w-full mb-2")

                    async def handle_upload(e: events.UploadEventArguments) -> None:
                        upload_alert.clear()
                        fname = e.name.strip()
                        lower_fname = fname.lower()
                        if not any(lower_fname.endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                            with upload_alert:
                                render_alert(
                                    f"Unsupported file format for '{fname}'. Only PDF, DOCX, TXT, MD, and CSV files are accepted.",
                                    level="negative",
                                )
                            return

                        try:
                            content = await e.read()
                            size = len(content)
                        except Exception:
                            content = b""
                            size = 0

                        try:
                            doc = api_client.upload_document(
                                kb_id=active_kb.id,
                                filename=fname,
                                content=content,
                                content_size_bytes=size,
                            )
                            ui.notify(
                                f"Uploaded '{doc.filename}' (Status: {doc.status})", type="positive"
                            )
                            refresh_doc_list()
                        except ValueError as err:
                            with upload_alert:
                                render_alert(str(err), level="negative")

                    ui.upload(
                        label=f"Drop files here or click to browse (up to {max_mb} MB)",
                        on_upload=handle_upload,
                        auto_upload=True,
                        max_file_size=max_upload_bytes,
                    ).props('accept=".pdf,.docx,.txt,.md,.csv"').classes("w-full")
            else:
                with ui.card().classes("w-full p-4 bg-blue-50 border border-blue-200 rounded-lg"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("lock", size="sm").classes("text-blue-700")
                        ui.label("Student Access (Read-Only)").classes(
                            "text-sm font-bold text-blue-900"
                        )
                    ui.label(
                        "You have student access to browse course materials and query context. "
                        "Document upload, ingestion, and deletion are reserved for Course Administrators."
                    ).classes("text-xs text-blue-800 mt-1 leading-relaxed")

            def refresh_doc_list() -> None:
                doc_container.clear()
                with doc_container:
                    render_documents_table()

            def render_documents_table() -> None:
                docs = api_client.get_documents(active_kb.id)

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
                        ui.button(icon="refresh", on_click=refresh_doc_list).props(
                            "flat round dense"
                        ).classes("text-slate-500 hover:text-slate-800").tooltip(
                            "Refresh Document Status"
                        )

                    if not docs:
                        render_empty_state(
                            icon="description",
                            title="No Documents Uploaded",
                            description="Upload syllabus, notes, or textbook materials above to populate this knowledge base.",
                        )
                        return

                    # Responsive Table Wrapper
                    with ui.element("div").classes("responsive-table-wrapper"):
                        with ui.element("table").classes(
                            "w-full text-left text-xs border-collapse"
                        ):
                            with ui.element("thead").classes(
                                "bg-slate-50 text-slate-600 uppercase font-semibold border-b border-slate-200"
                            ):
                                with ui.element("tr"):
                                    ui.element("th").classes("py-2.5 px-3").text = "Document"
                                    ui.element("th").classes("py-2.5 px-3").text = "Format"
                                    ui.element("th").classes("py-2.5 px-3").text = "Size"
                                    ui.element("th").classes("py-2.5 px-3").text = "Ingestion"
                                    ui.element("th").classes("py-2.5 px-3").text = "Vectors"
                                    ui.element("th").classes("py-2.5 px-3").text = "Chunks"
                                    ui.element("th").classes("py-2.5 px-3").text = "Uploaded"
                                    if is_admin:
                                        ui.element("th").classes(
                                            "py-2.5 px-3 text-right"
                                        ).text = "Actions"

                            with ui.element("tbody").classes(
                                "divide-y divide-slate-100 text-slate-800"
                            ):
                                for doc in docs:
                                    with ui.element("tr").classes(
                                        "hover:bg-slate-50 transition-colors"
                                    ):
                                        with ui.element("td").classes("py-2.5 px-3 font-medium"):
                                            with ui.column().classes("gap-0"):
                                                ui.label(doc.filename).classes(
                                                    "truncate max-w-[200px] font-semibold text-slate-900"
                                                )
                                                if doc.error_message and doc.status == "FAILED":
                                                    ui.label("Ingestion error").classes(
                                                        "text-[10px] text-rose-600"
                                                    ).tooltip(doc.error_message)

                                        with ui.element("td").classes("py-2.5 px-3 font-mono"):
                                            ui.badge(
                                                doc.file_type.upper(), color="slate-600"
                                            ).classes("text-[10px]")

                                        ui.element("td").classes(
                                            "py-2.5 px-3 font-mono"
                                        ).text = format_bytes(doc.file_size_bytes)

                                        with ui.element("td").classes("py-2.5 px-3"):
                                            render_status_badge(doc.status)

                                        with ui.element("td").classes("py-2.5 px-3"):
                                            render_indexing_status_badge(doc.indexing_status)

                                        ui.element("td").classes(
                                            "py-2.5 px-3 font-mono"
                                        ).text = str(doc.chunk_count)
                                        ui.element("td").classes(
                                            "py-2.5 px-3 font-mono text-slate-500"
                                        ).text = doc.created_at

                                        if is_admin:
                                            with ui.element("td").classes("py-2.5 px-3 text-right"):
                                                with ui.row().classes(
                                                    "items-center justify-end gap-1"
                                                ):
                                                    # Vector Indexing Trigger
                                                    if (
                                                        doc.status == "COMPLETED"
                                                        and doc.indexing_status != "COMPLETED"
                                                    ):

                                                        def trigger_index(d_id=doc.id) -> None:
                                                            try:
                                                                api_client.index_document(
                                                                    active_kb.id, d_id
                                                                )
                                                                ui.notify(
                                                                    "Indexing task initiated in background.",
                                                                    type="positive",
                                                                )
                                                                refresh_doc_list()
                                                            except ValueError as err:
                                                                ui.notify(str(err), type="negative")

                                                        ui.button(
                                                            "Index",
                                                            icon="storage",
                                                            on_click=trigger_index,
                                                        ).props(
                                                            "outline dense no-caps color=primary"
                                                        ).classes("text-[11px] px-2 py-0.5")

                                                    # Delete Action
                                                    def trigger_delete(
                                                        d_id=doc.id, d_name=doc.filename
                                                    ) -> None:
                                                        try:
                                                            api_client.delete_document(
                                                                active_kb.id, d_id
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

            # Initial render
            render_documents_table()
