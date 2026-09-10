"""
Knowledge Bases Management Page.

Allows listing, creating, and selecting active knowledge bases.
All operations are routed through FrontendAPIClient.
"""

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.components.layout import page_layout
from frontend.state.app_state import state


def register_knowledge_bases_page() -> None:
    """Register /knowledge-bases route with NiceGUI."""

    @ui.page("/knowledge-bases")
    def knowledge_bases_page() -> None:
        with page_layout(
            title="Knowledge Bases",
            subtitle="Manage isolated document collections and context scopes for your queries.",
            active_route="/knowledge-bases",
        ):
            # Container that can be refreshed when a KB is added or selected
            content_container = ui.column().classes("w-full gap-4")

            # Dialog for creating a new Knowledge Base
            with ui.dialog() as create_dialog, ui.card().classes("w-full max-w-md p-6"):
                ui.label("Create New Knowledge Base").classes("text-lg font-bold text-gray-900 mb-1")
                ui.label("Group related reference material under a specific subject.").classes(
                    "text-xs text-gray-500 mb-4"
                )

                name_input = ui.input(
                    label="Knowledge Base Name *",
                    placeholder="e.g. BCA Semester 5 Syllabus",
                ).classes("w-full mb-2")

                desc_input = ui.textarea(
                    label="Description",
                    placeholder="Brief description of the documents contained in this corpus.",
                ).classes("w-full mb-4")

                def handle_create() -> None:
                    name = (name_input.value or "").strip()
                    desc = (desc_input.value or "").strip()
                    try:
                        new_kb = api_client.create_knowledge_base(name, desc)
                        state.active_kb = new_kb
                        ui.notify(f"Created knowledge base '{new_kb.name}'", type="positive")
                        create_dialog.close()
                        name_input.value = ""
                        desc_input.value = ""
                        refresh_view()
                    except ValueError as err:
                        ui.notify(str(err), type="negative")

                with ui.row().classes("w-full justify-end gap-2"):
                    ui.button("Cancel", on_click=create_dialog.close).props("flat")
                    ui.button("Create", icon="check", on_click=handle_create).props("color=primary")

            def open_create_dialog() -> None:
                create_dialog.open()

            def refresh_view() -> None:
                content_container.clear()
                with content_container:
                    render_content()

            def render_content() -> None:
                kbs = api_client.get_knowledge_bases()
                active_kb = state.active_kb

                # Top Action Bar
                with ui.row().classes("w-full justify-between items-center bg-gray-50 p-4 border rounded"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("library_books", size="sm").classes("text-blue-600")
                        ui.label(f"{len(kbs)} Knowledge Base(s) Available").classes("text-sm font-semibold text-gray-700")

                    ui.button("New Knowledge Base", icon="add", on_click=open_create_dialog).props(
                        "color=primary dense"
                    )

                # Empty State
                if not kbs:
                    with ui.card().classes("w-full p-10 items-center justify-center text-center border-dashed border-2 border-gray-300"):
                        ui.icon("folder_off", size="xl").classes("text-gray-400 mb-2")
                        ui.label("No Knowledge Bases Found").classes("text-lg font-bold text-gray-800")
                        ui.label("Create your first knowledge base to begin uploading documents and querying context.").classes(
                            "text-sm text-gray-500 max-w-md mb-4"
                        )
                        ui.button("Create Knowledge Base", icon="add", on_click=open_create_dialog).props(
                            "color=primary"
                        )
                    return

                # Knowledge Base Cards List
                with ui.column().classes("w-full gap-3"):
                    for kb in kbs:
                        is_active = active_kb is not None and active_kb.id == kb.id
                        card_classes = "w-full p-4 border rounded bg-white transition-all "
                        if is_active:
                            card_classes += "border-blue-500 ring-2 ring-blue-50"
                        else:
                            card_classes += "border-gray-200 hover:border-gray-300"

                        with ui.card().classes(card_classes):
                            with ui.row().classes("w-full justify-between items-start"):
                                with ui.column().classes("gap-1"):
                                    with ui.row().classes("items-center gap-2"):
                                        ui.label(kb.name).classes("text-base font-bold text-gray-900")
                                        if is_active:
                                            ui.badge("ACTIVE", color="green").classes("text-xs font-semibold")

                                    if kb.description:
                                        ui.label(kb.description).classes("text-xs text-gray-600")
                                    else:
                                        ui.label("No description provided.").classes("text-xs text-gray-400 italic")

                                    with ui.row().classes("items-center gap-3 text-xs text-gray-500 mt-2"):
                                        ui.label(f"{kb.document_count} document(s)").classes("font-mono")
                                        ui.label(f"Created: {kb.created_at}").classes("text-gray-400")

                                # Actions on KB
                                with ui.row().classes("items-center gap-2"):
                                    if not is_active:
                                        def make_active(target_kb=kb) -> None:
                                            state.active_kb = target_kb
                                            ui.notify(f"Set '{target_kb.name}' as active knowledge base.", type="positive")
                                            refresh_view()

                                        ui.button("Set Active", icon="check_circle_outline", on_click=make_active).props(
                                            "outline dense color=primary"
                                        ).classes("text-xs")

                                    def view_docs(target_kb=kb) -> None:
                                        state.active_kb = target_kb
                                        ui.navigate.to("/documents")

                                    ui.button("Documents", icon="description", on_click=view_docs).props(
                                        "flat dense"
                                    ).classes("text-xs text-gray-700")

                                    def start_chat(target_kb=kb) -> None:
                                        state.active_kb = target_kb
                                        ui.navigate.to("/chat")

                                    ui.button("Query", icon="chat", on_click=start_chat).props(
                                        "flat dense color=primary"
                                    ).classes("text-xs")

            # Initial render
            render_content()
