"""
Courses Management & Catalog Page.

Provides a modern academic course directory with role-tailored interaction:
- STUDENTS: Clean course dashboard with top accent bars, metadata summaries, and direct 'Enter Classroom' actions.
- ADMINISTRATORS: Course provisioning, document lifecycle metrics, and management entry points.
- Professional breadcrumbs (Home > Courses) and modern minimalist search & filtering.
"""

from nicegui import ui

from backend.app.core.permissions import Permission
from frontend.client.api_client import api_client
from frontend.components.layout import has_admin_permission, page_layout
from frontend.components.ui_kit import render_alert, render_empty_state
from frontend.state.app_state import state


def get_course_accent_color(course_name: str) -> str:
    """Return colored accent bar hex based on course name."""
    nl = course_name.lower()
    if "bca" in nl:
        return "#002147"  # Oxford Blue
    elif "architecture" in nl or "computer" in nl:
        return "#059669"  # Emerald / Green
    elif "regulation" in nl or "policy" in nl:
        return "#4f46e5"  # Indigo
    else:
        palettes = ["#002147", "#059669", "#4f46e5", "#0891b2", "#d97706", "#7c3aed"]
        return palettes[sum(ord(ch) for ch in course_name) % len(palettes)]


def register_knowledge_bases_page() -> None:
    """Register /knowledge-bases route with NiceGUI."""

    @ui.page("/knowledge-bases")
    def knowledge_bases_page() -> None:
        user = state.current_user
        can_create_course = has_admin_permission(user, Permission.COURSE_CREATE)
        is_student = (user is None or user.role == "STUDENT")

        with page_layout(
            title="Course Knowledge Bases",
            subtitle="Explore published academic courses, learning modules, and verified reference documents.",
            active_route="/knowledge-bases",
            require_auth=True,
            breadcrumbs=[("Home", "/dashboard"), ("Courses", None)],
            show_back=False,
        ):
            # Dynamic content container with generous vertical breathing room
            content_container = ui.column().classes("w-full gap-8 my-2")

            # ------------------------------------------------------------------
            # Create Course Dialog (Admin Only)
            # ------------------------------------------------------------------
            with (
                ui.dialog() as create_dialog,
                ui.card().classes(
                    "w-full max-w-md p-6 bg-white border border-slate-200 rounded-xl shadow-md"
                ),
            ):
                ui.label("Create New Course").classes("text-lg font-bold text-slate-900 font-inter mb-1")
                ui.label(
                    "Provision a new university course to host syllabi, lecture notes, and learning materials."
                ).classes("text-xs text-slate-500 mb-4")

                dialog_error = ui.column().classes("w-full mb-2")

                with ui.column().classes("w-full gap-1 mb-3"):
                    ui.label("Course Name *").classes("text-xs font-semibold text-slate-700")
                    name_input = (
                        ui.input(
                            placeholder="e.g. BCA-301 Computer Architecture",
                        )
                        .props("outlined dense")
                        .classes("w-full minimalist-input")
                    )

                with ui.column().classes("w-full gap-1 mb-5"):
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

                with ui.row().classes("w-full justify-end gap-2 pt-2 border-t border-slate-100"):
                    ui.button("Cancel", on_click=create_dialog.close).props("flat no-caps").classes(
                        "text-sm text-slate-600"
                    )
                    ui.button("Create Course", icon="check", on_click=handle_create).props(
                        "no-caps"
                    ).classes(
                        "text-sm font-semibold px-4 py-2 !bg-[#002147] hover:!bg-[#001833] !text-white rounded-lg shadow-xs"
                    )

            # ------------------------------------------------------------------
            # Page Renderer with Search, Filter & Sort
            # ------------------------------------------------------------------
            filter_state = {
                "query": "",
                "category": "ALL",
                "sort": "NAME",
            }

            def refresh_view() -> None:
                content_container.clear()
                with content_container:
                    render_content()

            def render_content() -> None:
                try:
                    summaries = api_client.get_course_summaries()
                except ValueError as err:
                    render_alert(f"Unable to load courses. {err}", "negative")
                    return

                # Apply Search
                q = filter_state["query"].lower().strip()
                res = summaries
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

                # Top Action & Filter Bar (Minimalist Border Style & Same Horizontal Line)
                with ui.card().classes(
                    "w-full p-4 bg-white border border-slate-200/90 rounded-xl shadow-xs gap-3"
                ):
                    with ui.row().classes("w-full items-center justify-between gap-4 flex-wrap md:flex-nowrap"):
                        # Search Box
                        with ui.row().classes("items-center gap-2 flex-1 min-w-[240px]"):
                            s_box = (
                                ui.input(
                                    placeholder="Search courses by name, subject, or code...",
                                    value=filter_state["query"],
                                )
                                .props("outlined dense clearable")
                                .classes("w-full minimalist-input")
                            )
                            s_box.on("input", lambda e: on_search(e.value))

                        # Sort Selector and Create Button on the same horizontal line
                        with ui.row().classes("items-center gap-3 shrink-0"):
                            ui.select(
                                options={
                                    "NAME": "Course Name (A-Z)",
                                    "DOCS": "Most Documents",
                                    "RECENT": "Recently Created",
                                },
                                value=filter_state["sort"],
                                on_change=lambda e: on_sort_change(e.value),
                            ).props("outlined dense options-dense").classes("w-48 minimalist-select")

                            if can_create_course:
                                ui.button(
                                    "Create Course",
                                    icon="add",
                                    on_click=create_dialog.open,
                                ).props("no-caps dense").classes(
                                    "text-xs font-semibold px-4 py-2 !bg-[#002147] hover:!bg-[#001833] !text-white rounded-lg shadow-xs shrink-0 transition-colors"
                                )

                    # Filter Chips Row
                    with ui.row().classes("w-full items-center gap-2 pt-3 border-t border-slate-100 flex-wrap"):
                        ui.label("Filter:").classes("text-xs font-medium text-slate-400 mr-1")
                        chip_options = [
                            ("ALL", f"All Courses ({len(summaries)})"),
                            ("ACTIVE", "Active Materials"),
                            ("INDEXING", "Indexing in Progress"),
                            ("ATTENTION", "Needs Attention"),
                            ("EMPTY", "Empty Courses"),
                        ]
                        for c_key, c_label in chip_options:
                            is_active_chip = filter_state["category"] == c_key
                            chip_cls = "text-xs px-3 py-1 rounded-full transition-all "
                            if is_active_chip:
                                chip_cls += "bg-[#002147] text-white font-semibold shadow-xs"
                            else:
                                chip_cls += "text-slate-600 bg-slate-100 hover:bg-slate-200"
                            ui.button(
                                c_label,
                                on_click=lambda k=c_key: on_category_change(k),
                            ).props("flat dense no-caps").classes(chip_cls)

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

                # Course Cards Grid (Modern Dashboard Cards with Colored Accent Bar & Subtle Hover)
                with ui.row().classes("w-full gap-5 items-stretch flex-wrap"):
                    for c in res:
                        with ui.card().classes(
                            "modern-course-card w-full md:w-[calc(50%-0.625rem)] lg:w-[calc(33.333%-0.85rem)] p-0 bg-white border border-slate-200/90 rounded-xl shadow-xs flex flex-col justify-between overflow-hidden"
                        ):
                            # Colored accent bar at top of card (e.g. BCA = Blue, Computer Architecture = Green)
                            bar_color = get_course_accent_color(c.name)
                            ui.element("div").classes("w-full h-1.5 shrink-0").style(f"background-color: {bar_color};")

                            # Card Body
                            with ui.column().classes("w-full p-5 gap-3 flex-1"):
                                # Header: Title & Status Badge
                                with ui.row().classes("w-full justify-between items-start gap-2"):
                                    ui.label(c.name).classes(
                                        "text-base font-bold text-slate-900 tracking-tight leading-snug line-clamp-1 font-inter"
                                    )
                                    if c.failed_documents > 0:
                                        ui.badge(f"{c.failed_documents} Needs Attention", color="rose-700").classes("text-[10px] font-bold shrink-0")
                                    elif c.indexing_documents > 0:
                                        ui.badge(f"{c.indexing_documents} Indexing", color="blue-700").classes("text-[10px] font-bold shrink-0")
                                    elif c.active_documents > 0:
                                        ui.badge("Active", color="emerald-700").classes("text-[10px] font-semibold shrink-0")

                                # Description
                                ui.label(
                                    c.description
                                    if c.description
                                    else "Official university course materials and knowledge repository."
                                ).classes("text-xs text-slate-500 line-clamp-2 leading-relaxed")

                                # Document Previews (compact, elegant pill list)
                                if c.document_previews:
                                    with ui.column().classes("w-full gap-1 pt-1"):
                                        for doc in c.document_previews[:2]:
                                            with ui.row().classes(
                                                "w-full items-center justify-between py-1 px-2.5 bg-slate-50 rounded-md border border-slate-100 text-xs"
                                            ):
                                                with ui.row().classes("items-center gap-1.5 min-w-0"):
                                                    ui.icon("description", size="14px").classes("text-slate-400 shrink-0")
                                                    ui.label(doc.filename).classes(
                                                        "font-medium text-slate-700 truncate max-w-[180px] sm:max-w-[210px]"
                                                    )
                                                ui.badge(doc.file_type.upper(), color="slate-500").classes("text-[9px] font-mono")
                                        remaining = c.total_documents - min(2, len(c.document_previews))
                                        if remaining > 0:
                                            ui.label(f"+ {remaining} more material(s)").classes(
                                                "text-[10px] text-slate-400 pl-1"
                                            )

                            # Card Bottom: Clean metadata row + Action buttons
                            with ui.column().classes("w-full px-5 pb-5 pt-0 gap-3 mt-auto"):
                                # Clean metadata row with small, light-grey text
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

                                # Buttons: Students see 'Enter Classroom'; Admins see 'Chat' & 'Manage Documents'
                                with ui.row().classes("w-full justify-between items-center"):
                                    if is_student:
                                        ui.button(
                                            "Enter Classroom",
                                            icon="arrow_forward",
                                            on_click=lambda course_id=c.id: ui.navigate.to(
                                                f"/chat?kb_id={course_id}"
                                            ),
                                        ).props("no-caps dense").classes(
                                            "w-full py-2.5 text-xs font-semibold !bg-[#002147] hover:!bg-[#001833] !text-white rounded-lg shadow-xs transition-colors justify-center"
                                        )
                                    else:
                                        with ui.row().classes("w-full justify-end items-center gap-2"):
                                            ui.button(
                                                "Chat",
                                                icon="chat",
                                                on_click=lambda course_id=c.id: ui.navigate.to(
                                                    f"/chat?kb_id={course_id}"
                                                ),
                                            ).props("flat dense no-caps").classes(
                                                "text-xs text-slate-600 hover:text-slate-900 px-2.5 py-1.5"
                                            )
                                            ui.button(
                                                "Manage Documents",
                                                icon="folder_open",
                                                on_click=lambda course_id=c.id: ui.navigate.to(
                                                    f"/documents?kb_id={course_id}"
                                                ),
                                            ).props("no-caps dense").classes(
                                                "text-xs px-3.5 py-1.5 font-semibold !bg-[#002147] hover:!bg-[#001833] !text-white rounded-lg shadow-xs"
                                            )

            def on_search(val: str | None) -> None:
                filter_state["query"] = val or ""
                refresh_view()

            def on_category_change(cat: str) -> None:
                filter_state["category"] = cat
                refresh_view()

            def on_sort_change(s: str) -> None:
                filter_state["sort"] = s
                refresh_view()

            def clear_all_filters() -> None:
                filter_state["query"] = ""
                filter_state["category"] = "ALL"
                filter_state["sort"] = "NAME"
                refresh_view()

            refresh_view()
