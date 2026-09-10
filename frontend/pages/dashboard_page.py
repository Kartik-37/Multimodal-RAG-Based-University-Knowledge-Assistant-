"""
Dashboard Presentation Page.

Provides an executive summary of user knowledge bases, documents,
active context, and quick navigation shortcuts.
"""

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.components.layout import page_layout
from frontend.state.app_state import state


def register_dashboard_page() -> None:
    """Register /dashboard and index / routes with NiceGUI."""

    @ui.page("/")
    def index_route() -> None:
        """Route entry point: redirect to dashboard if authenticated, else login."""
        if state.current_user is not None:
            ui.navigate.to("/dashboard")
        else:
            ui.navigate.to("/login")

    @ui.page("/dashboard")
    def dashboard_page() -> None:
        with page_layout(
            title="Overview & Activity",
            subtitle="Central dashboard for your knowledge bases, documents, and query assistant.",
            active_route="/dashboard",
        ):
            kbs = api_client.get_knowledge_bases()
            active_kb = state.active_kb
            docs = api_client.get_documents(active_kb.id) if active_kb else []

            # Metric Summary Cards
            with ui.row().classes("w-full gap-4"):
                # Total Knowledge Bases
                with ui.card().classes("flex-1 p-4 border border-gray-200 bg-white rounded shadow-sm"):
                    with ui.row().classes("items-center justify-between"):
                        ui.label("Knowledge Bases").classes("text-xs font-semibold text-gray-500 uppercase")
                        ui.icon("folder", size="sm").classes("text-blue-500")
                    ui.label(str(len(kbs))).classes("text-3xl font-bold text-gray-900 mt-2")
                    ui.label("Isolated corpora available").classes("text-xs text-gray-400 mt-1")

                # Active Knowledge Base
                with ui.card().classes("flex-1 p-4 border border-gray-200 bg-white rounded shadow-sm"):
                    with ui.row().classes("items-center justify-between"):
                        ui.label("Active Knowledge Base").classes("text-xs font-semibold text-gray-500 uppercase")
                        ui.icon("radio_button_checked", size="sm").classes("text-green-500")
                    ui.label(active_kb.name if active_kb else "None Selected").classes(
                        "text-lg font-bold text-gray-900 mt-2 truncate"
                    )
                    ui.label(f"{len(docs)} documents loaded" if active_kb else "Select or create a KB").classes(
                        "text-xs text-gray-400 mt-1"
                    )

                # Total Documents
                total_docs = sum(len(api_client.get_documents(k.id)) for k in kbs)
                with ui.card().classes("flex-1 p-4 border border-gray-200 bg-white rounded shadow-sm"):
                    with ui.row().classes("items-center justify-between"):
                        ui.label("Total Documents").classes("text-xs font-semibold text-gray-500 uppercase")
                        ui.icon("description", size="sm").classes("text-purple-500")
                    ui.label(str(total_docs)).classes("text-3xl font-bold text-gray-900 mt-2")
                    ui.label("Ready for semantic search").classes("text-xs text-gray-400 mt-1")

            # Quick Actions Row
            with ui.row().classes("w-full gap-4 mt-2"):
                with ui.card().classes(
                    "flex-1 p-5 border border-blue-100 bg-blue-50 rounded hover:shadow-md transition-shadow"
                ):
                    ui.icon("chat", size="md").classes("text-blue-600 mb-2")
                    ui.label("Ask & Chat").classes("text-base font-bold text-gray-900")
                    ui.label("Query the active knowledge base with conversational RAG and inspect citations.").classes(
                        "text-xs text-gray-600 mb-4"
                    )
                    ui.button("Start Conversation", icon="arrow_forward", on_click=lambda: ui.navigate.to("/chat")).props(
                        "dense color=primary"
                    )

                with ui.card().classes(
                    "flex-1 p-5 border border-purple-100 bg-purple-50 rounded hover:shadow-md transition-shadow"
                ):
                    ui.icon("upload_file", size="md").classes("text-purple-600 mb-2")
                    ui.label("Upload Documents").classes("text-base font-bold text-gray-900")
                    ui.label("Add PDF, Word, Markdown, CSV, or text files to expand knowledge context.").classes(
                        "text-xs text-gray-600 mb-4"
                    )
                    ui.button(
                        "Manage Documents",
                        icon="arrow_forward",
                        on_click=lambda: ui.navigate.to("/documents"),
                    ).props("dense color=secondary")

            # Active KB Document Table Preview
            with ui.card().classes("w-full p-5 border border-gray-200 bg-white rounded shadow-sm mt-2"):
                with ui.row().classes("w-full justify-between items-center mb-4"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("table_chart", size="sm").classes("text-gray-600")
                        ui.label(f"Documents in '{active_kb.name if active_kb else 'Active KB'}'").classes(
                            "text-md font-bold text-gray-800"
                        )
                    ui.button(
                        "View All Documents",
                        icon="arrow_forward",
                        on_click=lambda: ui.navigate.to("/documents"),
                    ).props("flat dense").classes("text-xs text-blue-600")

                if not docs:
                    with ui.column().classes("w-full py-8 items-center justify-center text-center"):
                        ui.icon("folder_open", size="lg").classes("text-gray-300 mb-2")
                        ui.label("No documents in this knowledge base yet.").classes("text-sm text-gray-500")
                        ui.label("Upload PDF, DOCX, TXT, CSV, or MD files to get started.").classes(
                            "text-xs text-gray-400 mb-3"
                        )
                        ui.button(
                            "Upload Document",
                            icon="upload",
                            on_click=lambda: ui.navigate.to("/documents"),
                        ).props("dense color=primary")
                else:
                    columns = [
                        {"name": "filename", "label": "Filename", "field": "filename", "align": "left"},
                        {"name": "file_type", "label": "Format", "field": "file_type", "align": "center"},
                        {"name": "status", "label": "Status", "field": "status", "align": "center"},
                        {"name": "chunk_count", "label": "Chunks", "field": "chunk_count", "align": "right"},
                        {"name": "created_at", "label": "Ingested", "field": "created_at", "align": "right"},
                    ]
                    rows = [
                        {
                            "filename": d.filename,
                            "file_type": d.file_type.upper(),
                            "status": d.status,
                            "chunk_count": d.chunk_count,
                            "created_at": d.created_at,
                        }
                        for d in docs
                    ]
                    ui.table(columns=columns, rows=rows, row_key="filename").classes("w-full").props("dense flat")
