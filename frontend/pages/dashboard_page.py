"""
Dashboard Presentation Page with Role-Tailored Perspectives.

Provides distinct experiences:
- STUDENT: Direct inquiry entry point, enrolled course cards, and grounded Q&A access.
  Strictly membership-based: students see only courses they are enrolled in.
- ADMIN: University Knowledge Management with courses, document lifecycle, and indexing overview.
Strictly avoids N+1 API calls and uses no obsolete active-corpus concepts.
"""

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.components.layout import page_layout
from frontend.components.ui_kit import render_alert, render_empty_state, render_stat_card
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
            "University Knowledge Management"
            if is_admin
            else f"Welcome, {user.full_name if user else 'Student'}"
        )
        page_subtitle = (
            "Manage courses, learning materials, vector indexing, and administrative operations."
            if is_admin
            else "Access your enrolled course materials and ask questions with verified source citations."
        )

        with page_layout(
            title=page_title,
            subtitle=page_subtitle,
            active_route="/dashboard",
            require_auth=True,
        ):
            # ------------------------------------------------------------------
            # STUDENT PERSPECTIVE
            # ------------------------------------------------------------------
            if not is_admin:
                course_load_error = False
                enrolled_kbs = []
                try:
                    # Strictly membership-based access: fetch assigned knowledge bases
                    enrolled_kbs = api_client.get_knowledge_bases() if user else []
                except ValueError as err:
                    course_load_error = True
                    render_alert(f"Unable to load assigned courses. {err}", "negative")

                # 1. Quick Inquiry Input Box
                with ui.card().classes(
                    "w-full p-6 sm:p-7 bg-white border border-slate-200 rounded-xl shadow-xs gap-3 box-border"
                ):
                    with ui.row().classes("items-center justify-between w-full flex-wrap gap-2"):
                        with ui.row().classes("items-center gap-2"):
                            with ui.element("div").classes(
                                "w-8 h-8 rounded-lg bg-blue-50 text-blue-700 flex items-center justify-center font-bold"
                            ):
                                ui.icon("chat", size="18px")
                            ui.label("Ask Course Assistant").classes(
                                "text-base font-bold text-slate-900 tracking-tight"
                            )
                        ui.badge("Source Grounded", color="blue-1").props("text-color=blue-9").classes(
                            "text-[10px] font-bold px-2 py-0.5 border border-blue-200"
                        )

                    ui.label(
                        "Inquire across your enrolled course materials, syllabi, and official regulations. "
                        "Answers are synthesized strictly from verified documents with page citations."
                    ).classes("text-xs sm:text-sm text-slate-600 leading-relaxed")

                    def handle_quick_ask() -> None:
                        q = (ask_input.value or "").strip()
                        if q:
                            ui.navigate.to(f"/chat?q={ui.run_javascript('encodeURIComponent')}")
                            # Use query string navigation
                            import urllib.parse
                            ui.navigate.to(f"/chat?q={urllib.parse.quote(q)}")
                        else:
                            ui.navigate.to("/chat")

                    with ui.row().classes("w-full gap-2 items-center mt-1"):
                        ask_input = (
                            ui.input(
                                placeholder="Type a question (e.g. 'What is pipelining in Computer Architecture?')...",
                            )
                            .props("outlined dense")
                            .classes("flex-1 text-sm minimalist-input")
                        )
                        ask_input.on("keydown.enter", handle_quick_ask)

                        ui.button(
                            "Ask Assistant",
                            icon="arrow_forward",
                            on_click=handle_quick_ask,
                        ).props("no-caps").classes(
                            "px-4 py-2 font-medium text-sm rounded-lg !bg-blue-700 hover:!bg-blue-800 !text-white shadow-xs transition-colors"
                        )

                # 2. Enrolled Courses Section
                with ui.column().classes("w-full gap-4 mt-2"):
                    with ui.row().classes("items-center justify-between w-full flex-wrap gap-2"):
                        with ui.row().classes("items-center gap-2"):
                            with ui.element("div").classes(
                                "w-7 h-7 rounded-lg bg-slate-100 text-slate-700 flex items-center justify-center font-bold"
                            ):
                                ui.icon("school", size="16px")
                            ui.label("Enrolled Courses").classes(
                                "text-base font-bold text-slate-900 tracking-tight"
                            )
                            ui.label(
                                f"({len(enrolled_kbs)} assigned)"
                                if not course_load_error
                                else ""
                            ).classes("text-xs text-slate-500 font-mono")

                        if enrolled_kbs and len(enrolled_kbs) > 3:
                            search_input = (
                                ui.input(placeholder="Filter courses...")
                                .props("outlined dense clearable")
                                .classes("w-60 text-xs minimalist-input")
                            )

                    # Courses Cards Container
                    courses_container = ui.element("div").classes(
                        "w-full grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
                    )

                    def render_enrolled_cards(query_text: str = "") -> None:
                        courses_container.clear()
                        clean_q = (query_text or "").strip().lower()
                        filtered = (
                            [
                                k
                                for k in enrolled_kbs
                                if clean_q in k.name.lower()
                                or clean_q in (k.description or "").lower()
                            ]
                            if clean_q
                            else enrolled_kbs
                        )

                        with courses_container:
                            if not filtered and not course_load_error:
                                with ui.column().classes("col-span-full w-full"):
                                    render_empty_state(
                                        icon="search_off" if clean_q else "school",
                                        title=(
                                            "No Matching Courses"
                                            if clean_q
                                            else "No Assigned Courses"
                                        ),
                                        description=(
                                            f"No assigned course matches '{clean_q}'."
                                            if clean_q
                                            else "You are not currently assigned to any university courses. "
                                            "Your faculty instructor or administrator must enroll you in course materials."
                                        ),
                                    )
                            elif filtered:
                                for kb in filtered:
                                    with ui.card().classes(
                                        "academic-card p-5 bg-white border border-slate-200 rounded-xl shadow-xs flex flex-col justify-between"
                                    ):
                                        with ui.column().classes("gap-2 w-full"):
                                            with ui.row().classes("items-center justify-between w-full"):
                                                ui.label(kb.name).classes(
                                                    "text-sm font-bold text-slate-900 tracking-tight truncate flex-1"
                                                )
                                                ui.badge(
                                                    f"{kb.document_count} doc(s)",
                                                    color="slate-1",
                                                ).props("text-color=slate-7").classes(
                                                    "text-[10px] font-mono font-semibold px-1.5 py-0.5 border border-slate-200 shrink-0"
                                                )

                                            ui.label(
                                                kb.description
                                                or "Official learning modules, syllabi, and reference documents."
                                            ).classes(
                                                "text-xs text-slate-600 line-clamp-2 leading-relaxed"
                                            )

                                        with ui.row().classes(
                                            "w-full justify-between items-center pt-3 border-t border-slate-100 mt-3"
                                        ):
                                            ui.button(
                                                "Ask Questions",
                                                icon="chat",
                                                on_click=lambda c_id=kb.id: ui.navigate.to(
                                                    f"/chat?kb_id={c_id}"
                                                ),
                                            ).props("no-caps dense").classes(
                                                "text-xs font-medium px-3 py-1.5 !bg-blue-700 hover:!bg-blue-800 !text-white rounded-lg shadow-xs transition-colors"
                                            )
                                            ui.button(
                                                "View Materials",
                                                icon="menu_book",
                                                on_click=lambda: ui.navigate.to("/knowledge-bases"),
                                            ).props("flat dense no-caps").classes(
                                                "text-xs text-slate-600 hover:text-slate-900 px-2 py-1"
                                            )

                    if enrolled_kbs and len(enrolled_kbs) > 3:
                        search_input.on_value_change(lambda e: render_enrolled_cards(e.value))

                    render_enrolled_cards()
                return

            # ------------------------------------------------------------------
            # ADMINISTRATOR PERSPECTIVE
            # ------------------------------------------------------------------
            def user_can(perm: str) -> bool:
                if not user or user.role != "ADMIN":
                    return False
                if user.admin_role == "MAIN_ADMIN":
                    return True
                return perm in (user.permissions or [])

            try:
                course_summaries = api_client.get_course_summaries()
            except ValueError as err:
                render_alert(f"Unable to load course data. {err}", "negative")
                course_summaries = []

            try:
                indexing_jobs = api_client.get_indexing_jobs()
            except Exception:
                indexing_jobs = []

            total_courses = len(course_summaries)
            total_documents = sum(c.total_documents for c in course_summaries)
            active_documents = sum(c.active_documents for c in course_summaries)
            total_indexed = sum(c.indexed_documents for c in course_summaries)
            total_indexing = sum(c.indexing_documents for c in course_summaries)
            total_failed = sum(c.failed_documents for c in course_summaries)

            active_jobs = [
                j
                for j in indexing_jobs
                if j.status
                in (
                    "PROCESSING",
                    "STARTING",
                    "PARSING",
                    "CHUNKING",
                    "EMBEDDING",
                    "INDEXING",
                    "VERIFYING",
                )
            ]

            # 1. 4 Key Operational Metric Cards
            with ui.row().classes("w-full gap-4"):
                render_stat_card(
                    title="Courses",
                    value=total_courses,
                    subtitle=f"{total_courses} registered catalog"
                    if total_courses != 1
                    else "1 registered course",
                    icon="menu_book",
                    icon_color="blue-600",
                )
                render_stat_card(
                    title="Documents",
                    value=total_documents,
                    subtitle=f"{active_documents} active in retrieval",
                    icon="description",
                    icon_color="indigo-600",
                )
                render_stat_card(
                    title="Indexing",
                    value=total_indexing,
                    subtitle=f"{total_indexed} fully indexed"
                    if total_indexing == 0
                    else f"{len(active_jobs)} active worker job(s)",
                    icon="autorenew",
                    icon_color="amber-600" if total_indexing > 0 else "slate-500",
                )
                render_stat_card(
                    title="Failed Jobs",
                    value=total_failed,
                    subtitle="No action required"
                    if total_failed == 0
                    else f"{total_failed} need attention / retry",
                    icon="error_outline",
                    icon_color="rose-600" if total_failed > 0 else "emerald-600",
                )

            # 2. Operational Actions Bar
            with ui.card().classes(
                "academic-card w-full p-4 sm:p-5 bg-white border border-slate-200 rounded-xl shadow-xs"
            ):
                with ui.row().classes("w-full justify-between items-center mb-2.5 pb-2 border-b border-slate-100"):
                    with ui.row().classes("items-center gap-2"):
                        with ui.element("div").classes(
                            "w-7 h-7 rounded-lg bg-slate-100 text-slate-700 flex items-center justify-center font-bold"
                        ):
                            ui.icon("tune", size="16px")
                        ui.label("Operational Actions").classes(
                            "text-sm font-bold text-slate-900"
                        )
                    ui.label("Assigned administrative permissions").classes(
                        "text-xs text-slate-400 font-mono"
                    )

                with ui.row().classes("w-full gap-2.5 flex-wrap items-center"):
                    if user_can("DOCUMENT_UPLOAD"):
                        ui.button(
                            "Upload Document",
                            icon="upload_file",
                            on_click=lambda: ui.navigate.to("/documents"),
                        ).props("no-caps dense").classes(
                            "text-xs font-medium px-3.5 py-2 !bg-blue-700 hover:!bg-blue-800 !text-white rounded-lg shadow-xs transition-colors"
                        )

                    if user_can("COURSE_CREATE"):
                        ui.button(
                            "Create Course",
                            icon="add",
                            on_click=lambda: ui.navigate.to("/knowledge-bases"),
                        ).props("no-caps dense").classes(
                            "text-xs font-medium px-3.5 py-2 !bg-slate-900 hover:!bg-slate-800 !text-white rounded-lg shadow-xs transition-colors"
                        )

                    ui.button(
                        "Indexing Center",
                        icon="hub",
                        on_click=lambda: ui.navigate.to("/indexing"),
                    ).props("no-caps dense outline").classes(
                        "text-xs font-medium px-3.5 py-2 border-slate-300 text-slate-700 hover:bg-slate-50 rounded-lg transition-colors"
                    )

                    if user_can("ADMIN_CHAT") or user.role == "ADMIN":
                        ui.button(
                            "Admin Knowledge Chat",
                            icon="chat",
                            on_click=lambda: ui.navigate.to("/chat"),
                        ).props("no-caps dense outline").classes(
                            "text-xs font-medium px-3.5 py-2 border-blue-200 text-blue-700 hover:bg-blue-50 rounded-lg transition-colors"
                        )

                    ui.button(
                        "System Health",
                        icon="health_and_safety",
                        on_click=lambda: ui.navigate.to("/system-health"),
                    ).props("no-caps dense outline").classes(
                        "text-xs font-medium px-3.5 py-2 border-slate-300 text-slate-600 hover:bg-slate-50 rounded-lg transition-colors"
                    )

            # 3. Course Catalog & Material Breakdown Table
            with ui.card().classes(
                "academic-card w-full p-5 sm:p-6 bg-white border border-slate-200 rounded-xl shadow-xs"
            ):
                with ui.row().classes("w-full justify-between items-center mb-3 pb-2 border-b border-slate-100"):
                    with ui.row().classes("items-center gap-2"):
                        with ui.element("div").classes(
                            "w-7 h-7 rounded-lg bg-blue-50 text-blue-700 flex items-center justify-center font-bold"
                        ):
                            ui.icon("menu_book", size="16px")
                        ui.label("Course Catalog & Documents").classes(
                            "text-sm font-bold text-slate-900"
                        )
                    ui.button(
                        "Manage All Courses",
                        icon="arrow_forward",
                        on_click=lambda: ui.navigate.to("/knowledge-bases"),
                    ).props("flat dense no-caps").classes("text-xs text-blue-700 font-medium")

                if not course_summaries:
                    render_empty_state(
                        icon="menu_book",
                        title="No Courses Registered",
                        description="Create your first academic course knowledge base to start uploading and indexing documents.",
                    )
                else:
                    course_rows = [
                        {
                            "id": c.id,
                            "name": c.name,
                            "total": c.total_documents,
                            "active": c.active_documents,
                            "indexed": c.indexed_documents,
                        }
                        for c in course_summaries
                    ]
                    course_cols = [
                        {
                            "name": "name",
                            "label": "COURSE NAME",
                            "field": "name",
                            "align": "left",
                            "sortable": True,
                        },
                        {
                            "name": "total",
                            "label": "TOTAL MATERIALS",
                            "field": "total",
                            "align": "center",
                            "sortable": True,
                        },
                        {
                            "name": "active",
                            "label": "ACTIVE",
                            "field": "active",
                            "align": "center",
                            "sortable": True,
                        },
                        {
                            "name": "indexed",
                            "label": "INDEXED",
                            "field": "indexed",
                            "align": "center",
                            "sortable": True,
                        },
                        {
                            "name": "actions",
                            "label": "ACTION",
                            "field": "id",
                            "align": "right",
                        },
                    ]
                    table = ui.table(
                        columns=course_cols,
                        rows=course_rows,
                        row_key="id",
                        pagination={"rowsPerPage": 10},
                    ).classes("w-full shadow-none border-0 text-xs")

                    table.add_slot(
                        "body-cell-actions",
                        """
                        <q-td :props="props" class="text-right">
                            <q-btn flat dense no-caps color="primary" label="Manage Documents" icon-right="arrow_forward" size="sm" @click="() => $emit('open_docs', props.value)" />
                        </q-td>
                        """,
                    )
                    table.on(
                        "open_docs",
                        lambda e: ui.navigate.to(f"/documents?kb_id={e.args}"),
                    )
