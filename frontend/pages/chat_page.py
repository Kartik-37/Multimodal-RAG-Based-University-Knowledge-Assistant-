"""
Conversational RAG Chat & Search Presentation Page.

Provides an accessible conversational thread grounded in the active knowledge base.
Follows standard asynchronous request-response architecture (no fake streaming).
Sanitizes markdown output to prevent arbitrary HTML execution.
Includes citation pill buttons linked to the evidence inspection panel.
"""

import re

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.client.models import CitationDTO
from frontend.components.evidence_panel import render_evidence_panel
from frontend.components.hybrid_inspect import open_hybrid_retrieval_dialog
from frontend.components.layout import page_layout
from frontend.components.lexical_inspect import open_lexical_retrieval_dialog
from frontend.components.rerank_inspect import open_rerank_inspection_dialog
from frontend.components.retrieval_inspect import open_vector_retrieval_dialog
from frontend.components.status_badge import render_grounding_status_badge
from frontend.state.app_state import state


def sanitize_markdown_text(raw_text: str) -> str:
    """
    Sanitize text before markdown rendering by escaping raw HTML tags.
    Preserves standard markdown formatting (*, _, `, #, -, [link](url))
    while preventing HTML injection (scripts, iframes, event handlers).
    """
    if not raw_text:
        return ""
    # Strip or escape script, style, iframe, and dangerous HTML tags
    cleaned = re.sub(
        r"<\s*(script|style|iframe|object|embed|applet|form)[^>]*>.*?<\s*/\s*\1\s*>",
        "",
        raw_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    cleaned = re.sub(
        r"<\s*(script|style|iframe|object|embed|applet|form)[^>]*>",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Neutralize HTML event handlers like onload=, onclick=
    cleaned = re.sub(r"on\w+\s*=", "data-disabled-event=", cleaned, flags=re.IGNORECASE)
    return cleaned


def register_chat_page() -> None:
    """Register /chat route with NiceGUI."""

    @ui.page("/chat")
    def chat_page() -> None:
        user = state.current_user
        is_admin = bool(user and user.role == "ADMIN")
        page_title = "Chat & Semantic Search" if is_admin else "Ask Assistant"
        page_subtitle = (
            "Ask questions grounded in university course materials and inspect retrieval evidence."
            if is_admin
            else "Ask questions across all active course materials with verified citations."
        )

        with page_layout(
            title=page_title,
            subtitle=page_subtitle,
            active_route="/chat",
            require_auth=True,
        ):
            active_kb = state.active_kb

            # Top Context & Controls Bar
            with ui.card().classes(
                "w-full p-3.5 bg-white border border-slate-200 rounded-lg shadow-xs"
            ):
                with ui.row().classes("w-full justify-between items-center gap-2 flex-wrap"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("school", size="sm").classes("text-blue-600")
                        scope_label = "Target Scope:" if is_admin else "Searching In:"
                        ui.label(scope_label).classes(
                            "text-xs font-semibold text-slate-500 uppercase tracking-wider"
                        )
                        current_scope_name = active_kb.name if active_kb else "All Course Materials"
                        ui.label(current_scope_name).classes("text-sm font-bold text-slate-900")

                        if active_kb and not is_admin:

                            def reset_to_all_courses() -> None:
                                state.active_kb = None
                                ui.navigate.to("/chat")

                            ui.button(
                                "Search All Courses",
                                icon="clear",
                                on_click=reset_to_all_courses,
                            ).props("flat dense no-caps text-color=primary").classes(
                                "text-xs font-medium ml-2"
                            )

                    with ui.row().classes("items-center gap-2 flex-wrap"):
                        if is_admin and active_kb:
                            ui.button(
                                "Dense Vector",
                                icon="manage_search",
                                on_click=lambda: open_vector_retrieval_dialog(
                                    active_kb.id, active_kb.name
                                ),
                            ).props("outline dense no-caps").classes("text-xs text-blue-700")
                            ui.button(
                                "Lexical FTS",
                                icon="search",
                                on_click=lambda: open_lexical_retrieval_dialog(
                                    active_kb.id, active_kb.name
                                ),
                            ).props("outline dense no-caps").classes("text-xs text-teal-700")
                            ui.button(
                                "Hybrid RRF",
                                icon="layers",
                                on_click=lambda: open_hybrid_retrieval_dialog(
                                    active_kb.id, active_kb.name
                                ),
                            ).props("outline dense no-caps").classes("text-xs text-indigo-700")
                            ui.button(
                                "Reranker",
                                icon="tune",
                                on_click=lambda: open_rerank_inspection_dialog(
                                    active_kb.id, active_kb.name
                                ),
                            ).props("outline dense no-caps").classes("text-xs text-purple-700")

                        def clear_chat_history() -> None:
                            state.clear_chat()
                            ui.notify("Conversation cleared.", type="info")
                            render_messages()
                            render_evidence()

                        ui.button(
                            "Clear Chat",
                            icon="delete_sweep",
                            on_click=clear_chat_history,
                        ).props("flat dense no-caps").classes(
                            "text-xs text-rose-600 hover:bg-rose-50"
                        )

            # Main Two-Column Layout (Chat Thread + Evidence Panel)
            with ui.row().classes("w-full gap-6 items-start"):
                # Left Column: Conversation Thread (approx 65% width on desktop)
                with ui.column().classes("flex-1 min-w-[300px] w-full gap-4"):
                    # Message Container
                    message_container = ui.column().classes(
                        "w-full min-h-[400px] max-h-[600px] overflow-y-auto p-4 sm:p-5 bg-white border border-slate-200 rounded-lg shadow-xs gap-4"
                    )

                    # Loading Indicator (Asynchronous Processing Indicator)
                    loading_row = ui.row().classes(
                        "w-full items-center gap-2.5 p-3 bg-blue-50 border border-blue-200 rounded-md shadow-xs"
                    )
                    with loading_row:
                        ui.spinner(size="sm", color="primary")
                        ui.label(
                            "Searching course materials and synthesizing verified answer..."
                        ).classes("text-xs font-medium text-blue-900")
                    loading_row.visible = False

                    # Input Bar
                    input_placeholder = (
                        "Ask a question about your courses (e.g. syllabus, prerequisites, grading)..."
                        if not is_admin
                        else "Ask a question to test retrieval, reranking, and citation synthesis..."
                    )
                    with ui.card().classes(
                        "w-full p-2 bg-white border border-slate-200 rounded-lg shadow-xs"
                    ):
                        with ui.row().classes("w-full items-center gap-2"):
                            input_box = (
                                ui.input(
                                    placeholder=input_placeholder,
                                )
                                .props("outlined dense")
                                .classes("flex-1 text-sm")
                            )
                            send_btn = (
                                ui.button(icon="send")
                                .props("color=primary dense")
                                .classes("px-3 py-1.5")
                            )

                # Right Column: Evidence / Citation Panel (Collapsible or side panel)
                evidence_container = ui.column().classes("w-full lg:w-96 min-w-[280px] gap-2")

            # Controller functions in proper lexical scope
            async def send_message(question_text: str) -> None:
                q = question_text.strip()
                if not q:
                    ui.notify("Please enter a question.", type="warning")
                    return

                # Append user question to state
                state.add_user_message(q)
                render_messages()
                render_evidence()

                # Enable loading state
                loading_row.visible = True
                send_btn.disable()

                try:
                    # Centralized API client execution - pass None for global search
                    target_kb_id = active_kb.id if active_kb else None
                    response = api_client.send_chat_message(
                        kb_id=target_kb_id,
                        question=q,
                    )
                    state.add_assistant_message(response)
                    if response.citations:
                        state.selected_citation = response.citations[0]
                except ValueError as err:
                    ui.notify(f"{err}", type="negative")
                finally:
                    loading_row.visible = False
                    send_btn.enable()
                    render_messages()
                    render_evidence()

            async def handle_submit() -> None:
                q = (input_box.value or "").strip()
                if not q:
                    ui.notify("Please enter a question.", type="warning")
                    return
                input_box.value = ""
                await send_message(q)

            send_btn.on("click", handle_submit)
            input_box.on("keydown.enter", handle_submit)

            def select_citation(cit: CitationDTO) -> None:
                state.selected_citation = cit
                render_messages()
                render_evidence()

            def render_evidence() -> None:
                evidence_container.clear()
                with evidence_container:
                    assistant_msgs = [m for m in state.chat_history if m.role == "assistant"]
                    citations = assistant_msgs[-1].citations if assistant_msgs else []
                    render_evidence_panel(
                        citations=citations,
                        selected_citation=state.selected_citation,
                        on_select=select_citation,
                        is_admin=is_admin,
                    )

            def render_messages() -> None:
                message_container.clear()
                with message_container:
                    if not state.chat_history:
                        with ui.column().classes(
                            "w-full py-16 items-center justify-center text-center"
                        ):
                            ui.icon("chat_bubble_outline", size="3rem").classes(
                                "text-slate-300 mb-2"
                            )
                            ui.label("No Questions Asked Yet").classes(
                                "text-base font-bold text-slate-800"
                            )
                            ui.label(
                                "Type your academic question below. The assistant will retrieve relevant passages, "
                                "rerank evidence, and synthesize an answer with verified citations."
                            ).classes("text-xs text-slate-500 max-w-md mt-1 mb-5 leading-relaxed")

                            # Starter prompts
                            with ui.row().classes("gap-2 flex-wrap justify-center"):
                                starter_prompts = [
                                    "What are the examination grading criteria?",
                                    "Explain the core algorithms in this syllabus.",
                                    "What are the prerequisites for this course?",
                                ]
                                for prompt in starter_prompts:

                                    def make_prompt_handler(p=prompt):
                                        return lambda: send_message(p)

                                    ui.button(
                                        prompt,
                                        on_click=make_prompt_handler(),
                                    ).props("outline dense no-caps").classes(
                                        "text-xs text-blue-700 border-blue-200 hover:bg-blue-50"
                                    )
                    else:
                        for msg in state.chat_history:
                            if msg.role == "user":
                                with ui.row().classes("w-full justify-end"):
                                    with ui.card().classes(
                                        "max-w-xl bg-blue-700 text-white p-3.5 rounded-lg shadow-xs"
                                    ):
                                        ui.label(msg.content).classes(
                                            "text-sm text-white leading-relaxed"
                                        )
                            else:
                                with ui.row().classes("w-full justify-start"):
                                    with ui.card().classes(
                                        "w-full max-w-2xl bg-slate-50 border border-slate-200 p-4 rounded-lg shadow-xs gap-2"
                                    ):
                                        # Assistant Header Meta
                                        with ui.row().classes(
                                            "w-full justify-between items-center mb-1"
                                        ):
                                            with ui.row().classes("items-center gap-1.5"):
                                                ui.icon("school", size="xs").classes(
                                                    "text-blue-600"
                                                )
                                                ui.label("Assistant").classes(
                                                    "text-xs font-bold text-slate-800"
                                                )
                                                if msg.grounding_status:
                                                    render_grounding_status_badge(
                                                        msg.grounding_status,
                                                        is_grounded=msg.is_grounded,
                                                    )
                                            if msg.total_pipeline_ms:
                                                ui.label(f"{msg.total_pipeline_ms:.0f}ms").classes(
                                                    "text-[10px] text-slate-400 font-mono"
                                                )

                                        # Sanitized Markdown Answer
                                        clean_content = sanitize_markdown_text(msg.content)
                                        ui.markdown(clean_content).classes("safe-markdown text-sm")

                                        # Source Citations Pills
                                        if msg.citations:
                                            with ui.row().classes(
                                                "w-full items-center gap-1.5 mt-2 pt-2 border-t border-slate-200 flex-wrap"
                                            ):
                                                ui.label("Cited Sources:").classes(
                                                    "text-[11px] font-semibold text-slate-500 mr-1"
                                                )
                                                for idx, cit in enumerate(msg.citations, start=1):
                                                    page_suffix = (
                                                        f" p.{cit.page_number}"
                                                        if cit.page_number is not None
                                                        else ""
                                                    )
                                                    pill_text = (
                                                        f"[{idx}] {cit.document_name}{page_suffix}"
                                                    )
                                                    is_active_cit = (
                                                        state.selected_citation is not None
                                                        and state.selected_citation.chunk_id
                                                        == cit.chunk_id
                                                    )
                                                    pill_color = (
                                                        "primary"
                                                        if is_active_cit
                                                        else "blue-grey-7"
                                                    )
                                                    ui.button(
                                                        pill_text,
                                                        on_click=lambda c=cit: select_citation(c),
                                                    ).props(
                                                        f"outline dense color={pill_color} no-caps"
                                                    ).classes("text-[10px] font-mono px-2 py-0.5")

            # Initial render
            render_messages()
            render_evidence()
