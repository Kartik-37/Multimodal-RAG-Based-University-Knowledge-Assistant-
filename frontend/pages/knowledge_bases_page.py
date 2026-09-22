"""
Courses Management Page.

Provides university course management:
- Lists authorized university courses with aggregated document metrics and file previews.
- Administrators can provision new courses and jump directly to course document management.
- Uses N+1-safe summaries endpoint to retrieve course document counts and previews.
- Strictly replaces dynamic content in a single container to guarantee rendering integrity.
"""

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.components.layout import page_layout
from frontend.components.ui_kit import render_alert, render_empty_state
from frontend.state.app_state import state


def register_knowledge_bases_page() -> None:
    """Register /knowledge-bases route with NiceGUI."""

    @ui.page("/knowledge-bases")
    def knowledge_bases_page() -> None:
        with page_layout(
            title="Courses",
            subtitle="Manage university courses and their learning material.",
            active_route="/knowledge-bases",
            require_auth=True,
        ):
            user = state.current_user
            is_admin = bool(user and user.role == "ADMIN")

            # Dynamic content container (Guarantees single view)
            content_container = ui.column().classes("w-full gap-4")

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
                            placeholder="e.g. Computer Architecture",
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
            # Page Renderer
            # ------------------------------------------------------------------
            search_query = {"text": ""}

            def refresh_view() -> None:
                content_container.clear()
                with content_container:
                    render_content()

            def render_content() -> None:
                # Retrieve course summaries with document metrics in a single request (zero N+1)
                summaries = api_client.get_course_summaries()

                # Filter by search text if provided
                filtered_courses = (
                    [
                        c
                        for c in summaries
                        if search_query["text"].lower() in c.name.lower()
                        or search_query["text"].lower() in c.description.lower()
                    ]
                    if search_query["text"]
                    else summaries
                )

                # Action Bar
                with ui.row().classes(
                    "w-full justify-between items-center gap-3 bg-white p-4 border border-slate-200 rounded-lg shadow-xs"
                ):
                    with ui.row().classes("items-center gap-2 flex-1 max-w-md"):
                        search_box = (
                            ui.input(
                                placeholder="Search courses by name or subject...",
                                value=search_query["text"],
                            )
                            .props("outlined dense clearable")
                            .classes("w-full text-xs")
                        )
                        search_box.on("input", lambda e: on_search(e.value))

                    with ui.row().classes("items-center gap-3"):
                        ui.label(f"{len(filtered_courses)} Course(s)").classes(
                            "text-xs font-semibold text-slate-500"
                        )
                        if is_admin:
                            ui.button(
                                "Create Course",
                                icon="add",
                                on_click=create_dialog.open,
                            ).props("color=primary no-caps dense").classes(
                                "text-xs font-medium px-3 py-1.5"
                            )

                # Empty State
                if not filtered_courses:
                    if search_query["text"]:
                        render_empty_state(
                            icon="search_off",
                            title="No Matching Courses",
                            description=f"No courses match your query '{search_query['text']}'.",
                            action_label="Clear Search",
                            on_action=lambda: on_search(""),
                        )
                    else:
                        render_empty_state(
                            icon="menu_book",
                            title="No Courses Available",
                            description="No university courses are registered yet.",
                            action_label="Create Course" if is_admin else None,
                            on_action=create_dialog.open if is_admin else None,
                        )
                    return

                # Course Cards Grid
                with ui.row().classes("w-full gap-4 items-stretch"):
                    for c in filtered_courses:
                        with ui.card().classes(
                            "w-full md:w-[calc(50%-0.5rem)] p-5 bg-white border border-slate-200 hover:border-blue-300 rounded-lg shadow-xs transition-all flex flex-col justify-between"
                        ):
                            with ui.column().classes("w-full gap-3"):
                                # Header: Name and icon
                                with ui.row().classes("w-full justify-between items-start gap-2"):
                                    with ui.row().classes("items-center gap-2"):
                                        ui.icon("school", size="sm").classes("text-blue-600")
                                        ui.label(c.name).classes(
                                            "text-base font-bold text-slate-900 tracking-tight"
                                        )

                                # Description
                                ui.label(
                                    c.description
                                    if c.description
                                    else "No description provided for this academic course."
                                ).classes("text-xs text-slate-600 line-clamp-2 leading-relaxed")

                                # Document Counts Summary
                                with ui.row().classes(
                                    "w-full items-center gap-2 py-2 px-3 bg-slate-50 rounded border border-slate-100 text-xs"
                                ):
                                    ui.icon("description", size="xs").classes("text-slate-500")
                                    ui.label(f"{c.total_documents} Document(s)").classes(
                                        "font-semibold text-slate-800"
                                    )
                                    ui.label("•").classes("text-slate-300")
                                    with ui.row().classes("items-center gap-1"):
                                        ui.badge("●", color="emerald-600").classes(
                                            "text-[8px] p-0.5"
                                        )
                                        ui.label(f"{c.active_documents} Active").classes(
                                            "text-slate-600"
                                        )
                                    ui.label("•").classes("text-slate-300")
                                    with ui.row().classes("items-center gap-1"):
                                        ui.badge("○", color="slate-400").classes("text-[8px] p-0.5")
                                        ui.label(f"{c.inactive_documents} Inactive").classes(
                                            "text-slate-500"
                                        )

                                # File Previews
                                with ui.column().classes("w-full gap-1.5 mt-1"):
                                    if not c.document_previews:
                                        ui.label("No documents uploaded yet.").classes(
                                            "text-[11px] text-slate-400 italic"
                                        )
                                    else:
                                        for doc in c.document_previews:
                                            with ui.row().classes(
                                                "w-full items-center justify-between py-1 px-2 hover:bg-slate-50 rounded text-xs transition-colors"
                                            ):
                                                with ui.row().classes(
                                                    "items-center gap-1.5 truncate max-w-[240px]"
                                                ):
                                                    ui.icon("insert_drive_file", size="xs").classes(
                                                        "text-slate-400"
                                                    )
                                                    ui.label(doc.filename).classes(
                                                        "font-medium text-slate-700 truncate"
                                                    )
                                                with ui.row().classes("items-center gap-1"):
                                                    ui.badge(
                                                        doc.file_type.upper(), color="slate-500"
                                                    ).classes("text-[9px]")
                                                    if doc.is_active:
                                                        ui.badge(
                                                            "ACTIVE", color="emerald-700"
                                                        ).classes("text-[9px] font-bold")
                                                    else:
                                                        ui.badge(
                                                            "INACTIVE", color="slate-400"
                                                        ).classes("text-[9px]")

                                        remaining = c.total_documents - len(c.document_previews)
                                        if remaining > 0:
                                            ui.label(f"+ {remaining} more document(s)").classes(
                                                "text-[11px] text-blue-600 font-medium pl-2"
                                            )

                            # Footer Action
                            with ui.row().classes(
                                "w-full justify-between items-center pt-3 mt-3 border-t border-slate-100 text-xs text-slate-500"
                            ):
                                ui.label(f"Created {c.created_at}").classes("font-mono text-[11px]")
                                ui.button(
                                    "Open Course",
                                    icon="arrow_forward",
                                    on_click=lambda course_id=c.id: ui.navigate.to(
                                        f"/documents?kb_id={course_id}"
                                    ),
                                ).props("color=primary dense no-caps").classes(
                                    "text-xs px-3 py-1 font-medium"
                                )

            def on_search(val: str | None) -> None:
                search_query["text"] = (val or "").strip()
                refresh_view()

            # Strictly execute initial render inside content_container via refresh_view
            refresh_view()
