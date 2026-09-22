"""
Knowledge Bases Management Page.

Allows users to list, search, and select active knowledge base corpora.
Administrators can create new knowledge bases, while students browse authorized collections.
All interactions route strictly through FrontendAPIClient.
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
            title="Knowledge Bases",
            subtitle="Manage isolated document collections and select the active context for RAG queries.",
            active_route="/knowledge-bases",
            require_auth=True,
        ):
            user = state.current_user
            is_admin = bool(user and user.role == "ADMIN")

            # Dynamic content container
            content_container = ui.column().classes("w-full gap-4")

            # ------------------------------------------------------------------
            # Create Knowledge Base Dialog (Admin Only)
            # ------------------------------------------------------------------
            with (
                ui.dialog() as create_dialog,
                ui.card().classes(
                    "w-full max-w-md p-6 bg-white border border-slate-200 rounded-lg shadow-md"
                ),
            ):
                ui.label("Create New Knowledge Base").classes(
                    "text-lg font-bold text-slate-900 mb-1"
                )
                ui.label(
                    "Group related course materials under a dedicated subject corpus."
                ).classes("text-xs text-slate-500 mb-4")

                dialog_error = ui.column().classes("w-full mb-2")

                with ui.column().classes("w-full gap-1 mb-3"):
                    ui.label("Corpus Name *").classes("text-xs font-semibold text-slate-700")
                    name_input = (
                        ui.input(
                            placeholder="e.g. BCA-501 Operating Systems",
                        )
                        .props("outlined dense")
                        .classes("w-full")
                    )

                with ui.column().classes("w-full gap-1 mb-5"):
                    ui.label("Description").classes("text-xs font-semibold text-slate-700")
                    desc_input = (
                        ui.textarea(
                            placeholder="Brief overview of course syllabus, notes, or reference texts.",
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
                            render_alert("Knowledge base name is required.", "warning")
                        return

                    try:
                        new_kb = api_client.create_knowledge_base(name, desc)
                        state.active_kb = new_kb
                        ui.notify(f"Created knowledge base '{new_kb.name}'", type="positive")
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
                    ui.button("Create Corpus", icon="check", on_click=handle_create).props(
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
                kbs = api_client.get_knowledge_bases()
                active_kb = state.active_kb

                # Filter by search text if provided
                filtered_kbs = (
                    [
                        k
                        for k in kbs
                        if search_query["text"].lower() in k.name.lower()
                        or search_query["text"].lower() in k.description.lower()
                    ]
                    if search_query["text"]
                    else kbs
                )

                # Action Bar
                with ui.row().classes(
                    "w-full justify-between items-center gap-3 bg-white p-4 border border-slate-200 rounded-lg shadow-xs"
                ):
                    with ui.row().classes("items-center gap-2 flex-1 max-w-md"):
                        search_box = (
                            ui.input(
                                placeholder="Search knowledge bases by name or subject...",
                                value=search_query["text"],
                            )
                            .props("outlined dense clearable")
                            .classes("w-full text-xs")
                        )
                        search_box.on("input", lambda e: on_search(e.value))

                    with ui.row().classes("items-center gap-2"):
                        ui.label(f"{len(filtered_kbs)} of {len(kbs)} Corpus(es)").classes(
                            "text-xs font-semibold text-slate-500 font-mono"
                        )
                        if is_admin:
                            ui.button(
                                "New Knowledge Base",
                                icon="add",
                                on_click=create_dialog.open,
                            ).props("color=primary no-caps dense").classes(
                                "text-xs font-medium px-3 py-1.5"
                            )

                # Empty State
                if not kbs:
                    if is_admin:
                        render_empty_state(
                            icon="folder_off",
                            title="No Knowledge Bases Found",
                            description="Create your first subject knowledge base to begin uploading documents and testing RAG.",
                            action_label="Create Knowledge Base",
                            on_action=create_dialog.open,
                            action_icon="add",
                        )
                    else:
                        render_empty_state(
                            icon="lock",
                            title="No Enrolled Knowledge Bases",
                            description="Your student account has not been assigned membership to any knowledge base corpora yet. Please contact your instructor or administrator.",
                        )
                    return

                if not filtered_kbs:
                    render_empty_state(
                        icon="search_off",
                        title="No Matching Knowledge Bases",
                        description=f"No knowledge base matched '{search_query['text']}'. Clear the search term to view all corpora.",
                    )
                    return

                # Knowledge Base Cards Grid
                with ui.row().classes("w-full gap-4"):
                    for kb in filtered_kbs:
                        is_active = active_kb is not None and active_kb.id == kb.id
                        card_classes = "w-full md:w-[calc(50%-0.5rem)] p-5 bg-white border rounded-lg shadow-xs transition-all "
                        if is_active:
                            card_classes += "border-blue-500 ring-2 ring-blue-100"
                        else:
                            card_classes += "border-slate-200 hover:border-slate-300"

                        with ui.card().classes(card_classes):
                            with ui.row().classes("w-full justify-between items-start gap-2 mb-2"):
                                with ui.row().classes("items-center gap-2"):
                                    ui.icon("folder", size="sm").classes("text-blue-600")
                                    ui.label(kb.name).classes(
                                        "text-base font-bold text-slate-900 tracking-tight"
                                    )
                                if is_active:
                                    with ui.badge(color="emerald-700").classes(
                                        "text-[10px] font-bold px-2 py-0.5"
                                    ):
                                        with ui.row().classes("items-center gap-1"):
                                            ui.icon("check", size="xs")
                                            ui.label("ACTIVE")

                            ui.label(
                                kb.description
                                if kb.description
                                else "No description provided for this academic corpus."
                            ).classes("text-xs text-slate-600 mb-4 line-clamp-2 leading-relaxed")

                            with ui.row().classes(
                                "w-full justify-between items-center pt-3 border-t border-slate-100 text-xs text-slate-500 font-mono"
                            ):
                                ui.label(f"Created: {kb.created_at}")
                                with ui.row().classes("items-center gap-2"):
                                    if not is_active:

                                        def make_active(selected_kb=kb) -> None:
                                            state.active_kb = selected_kb
                                            ui.notify(
                                                f"Set '{selected_kb.name}' as active corpus.",
                                                type="info",
                                            )
                                            refresh_view()

                                        ui.button("Set Active", on_click=make_active).props(
                                            "flat dense no-caps"
                                        ).classes("text-xs text-blue-600 hover:bg-blue-50")

                                    ui.button(
                                        "Chat with Corpus",
                                        icon="chat",
                                        on_click=lambda k=kb: [
                                            setattr(state, "active_kb", k),
                                            ui.navigate.to("/chat"),
                                        ],
                                    ).props("color=primary dense no-caps").classes(
                                        "text-xs px-2.5 py-1"
                                    )

            def on_search(val: str | None) -> None:
                search_query["text"] = (val or "").strip()
                refresh_view()

            # Initial render
            render_content()
