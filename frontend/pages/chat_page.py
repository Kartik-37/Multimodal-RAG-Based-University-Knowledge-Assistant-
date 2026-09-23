"""
Conversational RAG Chat & Search Presentation Page.

Provides an accessible conversational thread grounded in the active knowledge base.
Follows standard asynchronous request-response architecture (no fake streaming).
Sanitizes markdown output to prevent arbitrary HTML execution.
Includes citation pill buttons linked to the evidence inspection panel.
Supports explicit search scopes: All Courses, Selected Course, and Selected Document.
"""

import re
from typing import Any

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.client.models import CitationDTO, DocumentDTO, KnowledgeBaseDTO
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
        page_title = "Admin Chat & Semantic Search" if is_admin else "Ask BCA Assistant"
        page_subtitle = (
            "Test retrieval, reranking, and citation synthesis across all courses, a specific course, or a single document."
            if is_admin
            else "Ask questions across verified course materials with grounded citations."
        )

        with page_layout(
            title=page_title,
            subtitle=page_subtitle,
            active_route="/chat",
            require_auth=True,
        ):
            # Fetch available knowledge bases for course selector
            kbs: list[KnowledgeBaseDTO] = []
            try:
                kbs = api_client.get_knowledge_bases()
            except Exception:
                kbs = []

            # Determine initial scope and selections
            initial_scope = "COURSE" if state.active_kb else "ALL_COURSES"
            active_scope: dict[str, Any] = {
                "scope": initial_scope,
                "kb_id": state.active_kb.id if state.active_kb else (kbs[0].id if kbs else None),
                "doc_id": None,
                "docs": [],
                "selected_doc": None,
            }

            def load_docs_for_current_kb() -> None:
                if active_scope["kb_id"]:
                    try:
                        active_scope["docs"] = api_client.get_documents(active_scope["kb_id"])
                    except Exception:
                        active_scope["docs"] = []
                else:
                    active_scope["docs"] = []

            if active_scope["kb_id"]:
                load_docs_for_current_kb()

            # Dynamic containers
            scope_controls_row = ui.row().classes("w-full items-center gap-3 flex-wrap")
            doc_warning_container = ui.column().classes("w-full")

            # Function to refresh doc warning banner
            def refresh_doc_warning() -> None:
                doc_warning_container.clear()
                if active_scope["scope"] != "DOCUMENT" or not active_scope["selected_doc"]:
                    return

                doc: DocumentDTO = active_scope["selected_doc"]
                with doc_warning_container:
                    if doc.indexing_status != "COMPLETED":
                        with ui.card().classes(
                            "w-full p-3 bg-amber-50 border border-amber-200 rounded-lg shadow-xs"
                        ):
                            with ui.row().classes("w-full items-center justify-between gap-2 flex-wrap"):
                                with ui.row().classes("items-center gap-2"):
                                    ui.icon("warning", size="sm").classes("text-amber-600")
                                    with ui.column().classes("gap-0.5"):
                                        ui.label(
                                            f"Document '{doc.filename}' is not ready for retrieval"
                                        ).classes("text-xs font-bold text-amber-900")
                                        ui.label(
                                            f"Current status: {doc.indexing_status}. Queries scoped to this document will be refused until indexing completes."
                                        ).classes("text-[11px] text-amber-700")

                                def trigger_doc_indexing(d=doc) -> None:
                                    try:
                                        api_client.index_document(active_scope["kb_id"], d.id)
                                        ui.notify(
                                            f"Triggered vector indexing for {d.filename}.",
                                            type="info",
                                        )
                                        load_docs_for_current_kb()
                                        for updated_doc in active_scope["docs"]:
                                            if updated_doc.id == d.id:
                                                active_scope["selected_doc"] = updated_doc
                                                break
                                        refresh_doc_warning()
                                    except Exception as exc:
                                        ui.notify(f"Indexing trigger failed: {exc}", type="negative")

                                ui.button(
                                    "Retry Indexing" if doc.indexing_status == "FAILED" else "Index Document",
                                    icon="play_arrow",
                                    on_click=trigger_doc_indexing,
                                ).props("color=amber-9 dense no-caps").classes("text-xs")
                    else:
                        with ui.card().classes(
                            "w-full p-2.5 bg-emerald-50 border border-emerald-200 rounded-lg shadow-xs"
                        ):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon("check_circle", size="sm").classes("text-emerald-600")
                                ui.label(
                                    f"Document '{doc.filename}' is fully indexed ({doc.chunk_count} chunks ready)."
                                ).classes("text-xs font-medium text-emerald-800")

            # Function to render top controls
            def render_controls() -> None:
                scope_controls_row.clear()
                with scope_controls_row:
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("filter_alt", size="sm").classes("text-blue-600")
                        ui.label("Search Scope:").classes(
                            "text-xs font-bold text-slate-700 uppercase tracking-wider"
                        )

                        scope_options = {
                            "ALL_COURSES": "All Published Courses",
                            "COURSE": "Selected Course",
                            "DOCUMENT": "Selected Document",
                        }

                        def on_scope_change(e: Any) -> None:
                            active_scope["scope"] = e.value
                            if e.value == "DOCUMENT" and not active_scope["selected_doc"] and active_scope["docs"]:
                                active_scope["selected_doc"] = active_scope["docs"][0]
                                active_scope["doc_id"] = active_scope["docs"][0].id
                            render_controls()
                            refresh_doc_warning()

                        ui.select(
                            options=scope_options,
                            value=active_scope["scope"],
                            on_change=on_scope_change,
                        ).props("outlined dense options-dense").classes("text-xs min-w-[190px]")

                    # Course selector (shown if COURSE or DOCUMENT)
                    if active_scope["scope"] in ("COURSE", "DOCUMENT"):
                        kb_options = {kb.id: kb.name for kb in kbs}
                        if not active_scope["kb_id"] and kbs:
                            active_scope["kb_id"] = kbs[0].id
                            load_docs_for_current_kb()

                        def on_kb_change(e: Any) -> None:
                            active_scope["kb_id"] = e.value
                            # Update global state active_kb as well
                            selected = next((k for k in kbs if k.id == e.value), None)
                            if selected:
                                state.active_kb = selected
                            load_docs_for_current_kb()
                            if active_scope["docs"]:
                                active_scope["selected_doc"] = active_scope["docs"][0]
                                active_scope["doc_id"] = active_scope["docs"][0].id
                            else:
                                active_scope["selected_doc"] = None
                                active_scope["doc_id"] = None
                            render_controls()
                            refresh_doc_warning()

                        ui.select(
                            options=kb_options,
                            value=active_scope["kb_id"],
                            on_change=on_kb_change,
                            label="Course",
                        ).props("outlined dense options-dense").classes("text-xs min-w-[200px]")

                    # Document selector (shown if DOCUMENT)
                    if active_scope["scope"] == "DOCUMENT":
                        doc_options = {d.id: d.filename for d in active_scope["docs"]}
                        if not active_scope["doc_id"] and active_scope["docs"]:
                            active_scope["doc_id"] = active_scope["docs"][0].id
                            active_scope["selected_doc"] = active_scope["docs"][0]

                        def on_doc_change(e: Any) -> None:
                            active_scope["doc_id"] = e.value
                            selected = next((d for d in active_scope["docs"] if d.id == e.value), None)
                            active_scope["selected_doc"] = selected
                            refresh_doc_warning()

                        ui.select(
                            options=doc_options,
                            value=active_scope["doc_id"],
                            on_change=on_doc_change,
                            label="Document",
                        ).props("outlined dense options-dense").classes("text-xs min-w-[220px]")

                    # Action diagnostics for Admin
                    with ui.row().classes("ml-auto items-center gap-2 flex-wrap"):
                        if is_admin and active_scope["kb_id"]:
                            kb_name = next(
                                (k.name for k in kbs if k.id == active_scope["kb_id"]), "Course"
                            )
                            ui.button(
                                "Dense Vector",
                                icon="manage_search",
                                on_click=lambda: open_vector_retrieval_dialog(
                                    active_scope["kb_id"], kb_name
                                ),
                            ).props("outline dense no-caps").classes("text-xs text-blue-700")
                            ui.button(
                                "Lexical FTS",
                                icon="search",
                                on_click=lambda: open_lexical_retrieval_dialog(
                                    active_scope["kb_id"], kb_name
                                ),
                            ).props("outline dense no-caps").classes("text-xs text-teal-700")
                            ui.button(
                                "Hybrid RRF",
                                icon="layers",
                                on_click=lambda: open_hybrid_retrieval_dialog(
                                    active_scope["kb_id"], kb_name
                                ),
                            ).props("outline dense no-caps").classes("text-xs text-indigo-700")
                            ui.button(
                                "Reranker",
                                icon="tune",
                                on_click=lambda: open_rerank_inspection_dialog(
                                    active_scope["kb_id"], kb_name
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

            # Top Context & Controls Card
            with ui.card().classes(
                "w-full p-3.5 bg-white border border-slate-200 rounded-lg shadow-xs mb-1"
            ):
                render_controls()

            # Warning banner for unindexed target doc
            refresh_doc_warning()

            # Main Two-Column Layout (Chat Thread + Evidence Panel)
            with ui.row().classes("w-full gap-6 items-start mt-2"):
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
                        "Ask a question about course materials, syllabi, grading, prerequisites..."
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

                # Validate scope parameters before sending
                cur_scope = active_scope["scope"]
                target_kb_id = active_scope["kb_id"] if cur_scope in ("COURSE", "DOCUMENT") else None
                target_doc_id = active_scope["doc_id"] if cur_scope == "DOCUMENT" else None

                if cur_scope in ("COURSE", "DOCUMENT") and not target_kb_id:
                    ui.notify("Please select a course for this search scope.", type="warning")
                    return

                if cur_scope == "DOCUMENT":
                    if not target_doc_id:
                        ui.notify("Please select a document for document-scoped search.", type="warning")
                        return
                    if active_scope["selected_doc"] and active_scope["selected_doc"].indexing_status != "COMPLETED":
                        ui.notify(
                            "Cannot query unindexed document. Please trigger indexing first.",
                            type="negative",
                        )
                        return

                # Append user question to state
                state.add_user_message(q)
                render_messages()
                render_evidence()

                # Enable loading state
                loading_row.visible = True
                send_btn.disable()

                try:
                    response = api_client.send_chat_message(
                        question=q,
                        kb_id=target_kb_id,
                        document_id=target_doc_id,
                        scope=cur_scope,
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

