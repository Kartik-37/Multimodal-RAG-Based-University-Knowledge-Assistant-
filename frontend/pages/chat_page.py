"""
Conversational RAG Chat & Search Page.

Provides question input, conversational message thread, loading/error states,
answer placeholder, and evidence/citation inspection panel.
All interactions route strictly through FrontendAPIClient.
"""

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.components.evidence_panel import render_evidence_panel
from frontend.components.layout import page_layout
from frontend.state.app_state import state


def register_chat_page() -> None:
    """Register /chat route with NiceGUI."""

    @ui.page("/chat")
    def chat_page() -> None:
        with page_layout(
            title="Chat & Semantic Search",
            subtitle="Ask questions grounded in the active knowledge base documents with source citations.",
            active_route="/chat",
        ):
            active_kb = state.active_kb

            if not active_kb:
                with ui.card().classes("w-full p-8 items-center justify-center text-center border-dashed border-2 border-gray-300"):
                    ui.icon("folder_off", size="lg").classes("text-gray-400 mb-2")
                    ui.label("No Active Knowledge Base").classes("text-lg font-bold text-gray-800")
                    ui.label("Select a knowledge base to begin conversational question answering.").classes(
                        "text-sm text-gray-500 mb-4"
                    )
                    ui.button("Select Knowledge Base", icon="arrow_forward", on_click=lambda: ui.navigate.to("/knowledge-bases")).props(
                        "color=primary"
                    )
                return

            # Top Context Bar
            with ui.card().classes("w-full p-3 border border-gray-200 bg-gray-50 rounded"):
                with ui.row().classes("w-full justify-between items-center"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("psychology", size="sm").classes("text-blue-600")
                        ui.label("Querying Knowledge Base:").classes("text-xs font-semibold text-gray-500 uppercase")
                        ui.label(active_kb.name).classes("text-sm font-bold text-gray-900")
                        ui.badge(f"{active_kb.document_count} doc(s)", color="blue-grey").classes("text-xs")

                    def clear_session() -> None:
                        state.clear_chat()
                        ui.notify("Conversation cleared.", type="info")
                        refresh_chat_view()

                    ui.button("Clear Conversation", icon="delete_outline", on_click=clear_session).props(
                        "flat dense"
                    ).classes("text-xs text-red-500")

            # Main Two-Column Layout: Chat on Left, Evidence Panel on Right
            with ui.row().classes("w-full gap-6 items-start"):
                # Left Column: Conversation Thread and Input (approx 62% width)
                chat_col = ui.column().classes("flex-1 min-w-[320px] gap-4")

                # Right Column: Evidence / Citation Inspection (approx 38% width)
                evidence_col = ui.column().classes("w-96 min-w-[300px] gap-2")

            def refresh_chat_view() -> None:
                chat_col.clear()
                evidence_col.clear()
                with chat_col:
                    render_chat_column()
                with evidence_col:
                    render_evidence_column()

            def render_evidence_column() -> None:
                # Get citations from the latest assistant message, if any
                assistant_msgs = [m for m in state.chat_history if m.role == "assistant"]
                citations = assistant_msgs[-1].citations if assistant_msgs else []

                def on_select_citation(c) -> None:
                    state.selected_citation = c
                    refresh_chat_view()

                render_evidence_panel(
                    citations=citations,
                    selected_citation=state.selected_citation,
                    on_select=on_select_citation,
                )

            def render_chat_column() -> None:
                # Message History Container
                with ui.column().classes("w-full min-h-[360px] p-4 bg-white border border-gray-200 rounded gap-3"):
                    if not state.chat_history:
                        with ui.column().classes("w-full py-16 items-center justify-center text-center"):
                            ui.icon("chat_bubble_outline", size="xl").classes("text-gray-300 mb-2")
                            ui.label("No Questions Asked Yet").classes("text-base font-bold text-gray-700")
                            ui.label(
                                "Type your question below. The assistant will retrieve relevant chunks, "
                                "rerank evidence, and synthesize an answer with citations."
                            ).classes("text-xs text-gray-500 max-w-sm mb-4")

                            # Quick starter prompts
                            with ui.row().classes("gap-2"):
                                prompts = [
                                    "What are the BCA examination attendance rules?",
                                    "What is the curriculum approval process?",
                                ]
                                for p in prompts:
                                    def use_prompt(prompt_text=p) -> None:
                                        send_message(prompt_text)

                                    ui.button(p, on_click=use_prompt).props("outline dense").classes("text-xs text-blue-700")
                    else:
                        for msg in state.chat_history:
                            if msg.role == "user":
                                with ui.row().classes("w-full justify-end"):
                                    with ui.column().classes("max-w-xl bg-blue-600 text-white p-3 rounded-lg shadow-sm"):
                                        ui.label(msg.content).classes("text-sm")
                                        if msg.created_at:
                                            ui.label(msg.created_at).classes("text-[10px] text-blue-200 self-end mt-1")
                            else:
                                with ui.row().classes("w-full justify-start"):
                                    with ui.column().classes("w-full max-w-2xl bg-gray-50 border border-gray-200 p-4 rounded-lg shadow-sm gap-2"):
                                        with ui.row().classes("items-center gap-2 mb-1"):
                                            ui.icon("psychology", size="xs").classes("text-blue-600")
                                            ui.label("Assistant").classes("text-xs font-bold text-gray-800")
                                            if msg.created_at:
                                                ui.label(msg.created_at).classes("text-[10px] text-gray-400 font-mono")

                                        ui.markdown(msg.content).classes("text-sm text-gray-800 leading-relaxed")

                                        # Citation Pills
                                        if msg.citations:
                                            with ui.row().classes("items-center gap-1 mt-2 pt-2 border-t border-gray-200"):
                                                ui.label("Sources:").classes("text-xs font-semibold text-gray-500")
                                                for idx, cit in enumerate(msg.citations, start=1):
                                                    def select_cit(c=cit) -> None:
                                                        state.selected_citation = c
                                                        refresh_chat_view()

                                                    page_info = f" p.{cit.page_number}" if cit.page_number else ""
                                                    pill_label = f"[{idx}] {cit.document_name}{page_info}"
                                                    ui.button(pill_label, on_click=select_cit).props(
                                                        "outline dense color=primary"
                                                    ).classes("text-[11px] normal-case")

                # Loading Indicator Placeholder
                loading_row = ui.row().classes("w-full items-center gap-2 p-2 bg-blue-50 border border-blue-200 rounded hidden")
                with loading_row:
                    ui.spinner(size="sm")
                    ui.label("Retrieving hybrid context, reranking passages, and generating response...").classes(
                        "text-xs text-blue-700"
                    )

                # Input Row
                with ui.row().classes("w-full items-center gap-2 mt-1"):
                    input_box = ui.input(
                        placeholder="Ask a question about documents in this knowledge base...",
                    ).classes("flex-1")

                    async def handle_submit() -> None:
                        q = (input_box.value or "").strip()
                        if not q:
                            ui.notify("Please enter a question.", type="warning")
                            return

                        input_box.value = ""
                        await send_message(q)

                    send_btn = ui.button(icon="send", on_click=handle_submit).props("color=primary")
                    input_box.on("keydown.enter", handle_submit)

                async def send_message(question_text: str) -> None:
                    # Append user message
                    state.add_user_message(question_text)
                    loading_row.classes(remove="hidden")
                    send_btn.disable()

                    try:
                        # Call centralized API client boundary (mock in Step 3, real in Step 4)
                        assistant_response = api_client.send_chat_message(
                            kb_id=active_kb.id,
                            question=question_text,
                        )
                        state.add_assistant_message(assistant_response)
                        if assistant_response.citations:
                            state.selected_citation = assistant_response.citations[0]
                    except ValueError as err:
                        ui.notify(f"Query error: {err}", type="negative")
                    finally:
                        loading_row.classes(add="hidden")
                        send_btn.enable()
                        refresh_chat_view()

            # Initial render
            refresh_chat_view()
