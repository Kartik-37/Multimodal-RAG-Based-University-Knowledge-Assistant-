"""
Courses & Knowledge Bases Presentation Page.

Authoritative Editorial Academic Identity:
- Students: Scholarly course catalogue, material inspection, and scoped inquiry.
- Administrators: Course provisioning, document management, and syllabus curation.
- Strictly adheres to context/FRONTEND_DESIGN_SYSTEM.md tokens and guidelines.
"""

import html
from typing import Any

from nicegui import ui

from backend.app.core.permissions import Permission
from frontend.client.api_client import api_client
from frontend.client.error_handler import normalize_error
from frontend.client.models import DocumentDTO, KnowledgeBaseDTO
from frontend.components.layout import page_layout
from frontend.components.source_viewer import open_source_viewer
from frontend.components.ui_kit import render_alert, render_empty_state
from frontend.security.access_control import has_admin_permission
from frontend.state.app_state import state


def format_document_count(count: int | None) -> str:
    """Produce clean, readable document count wording without technical jargon."""
    if count is None:
        return "Count unavailable"
    if count <= 0:
        return "No documents"
    if count == 1:
        return "1 document"
    return f"{count} documents"


def get_file_type_icon(filename: str) -> str:
    """Return appropriate Material icon based on document extension."""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return "picture_as_pdf"
    if lower.endswith((".docx", ".doc")):
        return "description"
    if lower.endswith(".csv"):
        return "table_chart"
    return "article"


