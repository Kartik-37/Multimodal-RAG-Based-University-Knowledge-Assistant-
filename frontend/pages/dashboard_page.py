"""
Dashboard Presentation Page with Role-Tailored Perspectives.

Provides distinct experiences:
- STUDENT: Direct inquiry entry point, course overview cards, grounded search access.
- ADMIN: Course management, document lifecycle stats, system indexing shortcuts, administrator access.
Strictly avoids N+1 API calls.
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
        user = state.current_user
        is_admin = bool(user and user.role == "ADMIN")

        page_title = (
            "Administrator Dashboard"
            if is_admin
            else f"Welcome, {user.full_name if user else 'Student'}"
        )
        page_subtitle = (
            "Central administration for courses, document lifecycle, and retrieval configuration."
            if is_admin
            else "University Knowledge Assistant — search course materials with verified citations."
        )

        with page_layout(
            title=page_title,
            subtitle=page_subtitle,
            active_route="/dashboard",
            require_auth=True,
        ):
            kbs = api_client.get_knowledge_bases() if user else []

            # ------------------------------------------------------------------
            # STUDENT PERSPECTIVE
            # ------------------------------------------------------------------
            if not is_admin:
                # 1. Primary Ask Hero Card
                with ui.card().classes(
                    "w-full p-6 bg-gradient-to-r from-blue-900 to-indigo-900 text-white rounded-xl shadow-sm gap-3"
                ):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("school", size="md").classes("text-blue-300")
                        ui.label("Ask the University Assistant").classes(
                            "text-xl font-bold tracking-tight text-white"
                        )
                    ui.label(
                        "Search across all your enrolled course syllabi, lecture notes, and reference materials. "
                        "Answers are strictly grounded in course documents with source page citations."
                    ).classes("text-sm text-blue-100 max-w-2xl leading-relaxed")

                    with ui.row().classes("gap-3 mt-2"):
                        ui.button(
                            "Ask a Question",
                            icon="chat",
                            on_click=lambda: ui.navigate.to("/chat"),
                        ).props("color=primary").classes(
                            "px-5 py-2.5 text-sm font-semibold bg-blue-600 hover:bg-blue-500"
                        )
                        ui.button(
                            "Browse Courses",
                            icon="menu_book",
                            on_click=lambda: ui.navigate.to("/knowledge-bases"),
                        ).props("outline text-color=white").classes(
                            "px-4 py-2 text-sm font-medium border-blue-400 hover:bg-blue-800/40"
                        )

                # 2. Enrolled Courses Section
                with ui.column().classes("w-full gap-3 mt-4"):
                    with ui.row().classes("items-center justify-between w-full"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("library_books", size="sm").classes("text-blue-600")
                            ui.label("Available Courses & Subjects").classes(
                                "text-base font-bold text-slate-800"
                            )
                        ui.label(f"{len(kbs)} course(s) enrolled").classes("text-xs text-slate-500")

                    if not kbs:
                        render_empty_state(
                            icon="school",
                            title="No Courses Enrolled Yet",
                            description="You are not currently enrolled in any courses with uploaded materials.",
                        )
                    else:
                        with ui.row().classes("w-full gap-4 flex-wrap"):
                            for kb in kbs:
                                with ui.card().classes(
                                    "flex-1 min-w-[280px] p-4 bg-white border border-slate-200 rounded-lg shadow-xs hover:border-blue-300 transition-all gap-2"
                                ):
                                    with ui.row().classes("items-center justify-between w-full"):
                                        ui.label(kb.name).classes(
                                            "text-sm font-bold text-slate-900 truncate"
                                        )
                                        ui.icon("book", size="xs").classes("text-slate-400")
                                    ui.label(
                                        kb.description
                                        or "Official course materials, syllabus, and lecture notes."
                                    ).classes("text-xs text-slate-600 line-clamp-2 leading-relaxed")

                                    def make_ask_course_handler(course=kb):
                                        def handler():
                                            state.active_kb = course
                                            ui.navigate.to("/chat")

                                        return handler

                                    ui.button(
                                        "Ask about this course",
                                        icon="chat_bubble_outline",
                                        on_click=make_ask_course_handler(),
                                    ).props("flat dense no-caps text-color=primary").classes(
                                        "text-xs font-semibold self-start mt-1 p-0"
                                    )
                return

            # ------------------------------------------------------------------
            # ADMINISTRATOR PERSPECTIVE
            # ------------------------------------------------------------------
            active_kb = state.active_kb
            docs = api_client.get_documents(active_kb.id) if active_kb else []

            # 1. Admin Stat Cards
            with ui.row().classes("w-full gap-4"):
                render_stat_card(
                    title="Courses / Knowledge Bases",
                    value=len(kbs),
                    subtitle="Managed university corpora",
                    icon="folder",
                    icon_color="blue-600",
                )

                render_stat_card(
                    title="Active Course Scope",
                    value=active_kb.name if active_kb else "None Selected",
                    subtitle=f"{len(docs)} document(s) in active scope"
                    if active_kb
                    else "Select a course to inspect",
                    icon="radio_button_checked",
                    icon_color="emerald-600",
                )

                render_stat_card(
                    title="Active Scope Documents",
                    value=len(docs) if active_kb else 0,
                    subtitle="Eligible for semantic & lexical retrieval"
                    if active_kb
                    else "No active scope selected",
                    icon="description",
                    icon_color="indigo-600",
                )

            # 2. Admin Action Cards
            with ui.row().classes("w-full gap-4 mt-1"):
                # Course Management
                with ui.card().classes(
                    "flex-1 min-w-[240px] p-4 bg-white border border-slate-200 rounded-lg shadow-xs hover:border-blue-300 transition-colors"
                ):
                    with ui.row().classes("items-center gap-2 mb-1"):
                        ui.icon("menu_book", size="sm").classes("text-blue-600")
                        ui.label("Courses").classes("text-sm font-bold text-slate-900")
                    ui.label("Create new courses and manage student enrollment access.").classes(
                        "text-xs text-slate-600 mb-3"
                    )
                    ui.button(
                        "Manage Courses",
                        icon="arrow_forward",
                        on_click=lambda: ui.navigate.to("/knowledge-bases"),
                    ).props("color=primary no-caps dense").classes(
                        "text-xs font-medium px-3 py-1.5"
                    )

                # Document Management
                with ui.card().classes(
                    "flex-1 min-w-[240px] p-4 bg-white border border-slate-200 rounded-lg shadow-xs hover:border-emerald-300 transition-colors"
                ):
                    with ui.row().classes("items-center gap-2 mb-1"):
                        ui.icon("upload_file", size="sm").classes("text-emerald-600")
                        ui.label("Documents").classes("text-sm font-bold text-slate-900")
                    ui.label(
                        "Upload syllabi, activate new versions, or deactivate historical material."
                    ).classes("text-xs text-slate-600 mb-3")
                    ui.button(
                        "Manage Documents",
                        icon="arrow_forward",
                        on_click=lambda: ui.navigate.to("/documents"),
                    ).props("color=positive no-caps dense").classes(
                        "text-xs font-medium px-3 py-1.5"
                    )

                # Administrator Management
                with ui.card().classes(
                    "flex-1 min-w-[240px] p-4 bg-white border border-slate-200 rounded-lg shadow-xs hover:border-purple-300 transition-colors"
                ):
                    with ui.row().classes("items-center gap-2 mb-1"):
                        ui.icon("admin_panel_settings", size="sm").classes("text-purple-600")
                        ui.label("Administrators").classes("text-sm font-bold text-slate-900")
                    ui.label(
                        "Provision new faculty administrators and audit active admin accounts."
                    ).classes("text-xs text-slate-600 mb-3")
                    ui.button(
                        "Manage Admins",
                        icon="arrow_forward",
                        on_click=lambda: ui.navigate.to("/administrators"),
                    ).props("outline color=purple no-caps dense").classes(
                        "text-xs font-medium px-3 py-1.5"
                    )

            # 3. Active Corpus Document Table Preview
            with ui.card().classes(
                "w-full p-5 bg-white border border-slate-200 rounded-lg shadow-xs mt-2"
            ):
                with ui.row().classes(
                    "w-full justify-between items-center mb-3 pb-2 border-b border-slate-100"
                ):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("table_chart", size="sm").classes("text-slate-600")
                        ui.label(
                            f"Documents in '{active_kb.name if active_kb else 'Active Scope'}'"
                        ).classes("text-sm font-bold text-slate-800")
                    ui.button(
                        "Manage Documents",
                        icon="arrow_forward",
                        on_click=lambda: ui.navigate.to("/documents"),
                    ).props("flat dense no-caps").classes("text-xs text-blue-600")

                if not active_kb:
                    render_empty_state(
                        icon="folder_off",
                        title="No Course Selected",
                        description="Select a course to inspect documents and vector indexing status.",
                        action_label="Select Course",
                        on_action=lambda: ui.navigate.to("/knowledge-bases"),
                    )
                elif not docs:
                    render_empty_state(
                        icon="description",
                        title="No Documents Uploaded",
                        description="This course does not contain any uploaded documents yet.",
                        action_label="Upload Document",
                        on_action=lambda: ui.navigate.to("/documents"),
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
                                    ui.element("th").classes("py-2.5 px-3").text = "Version State"
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
                                        with ui.element("td").classes("py-2.5 px-3"):
                                            if doc.is_active:
                                                ui.badge("ACTIVE", color="emerald-700").classes(
                                                    "text-[10px] font-bold"
                                                )
                                            else:
                                                ui.badge("INACTIVE", color="slate-500").classes(
                                                    "text-[10px] font-bold"
                                                )
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
