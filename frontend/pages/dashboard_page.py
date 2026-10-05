"""
Dashboard Presentation Page with Role-Tailored Perspectives.

Provides distinct experiences:
- STUDENT: Direct inquiry entry point, course overview cards, grounded search access.
- ADMIN: University Knowledge Management with courses, document lifecycle, and administrators.
Strictly avoids N+1 API calls and uses no obsolete active-corpus concepts.
"""

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.client.models import KnowledgeBaseDTO
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
            "Manage courses, learning material, document lifecycle, and administrators."
            if is_admin
            else "University Knowledge Assistant — search course materials with verified citations."
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
                kbs = []
                try:
                    kbs = api_client.get_knowledge_bases() if user else []
                    # Even if the 'enrolled' list is empty, fetch and display the full global course catalog
                    if not kbs and user:
                        try:
                            summaries = api_client.get_course_summaries()
                            if summaries:
                                kbs = [
                                    KnowledgeBaseDTO(
                                        id=s.id,
                                        name=s.name,
                                        description=s.description,
                                        document_count=s.total_documents,
                                        created_at=s.created_at,
                                    )
                                    for s in summaries
                                ]
                        except Exception:
                            pass
                except ValueError as err:
                    # Fallback to course catalog summaries on error if available
                    try:
                        summaries = api_client.get_course_summaries() if user else []
                        if summaries:
                            kbs = [
                                KnowledgeBaseDTO(
                                    id=s.id,
                                    name=s.name,
                                    description=s.description,
                                    document_count=s.total_documents,
                                    created_at=s.created_at,
                                )
                                for s in summaries
                            ]
                        else:
                            course_load_error = True
                            render_alert(f"Unable to load your courses. {err}", "negative")
                    except Exception:
                        course_load_error = True
                        render_alert(f"Unable to load your courses. {err}", "negative")

                # 1. Primary Ask Hero Card (Modern Academic High-Contrast Surface)
                with ui.card().classes(
                    "academic-card w-full p-6 sm:p-8 bg-gradient-to-r from-blue-50/80 via-indigo-50/40 to-slate-50 border border-blue-100/90 rounded-2xl shadow-xs gap-3"
                ):
                    with ui.element("div").classes(
                        "inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-100/80 border border-blue-200/90 text-blue-800 text-xs font-semibold tracking-wide w-fit"
                    ):
                        ui.icon("school", size="14px").classes("text-blue-700")
                        ui.label("University Academic Knowledge Assistant")

                    ui.label("Direct Knowledge Retrieval with Source Grounding").classes(
                        "text-xl sm:text-2xl font-bold tracking-tight text-slate-900 font-sans mt-1"
                    )
                    ui.label(
                        "Ask natural language inquiries across syllabi, exam statutes, and lecture notes. "
                        "Answers are strictly grounded in course documents with source page citations."
                    ).classes("text-sm text-slate-600 max-w-2xl leading-relaxed")

                    with ui.row().classes("gap-3 mt-3 flex-wrap items-center"):
                        ui.button(
                            "Ask a Question",
                            icon="chat",
                            on_click=lambda: ui.navigate.to("/chat"),
                        ).props("no-caps").classes(
                            "px-5 py-2.5 text-sm font-semibold !bg-blue-600 hover:!bg-blue-700 !text-white rounded-xl shadow-xs transition-colors"
                        )
                        ui.button(
                            "Browse Course Catalog",
                            icon="menu_book",
                            on_click=lambda: ui.navigate.to("/knowledge-bases"),
                        ).props("outline no-caps").classes(
                            "px-4 py-2.5 text-sm font-medium border border-slate-300 text-slate-700 hover:bg-white rounded-xl transition-colors"
                        )

                # 2. Course Folders & Search Section
                with ui.column().classes("w-full gap-4 mt-6"):
                    with ui.row().classes("items-center justify-between w-full flex-wrap gap-3"):
                        with ui.row().classes("items-center gap-2.5"):
                            with ui.element("div").classes(
                                "w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold"
                            ):
                                ui.icon("folder_special", size="20px")
                            with ui.column().classes("gap-0"):
                                ui.label("Course Folders & Subjects").classes(
                                    "text-base font-bold text-slate-900 tracking-tight font-sans"
                                )
                                count_label = ui.label(
                                    "Unable to load courses"
                                    if course_load_error
                                    else f"{len(kbs)} course folder(s) available"
                                ).classes("text-xs text-slate-500 font-mono")

                        with ui.row().classes("items-center gap-2 flex-wrap"):
                            search_input = (
                                ui.input(
                                    placeholder="Search course folders or subjects...",
                                )
                                .props("outlined dense clearable")
                                .classes("w-64 sm:w-72 text-xs minimalist-input")
                            )
                            ui.button(
                                "Browse Catalog",
                                icon="menu_book",
                                on_click=lambda: ui.navigate.to("/knowledge-bases"),
                            ).props("outline dense no-caps").classes(
                                "text-xs border-slate-300 text-slate-700 hover:bg-slate-50 px-3 py-1.5 rounded-xl transition-colors"
                            )

                    # Dynamic container for filtered course cards
                    courses_container = ui.row().classes("w-full gap-4 flex-wrap")

                    def render_course_cards(query_text: str = "") -> None:
                        courses_container.clear()
                        clean_q = (query_text or "").strip().lower()
                        filtered = (
                            [
                                k
                                for k in kbs
                                if clean_q in k.name.lower()
                                or clean_q in (k.description or "").lower()
                            ]
                            if clean_q
                            else kbs
                        )

                        if not course_load_error:
                            count_label.text = (
                                f"{len(filtered)} of {len(kbs)} course folder(s)"
                                if clean_q
                                else f"{len(kbs)} course folder(s) available"
                            )

                        with courses_container:
                            if not filtered and not course_load_error:
                                render_empty_state(
                                    icon="search_off" if clean_q else "school",
                                    title=(
                                        "No Matching Course Folders"
                                        if clean_q
                                        else "No Course Folders Available"
                                    ),
                                    description=(
                                        f"No course folders match '{clean_q}'. Try a different search term or browse the catalog."
                                        if clean_q
                                        else "There are currently no published course folders available in the university catalog."
                                    ),
                                )
                            elif filtered:
                                for kb in filtered:
                                    with ui.card().classes(
                                        "academic-card modern-course-card flex-1 min-w-[280px] p-5 bg-white border border-slate-200/80 rounded-2xl shadow-xs hover:border-blue-300 hover:shadow-md hover:-translate-y-0.5 transition-all flex flex-col justify-between"
                                    ):
                                        with ui.column().classes("gap-2.5 w-full"):
                                            with ui.row().classes(
                                                "items-center justify-between w-full"
                                            ):
                                                with ui.element("div").classes(
                                                    "w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold"
                                                ):
                                                    ui.icon("folder", size="20px")
                                                with ui.element("div").classes(
                                                    "px-2 py-0.5 rounded-full bg-blue-50 border border-blue-200 text-blue-700 text-[10px] font-mono font-medium"
                                                ):
                                                    ui.label("Course Folder")

                                            ui.label(kb.name).classes(
                                                "text-sm font-bold text-slate-900 tracking-tight font-sans line-clamp-1"
                                            )
                                            ui.label(
                                                kb.description
                                                or "Official course materials, syllabus modules, and lecture notes."
                                            ).classes(
                                                "text-xs text-slate-500 line-clamp-2 leading-relaxed"
                                            )

                                        with ui.row().classes(
                                            "w-full justify-between items-center pt-3 border-t border-slate-100 mt-2"
                                        ):
                                            ui.button(
                                                "Ask Questions",
                                                icon="chat",
                                                on_click=lambda course_id=kb.id: ui.navigate.to(
                                                    f"/chat?kb_id={course_id}"
                                                ),
                                            ).props("no-caps dense").classes(
                                                "text-xs !bg-blue-600 hover:!bg-blue-700 !text-white px-3.5 py-2 rounded-xl shadow-xs transition-colors font-semibold"
                                            )
                                            ui.button(
                                                "View Folder",
                                                icon="folder_open",
                                                on_click=lambda: ui.navigate.to("/knowledge-bases"),
                                            ).props("flat dense no-caps").classes(
                                                "text-xs text-slate-600 hover:text-slate-900 font-medium px-3 py-1.5 rounded-lg"
                                            )

                    # Wire search input to dynamic card filtering
                    search_input.on_value_change(lambda e: render_course_cards(e.value))

                    # Initial render
                    render_course_cards()
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

            try:
                activity_events = api_client.get_activity_log()
            except Exception:
                activity_events = []

            total_courses = len(course_summaries)
            total_documents = sum(c.total_documents for c in course_summaries)
            active_documents = sum(c.active_documents for c in course_summaries)
            total_indexed = sum(c.indexed_documents for c in course_summaries)
            total_indexing = sum(c.indexing_documents for c in course_summaries)
            total_failed = sum(c.failed_documents for c in course_summaries)

            # Active indexing jobs from persistent backend
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

            # 1. Compact Operational Summary Cards
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

            # 2. RBAC-Aware Quick Actions Bar
            with ui.card().classes(
                "academic-card w-full p-5 bg-white border border-slate-200/80 rounded-2xl shadow-xs mt-3"
            ):
                with ui.row().classes(
                    "items-center justify-between w-full mb-3 pb-3 border-b border-slate-100"
                ):
                    with ui.row().classes("items-center gap-2.5"):
                        with ui.element("div").classes(
                            "w-8 h-8 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center font-bold"
                        ):
                            ui.icon("bolt", size="18px")
                        ui.label("Operational Quick Actions").classes(
                            "text-sm font-bold text-slate-900 font-sans"
                        )
                    ui.label("Permitted by assigned administrative role").classes(
                        "text-xs text-slate-400 font-mono"
                    )

                with ui.row().classes("w-full gap-2.5 flex-wrap items-center"):
                    if user_can("DOCUMENT_UPLOAD"):
                        ui.button(
                            "Upload Document",
                            icon="upload_file",
                            on_click=lambda: ui.navigate.to("/documents"),
                        ).props("no-caps dense").classes(
                            "text-xs font-semibold px-4 py-2 !bg-emerald-600 hover:!bg-emerald-700 !text-white rounded-xl shadow-xs transition-colors"
                        )

                    if user_can("COURSE_CREATE"):
                        ui.button(
                            "Create Course",
                            icon="add",
                            on_click=lambda: ui.navigate.to("/knowledge-bases"),
                        ).props("no-caps dense").classes(
                            "text-xs font-semibold px-4 py-2 !bg-slate-900 hover:!bg-slate-800 !text-white rounded-xl shadow-xs transition-colors"
                        )

                    ui.button(
                        "Indexing Center",
                        icon="hub",
                        on_click=lambda: ui.navigate.to("/indexing"),
                    ).props("no-caps dense").classes(
                        "text-xs font-medium px-4 py-2 border border-slate-200 text-slate-700 hover:bg-slate-50 rounded-xl transition-colors"
                    )

                    if user_can("ADMIN_CHAT") or user.role == "ADMIN":
                        ui.button(
                            "Admin Knowledge Chat",
                            icon="chat",
                            on_click=lambda: ui.navigate.to("/chat"),
                        ).props("no-caps dense").classes(
                            "text-xs font-medium px-4 py-2 border border-blue-200 text-blue-700 hover:bg-blue-50 rounded-xl transition-colors"
                        )

                    if user_can("ADMIN_VIEW") or user.admin_role == "MAIN_ADMIN":
                        ui.button(
                            "Manage Administrators",
                            icon="admin_panel_settings",
                            on_click=lambda: ui.navigate.to("/administrators"),
                        ).props("no-caps dense").classes(
                            "text-xs font-medium px-4 py-2 border border-purple-200 text-purple-700 hover:bg-purple-50 rounded-xl transition-colors"
                        )

                    ui.button(
                        "System Health",
                        icon="monitor_heart",
                        on_click=lambda: ui.navigate.to("/system-health"),
                    ).props("flat no-caps dense").classes(
                        "text-xs font-medium px-3.5 py-2 text-slate-600 hover:text-slate-900 rounded-xl hover:bg-slate-100 transition-colors"
                    )

            # 3. Prominent Indexing Activity Section
            with ui.card().classes(
                "academic-card w-full p-5 bg-white border border-slate-200/80 rounded-2xl shadow-xs mt-3"
            ):
                with ui.row().classes(
                    "w-full justify-between items-center mb-3 pb-2 border-b border-slate-100"
                ):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("precision_manufacturing", size="sm").classes("text-indigo-600")
                        ui.label("Indexing Activity & Vector Generation").classes(
                            "text-sm font-bold text-slate-800"
                        )
                        if active_jobs:
                            ui.badge(f"{len(active_jobs)} Active", color="amber-700").classes(
                                "text-[10px] font-bold"
                            )
                        else:
                            ui.badge("Idle", color="slate-500").classes("text-[10px]")

                    ui.button(
                        "Open Indexing Center",
                        icon="arrow_forward",
                        on_click=lambda: ui.navigate.to("/indexing"),
                    ).props("flat dense no-caps").classes("text-xs text-indigo-600 font-medium")

                if not active_jobs:
                    with ui.row().classes(
                        "w-full items-center justify-between p-4 bg-slate-50 border border-slate-200 rounded-lg"
                    ):
                        with ui.row().classes("items-center gap-3"):
                            ui.icon("task_alt", size="md").classes("text-emerald-500")
                            with ui.column().classes("gap-0"):
                                ui.label("No documents are currently being indexed").classes(
                                    "text-sm font-semibold text-slate-800"
                                )
                                ui.label(
                                    f"All {total_indexed} indexed document vectors are synchronized in PostgreSQL/pgvector."
                                ).classes("text-xs text-slate-500")
                        ui.button(
                            "View All Jobs",
                            icon="history",
                            on_click=lambda: ui.navigate.to("/indexing"),
                        ).props("outline dense no-caps color=slate-7").classes("text-xs")
                else:
                    with ui.column().classes("w-full gap-3"):
                        for job in active_jobs:
                            progress_val = (
                                job.processed_chunks / job.total_chunks
                                if job.total_chunks > 0
                                else (job.progress_percent / 100.0)
                            )
                            with ui.card().classes(
                                "w-full p-4 bg-slate-50 border border-slate-200 rounded-lg gap-2"
                            ):
                                with ui.row().classes("w-full items-center justify-between"):
                                    with ui.row().classes("items-center gap-2"):
                                        ui.icon("description", size="sm").classes("text-indigo-600")
                                        ui.label(
                                            job.document_name or f"Document {job.document_id[:8]}"
                                        ).classes("text-sm font-bold text-slate-900")
                                        if job.course_name:
                                            ui.badge(job.course_name, color="blue-700").classes(
                                                "text-[10px]"
                                            )
                                    ui.badge(job.stage.upper(), color="amber-800").classes(
                                        "text-[10px] font-bold"
                                    )

                                with ui.row().classes(
                                    "w-full items-center gap-4 text-xs text-slate-600"
                                ):
                                    ui.label(f"Stage: {job.stage.title()}")
                                    ui.label(f"Chunks: {job.processed_chunks} / {job.total_chunks}")
                                    ui.label(f"Vectors: {job.indexed_chunks} / {job.total_chunks}")
                                    ui.label(f"Status: {job.status.title()}")
                                    if job.started_at:
                                        ui.label(f"Started: {job.started_at[:16]}")

                                ui.linear_progress(
                                    value=min(1.0, max(0.0, progress_val)),
                                    show_value=False,
                                    size="8px",
                                ).props("color=amber rounded")

                                with ui.row().classes("w-full justify-end mt-1"):
                                    ui.button(
                                        "View Details",
                                        icon="visibility",
                                        on_click=lambda kb_id=job.knowledge_base_id: ui.navigate.to(
                                            f"/documents?kb_id={kb_id}"
                                        ),
                                    ).props("flat dense no-caps color=primary").classes("text-xs")

            # 4. Course Catalog Summary Table
            with ui.card().classes(
                "w-full p-5 bg-white border border-slate-200 rounded-lg shadow-xs mt-3"
            ):
                with ui.row().classes(
                    "w-full justify-between items-center mb-3 pb-2 border-b border-slate-100"
                ):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("school", size="sm").classes("text-blue-600")
                        ui.label("Course Catalog & Material Breakdown").classes(
                            "text-sm font-bold text-slate-800"
                        )
                    ui.button(
                        "Manage All Courses",
                        icon="arrow_forward",
                        on_click=lambda: ui.navigate.to("/knowledge-bases"),
                    ).props("flat dense no-caps").classes("text-xs text-blue-600 font-medium")

                if not course_summaries:
                    render_empty_state(
                        icon="menu_book",
                        title="No Courses Registered",
                        description="Create university courses to begin uploading materials.",
                        action_label="Create Course",
                        on_action=lambda: ui.navigate.to("/knowledge-bases"),
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
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Course Name")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Total Materials")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Active (Published)")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Indexing Status")
                                    with ui.element("th").classes("py-2.5 px-3 text-right"):
                                        ui.label("Action")

                            with ui.element("tbody").classes(
                                "divide-y divide-slate-100 text-slate-800"
                            ):
                                for c in course_summaries:
                                    with ui.element("tr").classes(
                                        "hover:bg-slate-50 transition-colors"
                                    ):
                                        with ui.element("td").classes(
                                            "py-2.5 px-3 font-semibold text-slate-900"
                                        ):
                                            ui.label(c.name)
                                        with ui.element("td").classes("py-2.5 px-3 font-mono"):
                                            ui.label(str(c.total_documents))
                                        with ui.element("td").classes("py-2.5 px-3"):
                                            ui.badge(
                                                f"{c.active_documents} Active", color="emerald-700"
                                            ).classes("text-[10px] font-bold")
                                        with ui.element("td").classes("py-2.5 px-3"):
                                            if c.indexing_documents > 0:
                                                ui.badge(
                                                    f"{c.indexing_documents} Indexing",
                                                    color="amber-700",
                                                ).classes("text-[10px]")
                                            elif c.failed_documents > 0:
                                                ui.badge(
                                                    f"{c.failed_documents} Failed", color="rose-700"
                                                ).classes("text-[10px]")
                                            else:
                                                ui.badge(
                                                    f"{c.indexed_documents} Indexed",
                                                    color="emerald-800",
                                                ).classes("text-[10px]")
                                        with ui.element("td").classes("py-2.5 px-3 text-right"):
                                            ui.button(
                                                "Manage Documents",
                                                icon="arrow_forward",
                                                on_click=lambda course_id=c.id: ui.navigate.to(
                                                    f"/documents?kb_id={course_id}"
                                                ),
                                            ).props("flat dense no-caps color=primary").classes(
                                                "text-xs"
                                            )

            # 5. Operational Activity Audit Timeline
            with ui.card().classes(
                "w-full p-5 bg-white border border-slate-200 rounded-lg shadow-xs mt-3 mb-6"
            ):
                with ui.row().classes(
                    "w-full justify-between items-center mb-3 pb-2 border-b border-slate-100"
                ):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("history", size="sm").classes("text-slate-600")
                        ui.label("Recent Administrative Activity & Audit Log").classes(
                            "text-sm font-bold text-slate-800"
                        )
                    ui.button(
                        "View Full Audit Log",
                        icon="arrow_forward",
                        on_click=lambda: ui.navigate.to("/activity"),
                    ).props("flat dense no-caps").classes("text-xs text-slate-600 font-medium")

                if not activity_events:
                    with ui.row().classes(
                        "w-full items-center justify-between p-4 bg-slate-50 border border-slate-200 rounded-lg"
                    ):
                        with ui.row().classes("items-center gap-3"):
                            ui.icon("event_available", size="md").classes("text-slate-400")
                            ui.label("No recent administrative operations recorded yet.").classes(
                                "text-sm text-slate-600"
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
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Time")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Actor")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Action")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Resource")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Status")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Details")

                            with ui.element("tbody").classes(
                                "divide-y divide-slate-100 text-slate-800"
                            ):
                                for ev in activity_events[:10]:
                                    with ui.element("tr").classes(
                                        "hover:bg-slate-50 transition-colors"
                                    ):
                                        with ui.element("td").classes(
                                            "py-2.5 px-3 text-slate-500 whitespace-nowrap"
                                        ):
                                            ui.label(str(ev.timestamp)[:19].replace("T", " "))
                                        with ui.element("td").classes(
                                            "py-2.5 px-3 font-medium text-slate-900"
                                        ):
                                            ui.label(ev.actor_name or ev.actor_email)
                                        with ui.element("td").classes(
                                            "py-2.5 px-3 font-semibold text-slate-800"
                                        ):
                                            ui.label(ev.action.replace("_", " ").title())
                                        with ui.element("td").classes("py-2.5 px-3 text-slate-700"):
                                            ui.label(f"{ev.resource_type}: {ev.resource_name}")
                                        with ui.element("td").classes("py-2.5 px-3"):
                                            if ev.status == "SUCCESS":
                                                ui.badge("SUCCESS", color="emerald-700").classes(
                                                    "text-[10px] font-bold"
                                                )
                                            elif ev.status == "FAILED":
                                                ui.badge("FAILED", color="rose-700").classes(
                                                    "text-[10px] font-bold"
                                                )
                                            else:
                                                ui.badge(ev.status, color="amber-700").classes(
                                                    "text-[10px]"
                                                )
                                        with ui.element("td").classes(
                                            "py-2.5 px-3 text-slate-500 max-w-[200px] truncate"
                                        ):
                                            ui.label(ev.details or "—")
