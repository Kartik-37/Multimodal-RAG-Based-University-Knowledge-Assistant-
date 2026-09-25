"""
Courses Management Page.

Provides complete university course management:
- Lists authorized university courses with aggregated document metrics and file previews.
- Search, filter (All, Active, Needs Attention, Indexing, Empty), and sort.
- Administrators can provision new courses and jump directly to course document management.
- Uses N+1-safe summaries endpoint to retrieve course document counts and previews.
"""

from nicegui import ui

from backend.app.core.permissions import Permission
from frontend.client.api_client import api_client
from frontend.components.layout import has_admin_permission, page_layout
from frontend.components.ui_kit import render_alert, render_empty_state
from frontend.state.app_state import state


def register_knowledge_bases_page() -> None:
    """Register /knowledge-bases route with NiceGUI."""

    @ui.page("/knowledge-bases")
    def knowledge_bases_page() -> None:
        with page_layout(
            title="Course Knowledge Bases",
            subtitle="Organize university courses, subject materials, and document versioning.",
            active_route="/knowledge-bases",
            require_auth=True,
        ):
            user = state.current_user
            can_create_course = has_admin_permission(user, Permission.COURSE_CREATE)

            # Dynamic content container
            content_container = ui.column().classes("w-full gap-5")

            # ------------------------------------------------------------------
            # Create Course Dialog (Admin Only)
            # ------------------------------------------------------------------
            with (
                ui.dialog() as create_dialog,
                ui.card().classes(
                    "w-full max-w-md p-6 bg-white border border-slate-200 rounded-lg shadow-md"
                ),
            ):
                ui.label("Create New Course").classes("text-lg font-bold text-slate-900 mb-1")
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
                        .classes("w-full")
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
                        "color=primary no-caps"
                    ).classes("text-sm font-medium px-4")

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

                # Apply Category Filter (Section 12: All, Active, Needs Attention, Indexing, Empty)
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

                # Top Action & Filter Bar
                with ui.card().classes(
                    "w-full p-4 bg-white border border-slate-200 rounded-lg shadow-xs gap-3"
                ):
                    with ui.row().classes("w-full justify-between items-center gap-3 flex-wrap"):
                        # Search Box
                        with ui.row().classes("items-center gap-2 flex-1 min-w-[240px] max-w-md"):
                            s_box = (
                                ui.input(
                                    placeholder="Search courses by name or subject...",
                                    value=filter_state["query"],
                                )
                                .props("outlined dense clearable")
                                .classes("w-full text-xs")
                            )
                            s_box.on("input", lambda e: on_search(e.value))

                        # Sort Selector
                        with ui.row().classes("items-center gap-2"):
                            ui.label("Sort:").classes("text-xs font-semibold text-slate-500")
                            ui.select(
                                options={
                                    "NAME": "Course Name (A-Z)",
                                    "DOCS": "Most Documents",
                                    "RECENT": "Recently Created",
                                },
                                value=filter_state["sort"],
                                on_change=lambda e: on_sort_change(e.value),
                            ).props("outlined dense options-dense").classes("text-xs min-w-[170px]")

                        if can_create_course:
                            ui.button(
                                "Create Course",
                                icon="add",
                                on_click=create_dialog.open,
                            ).props("color=primary no-caps dense").classes(
                                "text-xs font-medium px-3 py-1.5"
                            )

                    # Filter Chips Row
                    with ui.row().classes("w-full items-center gap-2 pt-2 border-t border-slate-100 flex-wrap"):
                        ui.label("Filter:").classes("text-xs font-semibold text-slate-400 mr-1")
                        chip_options = [
                            ("ALL", f"All Courses ({len(summaries)})"),
                            ("ACTIVE", "Active Materials"),
                            ("INDEXING", "Indexing in Progress"),
                            ("ATTENTION", "Needs Attention"),
                            ("EMPTY", "Empty Courses"),
                        ]
                        for c_key, c_label in chip_options:
                            is_active_chip = filter_state["category"] == c_key
                            chip_cls = "text-xs px-2.5 py-1 rounded transition-colors "
                            if is_active_chip:
                                chip_cls += "bg-blue-600 text-white font-semibold shadow-xs"
                            else:
                                chip_cls += "text-slate-600 hover:bg-slate-100"
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

                # Course Cards Grid
                with ui.row().classes("w-full gap-4 items-stretch"):
                    for c in res:
                        with ui.card().classes(
                            "w-full md:w-[calc(50%-0.5rem)] p-5 bg-white border border-slate-200 hover:border-blue-300 rounded-lg shadow-xs transition-all flex flex-col justify-between"
                        ):
                            with ui.column().classes("w-full gap-3"):
                                # Header: Name and status badge
                                with ui.row().classes("w-full justify-between items-start gap-2"):
                                    with ui.row().classes("items-center gap-2.5 min-w-0"):
                                        with ui.element("div").classes(
                                            "w-9 h-9 rounded-lg bg-blue-600/10 text-blue-700 flex items-center justify-center font-bold text-sm shrink-0"
                                        ):
                                            ui.icon("school", size="xs")
                                        ui.label(c.name).classes(
                                            "text-base font-bold text-slate-900 tracking-tight truncate"
                                        )

                                    if c.failed_documents > 0:
                                        ui.badge(f"{c.failed_documents} Failed", color="rose-700").classes("text-[10px] font-bold")
                                    elif c.indexing_documents > 0:
                                        ui.badge(f"{c.indexing_documents} Indexing", color="blue-700").classes("text-[10px] font-bold")
                                    elif c.active_documents > 0:
                                        ui.badge(f"{c.active_documents} Active", color="emerald-700").classes("text-[10px] font-bold")

                                # Description
                                ui.label(
                                    c.description
                                    if c.description
                                    else "Official university course materials and knowledge repository."
                                ).classes("text-xs text-slate-600 line-clamp-2 leading-relaxed")

                                # Operational Metrics Row (Section 12)
                                with ui.row().classes(
                                    "w-full items-center gap-3 py-2 px-3 bg-slate-50 rounded border border-slate-100 text-xs flex-wrap"
                                ):
                                    ui.label(f"{c.total_documents} documents").classes("font-semibold text-slate-800")
                                    ui.label("•").classes("text-slate-300")
                                    ui.label(f"{c.active_documents} active").classes("text-emerald-700 font-medium")
                                    if c.indexing_documents > 0:
                                        ui.label("•").classes("text-slate-300")
                                        ui.label(f"{c.indexing_documents} indexing").classes("text-blue-700 font-medium")
                                    if c.failed_documents > 0:
                                        ui.label("•").classes("text-slate-300")
                                        ui.label(f"{c.failed_documents} needs attention").classes("text-rose-700 font-medium")

                                # Document Previews
                                with ui.column().classes("w-full gap-1.5 mt-1"):
                                    if not c.document_previews:
                                        ui.label("No documents uploaded yet.").classes(
                                            "text-[11px] text-slate-400 italic"
                                        )
                                    else:
                                        for doc in c.document_previews[:3]:
                                            with ui.row().classes(
                                                "w-full items-center justify-between py-1 px-2 hover:bg-slate-50 rounded text-xs transition-colors"
                                            ):
                                                with ui.row().classes(
                                                    "items-center gap-1.5 truncate max-w-[240px]"
                                                ):
                                                    ui.icon("description", size="xs").classes("text-slate-400")
                                                    ui.label(doc.filename).classes(
                                                        "font-medium text-slate-700 truncate"
                                                    )
                                                with ui.row().classes("items-center gap-1"):
                                                    ui.badge(
                                                        doc.file_type.upper(), color="slate-600"
                                                    ).classes("text-[9px]")
                                                    if doc.is_active:
                                                        ui.badge(
                                                            "ACTIVE", color="emerald-700"
                                                        ).classes("text-[9px] font-bold")

                                        remaining = c.total_documents - min(3, len(c.document_previews))
                                        if remaining > 0:
                                            ui.label(f"+ {remaining} more document(s)").classes(
                                                "text-[11px] text-blue-600 font-medium pl-2"
                                            )

                            # Footer Actions (Section 12: Open, Manage Documents, Chat)
                            with ui.row().classes(
                                "w-full justify-between items-center pt-3 mt-3 border-t border-slate-100 text-xs text-slate-500"
                            ):
                                ui.label(f"Created {c.created_at[:10]}").classes("font-mono text-[11px]")
                                with ui.row().classes("items-center gap-2"):
                                    ui.button(
                                        "Chat",
                                        icon="chat",
                                        on_click=lambda course_id=c.id: ui.navigate.to(
                                            f"/chat?kb_id={course_id}"
                                        ),
                                    ).props("flat dense no-caps color=grey-7").classes("text-xs")

                                    ui.button(
                                        "Manage Documents",
                                        icon="folder_open",
                                        on_click=lambda course_id=c.id: ui.navigate.to(
                                            f"/documents?kb_id={course_id}"
                                        ),
                                    ).props("color=primary dense no-caps").classes(
                                        "text-xs px-3 py-1 font-semibold"
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
