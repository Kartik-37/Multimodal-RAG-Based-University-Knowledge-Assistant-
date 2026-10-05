"""
Courses Management & Catalog Page.

Provides a modern academic course directory with role-tailored interaction:
- STUDENTS: Clean course dashboard with top accent bars, metadata summaries, and direct 'Enter Classroom' actions.
- ADMINISTRATORS: Course provisioning, document lifecycle metrics, and management entry points.
- Professional breadcrumbs (Home > Courses) and modern minimalist search & filtering.
"""

from typing import Any

from nicegui import ui

from backend.app.core.permissions import Permission
from frontend.client.api_client import api_client
from frontend.components.layout import has_admin_permission, page_layout
from frontend.components.source_viewer import open_source_viewer
from frontend.components.ui_kit import render_alert, render_empty_state
from frontend.state.app_state import state


def get_course_accent_color(course_name: str) -> str:
    """Return colored accent gradient/hex based on course name."""
    nl = course_name.lower()
    if "bca" in nl:
        return "#2563EB"  # Sapphire Blue
    elif "architecture" in nl or "computer" in nl:
        return "#10B981"  # Emerald
    elif "regulation" in nl or "policy" in nl:
        return "#6366F1"  # Indigo
    else:
        palettes = ["#2563EB", "#10B981", "#6366F1", "#0891B2", "#F59E0B", "#8B5CF6"]
        return palettes[sum(ord(ch) for ch in course_name) % len(palettes)]


