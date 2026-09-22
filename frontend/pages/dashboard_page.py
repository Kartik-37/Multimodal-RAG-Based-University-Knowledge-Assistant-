"""
Dashboard Presentation Page with Role-Tailored Metrics.

Displays summary metrics and quick-action navigation for university knowledge bases.
Strictly avoids N+1 API calls by deriving document metrics from the active corpus alone.
Provides distinct perspectives for Administrators versus Students.
"""

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.components.layout import page_layout
from frontend.components.status_badge import render_indexing_status_badge, render_status_badge
from frontend.components.ui_kit import render_empty_state, render_stat_card
from frontend.state.app_state import state


def register_dashboard_page() -> None:
    """Register /dashboard and index / routes with NiceGUI."""

    @ui.page("/")
    def index_route() -> None:
        """Entry point redirecting to dashboard if authenticated, else login."""
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
            require_auth=True,
        ):
            user = state.current_user
            is_admin = bool(user and user.role == "ADMIN")

            # Fetch accessible KBs (single authorized call)
            kbs = api_client.get_knowledge_bases()
            active_kb = state.active_kb

            # Single call for active KB documents (strictly avoids N+1 calls across all KBs)
            docs = api_client.get_documents(active_kb.id) if active_kb else []

            # ------------------------------------------------------------------
            # 1. Metric Summary Cards
            # ------------------------------------------------------------------
            with ui.row().classes("w-full gap-4"):
                render_stat_card(
                    title="Knowledge Bases",
                    value=len(kbs),
                    subtitle="Authorized corpora available",
                    icon="folder",
                    icon_color="blue-600",
                )

                render_stat_card(
                    title="Active Knowledge Base",
                    value=active_kb.name if active_kb else "None Selected",
                    subtitle=f"{len(docs)} document(s) in active corpus"
                    if active_kb
                    else "Select an active corpus",
                    icon="radio_button_checked",
                    icon_color="emerald-600",
                )

                render_stat_card(
                    title="Active Corpus Documents",
                    value=len(docs) if active_kb else 0,
                    subtitle="Ready for semantic & lexical retrieval"
                    if active_kb
                    else "No active corpus selected",
                    icon="description",
                    icon_color="indigo-600",
                )

            # ------------------------------------------------------------------
            # 2. Role-Tailored Action Shortcuts
            # ------------------------------------------------------------------
            with ui.row().classes("w-full gap-4 mt-1"):
                # Chat & Ask Card (All Users)
                with ui.card().classes(
                    "flex-1 min-w-[280px] p-5 bg-white border border-blue-100 rounded-lg shadow-xs hover:border-blue-300 transition-colors"
                ):
                    with ui.row().classes("items-center gap-2 mb-1.5"):
                        ui.icon("chat", size="sm").classes("text-blue-600")
                        ui.label("Ask & Chat").classes("text-base font-bold text-slate-900")
                    ui.label(
                        "Query active documents with dense vector + lexical retrieval, reranking, and verified source citations."
                    ).classes("text-xs text-slate-600 mb-4 leading-relaxed")
                    ui.button(
                        "Open Chat & Search",
                        icon="arrow_forward",
                        on_click=lambda: ui.navigate.to("/chat"),
                    ).props("color=primary no-caps dense").classes(
                        "text-xs font-medium px-3 py-1.5"
                    )

                # Knowledge Bases Card (All Users)
                with ui.card().classes(
                    "flex-1 min-w-[280px] p-5 bg-white border border-slate-200 rounded-lg shadow-xs hover:border-slate-300 transition-colors"
                ):
                    with ui.row().classes("items-center gap-2 mb-1.5"):
                        ui.icon("menu_book", size="sm").classes("text-indigo-600")
                        ui.label("Knowledge Bases").classes("text-base font-bold text-slate-900")
                    ui.label(
                        "Switch active corpus or review accessible subject collections."
                    ).classes("text-xs text-slate-600 mb-4 leading-relaxed")
                    ui.button(
                        "Browse Knowledge Bases",
                        icon="arrow_forward",
                        on_click=lambda: ui.navigate.to("/knowledge-bases"),
                    ).props("outline color=primary no-caps dense").classes(
                        "text-xs font-medium px-3 py-1.5"
                    )

                # Document Management (Administrators Only)
                if is_admin:
                    with ui.card().classes(
                        "flex-1 min-w-[280px] p-5 bg-white border border-emerald-100 rounded-lg shadow-xs hover:border-emerald-300 transition-colors"
                    ):
                        with ui.row().classes("items-center gap-2 mb-1.5"):
                            ui.icon("upload_file", size="sm").classes("text-emerald-600")
                            ui.label("Manage Documents").classes(
                                "text-base font-bold text-slate-900"
                            )
                        ui.label(
                            "Upload course syllabi, lecture notes, or textbooks (PDF, DOCX, TXT, MD, CSV) for automated ingestion."
                        ).classes("text-xs text-slate-600 mb-4 leading-relaxed")
                        ui.button(
                            "Upload & Index",
                            icon="arrow_forward",
                            on_click=lambda: ui.navigate.to("/documents"),
                        ).props("color=positive no-caps dense").classes(
                            "text-xs font-medium px-3 py-1.5"
                        )

            # ------------------------------------------------------------------
            # 3. Active Corpus Document Table Preview
            # ------------------------------------------------------------------
            with ui.card().classes(
                "w-full p-5 bg-white border border-slate-200 rounded-lg shadow-xs mt-2"
            ):
                with ui.row().classes(
                    "w-full justify-between items-center mb-3 pb-2 border-b border-slate-100"
                ):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("table_chart", size="sm").classes("text-slate-600")
                        ui.label(
                            f"Documents in '{active_kb.name if active_kb else 'Active Corpus'}'"
                        ).classes("text-sm font-bold text-slate-800")
                    if is_admin:
                        ui.button(
                            "Manage Documents",
                            icon="arrow_forward",
                            on_click=lambda: ui.navigate.to("/documents"),
                        ).props("flat dense no-caps").classes("text-xs text-blue-600")

                if not active_kb:
                    render_empty_state(
                        icon="folder_off",
                        title="No Knowledge Base Selected",
                        description="Select or create a knowledge base to inspect documents and query context.",
                        action_label="Select Knowledge Base",
                        on_action=lambda: ui.navigate.to("/knowledge-bases"),
                    )
                elif not docs:
                    render_empty_state(
                        icon="description",
                        title="Corpus is Empty",
                        description="This knowledge base does not contain any ingested documents yet.",
                        action_label="Upload Document" if is_admin else "Ask an Admin to Upload",
                        on_action=(lambda: ui.navigate.to("/documents")) if is_admin else None,
                    )
                else:
                    with ui.element("div").classes("responsive-table-wrapper"):
                        with ui.element("table").classes(
                            "w-full text-left text-xs border-collapse"
                        ):
                            with ui.element("thead").classes(
                                "bg-slate-50 text-slate-600 uppercase font-semibold border-b border-slate-200"
                            ):
                                with ui.element("tr"):
                                    ui.element("th").classes("py-2.5 px-3").text = "Filename"
                                    ui.element("th").classes("py-2.5 px-3").text = "Format"
                                    ui.element("th").classes(
                                        "py-2.5 px-3"
                                    ).text = "Ingestion Status"
                                    ui.element("th").classes("py-2.5 px-3").text = "Vectors"
                                    ui.element("th").classes("py-2.5 px-3").text = "Chunks"

                            with ui.element("tbody").classes(
                                "divide-y divide-slate-100 text-slate-800"
                            ):
                                for doc in docs[:10]:
                                    with ui.element("tr").classes(
                                        "hover:bg-slate-50 transition-colors"
                                    ):
                                        ui.element("td").classes(
                                            "py-2.5 px-3 font-medium truncate max-w-[220px]"
                                        ).text = doc.filename
                                        with ui.element("td").classes("py-2.5 px-3 font-mono"):
                                            ui.badge(
                                                doc.file_type.upper(), color="slate-500"
                                            ).classes("text-[10px]")
                                        with ui.element("td").classes("py-2.5 px-3"):
                                            render_status_badge(doc.status)
                                        with ui.element("td").classes("py-2.5 px-3"):
                                            render_indexing_status_badge(doc.indexing_status)
                                        ui.element("td").classes(
                                            "py-2.5 px-3 font-mono"
                                        ).text = str(doc.chunk_count)
