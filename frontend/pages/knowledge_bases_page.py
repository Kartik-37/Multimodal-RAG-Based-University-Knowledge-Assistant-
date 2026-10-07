"""
Courses & Knowledge Bases Presentation Page.

Provides clean academic course management and browsing:
- STUDENTS: Enrolled course directory with document counts, material inspection, and direct Q&A access.
  Strictly membership-based: students see only their assigned courses.
- ADMINISTRATORS: Course provisioning, material management links, and diagnostic chat access.
"""

from nicegui import ui

from backend.app.core.permissions import Permission
from frontend.client.api_client import api_client
from frontend.client.error_handler import normalize_error
from frontend.components.layout import has_admin_permission, page_layout
from frontend.components.source_viewer import open_source_viewer
from frontend.components.ui_kit import render_alert, render_empty_state
from frontend.state.app_state import state


def register_knowledge_bases_page() -> None:
    """Register /knowledge-bases route with NiceGUI."""

    @ui.page("/knowledge-bases")
    def knowledge_bases_page() -> None:
        user = state.current_user
        is_student = user is None or user.role == "STUDENT"
        can_create_course = has_admin_permission(user, Permission.COURSE_CREATE)

        page_title = "Academic Library & Courses" if is_student else "Course Knowledge Bases"
        page_subtitle = (
            "Explore published courses, inspect learning materials, and launch grounded assistant inquiries."
            if is_student
            else "Curate academic courses, provision syllabi repositories, and manage learning documents."
        )

        with page_layout(
            title=page_title,
            subtitle=page_subtitle,
            active_route="/knowledge-bases",
            require_auth=True,
            breadcrumbs=None if is_student else [("Dashboard", "/dashboard"), ("Courses", None)],
        ):
            # ------------------------------------------------------------------
            # CREATE COURSE DIALOG (Admin Only)
            # ------------------------------------------------------------------
            create_dialog = ui.dialog()
            with (
                create_dialog,
                ui.card().classes(
                    "w-full max-w-md p-6 bg-white border border-slate-200 rounded-xl shadow-lg"
                ),
            ):
                with ui.row().classes("w-full items-center justify-between pb-3 border-b border-slate-100"):
                    with ui.row().classes("items-center gap-2"):
                        with ui.element("div").classes(
                            "w-8 h-8 rounded-lg bg-blue-50 text-blue-700 flex items-center justify-center font-bold"
                        ):
                            ui.icon("school", size="18px")
                        ui.label("Create New Course").classes("text-base font-bold text-slate-900")
                    ui.button(icon="close", on_click=create_dialog.close).props(
                        "flat round dense"
                    ).classes("text-slate-400 hover:text-slate-700")

                ui.label(
                    "Provision a new university course repository for syllabi, lecture notes, and reference documents."
                ).classes("text-xs text-slate-600 mt-2 mb-4 leading-relaxed")

                dialog_error = ui.column().classes("w-full mb-2")

                with ui.column().classes("w-full gap-1.5 mb-3.5"):
                    ui.label("Course Name *").classes("text-xs font-semibold text-slate-700")
                    name_input = (
                        ui.input(placeholder="e.g. BCA-301 Computer Architecture")
                        .props("outlined dense")
                        .classes("w-full minimalist-input")
                    )

                with ui.column().classes("w-full gap-1.5 mb-5"):
                    ui.label("Description").classes("text-xs font-semibold text-slate-700")
                    desc_input = (
                        ui.textarea(
                            placeholder="Brief overview of course syllabus, subject matter, or semester."
                        )
                        .props("outlined dense rows=3")
                        .classes("w-full")
                    )

                def handle_create() -> None:
                    dialog_error.clear()
                    c_name = (name_input.value or "").strip()
                    c_desc = (desc_input.value or "").strip()

                    if not c_name:
                        with dialog_error:
                            render_alert("Course name is required.", "warning")
                        return

                    create_btn.props("loading disable")
                    try:
                        api_client.create_knowledge_base(name=c_name, description=c_desc)
                        ui.notify(f"Course '{c_name}' created successfully.", type="positive")
                        create_dialog.close()
                        name_input.value = ""
                        desc_input.value = ""
                        load_and_render_courses()
                    except ValueError as err:
                        with dialog_error:
                            render_alert(normalize_error(err, context="course"), "negative")
                    finally:
                        create_btn.props(remove="loading disable")

                with ui.row().classes("w-full justify-end gap-2 pt-3 border-t border-slate-100"):
                    ui.button("Cancel", on_click=create_dialog.close).props(
                        "flat dense no-caps"
                    ).classes("text-xs text-slate-600")
                    create_btn = (
                        ui.button("Create Course", icon="add", on_click=handle_create)
                        .props("no-caps dense")
                        .classes(
                            "text-xs px-4 py-2 !bg-blue-700 hover:!bg-blue-800 !text-white rounded-lg shadow-xs transition-colors"
                        )
                    )

            # ------------------------------------------------------------------
            # TOP TOOLBAR: Search & Actions
            # ------------------------------------------------------------------
            with ui.row().classes("w-full items-center justify-between gap-3 flex-wrap mb-2"):
                search_input = (
                    ui.input(placeholder="Search courses by name or subject...")
                    .props("outlined dense clearable")
                    .classes("w-72 sm:w-80 text-xs minimalist-input")
                )

                with ui.row().classes("items-center gap-2"):
                    if can_create_course:
                        ui.button(
                            "Create Course",
                            icon="add",
                            on_click=create_dialog.open,
                        ).props("no-caps dense").classes(
                            "text-xs font-medium px-3.5 py-2 !bg-blue-700 hover:!bg-blue-800 !text-white rounded-lg shadow-xs transition-colors"
                        )

            # ------------------------------------------------------------------
            # COURSES GRID CONTAINER
            # ------------------------------------------------------------------
            courses_grid = ui.element("div").classes(
                "w-full grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 mt-2"
            )

            all_courses = []

            def load_and_render_courses(query_filter: str = "") -> None:
                nonlocal all_courses
                courses_grid.clear()

                if not all_courses:
                    try:
                        if is_student:
                            all_courses = api_client.get_knowledge_bases()
                        else:
                            all_courses = api_client.get_knowledge_bases()
                    except ValueError as err:
                        with courses_grid:
                            with ui.column().classes("col-span-full w-full"):
                                render_alert(f"Unable to load courses. {err}", "negative")
                        return

                clean_q = query_filter.strip().lower()
                filtered = (
                    [
                        c
                        for c in all_courses
                        if clean_q in c.name.lower() or clean_q in (c.description or "").lower()
                    ]
                    if clean_q
                    else all_courses
                )

                with courses_grid:
                    if not filtered:
                        with ui.column().classes("col-span-full w-full"):
                            render_empty_state(
                                icon="search_off" if clean_q else "school",
                                title=(
                                    "No Matching Courses"
                                    if clean_q
                                    else ("No Assigned Courses" if is_student else "No Courses Registered")
                                ),
                                description=(
                                    f"No courses match '{clean_q}'. Try a different search term."
                                    if clean_q
                                    else (
                                        "You are not assigned to any courses. Please contact your instructor to be enrolled."
                                        if is_student
                                        else "No course knowledge bases exist yet. Use 'Create Course' to provision one."
                                    )
                                ),
                            )
                        return

                    for course in filtered:
                        with ui.card().classes(
                            "academic-card p-5 bg-white border border-slate-200 rounded-xl shadow-xs flex flex-col justify-between"
                        ):
                            with ui.column().classes("gap-2.5 w-full"):
                                with ui.row().classes("items-center justify-between w-full"):
                                    ui.label(course.name).classes(
                                        "text-sm font-bold text-slate-900 tracking-tight truncate flex-1"
                                    )
                                    ui.badge(
                                        f"{course.document_count} doc(s)",
                                        color="slate-1",
                                    ).props("text-color=slate-7").classes(
                                        "text-[10px] font-mono font-semibold px-2 py-0.5 border border-slate-200 shrink-0"
                                    )

                                ui.label(
                                    course.description
                                    or "Official university course materials and verified documents."
                                ).classes("text-xs text-slate-600 line-clamp-2 leading-relaxed")

                            with ui.row().classes(
                                "w-full justify-between items-center pt-3 border-t border-slate-100 mt-4"
                            ):
                                if is_student:
                                    ui.button(
                                        "Ask Assistant",
                                        icon="chat",
                                        on_click=lambda c_id=course.id: ui.navigate.to(
                                            f"/chat?kb_id={c_id}"
                                        ),
                                    ).props("no-caps dense").classes(
                                        "text-xs font-medium px-3.5 py-1.5 !bg-blue-700 hover:!bg-blue-800 !text-white rounded-lg shadow-xs transition-colors"
                                    )

                                    def make_view_docs_handler(c_id=course.id, c_name=course.name):
                                        def _show_docs():
                                            try:
                                                docs = api_client.get_documents(c_id)
                                            except Exception:
                                                docs = []
                                            with (
                                                ui.dialog() as docs_dlg,
                                                ui.card().classes(
                                                    "w-full max-w-md p-6 bg-white border border-slate-200 rounded-xl shadow-xl"
                                                ),
                                            ):
                                                with ui.row().classes(
                                                    "w-full items-center justify-between pb-3 border-b border-slate-100"
                                                ):
                                                    ui.label(f"{c_name} — Materials").classes(
                                                        "text-sm font-bold text-slate-900"
                                                    )
                                                    ui.button(
                                                        icon="close", on_click=docs_dlg.close
                                                    ).props("flat round dense").classes(
                                                        "text-slate-400 hover:text-slate-700"
                                                    )
                                                if not docs:
                                                    ui.label("No documents uploaded yet.").classes(
                                                        "text-xs text-slate-500 py-4"
                                                    )
                                                else:
                                                    with ui.column().classes(
                                                        "w-full gap-2 py-2 max-h-72 overflow-y-auto"
                                                    ):
                                                        for d in docs:
                                                            with (
                                                                ui.row()
                                                                .classes(
                                                                    "w-full items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-200/80 text-xs cursor-pointer hover:bg-blue-50 transition-colors"
                                                                )
                                                                .on(
                                                                    "click",
                                                                    lambda d_id=d.id, d_name=d.filename: [
                                                                        docs_dlg.close(),
                                                                        open_source_viewer(
                                                                            document_id=str(d_id),
                                                                            document_name=d_name,
                                                                            kb_id=str(c_id),
                                                                            course_name=c_name,
                                                                        ),
                                                                    ],
                                                                )
                                                            ):
                                                                with ui.row().classes(
                                                                    "items-center gap-2 min-w-0 flex-1"
                                                                ):
                                                                    ui.icon(
                                                                        "picture_as_pdf"
                                                                        if d.filename.lower().endswith(".pdf")
                                                                        else "description",
                                                                        size="16px",
                                                                    ).classes("text-blue-700")
                                                                    ui.label(d.filename).classes(
                                                                        "font-medium text-slate-800 truncate"
                                                                    )
                                                                ui.icon("visibility", size="14px").classes(
                                                                    "text-slate-400"
                                                                )
                                            docs_dlg.open()

                                        return _show_docs

                                    ui.button(
                                        "View Materials",
                                        icon="description",
                                        on_click=make_view_docs_handler(),
                                    ).props("flat dense no-caps").classes(
                                        "text-xs text-slate-600 hover:text-slate-900 px-2 py-1"
                                    )
                                else:
                                    # Administrator actions
                                    ui.button(
                                        "Manage Documents",
                                        icon="folder_open",
                                        on_click=lambda c_id=course.id: ui.navigate.to(
                                            f"/documents?kb_id={c_id}"
                                        ),
                                    ).props("no-caps dense").classes(
                                        "text-xs font-medium px-3.5 py-1.5 !bg-blue-700 hover:!bg-blue-800 !text-white rounded-lg shadow-xs transition-colors"
                                    )
                                    ui.button(
                                        "Chat",
                                        icon="chat",
                                        on_click=lambda c_id=course.id: ui.navigate.to(
                                            f"/chat?kb_id={c_id}"
                                        ),
                                    ).props("flat dense no-caps").classes(
                                        "text-xs text-slate-700 hover:text-blue-700 px-2 py-1 font-medium"
                                    )

            search_input.on_value_change(lambda e: load_and_render_courses(e.value or ""))
            load_and_render_courses()
