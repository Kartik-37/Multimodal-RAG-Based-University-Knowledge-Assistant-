"""
Documents Management Page.

Provides document upload UI with supported format indicators,
status tracking badges, ingestion progress placeholder, and empty states.
All operations communicate via FrontendAPIClient.
"""

from nicegui import events, ui

from frontend.client.api_client import api_client
from frontend.components.layout import page_layout
from frontend.components.status_badge import render_indexing_status_badge, render_status_badge
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
            subtitle="Upload and manage knowledge base source files for parsing, chunking, and indexing.",
            active_route="/documents",
        ):
            active_kb = state.active_kb

            # If no KB exists or none selected
            if not active_kb:
                with ui.card().classes(
                    "w-full p-8 items-center justify-center text-center border-dashed border-2 border-gray-300"
                ):
                    ui.icon("folder_off", size="lg").classes("text-gray-400 mb-2")
                    ui.label("No Active Knowledge Base Selected").classes(
                        "text-lg font-bold text-gray-800"
                    )
                    ui.label(
                        "Please select or create a knowledge base before uploading documents."
                    ).classes("text-sm text-gray-500 max-w-md mb-4")
                    ui.button(
                        "Go to Knowledge Bases",
                        icon="arrow_forward",
                        on_click=lambda: ui.navigate.to("/knowledge-bases"),
                    ).props("color=primary")
                return

            # Active KB Header & Format Indicator Card
            with ui.card().classes("w-full p-4 border border-gray-200 bg-white rounded shadow-sm"):
                with ui.row().classes("w-full justify-between items-center"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("folder", size="sm").classes("text-blue-500")
                        ui.label("Target Knowledge Base:").classes(
                            "text-xs font-semibold text-gray-500 uppercase"
                        )
                        ui.label(active_kb.name).classes("text-sm font-bold text-gray-900")

                    with ui.row().classes("items-center gap-2"):
                        ui.label("Supported Initial Formats:").classes(
                            "text-xs font-semibold text-gray-500"
                        )
                        formats = [
                            ("PDF", "red"),
                            ("DOCX", "blue"),
                            ("TXT", "grey"),
                            ("Markdown", "purple"),
                            ("CSV", "green"),
                        ]
                        for fmt_label, fmt_color in formats:
                            ui.badge(fmt_label, color=fmt_color).classes("text-xs font-mono")

            # Document Upload Section (Admin Only)
            user = state.current_user
            is_admin = user is not None and user.role == "ADMIN"

            if is_admin:
                with ui.card().classes(
                    "w-full p-5 border border-gray-200 bg-white rounded shadow-sm"
                ):
                    ui.label("Upload New Document (Administrator)").classes(
                        "text-sm font-bold text-gray-800 mb-1"
                    )
                    ui.label(
                        "Select a supported file (PDF, DOCX, TXT, MD, CSV). Files will be ingested, normalized, and chunked."
                    ).classes("text-xs text-gray-500 mb-3")

                    async def handle_upload(e: events.UploadEventArguments) -> None:
                        fname = e.name.strip()
                        lower_fname = fname.lower()
                        if not any(lower_fname.endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                            ui.notify(
                                f"Unsupported file type: '{fname}'. Only PDF, DOCX, TXT, MD, and CSV are accepted.",
                                type="negative",
                                close_button=True,
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
                                f"Uploaded '{doc.filename}'. Ingestion status: {doc.status}.",
                                type="positive",
                            )
                            refresh_doc_list()
                        except ValueError as err:
                            ui.notify(str(err), type="negative")

                    ui.upload(
                        label="Drop files here or click to browse",
                        on_upload=handle_upload,
                        auto_upload=True,
                        max_file_size=20 * 1024 * 1024,  # 20MB
                    ).props('accept=".pdf,.docx,.txt,.md,.csv"').classes("w-full")
            else:
                with ui.card().classes("w-full p-4 border border-blue-100 bg-blue-50 rounded"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("lock", size="sm").classes("text-blue-600")
                        ui.label("Student Access (Read-Only)").classes(
                            "text-sm font-bold text-blue-900"
                        )
                    ui.label(
                        "You have student access to browse documents and ask questions. "
                        "Document upload, ingestion, and deletion are restricted to Administrators."
                    ).classes("text-xs text-blue-700 mt-1")

            # Documents Table Container
            doc_container = ui.column().classes("w-full gap-2")

            def refresh_doc_list() -> None:
                doc_container.clear()
                with doc_container:
                    render_doc_list()

            def render_doc_list() -> None:
                docs = api_client.get_documents(active_kb.id)

                with ui.card().classes(
                    "w-full p-5 border border-gray-200 bg-white rounded shadow-sm"
                ):
                    with ui.row().classes("w-full justify-between items-center mb-4"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("description", size="sm").classes("text-gray-700")
                            ui.label(f"Stored Documents ({len(docs)})").classes(
                                "text-sm font-bold text-gray-800"
                            )

                        ui.button("Refresh", icon="refresh", on_click=refresh_doc_list).props(
                            "flat dense"
                        ).classes("text-xs text-gray-600")

                    if not docs:
                        with ui.column().classes(
                            "w-full py-10 items-center justify-center text-center"
                        ):
                            ui.icon("insert_drive_file", size="xl").classes("text-gray-300 mb-2")
                            ui.label("No Documents in this Knowledge Base").classes(
                                "text-base font-bold text-gray-700"
                            )
                            ui.label(
                                "Use the upload component above to add your first document."
                            ).classes("text-xs text-gray-500")
                        return

                    # Document Items List
                    with ui.column().classes("w-full gap-2"):
                        for doc in docs:
                            with ui.row().classes(
                                "w-full justify-between items-center p-3 border rounded bg-gray-50 hover:bg-gray-100 transition-colors"
                            ):
                                with ui.row().classes("items-center gap-3"):
                                    # File format icon
                                    fmt = doc.file_type.lower()
                                    icon_name = "picture_as_pdf" if fmt == "pdf" else "description"
                                    ui.icon(icon_name, size="sm").classes("text-blue-600")

                                    with ui.column().classes("gap-0.5"):
                                        ui.label(doc.filename).classes(
                                            "text-sm font-bold text-gray-900"
                                        )
                                        with ui.row().classes(
                                            "items-center gap-2 text-xs text-gray-500"
                                        ):
                                            ui.label(f"Size: {format_bytes(doc.file_size_bytes)}")
                                            ui.label(f"Uploaded: {doc.created_at}")

                                        if doc.error_message:
                                            ui.label(
                                                f"Ingestion Error: {doc.error_message}"
                                            ).classes("text-xs text-red-600 font-mono")
                                        if doc.indexing_error:
                                            ui.label(f"Vector Error: {doc.indexing_error}").classes(
                                                "text-xs text-deep-orange-600 font-mono"
                                            )

                                with ui.row().classes("items-center gap-3"):
                                    with ui.row().classes("items-center gap-1"):
                                        ui.icon("layers", size="xs").classes("text-gray-400")
                                        ui.label(f"{doc.chunk_count} chunk(s)").classes(
                                            "text-xs font-mono text-gray-600"
                                        )

                                    render_status_badge(doc.status)
                                    render_indexing_status_badge(doc.indexing_status)

                                    # Admin index / retry vector indexing action
                                    if is_admin and doc.status == "COMPLETED":
                                        if doc.indexing_status in ("PENDING", "FAILED"):

                                            def trigger_index(
                                                target_id=doc.id, target_name=doc.filename
                                            ) -> None:
                                                try:
                                                    api_client.index_document(
                                                        active_kb.id, target_id
                                                    )
                                                    ui.notify(
                                                        f"Vector indexing started for '{target_name}'.",
                                                        type="positive",
                                                    )
                                                    refresh_doc_list()
                                                except ValueError as err:
                                                    ui.notify(str(err), type="negative")

                                            btn_label = (
                                                "Index"
                                                if doc.indexing_status == "PENDING"
                                                else "Retry Index"
                                            )
                                            ui.button(
                                                btn_label,
                                                icon="scatter_plot",
                                                on_click=trigger_index,
                                            ).props("flat dense color=primary").classes("text-xs")

                                    def show_ingestion_progress(target_doc=doc) -> None:
                                        with (
                                            ui.dialog() as dlg,
                                            ui.card().classes("w-full max-w-lg p-6"),
                                        ):
                                            ui.label(
                                                "Document & Vector Pipeline Lifecycle"
                                            ).classes("text-lg font-bold text-gray-900 mb-1")
                                            ui.label(f"Document: {target_doc.filename}").classes(
                                                "text-xs text-gray-500 mb-4"
                                            )

                                            is_completed = target_doc.status == "COMPLETED"
                                            is_vector_indexed = (
                                                target_doc.indexing_status == "COMPLETED"
                                            )
                                            stages = [
                                                (
                                                    "1. Ingestion & Validation",
                                                    "File validated against supported format allowlist and magic bytes.",
                                                    True,
                                                ),
                                                (
                                                    "2. Parsing & Normalization",
                                                    "Extracted structural headings, pages, and normalized text.",
                                                    is_completed
                                                    or target_doc.status == "PROCESSING",
                                                ),
                                                (
                                                    "3. Semantic Chunking",
                                                    f"Partitioned into {target_doc.chunk_count} token-bounded chunks.",
                                                    is_completed,
                                                ),
                                                (
                                                    "4. Vector Embeddings (1024-d)",
                                                    "Generated 1024-dim vectors via qwen3-embedding:0.6b stored in pgvector.",
                                                    is_vector_indexed,
                                                ),
                                                (
                                                    "5. Retrieval & Hybrid Search (Planned)",
                                                    "Exact cosine similarity & hybrid BM25 fusion (Step 7).",
                                                    False,
                                                ),
                                            ]
                                            for stage_title, stage_desc, is_done in stages:
                                                with ui.row().classes("items-start gap-2 mb-2"):
                                                    ui.icon(
                                                        "check_circle" if is_done else "pending",
                                                        size="xs",
                                                    ).classes(
                                                        "text-green-600"
                                                        if is_done
                                                        else "text-gray-400"
                                                    )
                                                    with ui.column().classes("gap-0"):
                                                        ui.label(stage_title).classes(
                                                            "text-xs font-bold text-gray-800"
                                                        )
                                                        ui.label(stage_desc).classes(
                                                            "text-xs text-gray-500"
                                                        )

                                            with ui.row().classes("w-full justify-end mt-4"):
                                                ui.button("Close", on_click=dlg.close).props("flat")
                                        dlg.open()

                                    ui.button(
                                        "Details",
                                        icon="info",
                                        on_click=show_ingestion_progress,
                                    ).props("flat dense").classes("text-xs text-blue-600")

                                    # Admin delete action
                                    if is_admin:

                                        def delete_this_doc(
                                            target_id=doc.id, target_name=doc.filename
                                        ) -> None:
                                            try:
                                                api_client.delete_document(active_kb.id, target_id)
                                                ui.notify(
                                                    f"Deleted '{target_name}'.", type="positive"
                                                )
                                                refresh_doc_list()
                                            except ValueError as err:
                                                ui.notify(str(err), type="negative")

                                        ui.button(
                                            icon="delete",
                                            on_click=delete_this_doc,
                                        ).props("flat dense color=red").classes("text-xs")

            # Initial render
            render_doc_list()
