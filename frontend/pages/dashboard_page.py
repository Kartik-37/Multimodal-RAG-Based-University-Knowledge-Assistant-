"""
Dashboard Presentation Page with Role-Tailored Perspectives.

Provides distinct experiences:
- STUDENT: Direct inquiry entry point, course overview cards, grounded search access.
- ADMIN: University Knowledge Management with courses, document lifecycle, and administrators.
Strictly avoids N+1 API calls and uses no obsolete active-corpus concepts.
"""

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.components.layout import page_layout
from frontend.components.status_badge import render_status_badge
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
                kbs = api_client.get_knowledge_bases() if user else []

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

                                    ui.button(
                                        "Ask about this course",
                                        icon="chat_bubble_outline",
                                        on_click=lambda course_id=kb.id: ui.navigate.to(
                                            f"/chat?kb_id={course_id}"
                                        ),
                                    ).props("flat dense no-caps text-color=primary").classes(
                                        "text-xs font-semibold self-start mt-1 p-0"
                                    )
                return

            # ------------------------------------------------------------------
            # ADMINISTRATOR PERSPECTIVE
            # ------------------------------------------------------------------
            course_summaries = api_client.get_course_summaries()
            try:
                admins = api_client.get_admins()
            except Exception:
                admins = []

            total_courses = len(course_summaries)
            total_documents = sum(c.total_documents for c in course_summaries)
            active_documents = sum(c.active_documents for c in course_summaries)
            total_admins = len(admins)

            # 1. Summary Cards (Courses, Documents, Active Documents, Administrators)
            with ui.row().classes("w-full gap-4"):
                render_stat_card(
                    title="Courses",
                    value=total_courses,
                    subtitle="Registered university courses",
                    icon="menu_book",
                    icon_color="blue-600",
                )
                render_stat_card(
                    title="Documents",
                    value=total_documents,
                    subtitle="Course learning materials",
                    icon="description",
                    icon_color="indigo-600",
                )
                render_stat_card(
                    title="Active Documents",
                    value=active_documents,
                    subtitle="Published & retrieval eligible",
                    icon="verified",
                    icon_color="emerald-600",
                )
                render_stat_card(
                    title="Administrators",
                    value=total_admins,
                    subtitle="Faculty administrators",
                    icon="admin_panel_settings",
                    icon_color="purple-600",
                )

            # 2. Quick Actions
            with ui.card().classes(
                "w-full p-4 bg-white border border-slate-200 rounded-lg shadow-xs mt-1"
            ):
                with ui.row().classes(
                    "items-center justify-between w-full mb-3 pb-2 border-b border-slate-100"
                ):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("bolt", size="sm").classes("text-amber-500")
                        ui.label("Quick Actions").classes("text-sm font-bold text-slate-800")

                with ui.row().classes("w-full gap-3 flex-wrap"):
                    ui.button(
                        "Create Course",
                        icon="add",
                        on_click=lambda: ui.navigate.to("/knowledge-bases"),
                    ).props("color=primary no-caps dense").classes("text-xs font-medium px-4 py-2")

                    ui.button(
                        "Upload Document",
                        icon="upload_file",
                        on_click=lambda: ui.navigate.to("/documents"),
                    ).props("color=positive no-caps dense").classes("text-xs font-medium px-4 py-2")

                    ui.button(
                        "Manage Courses",
                        icon="menu_book",
                        on_click=lambda: ui.navigate.to("/knowledge-bases"),
                    ).props("outline color=primary no-caps dense").classes(
                        "text-xs font-medium px-4 py-2"
                    )

                    ui.button(
                        "Manage Administrators",
                        icon="admin_panel_settings",
                        on_click=lambda: ui.navigate.to("/administrators"),
                    ).props("outline color=purple no-caps dense").classes(
                        "text-xs font-medium px-4 py-2"
                    )

            # 3. Courses Overview
            with ui.card().classes(
                "w-full p-5 bg-white border border-slate-200 rounded-lg shadow-xs mt-2"
            ):
                with ui.row().classes(
                    "w-full justify-between items-center mb-3 pb-2 border-b border-slate-100"
                ):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("school", size="sm").classes("text-blue-600")
                        ui.label("Courses").classes("text-sm font-bold text-slate-800")
                    ui.button(
                        "View All Courses",
                        icon="arrow_forward",
                        on_click=lambda: ui.navigate.to("/knowledge-bases"),
                    ).props("flat dense no-caps").classes("text-xs text-blue-600")

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
                                        ui.label("Inactive (Historical)")
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
                                            ui.badge(
                                                f"{c.inactive_documents} Inactive",
                                                color="slate-500",
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

            # 4. Recent Document Activity
            recent_docs = []
            for c in course_summaries:
                for preview in c.document_previews:
                    recent_docs.append(
                        {
                            "course_name": c.name,
                            "course_id": c.id,
                            "filename": preview.filename,
                            "file_type": preview.file_type,
                            "status": preview.status,
                            "is_active": preview.is_active,
                        }
                    )

            with ui.card().classes(
                "w-full p-5 bg-white border border-slate-200 rounded-lg shadow-xs mt-2"
            ):
                with ui.row().classes(
                    "w-full justify-between items-center mb-3 pb-2 border-b border-slate-100"
                ):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("history", size="sm").classes("text-slate-600")
                        ui.label("Recent Document Activity").classes(
                            "text-sm font-bold text-slate-800"
                        )

                if not recent_docs:
                    render_empty_state(
                        icon="description",
                        title="No Recent Documents",
                        description="Uploaded documents across all courses will appear here.",
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
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Filename")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Course")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Format")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Processing")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Retrieval Status")

                            with ui.element("tbody").classes(
                                "divide-y divide-slate-100 text-slate-800"
                            ):
                                for d in recent_docs[:10]:
                                    with ui.element("tr").classes(
                                        "hover:bg-slate-50 transition-colors"
                                    ):
                                        with ui.element("td").classes(
                                            "py-2.5 px-3 font-medium text-slate-900 truncate max-w-[220px]"
                                        ):
                                            ui.label(d["filename"])
                                        with ui.element("td").classes("py-2.5 px-3 text-slate-600"):
                                            ui.label(d["course_name"])
                                        with ui.element("td").classes("py-2.5 px-3 font-mono"):
                                            ui.badge(
                                                d["file_type"].upper(), color="slate-600"
                                            ).classes("text-[10px]")
                                        with ui.element("td").classes("py-2.5 px-3"):
                                            render_status_badge(d["status"])
                                        with ui.element("td").classes("py-2.5 px-3"):
                                            if d["is_active"]:
                                                ui.badge("ACTIVE", color="emerald-700").classes(
                                                    "text-[10px] font-bold"
                                                )
                                            else:
                                                ui.badge("INACTIVE", color="slate-500").classes(
                                                    "text-[10px]"
                                                )