def register_knowledge_bases_page() -> None:
    """Register /knowledge-bases route with NiceGUI."""

    @ui.page("/knowledge-bases")
    def knowledge_bases_page() -> None:
        user = state.current_user
        can_create_course = has_admin_permission(user, Permission.COURSE_CREATE)
        is_student = user is None or user.role == "STUDENT"

        with page_layout(
            title="Course Knowledge Bases",
            subtitle="Explore published academic courses, learning modules, and verified reference documents.",
            active_route="/knowledge-bases",
            require_auth=True,
            breadcrumbs=[("Home", "/dashboard"), ("Courses", None)],
            show_back=False,
        ):

            # ------------------------------------------------------------------
            # Create Course Dialog (Admin Only)
            # ------------------------------------------------------------------
            with (
                ui.dialog() as create_dialog,
                ui.card().classes(
                    "w-full max-w-md p-7 bg-white border border-slate-200/90 rounded-2xl shadow-xl"
                ),
            ):
                with ui.row().classes("w-full items-center justify-between mb-1"):
                    with ui.row().classes("items-center gap-2"):
                        with ui.element("div").classes(
                            "w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center"
                        ):
                            ui.icon("school", size="18px")
                        ui.label("Create New Course").classes(
                            "text-lg font-bold text-slate-900 font-sans"
                        )
                    ui.button(icon="close", on_click=create_dialog.close).props(
                        "flat round dense"
                    ).classes("text-slate-400 hover:text-slate-700")

                ui.label(
                    "Provision a new university course to host syllabi, lecture notes, and learning materials."
                ).classes("text-xs text-slate-500 mb-5 leading-relaxed")

                dialog_error = ui.column().classes("w-full mb-2")

                with ui.column().classes("w-full gap-1 mb-4"):
                    ui.label("Course Name *").classes("text-xs font-semibold text-slate-700")
                    name_input = (
                        ui.input(
                            placeholder="e.g. BCA-301 Computer Architecture",
                        )
                        .props("outlined dense")
                        .classes("w-full minimalist-input")
                    )

                with ui.column().classes("w-full gap-1 mb-6"):
                    ui.label("Description / Subject").classes(
                        "text-xs font-semibold text-slate-700"
                    )
                    desc_input = (
                        ui.textarea(
                            placeholder="Brief overview of course syllabus, subject matter, or semester.",
                        )
                        .props("outlined dense rows=3")
                        .classes("w-full")
                    )

                def handle_create() -> None:
                    dialog_error.clear()
                    name = (name_input.value or "").strip()
                    desc = (desc_input.value or "").strip()
                    if not name:
                        with dialog_error:
                            render_alert("Course name is required.", "warning")
                        return

                    try:
                        new_course = api_client.create_knowledge_base(name, desc)
                        ui.notify(f"Created course '{new_course.name}'", type="positive")
                        create_dialog.close()
                        name_input.value = ""
                        desc_input.value = ""
                        refresh_view()
                    except ValueError as err:
                        with dialog_error:
                            render_alert(str(err), "negative")

                with ui.row().classes("w-full justify-end gap-2 pt-3 border-t border-slate-100"):
                    ui.button("Cancel", on_click=create_dialog.close).props("flat no-caps").classes(
                        "text-xs font-medium text-slate-600 px-3 py-2"
                    )
                    ui.button("Create Course", icon="check", on_click=handle_create).props(
                        "no-caps"
                    ).classes(
                        "text-xs font-semibold px-4 py-2 !bg-slate-900 hover:!bg-slate-800 !text-white rounded-xl shadow-xs transition-colors"
                    )

            # State for Search, Filter & Sort
            filter_state = {
                "query": "",
                "category": "ALL",
                "sort": "NAME",
            }
            all_summaries: list[Any] = []

            # ------------------------------------------------------------------
            # Top Action & Filter Bar (Persistent, Never Re-created on Type)
            # ------------------------------------------------------------------
            filter_card = ui.card().classes(
                "academic-card w-full p-4 bg-white border border-slate-200/90 rounded-2xl shadow-xs gap-3.5 my-2"
            )
            with filter_card:
                with ui.row().classes(
                    "w-full items-center justify-between gap-4 flex-wrap md:flex-nowrap"
                ):
                    # Search Box with Quick Icon
                    with ui.row().classes("items-center gap-2 flex-1 min-w-[240px]"):
                        s_box = (
                            ui.input(
                                placeholder="Search courses by name, subject, or code...",
                            )
                            .props("outlined dense clearable")
                            .classes("w-full minimalist-input")
                        )

                    # Sort Selector and Create Button
                    with ui.row().classes("items-center gap-3 shrink-0"):
                        sort_select = ui.select(
                            options={
                                "NAME": "Course Name (A-Z)",
                                "DOCS": "Most Documents",
                                "RECENT": "Recently Created",
                            },
                            value="NAME",
                        ).props("outlined dense options-dense").classes(
                            "w-48 minimalist-select"
                        )

                        if can_create_course:
                            ui.button(
                                "Create Course",
                                icon="add",
                                on_click=create_dialog.open,
                            ).props("no-caps dense").classes(
                                "text-xs font-semibold px-4 py-2 !bg-slate-900 hover:!bg-slate-800 !text-white rounded-xl shadow-xs shrink-0 transition-colors"
                            )

                # Filter Chips Row
                chips_row = ui.row().classes(
                    "w-full items-center gap-2 pt-3 border-t border-slate-100 flex-wrap"
                )

            # Dynamic Container for Course Cards Only
            cards_container = ui.row().classes("w-full gap-5 items-stretch flex-wrap my-2")

            def render_chips() -> None:
                chips_row.clear()
                with chips_row:
                    ui.label("Filter:").classes("text-xs font-medium text-slate-400 mr-1")
                    chip_options = [
                        ("ALL", f"All Courses ({len(all_summaries)})"),
                        ("ACTIVE", "Active Materials"),
                        ("INDEXING", "Indexing in Progress"),
                        ("ATTENTION", "Needs Attention"),
                        ("EMPTY", "Empty Courses"),
                    ]
                    for c_key, c_label in chip_options:
                        is_active_chip = filter_state["category"] == c_key
                        chip_cls = "text-xs px-3.5 py-1.5 rounded-full transition-all "
                        if is_active_chip:
                            chip_cls += "!bg-slate-900 !text-white font-semibold shadow-xs"
                        else:
                            chip_cls += "!text-slate-600 !bg-slate-100/90 hover:!bg-slate-200/90 hover:!text-slate-900"
                        ui.button(
                            c_label,
                            on_click=lambda k=c_key: on_category_change(k),
                        ).props("flat dense no-caps").classes(chip_cls)

            def render_cards_grid() -> None:
                cards_container.clear()

                # Apply Search
                q = filter_state["query"].lower().strip()
                res = list(all_summaries)
                if q:
                    res = [
                        c
                        for c in res
                        if q in c.name.lower() or (c.description and q in c.description.lower())
                    ]

                # Apply Category Filter
                cat = filter_state["category"]
                if cat == "ACTIVE":
                    res = [c for c in res if c.active_documents > 0]
                elif cat == "ATTENTION":
                    res = [c for c in res if c.failed_documents > 0]
                elif cat == "INDEXING":
                    res = [c for c in res if c.indexing_documents > 0]
                elif cat == "EMPTY":
                    res = [c for c in res if c.total_documents == 0]

                # Apply Sorting
                sort_mode = filter_state["sort"]
                if sort_mode == "DOCS":
                    res = sorted(res, key=lambda c: c.total_documents, reverse=True)
                elif sort_mode == "RECENT":
                    res = sorted(res, key=lambda c: c.created_at, reverse=True)
                else:  # NAME
                    res = sorted(res, key=lambda c: c.name.lower())

                with cards_container:
                    # Empty State
                    if not res:
                        if filter_state["query"] or filter_state["category"] != "ALL":
                            render_empty_state(
                                icon="search_off",
                                title="No Matching Courses",
                                description="No courses match the active search term or filter.",
                                action_label="Clear Filters",
                                on_action=clear_all_filters,
                            )
                        else:
                            render_empty_state(
                                icon="menu_book",
                                title="No Courses Available",
                                description="No university courses are registered in the knowledge platform yet.",
                                action_label="Create Course" if can_create_course else None,
                                on_action=create_dialog.open if can_create_course else None,
                            )
                        return
                    for c in res:
                        with ui.card().classes(
                            "academic-card modern-course-card w-full md:w-[calc(50%-0.625rem)] lg:w-[calc(33.333%-0.85rem)] p-0 bg-white border border-slate-200/80 rounded-2xl shadow-xs hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 flex flex-col justify-between overflow-hidden"
                        ):
                            # Colored accent bar at top of card
                            bar_color = get_course_accent_color(c.name)
                            ui.element("div").classes("w-full h-1.5 shrink-0").style(
                                f"background-color: {bar_color};"
                            )

                            # Card Body
                            with ui.column().classes("w-full p-5 gap-3.5 flex-1"):
                                # Header: Title & Status Badge
                                with ui.row().classes("w-full justify-between items-start gap-2"):
                                    ui.label(c.name).classes(
                                        "text-base font-bold text-slate-900 tracking-tight leading-snug line-clamp-1 font-sans"
                                    )
                                    if c.failed_documents > 0:
                                        with ui.element("div").classes(
                                            "inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-rose-50 border border-rose-200 text-rose-700 text-[10px] font-mono font-bold shrink-0"
                                        ):
                                            ui.icon("error_outline", size="12px")
                                            ui.label(f"{c.failed_documents} Needs Attention")
                                    elif c.indexing_documents > 0:
                                        with ui.element("div").classes(
                                            "inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-50 border border-blue-200 text-blue-700 text-[10px] font-mono font-bold shrink-0"
                                        ):
                                            ui.icon("sync", size="12px").classes("animate-spin")
                                            ui.label(f"{c.indexing_documents} Indexing")
                                    elif c.active_documents > 0:
                                        with ui.element("div").classes(
                                            "inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-[10px] font-mono font-medium shrink-0"
                                        ):
                                            ui.icon("check_circle", size="12px")
                                            ui.label("Active")

                                # Description
                                ui.label(
                                    c.description
                                    if c.description
                                    else "Official university course materials and knowledge repository."
                                ).classes("text-xs text-slate-500 line-clamp-2 leading-relaxed")

                                # Document Previews (interactive source viewer pills)
                                if c.document_previews:
                                    with ui.column().classes("w-full gap-1.5 pt-1"):
                                        for doc in c.document_previews[:3]:
                                            is_pdf = doc.filename.lower().endswith(".pdf")
                                            doc_icon = "picture_as_pdf" if is_pdf else "description"
                                            icon_color = (
                                                "text-rose-500"
                                                if is_pdf
                                                else "text-slate-400 group-hover:text-blue-600"
                                            )
                                            with (
                                                ui.row()
                                                .classes(
                                                    "w-full items-center justify-between py-2 px-3 bg-slate-50/80 hover:bg-blue-50/80 rounded-xl border border-slate-100 hover:border-blue-200/80 text-xs cursor-pointer transition-all group"
                                                )
                                                .tooltip(
                                                    f"Click to read '{doc.filename}' in Source Viewer"
                                                )
                                                .on(
                                                    "click",
                                                    lambda d=doc, crs=c: open_source_viewer(
                                                        document_id=str(d.id),
                                                        document_name=d.filename,
                                                        kb_id=str(crs.id),
                                                        course_name=crs.name,
                                                    ),
                                                )
                                            ):
                                                with ui.row().classes(
                                                    "items-center gap-2 min-w-0 flex-1"
                                                ):
                                                    ui.icon(doc_icon, size="16px").classes(
                                                        f"{icon_color} shrink-0 transition-colors"
                                                    )
                                                    ui.label(doc.filename).classes(
                                                        "font-medium text-slate-700 group-hover:text-blue-900 truncate max-w-[170px] sm:max-w-[195px]"
                                                    )
                                                with ui.row().classes(
                                                    "items-center gap-1.5 shrink-0"
                                                ):
                                                    with ui.element("div").classes(
                                                        "text-[9px] font-mono text-slate-500 bg-slate-200/60 px-1.5 py-0.5 rounded"
                                                    ):
                                                        ui.label(doc.file_type.upper())
                                                    ui.icon("visibility", size="13px").classes(
                                                        "text-slate-400 group-hover:text-blue-600 transition-colors"
                                                    )
                                        remaining = c.total_documents - min(
                                            3, len(c.document_previews)
                                        )
                                        if remaining > 0:

                                            def make_more_handler(crs_id=c.id, crs_name=c.name):
                                                def _open_all():
                                                    try:
                                                        all_docs = api_client.get_documents(
                                                            str(crs_id)
                                                        )
                                                    except Exception:
                                                        all_docs = []
                                                    with (
                                                        ui.dialog() as more_dialog,
                                                        ui.card().classes(
                                                            "w-full max-w-md p-6 bg-white rounded-2xl shadow-xl border border-slate-200/90"
                                                        ),
                                                    ):
                                                        with ui.row().classes(
                                                            "w-full items-center justify-between pb-3 border-b border-slate-100"
                                                        ):
                                                            with ui.row().classes(
                                                                "items-center gap-2"
                                                            ):
                                                                ui.icon(
                                                                    "menu_book", size="20px"
                                                                ).classes("text-blue-600")
                                                                ui.label(
                                                                    f"{crs_name} Materials"
                                                                ).classes(
                                                                    "text-sm font-bold text-slate-900 font-sans"
                                                                )
                                                            ui.button(
                                                                icon="close",
                                                                on_click=more_dialog.close,
                                                            ).props("flat round dense").classes(
                                                                "text-slate-400 hover:text-slate-700"
                                                            )
                                                        if not all_docs:
                                                            ui.label(
                                                                "No additional materials available."
                                                            ).classes("text-xs text-slate-500 py-3")
                                                        else:
                                                            with ui.column().classes(
                                                                "w-full gap-2 py-3 max-h-72 overflow-y-auto"
                                                            ):
                                                                for d in all_docs:
                                                                    is_p = (
                                                                        d.filename.lower().endswith(
                                                                            ".pdf"
                                                                        )
                                                                    )
                                                                    with (
                                                                        ui.row()
                                                                        .classes(
                                                                            "w-full items-center justify-between p-2.5 rounded-xl bg-slate-50/80 hover:bg-blue-50/80 border border-slate-100 cursor-pointer group text-xs transition-colors"
                                                                        )
                                                                        .on(
                                                                            "click",
                                                                            lambda m_doc=d: [
                                                                                more_dialog.close(),
                                                                                open_source_viewer(
                                                                                    document_id=str(
                                                                                        m_doc.id
                                                                                    ),
                                                                                    document_name=m_doc.filename,
                                                                                    kb_id=str(
                                                                                        crs_id
                                                                                    ),
                                                                                    course_name=crs_name,
                                                                                ),
                                                                            ],
                                                                        )
                                                                    ):
                                                                        with ui.row().classes(
                                                                            "items-center gap-2 min-w-0"
                                                                        ):
                                                                            ui.icon(
                                                                                "picture_as_pdf"
                                                                                if is_p
                                                                                else "description",
                                                                                size="16px",
                                                                            ).classes(
                                                                                "text-rose-500"
                                                                                if is_p
                                                                                else "text-slate-400"
                                                                            )
                                                                            ui.label(
                                                                                d.filename
                                                                            ).classes(
                                                                                "font-medium text-slate-800 group-hover:text-blue-900 truncate max-w-[260px]"
                                                                            )
                                                                        with ui.element(
                                                                            "div"
                                                                        ).classes(
                                                                            "text-[9px] font-mono text-slate-500 bg-slate-200/60 px-1.5 py-0.5 rounded"
                                                                        ):
                                                                            ui.label(
                                                                                d.file_type.upper()
                                                                            )
                                                    more_dialog.open()

                                                return _open_all

                                            ui.button(
                                                f"+ {remaining} more material(s)",
                                                on_click=make_more_handler(),
                                            ).props("flat dense no-caps").classes(
                                                "text-[11px] text-blue-600 hover:text-blue-800 font-semibold pl-1"
                                            )

                            # Card Bottom: Clean metadata row + Action buttons
                            with ui.column().classes("w-full px-5 pb-5 pt-0 gap-3 mt-auto"):
                                # Clean metadata row
                                with ui.row().classes(
                                    "w-full items-center justify-between text-xs pt-3 border-t border-slate-100"
                                ):
                                    doc_cnt_text = (
                                        f"{c.total_documents} document"
                                        if c.total_documents == 1
                                        else f"{c.total_documents} documents"
                                    )
                                    active_cnt_text = f"{c.active_documents} active"
                                    ui.label(f"{doc_cnt_text} • {active_cnt_text}").classes(
                                        "text-[11px] text-slate-400 font-normal"
                                    )
                                    ui.label(f"Created {c.created_at[:10]}").classes(
                                        "text-[11px] text-slate-400 font-mono"
                                    )

                                # Buttons: Students see 'Ask Questions' & 'Enter Classroom'; Admins see 'Admin Chat' & 'Manage Documents'
                                with ui.row().classes("w-full justify-between items-center"):
                                    if is_student:
                                        with ui.row().classes("w-full justify-between items-center pt-1"):
                                            ui.button(
                                                "Ask Questions",
                                                icon="chat",
                                                on_click=lambda course_id=c.id: ui.navigate.to(
                                                    f"/chat?kb_id={course_id}"
                                                ),
                                            ).props("no-caps dense").classes(
                                                "px-4 py-2 text-xs font-semibold !bg-blue-600 hover:!bg-blue-700 !text-white rounded-xl shadow-xs transition-all"
                                            )
                                            ui.button(
                                                "Enter Classroom",
                                                icon="arrow_forward",
                                                on_click=lambda course_id=c.id: ui.navigate.to(
                                                    f"/chat?kb_id={course_id}"
                                                ),
                                            ).props("flat dense no-caps").classes(
                                                "text-xs text-blue-700 font-semibold hover:bg-blue-50 px-3 py-1.5 rounded-lg"
                                            )
                                    else:
                                        with ui.row().classes("w-full justify-between items-center pt-1"):
                                            ui.button(
                                                "Admin Chat",
                                                icon="chat",
                                                on_click=lambda course_id=c.id: ui.navigate.to(
                                                    f"/chat?kb_id={course_id}"
                                                ),
                                            ).props("flat dense no-caps").classes(
                                                "text-xs text-slate-700 hover:text-blue-700 px-3 py-1.5 font-semibold rounded-lg hover:bg-blue-50"
                                            )
                                            ui.button(
                                                "Manage Documents",
                                                icon="folder_open",
                                                on_click=lambda course_id=c.id: ui.navigate.to(
                                                    f"/documents?kb_id={course_id}"
                                                ),
                                            ).props("no-caps dense").classes(
                                                "text-xs px-3.5 py-1.5 font-semibold !bg-blue-600 hover:!bg-blue-700 !text-white rounded-xl shadow-xs transition-colors"
                                            )

            def on_search(val: str | None) -> None:
                filter_state["query"] = val or ""
                render_cards_grid()

            def on_category_change(cat: str) -> None:
                filter_state["category"] = cat
                render_chips()
                render_cards_grid()

            def on_sort_change(s: str) -> None:
                filter_state["sort"] = s
                render_cards_grid()

            def clear_all_filters() -> None:
                s_box.value = ""
                sort_select.value = "NAME"
                filter_state["query"] = ""
                filter_state["category"] = "ALL"
                filter_state["sort"] = "NAME"
                render_chips()
                render_cards_grid()

            def refresh_view() -> None:
                nonlocal all_summaries
                try:
                    all_summaries = api_client.get_course_summaries()
                except ValueError as err:
                    cards_container.clear()
                    with cards_container:
                        render_alert(f"Unable to load courses. {err}", "negative")
                    return
                render_chips()
                render_cards_grid()

            # Wire up reactive search & sort without destroying input DOM
            s_box.on_value_change(lambda e: on_search(e.value))
            sort_select.on_value_change(lambda e: on_sort_change(e.value))

            refresh_view()