def format_file_size(size_bytes: int, file_type: str = "") -> str:
    """Format byte size into clean human-readable text."""
    if size_bytes <= 0:
        return file_type.upper() if file_type else "Document"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes // 1024} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def register_knowledge_bases_page() -> None:
    @ui.page("/knowledge-bases")
    def knowledge_bases_page() -> None:
        user = state.current_user
        if not user:
            ui.navigate.to("/login")
            return

        is_student = user.role == "STUDENT"
        can_create_course = has_admin_permission(user, Permission.COURSE_CREATE)

        page_title = "" if is_student else "Course Management"
        page_subtitle = (
            ""
            if is_student
            else "Curate academic courses and provision syllabi repositories."
        )

        with page_layout(
            title=page_title,
            subtitle=page_subtitle,
            active_route="/knowledge-bases",
            require_auth=True,
        ):
            # ------------------------------------------------------------------
            # Administrator: Course Creation Dialog
            # ------------------------------------------------------------------
            create_dialog = ui.dialog()
            with (
                create_dialog,
                ui.card().classes(
                    "w-full max-w-md p-6 sm:p-8 bg-surface-elevated border border-subtle rounded-lg shadow-none"
                ),
            ):
                with ui.row().classes(
                    "w-full items-center justify-between pb-4 border-b border-subtle"
                ):
                    with ui.row().classes("items-center gap-2.5"):
                        ui.icon("school", size="1.25rem").classes("text-gold")
                        ui.label("Create Course").classes(
                            "text-xl font-bold text-primary-navy font-editorial"
                        )
                    ui.button(icon="close", on_click=create_dialog.close).props(
                        "flat round dense"
                    ).classes("text-secondary-navy hover:text-primary-navy")

                dialog_error = ui.column().classes("w-full mt-3")

                with ui.column().classes("w-full gap-1.5 mt-3"):
                    ui.label("Course Name *").classes(
                        "text-xs font-semibold uppercase tracking-wider text-secondary-navy"
                    )
                    name_input = (
                        ui.input(placeholder="e.g. CS-101 Introduction to Computer Science")
                        .props("outlined dense")
                        .classes("w-full minimalist-input")
                    )

                with ui.column().classes("w-full gap-1.5 mt-3 mb-4"):
                    ui.label("Description").classes(
                        "text-xs font-semibold uppercase tracking-wider text-secondary-navy"
                    )
                    desc_input = (
                        ui.textarea(placeholder="Brief overview of course syllabus.")
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
                        ui.notify(f"Course '{c_name}' created.", type="positive")
                        create_dialog.close()
                        name_input.value = ""
                        desc_input.value = ""
                        load_courses(force_refresh=True)
                    except ValueError as err:
                        with dialog_error:
                            render_alert(normalize_error(err, context="course"), "negative")
                    finally:
                        create_btn.props(remove="loading disable")

                with ui.row().classes("w-full justify-end gap-3 pt-4 border-t border-subtle"):
                    ui.button("Cancel", on_click=create_dialog.close).props(
                        "flat dense no-caps"
                    ).classes("text-sm font-semibold text-secondary-navy")
                    create_btn = (
                        ui.button("Create Course", on_click=handle_create)
                        .props("no-caps")
                        .classes("bg-surface-navy text-inverted font-bold px-5 py-2 rounded text-sm")
                    )

            # ------------------------------------------------------------------
            # Student & Admin Page Introduction
            # ------------------------------------------------------------------
            if is_student:
                with ui.row().classes("w-full justify-between items-start gap-4 mb-1"):
                    with ui.column().classes("gap-1"):
                        ui.label("Course Library").classes(
                            "text-3xl font-bold text-primary-navy font-editorial tracking-tight"
                        )
                        ui.label(
                            "Browse accessible courses, inspect syllabus materials, and ask questions."
                        ).classes("text-sm text-secondary-navy leading-relaxed")

            # ------------------------------------------------------------------
            # Toolbar: Search, Filters, and Actions
            # ------------------------------------------------------------------
            active_filter = "all"  # "all" | "with_docs" | "no_docs"
            search_query = ""

            with ui.column().classes("w-full gap-3 mb-6"):
                with ui.row().classes("w-full items-center justify-between gap-4 flex-wrap"):
                    search_input = (
                        ui.input(placeholder="Search by course name or description...")
                        .props("outlined dense clearable")
                        .classes("w-full sm:w-80 md:w-96 text-sm minimalist-input")
                    )
                    search_input.props('aria-label="Search course catalog"')

                    with ui.row().classes("items-center gap-3"):
                        if can_create_course:
                            ui.button("New Course", icon="add", on_click=create_dialog.open).props(
                                "no-caps"
                            ).classes("bg-surface-navy text-inverted font-bold px-4 py-2 rounded shrink-0 text-sm")

                # Filter chips bar
                filter_bar = ui.row().classes("items-center gap-2 flex-wrap")

            # ------------------------------------------------------------------
            # Course Catalogue Container
            # ------------------------------------------------------------------
            catalogue_container = ui.column().classes("w-full min-h-[200px]")

            # In-memory cached courses for live filtering
            cached_courses: list[KnowledgeBaseDTO] = []

            # ------------------------------------------------------------------
            # Document Viewing Modal Dialog
            # ------------------------------------------------------------------
            materials_dialog = ui.dialog()
            with (
                materials_dialog,
                ui.card().classes(
                    "w-full max-w-lg p-6 bg-surface-elevated border border-subtle rounded-lg shadow-none"
                ),
            ):
                with ui.row().classes(
                    "w-full items-center justify-between pb-3 border-b border-subtle"
                ):
                    with ui.row().classes("items-center gap-2.5 min-w-0 flex-1 pr-2"):
                        ui.icon("menu_book", size="1.25rem").classes("text-gold shrink-0")
                        materials_title_lbl = ui.label("Course Materials").classes(
                            "text-lg font-bold text-primary-navy font-editorial truncate"
                        )
                    ui.button(
                        icon="close", on_click=materials_dialog.close
                    ).props("flat round dense").classes(
                        "text-secondary-navy hover:text-primary-navy shrink-0"
                    )

                materials_docs_container = ui.column().classes("w-full mt-3 min-h-[120px]")

            def open_materials_dialog(course: KnowledgeBaseDTO) -> None:
                materials_title_lbl.text = f"{course.name} Materials"
                materials_title_lbl.props(f'title="{html.escape(course.name, quote=True)} Materials"')
                materials_dialog.open()

                def load_docs() -> None:
                    materials_docs_container.clear()
                    with materials_docs_container:
                        with ui.row().classes("w-full py-8 justify-center items-center gap-2"):
                            ui.spinner("dots", size="md", color="primary")
                            ui.label("Loading materials...").classes("text-xs text-secondary-navy font-medium")

                    try:
                        docs: list[DocumentDTO] = api_client.get_documents(course.id)
                    except Exception as err:
                        materials_docs_container.clear()
                        with materials_docs_container:
                            render_alert(normalize_error(err, context="document"), "negative")
                            with ui.row().classes("w-full justify-center mt-4"):
                                ui.button("Retry", icon="refresh", on_click=load_docs).props(
                                    "outline no-caps dense"
                                ).classes("text-xs font-semibold text-primary-navy border border-subtle")
                        return

                    materials_docs_container.clear()
                    with materials_docs_container:
                        if not docs:
                            render_empty_state(
                                icon="auto_stories",
                                title="No Documents Available",
                                description="No published reference documents or syllabus files are currently available for this course.",
                            )
                            return

                        with ui.column().classes("w-full gap-2.5 max-h-96 overflow-y-auto pr-1"):
                            for d in docs:
                                with ui.row().classes(
                                    "w-full items-center justify-between p-3 rounded-lg border border-subtle "
                                    "bg-canvas hover:bg-surface transition-colors gap-3"
                                ):
                                    with ui.row().classes("items-center gap-3 min-w-0 flex-1"):
                                        ui.icon(
                                            get_file_type_icon(d.filename),
                                            size="1.25rem",
                                        ).classes("text-primary-navy shrink-0")
                                        with ui.column().classes("gap-0 min-w-0 flex-1"):
                                            ui.label(d.filename).classes(
                                                "text-sm font-semibold text-primary-navy truncate"
                                            ).props(f'title="{html.escape(d.filename, quote=True)}"')
                                            size_text = format_file_size(d.file_size_bytes, d.file_type)
                                            ui.label(size_text).classes(
                                                "text-[11px] text-secondary-navy/70 font-mono"
                                            )

                                    def make_reader_opener(doc=d):
                                        return lambda: [
                                            materials_dialog.close(),
                                            open_source_viewer(
                                                document_id=str(doc.id),
                                                document_name=doc.filename,
                                                kb_id=str(course.id),
                                                course_name=course.name,
                                                return_to="/knowledge-bases",
                                            ),
                                        ]

                                    ui.button(
                                        "Read",
                                        icon="visibility",
                                        on_click=make_reader_opener(),
                                    ).props(f'flat dense no-caps aria-label="Read {html.escape(d.filename, quote=True)}"').classes(
                                        "doc-read-btn text-xs font-bold text-primary-navy hover:text-gold shrink-0 px-2.5 py-1"
                                    )

                load_docs()

            # ------------------------------------------------------------------
            # Render Catalogue Grid
            # ------------------------------------------------------------------
            def render_catalogue() -> None:
                nonlocal active_filter
                catalogue_container.clear()
                filter_bar.clear()

                total_count = len(cached_courses)
                with_materials_count = sum(
                    1 for c in cached_courses if c.document_count is not None and c.document_count > 0
                )
                no_materials_count = sum(
                    1 for c in cached_courses if c.document_count is not None and c.document_count == 0
                )
                unknown_count = sum(1 for c in cached_courses if c.document_count is None)

                if active_filter == "uncounted" and unknown_count == 0:
                    active_filter = "all"

                # Render Filter Pills
                with filter_bar:
                    filter_defs = [
                        ("all", f"All Courses ({total_count})"),
                        ("with_docs", f"With Materials ({with_materials_count})"),
                        ("no_docs", f"No Materials ({no_materials_count})"),
                    ]
                    if unknown_count > 0:
                        filter_defs.append(("uncounted", f"Count Unavailable ({unknown_count})"))

                    for f_key, f_label in filter_defs:
                        is_active_filter = active_filter == f_key
                        btn_cls = (
                            "bg-primary-navy !text-white font-bold filter-pill-selected shadow-none"
                            if is_active_filter
                            else "bg-surface text-secondary-navy hover:text-primary-navy hover:bg-surface-subtle font-medium"
                        )

                        def make_filter_handler(target_key=f_key):
                            nonlocal active_filter
                            active_filter = target_key
                            render_catalogue()

                        ui.button(
                            f_label,
                            on_click=make_filter_handler,
                        ).props("flat dense no-caps").classes(
                            f"px-3 py-1 text-xs rounded-full border border-subtle transition-colors {btn_cls}"
                        )

                    if unknown_count > 0:
                        ui.label("Some material counts could not be verified").classes(
                            "text-[11px] text-secondary-navy/60 italic self-center ml-1"
                        )

                # Apply Search & Filter
                clean_q = search_query.strip().lower()
                filtered = cached_courses

                if clean_q:
                    filtered = [
                        c
                        for c in filtered
                        if clean_q in c.name.lower() or clean_q in (c.description or "").lower()
                    ]

                if active_filter == "with_docs":
                    filtered = [
                        c for c in filtered if c.document_count is not None and c.document_count > 0
                    ]
                elif active_filter == "no_docs":
                    filtered = [
                        c for c in filtered if c.document_count is not None and c.document_count == 0
                    ]
                elif active_filter == "uncounted":
                    filtered = [c for c in filtered if c.document_count is None]

                with catalogue_container:
                    if not cached_courses:
                        render_empty_state(
                            icon="school",
                            title="No Courses Available",
                            description="No courses have been provisioned or published for your account.",
                        )
                        return

                    if not filtered:
                        def clear_filters() -> None:
                            nonlocal active_filter, search_query
                            active_filter = "all"
                            search_query = ""
                            search_input.value = ""
                            render_catalogue()

                        render_empty_state(
                            icon="search_off",
                            title="No Courses Match Your Search",
                            description=f'No courses found matching "{clean_q}". Try adjusting your keywords or clearing filters.'
                            if clean_q
                            else "No courses match the selected filter.",
                            action_label="Clear Search & Filters",
                            on_action=clear_filters,
                            action_icon="clear",
                        )
                        return

                    # Deliberate academic catalogue grid
                    if is_student:
                        # Deliberate academic catalogue grid for students
                        with ui.element("div").classes(
                            "w-full grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 items-stretch"
                        ):
                            for course in filtered:
                                with ui.card().classes(
                                    "w-full flex flex-col justify-between bg-surface-elevated border border-subtle "
                                    "rounded-lg p-5 transition-colors hover:border-gold/60 shadow-none"
                                ):
                                    # Top row: Icon + Document Count Pill
                                    with ui.row().classes("w-full items-center justify-between gap-2 mb-2"):
                                        ui.icon("school", size="1.25rem").classes("text-gold shrink-0")
                                        ui.label(format_document_count(course.document_count)).classes(
                                            "text-xs font-medium text-primary-navy bg-gold-light/60 px-2.5 py-0.5 rounded border border-gold/40 shrink-0"
                                        )

                                    # Course Title & Description
                                    with ui.column().classes("gap-1.5 flex-1 min-w-0 my-2"):
                                        ui.label(course.name).classes(
                                            "text-lg font-bold text-primary-navy font-editorial leading-snug line-clamp-2"
                                        ).props(f'title="{html.escape(course.name, quote=True)}"')
                                        ui.label(
                                            course.description or "Official university course materials and reference documents."
                                        ).classes("text-sm text-secondary-navy leading-relaxed line-clamp-3")

                                    # Card Actions
                                    with ui.row().classes(
                                        "w-full items-center justify-between pt-3 mt-auto border-t border-subtle gap-2"
                                    ):
                                        ui.button(
                                            "Materials",
                                            icon="menu_book",
                                            on_click=lambda c=course: open_materials_dialog(c),
                                        ).props(f'flat dense no-caps aria-label="View materials for {html.escape(course.name, quote=True)}"').classes(
                                            "course-materials-btn text-xs font-semibold text-secondary-navy hover:text-primary-navy px-2 py-1"
                                        )

                                        def make_ask_handler(c_id=course.id):
                                            return lambda: ui.navigate.to(f"/chat?kb_id={c_id}")

                                        ui.button(
                                            "Ask in Course",
                                            icon="chat",
                                            on_click=make_ask_handler(),
                                        ).props("no-caps dense").classes(
                                            "bg-surface-navy text-inverted font-bold px-3 py-1.5 rounded text-xs hover:bg-opacity-90"
                                        )
                    else:
                        # Clean editorial table for Administrator Course Management
                        with ui.column().classes("w-full bg-surface-elevated border border-subtle rounded-lg overflow-hidden shadow-none"):
                            with ui.row().classes(
                                "w-full px-5 py-3 border-b border-subtle text-xs font-bold text-secondary-navy uppercase tracking-wider items-center justify-between bg-surface/30"
                            ):
                                ui.label("Course").classes("flex-1 min-w-[200px]")
                                ui.label("Materials").classes("w-32 text-center hidden sm:block")
                                ui.label("Status").classes("w-28 text-center hidden md:block")
                                ui.label("Actions").classes("w-40 text-right")

                            for idx, course in enumerate(filtered):
                                is_last = idx == len(filtered) - 1
                                border_b = "" if is_last else "border-b border-subtle"
                                with ui.row().classes(
                                    f"w-full px-5 py-3.5 items-center justify-between hover:bg-surface/50 transition-colors {border_b} gap-4"
                                ):
                                    with ui.column().classes("flex-1 min-w-[200px] gap-0.5"):
                                        with ui.row().classes("items-center gap-2"):
                                            ui.icon("school", size="16px").classes("text-gold shrink-0")
                                            ui.label(course.name).classes(
                                                "text-sm font-bold text-primary-navy font-editorial truncate"
                                            ).props(f'title="{html.escape(course.name, quote=True)}"')
                                        if course.description:
                                            ui.label(course.description).classes(
                                                "text-xs text-secondary-navy line-clamp-1 pl-6"
                                            )

                                    with ui.row().classes("w-32 justify-center hidden sm:flex"):
                                        ui.label(format_document_count(course.document_count)).classes(
                                            "text-xs font-medium text-primary-navy bg-gold-light/60 px-2.5 py-0.5 rounded border border-gold/40 shrink-0 font-sans"
                                        )

                                    with ui.row().classes("w-28 justify-center hidden md:flex"):
                                        is_active = getattr(course, "is_active", True)
                                        if is_active:
                                            ui.label("Active").classes(
                                                "text-[10px] font-mono uppercase tracking-wider text-green-700 bg-green-50 px-2 py-0.5 rounded border border-green-200"
                                            )
                                        else:
                                            ui.label("Inactive").classes(
                                                "text-[10px] font-mono uppercase tracking-wider text-secondary-navy bg-surface px-2 py-0.5 rounded border border-subtle"
                                            )

                                    with ui.row().classes("w-40 justify-end items-center gap-2 shrink-0"):
                                        ui.button(
                                            "Documents",
                                            icon="folder_open",
                                            on_click=lambda c_id=course.id: ui.navigate.to(f"/documents?kb_id={c_id}"),
                                        ).props("outline no-caps dense").classes(
                                            "text-xs font-semibold text-primary-navy border border-subtle hover:bg-surface px-2.5 py-1"
                                        )
                                        ui.button(
                                            icon="chat",
                                            on_click=lambda c_id=course.id: ui.navigate.to(f"/chat?kb_id={c_id}"),
                                        ).props('flat round dense aria-label="Course Test Assistant"').classes(
                                            "text-secondary-navy hover:text-primary-navy"
                                        ).tooltip("Test Assistant in Course")

            # ------------------------------------------------------------------
            # Course Loading
            # ------------------------------------------------------------------
            def load_courses(force_refresh: bool = False) -> None:
                nonlocal cached_courses
                if not cached_courses or force_refresh:
                    catalogue_container.clear()
                    with catalogue_container:
                        with ui.row().classes("w-full py-12 justify-center items-center gap-2"):
                            ui.spinner("dots", size="md", color="primary")
                            ui.label("Loading courses...").classes("text-sm text-secondary-navy font-medium")
                    try:
                        cached_courses = api_client.get_knowledge_bases()
                    except Exception as err:
                        catalogue_container.clear()
                        with catalogue_container:
                            render_alert(normalize_error(err, context="course"), "negative")
                            with ui.row().classes("w-full justify-center mt-4"):
                                ui.button("Retry", icon="refresh", on_click=lambda: load_courses(True)).props(
                                    "outline no-caps dense"
                                ).classes("text-xs font-semibold text-primary-navy border border-subtle")
                        return

                render_catalogue()

            def on_search_change(e: Any) -> None:
                nonlocal search_query
                search_query = e.value or ""
                render_catalogue()

            search_input.on_value_change(on_search_change)
            load_courses()
