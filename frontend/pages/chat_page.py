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

from backend.app.core.permissions import Permission
from frontend.client.api_client import api_client
from frontend.client.models import CitationDTO, DocumentDTO, KnowledgeBaseDTO
from frontend.components.evidence_panel import render_evidence_panel
from frontend.components.hybrid_inspect import open_hybrid_retrieval_dialog
from frontend.components.layout import has_admin_permission, page_layout
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
    def chat_page(kb_id: str | None = None) -> None:
        user = state.current_user
        is_admin = bool(user and user.role == "ADMIN")
        can_admin_chat = is_admin or has_admin_permission(user, Permission.ADMIN_CHAT)
        page_title = "Admin Knowledge Chat" if is_admin else "Ask BCA Assistant"
        page_subtitle = (
            "Interactive RAG queries across authorized course materials with verifiable citations and provenance."
            if is_admin
            else "Ask questions across verified course materials with grounded citations."
        )

        with page_layout(
            title=page_title,
            subtitle=page_subtitle,
            active_route="/chat",
            require_auth=True,
        ):
            if not is_admin and not can_admin_chat:
                with ui.card().classes(
                    "w-full max-w-2xl mx-auto p-6 bg-white border border-rose-200 rounded-lg shadow-xs"
                ):
                    ui.icon("lock", size="2.5rem").classes("text-rose-500 mb-2")
                    ui.label("Chat Not Authorized").classes(
                        "text-lg font-bold text-slate-900"
                    )
                    ui.label(
                        "Your account is not authorized to access conversational assistant."
                    ).classes("text-sm text-slate-600")
                return

            # Fetch available knowledge bases for course selector.
            # Errors are kept distinct from a genuinely empty authorized course set.
            kbs: list[KnowledgeBaseDTO] = []
            course_load_error: str | None = None
            try:
                kbs = api_client.get_chat_scope_courses()
            except ValueError as err:
                course_load_error = str(err)

            requested_kb = next((course for course in kbs if course.id == kb_id), None)
            if kb_id and requested_kb is None and course_load_error is None:
                ui.notify("The requested course is not available to your account.", type="warning")

            selected_kb = requested_kb or state.active_kb
            if selected_kb is not None and not any(k.id == selected_kb.id for k in kbs):
                selected_kb = None

            # Determine initial scope and selections
            initial_scope = "COURSE" if selected_kb else "ALL_COURSES"
            active_scope: dict[str, Any] = {
                "scope": initial_scope,
                "kb_id": selected_kb.id if selected_kb else (kbs[0].id if kbs else None),
                "doc_id": None,
                "docs": [],
                "selected_doc": None,
            }

            document_load_error: str | None = None

            def load_docs_for_current_kb() -> None:
                nonlocal document_load_error
                document_load_error = None
                if active_scope["kb_id"]:
                    try:
                        active_scope["docs"] = api_client.get_documents(active_scope["kb_id"])
                    except ValueError as err:
                        active_scope["docs"] = []
                        document_load_error = str(err)
                else:
                    active_scope["docs"] = []

            if active_scope["kb_id"]:
                load_docs_for_current_kb()

            # Dynamic containers
            scope_controls_row = ui.row().classes("w-full items-center gap-3 flex-wrap")
            scope_error_container = ui.column().classes("w-full")
            doc_warning_container = ui.column().classes("w-full")

            def refresh_scope_error() -> None:
                scope_error_container.clear()
                if course_load_error:
                    with scope_error_container:
                        ui.label(f"Unable to load courses. {course_load_error}").classes(
                            "text-xs text-rose-700"
                        )
                elif document_load_error and active_scope["scope"] == "DOCUMENT":
                    with scope_error_container:
                        ui.label(f"Unable to load documents. {document_load_error}").classes(
                            "text-xs text-rose-700"
                        )

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
                            with ui.row().classes(
                                "w-full items-center justify-between gap-2 flex-wrap"
                            ):
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
                                        ui.notify(
                                            f"Indexing trigger failed: {exc}", type="negative"
                                        )

                                if (
                                    doc.indexing_status == "FAILED"
                                    and has_admin_permission(user, Permission.DOCUMENT_INDEX_RETRY)
                                ) or (
                                    doc.indexing_status != "FAILED"
                                    and has_admin_permission(user, Permission.DOCUMENT_INDEX)
                                ):
                                    ui.button(
                                        "Retry Indexing"
                                        if doc.indexing_status == "FAILED"
                                        else "Index Document",
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
                            active_scope["doc_id"] = None
                            active_scope["selected_doc"] = None
                            if e.value == "COURSE" and not active_scope["kb_id"] and kbs:
                                active_scope["kb_id"] = kbs[0].id
                                load_docs_for_current_kb()
                            elif e.value == "DOCUMENT":
                                if not active_scope["kb_id"] and kbs:
                                    active_scope["kb_id"] = kbs[0].id
                                load_docs_for_current_kb()
                                if active_scope["docs"]:
                                    active_scope["selected_doc"] = active_scope["docs"][0]
                                    active_scope["doc_id"] = active_scope["docs"][0].id
                            else:
                                active_scope["kb_id"] = None
                                active_scope["docs"] = []
                            render_controls()
                            refresh_scope_error()
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
                            # Course changes invalidate every previous document selection.
                            active_scope["selected_doc"] = None
                            active_scope["doc_id"] = None
                            active_scope["docs"] = []
                            selected = next((k for k in kbs if k.id == e.value), None)
                            if selected:
                                state.active_kb = selected
                            load_docs_for_current_kb()
                            if active_scope["scope"] == "DOCUMENT" and active_scope["docs"]:
                                active_scope["selected_doc"] = active_scope["docs"][0]
                                active_scope["doc_id"] = active_scope["docs"][0].id
                            render_controls()
                            refresh_scope_error()
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
                            selected = next(
                                (d for d in active_scope["docs"] if d.id == e.value), None
                            )
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

            # Scope/document load diagnostics
            refresh_scope_error()

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
                target_kb_id = (
                    active_scope["kb_id"] if cur_scope in ("COURSE", "DOCUMENT") else None
                )
                target_doc_id = active_scope["doc_id"] if cur_scope == "DOCUMENT" else None

                if cur_scope in ("COURSE", "DOCUMENT") and not target_kb_id:
                    ui.notify("Please select a course for this search scope.", type="warning")
                    return

                if cur_scope == "DOCUMENT":
                    if not target_doc_id:
                        ui.notify(
                            "Please select a document for document-scoped search.", type="warning"
                        )
                        return
                    if (
                        active_scope["selected_doc"]
                        and active_scope["selected_doc"].indexing_status != "COMPLETED"
                    ):
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

                                        # Source Citations with Provenance
                                        if msg.citations:
                                            with ui.column().classes(
                                                "w-full mt-3 pt-2.5 border-t border-slate-200 gap-1.5"
                                            ):
                                                ui.label("Sources & Evidence:").classes(
                                                    "text-[11px] font-bold text-slate-700"
                                                )
                                                for idx, cit in enumerate(msg.citations, start=1):
                                                    course_lbl = (
                                                        f" • {cit.course_name}"
                                                        if cit.course_name
                                                        else ""
                                                    )
                                                    page_lbl = (
                                                        f" • Page {cit.page_number}"
                                                        if cit.page_number is not None
                                                        else ""
                                                    )
                                                    chunk_lbl = (
                                                        f" • Chunk {cit.chunk_id[:8]}"
                                                        if cit.chunk_id
                                                        else ""
                                                    )
                                                    with (
                                                        ui.row()
                                                        .classes(
                                                            "w-full items-center justify-between p-2 rounded bg-white border border-slate-200 hover:border-blue-400 transition-colors cursor-pointer"
                                                        )
                                                        .on("click", lambda c=cit: select_citation(c))
                                                    ):
                                                        with ui.row().classes(
                                                            "items-center gap-2 min-w-0"
                                                        ):
                                                            ui.badge(str(idx), color="blue-700").classes(
                                                                "text-[9px] font-bold px-1.5 py-0.5"
                                                            )
                                                            with ui.column().classes("gap-0 min-w-0"):
                                                                ui.label(cit.document_name).classes(
                                                                    "text-xs font-semibold text-slate-900 truncate"
                                                                )
                                                                ui.label(
                                                                    f"Evidence{course_lbl}{page_lbl}{chunk_lbl}"
                                                                ).classes(
                                                                    "text-[10px] text-slate-500 font-mono"
                                                                )
                                                        ui.icon("chevron_right", size="xs").classes(
                                                            "text-slate-400"
                                                        )

            # Initial render
            render_messages()
            render_evidence()
