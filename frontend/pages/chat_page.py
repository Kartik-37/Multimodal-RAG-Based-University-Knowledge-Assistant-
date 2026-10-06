"""
Conversational RAG Chat & Search Presentation Page.

Provides an accessible conversational thread grounded in the active knowledge base.
Follows standard asynchronous request-response architecture (no fake streaming).
Sanitizes markdown output to prevent arbitrary HTML execution.
Includes citation pill buttons linked to the evidence inspection panel.
Supports explicit search scopes: All Courses, Selected Course, and Selected Document.
"""

import html
from typing import Any

from nicegui import ui

from backend.app.core.permissions import Permission
from frontend.client.api_client import api_client
from frontend.client.citations import SemanticCitationRef, replace_citation_markers
from frontend.client.content_safety import sanitize_markdown_text
from frontend.client.error_handler import normalize_error
from frontend.client.models import CitationDTO, DocumentDTO, KnowledgeBaseDTO
from frontend.components.evidence_panel import render_evidence_panel
from frontend.components.hybrid_inspect import open_hybrid_retrieval_dialog
from frontend.components.layout import has_admin_permission, page_layout
from frontend.components.lexical_inspect import open_lexical_retrieval_dialog
from frontend.components.rerank_inspect import open_rerank_inspection_dialog
from frontend.components.retrieval_inspect import open_vector_retrieval_dialog
from frontend.components.source_viewer import open_source_viewer
from frontend.state.app_state import state


def format_citation_links(text: str, citations: list[CitationDTO]) -> str:
    """Transform citation tags [1], [2] or [source_1], [source_2] in assistant markdown into interactive citation pills.

    Separates semantic citation processing from visual pill rendering:
    Uses replace_citation_markers() to resolve citations semantically, then formats as NiceGUI citation-pill anchors.
    """
    if not citations or not text:
        return text

    def _render_pill(ref: SemanticCitationRef) -> str:
        idx = ref.index
        cit = ref.citation
        page_info = f" • Page {cit.page_number}" if cit.page_number else ""
        title_text = html.escape(f"Click to view {cit.document_name}{page_info} in Source Viewer", quote=True)
        return (
            f'<a href="#" data-citation-index="{idx}" '
            f'title="{title_text}" '
            f'class="citation-pill inline-flex items-center px-1.5 py-0.5 mx-0.5 text-[11px] font-bold font-mono '
            f"text-blue-700 bg-blue-100 hover:bg-blue-200 hover:text-blue-950 rounded cursor-pointer "
            f'no-underline border border-blue-300 transition-colors shadow-2xs">[{idx}]</a>'
        )

    return replace_citation_markers(text, citations, _render_pill)


def register_chat_page() -> None:
    """Register /chat route with NiceGUI."""

    @ui.page("/chat")
    def chat_page(kb_id: str | None = None) -> None:
        user = state.current_user
        is_admin = bool(user and user.role == "ADMIN")
        can_admin_chat = is_admin or has_admin_permission(user, Permission.ADMIN_CHAT)
        page_title = "Admin Knowledge Chat" if is_admin else "Ask RAG Assistant"
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
            if not user:
                return

            if is_admin and not can_admin_chat:
                with ui.card().classes(
                    "w-full max-w-2xl mx-auto p-6 bg-white border border-rose-200 rounded-lg shadow-xs"
                ):
                    ui.icon("lock", size="2.5rem").classes("text-rose-500 mb-2")
                    ui.label("Admin Chat Not Authorized").classes(
                        "text-lg font-bold text-slate-900"
                    )
                    ui.label(
                        "Your administrative account does not have permission for Admin Chat. Please contact the Main Administrator."
                    ).classes("text-sm text-slate-600")
                return

            # Fetch available knowledge bases for course selector.
            # Errors are kept distinct from a genuinely empty authorized course set.
            kbs: list[KnowledgeBaseDTO] = []
            course_load_error: str | None = None
            try:
                kbs = api_client.get_chat_scope_courses()
                # For students, ensure all published courses from the global catalog are available
                if not is_admin:
                    all_courses = api_client.get_knowledge_bases()
                    existing_ids = {k.id for k in kbs}
                    for c in all_courses:
                        if c.id not in existing_ids:
                            kbs.append(c)
            except ValueError as err:
                try:
                    kbs = api_client.get_knowledge_bases()
                except Exception:
                    course_load_error = normalize_error(err, context="course")

            # Check requested course; verify existence across global catalog if not in initial list
            requested_kb = next((course for course in kbs if course.id == kb_id), None)
            if kb_id and requested_kb is None:
                try:
                    all_courses = api_client.get_knowledge_bases()
                    requested_kb = next(
                        (course for course in all_courses if course.id == kb_id), None
                    )
                    if requested_kb and not any(k.id == requested_kb.id for k in kbs):
                        kbs.append(requested_kb)
                except Exception:
                    pass

            # For students, permission check allows course access as long as the course exists
            if kb_id and requested_kb is None and course_load_error is None:
                ui.notify("The requested course could not be found.", type="warning")

            selected_kb = requested_kb or state.active_kb
            if selected_kb is not None and not any(k.id == selected_kb.id for k in kbs):
                try:
                    all_courses = api_client.get_knowledge_bases()
                    if any(c.id == selected_kb.id for c in all_courses):
                        match_kb = next(c for c in all_courses if c.id == selected_kb.id)
                        kbs.append(match_kb)
                    else:
                        selected_kb = None
                except Exception:
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
                        document_load_error = normalize_error(err, context="document")
                else:
                    active_scope["docs"] = []

            if active_scope["kb_id"]:
                load_docs_for_current_kb()

            # Top Context & Controls Card
            with ui.card().classes(
                "w-full p-3.5 bg-white border border-slate-200 rounded-xl shadow-xs mb-1"
            ):
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

                    # Action diagnostics & chat controls
                    with ui.row().classes("ml-auto items-center gap-2 flex-wrap"):
                        diag_kb_id = active_scope["kb_id"] or (kbs[0].id if kbs else None)
                        if is_admin and diag_kb_id:
                            diag_kb_name = next(
                                (k.name for k in kbs if k.id == diag_kb_id), "Course"
                            )
                            with (
                                ui.button("Debug Mode", icon="bug_report")
                                .props("outline dense no-caps icon-right=arrow_drop_down")
                                .classes(
                                    "text-xs text-slate-700 border-slate-300 hover:bg-slate-50"
                                )
                            ):
                                with ui.menu().classes(
                                    "p-2 bg-white border border-slate-200 shadow-lg rounded-lg"
                                ) as debug_menu:
                                    ui.label("RAG Diagnostics").classes(
                                        "text-[10px] font-bold text-slate-400 uppercase tracking-wider px-2 py-1"
                                    )
                                    with ui.column().classes("gap-1 w-full min-w-[180px]"):
                                        ui.button(
                                            "Dense Vector",
                                            icon="manage_search",
                                            on_click=lambda k=diag_kb_id, n=diag_kb_name: (
                                                debug_menu.close(),
                                                open_vector_retrieval_dialog(k, n),
                                            ),
                                        ).props("flat dense no-caps align=left").classes(
                                            "w-full text-xs text-blue-700 justify-start hover:bg-blue-50"
                                        )
                                        ui.button(
                                            "Lexical FTS",
                                            icon="search",
                                            on_click=lambda k=diag_kb_id, n=diag_kb_name: (
                                                debug_menu.close(),
                                                open_lexical_retrieval_dialog(k, n),
                                            ),
                                        ).props("flat dense no-caps align=left").classes(
                                            "w-full text-xs text-teal-700 justify-start hover:bg-teal-50"
                                        )
                                        ui.button(
                                            "Hybrid RRF",
                                            icon="layers",
                                            on_click=lambda k=diag_kb_id, n=diag_kb_name: (
                                                debug_menu.close(),
                                                open_hybrid_retrieval_dialog(k, n),
                                            ),
                                        ).props("flat dense no-caps align=left").classes(
                                            "w-full text-xs text-indigo-700 justify-start hover:bg-indigo-50"
                                        )
                                        ui.button(
                                            "Reranker",
                                            icon="tune",
                                            on_click=lambda k=diag_kb_id, n=diag_kb_name: (
                                                debug_menu.close(),
                                                open_rerank_inspection_dialog(k, n),
                                            ),
                                        ).props("flat dense no-caps align=left").classes(
                                            "w-full text-xs text-purple-700 justify-start hover:bg-purple-50"
                                        )

                        def clear_chat_history() -> None:
                            state.clear_chat()
                            try:
                                send_btn.enable()
                                input_box.enable()
                            except NameError:
                                pass
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

            # Top Context & Controls populated directly inside card
            render_controls()

            # Scope/document load diagnostics
            refresh_scope_error()

            # Warning banner for unindexed target doc
            refresh_doc_warning()

            # Evidence Inspection Dialog (On-Demand Deep Technical Provenance)
            evidence_dialog = ui.dialog().props("position=right")
            with evidence_dialog:
                with ui.card().classes(
                    "w-[94vw] md:w-[540px] max-w-full h-full p-4 bg-white flex flex-col rounded-none md:rounded-l-2xl border-l border-slate-200"
                ):
                    with ui.row().classes("w-full items-center justify-between pb-3 border-b border-slate-100 mb-2"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("find_in_page", size="sm").classes("text-blue-600")
                            ui.label("Technical Grounding Inspection").classes("text-sm font-bold text-slate-800")
                        ui.button(icon="close", on_click=evidence_dialog.close).props("flat round dense")
                    evidence_container = ui.column().classes("w-full flex-1 overflow-y-auto")

            # Main Centered Chat Container
            with ui.column().classes("w-full max-w-4xl mx-auto gap-4 mt-2"):
                # Message Container (Responsive Studio Height)
                message_container = ui.column().classes(
                    "w-full min-h-[500px] max-h-[68vh] overflow-y-auto p-4 sm:p-6 bg-slate-50/60 border border-slate-200/90 rounded-2xl shadow-xs gap-4"
                )

                # Floating Input Dock
                input_placeholder = (
                    "Ask a question about course materials, syllabi, grading, prerequisites..."
                    if not is_admin
                    else "Ask a question to test retrieval, reranking, and citation synthesis..."
                )
                with ui.card().classes(
                    "w-full p-2.5 bg-white border border-slate-200/90 rounded-2xl shadow-xs hover:shadow-sm focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-100 transition-all"
                ):
                    with ui.row().classes("w-full items-center gap-2"):
                        input_box = (
                            ui.input(
                                placeholder=input_placeholder,
                            )
                            .props("outlined dense")
                            .classes("flex-1 text-sm minimalist-input")
                        )
                        send_btn = (
                            ui.button(icon="send")
                            .props("color=primary dense")
                            .classes(
                                "w-10 h-10 rounded-xl bg-blue-600 hover:bg-blue-700 text-white shadow-xs shrink-0 flex items-center justify-center transition-colors"
                            )
                        ).tooltip("Send question (Enter)")

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

                if state.is_generating:
                    ui.notify("RAG Assistant is still thinking. Please wait...", type="info")
                    return

                # Append user question to state immediately
                state.add_user_message(q)
                send_btn.disable()
                input_box.disable()
                render_messages()
                render_evidence()

                # Launch decoupled background generation so navigating pages doesn't abort it
                state.start_background_generation(
                    kb_id=target_kb_id,
                    question=q,
                    document_id=target_doc_id,
                    scope=cur_scope,
                )

            async def handle_submit() -> None:
                if state.is_generating:
                    ui.notify("RAG Assistant is still thinking. Please wait...", type="info")
                    return
                q = (input_box.value or "").strip()
                if not q:
                    ui.notify("Please enter a question.", type="warning")
                    return
                input_box.value = ""
                await send_message(q)

            send_btn.on("click", handle_submit)
            input_box.on("keydown.enter", handle_submit)

            # Observe background generation state across page visits
            was_generating = {"value": state.is_generating}

            def check_generation_status() -> None:
                is_now = state.is_generating
                if was_generating["value"] != is_now:
                    was_generating["value"] = is_now
                    if not is_now:
                        send_btn.enable()
                        input_box.enable()
                        if state.generation_error:
                            ui.notify(f"Query error: {state.generation_error}", type="negative")
                            state.clear_generation_error()
                        render_messages()
                        render_evidence()
                    else:
                        send_btn.disable()
                        input_box.disable()
                        render_messages()

            ui.timer(0.3, check_generation_status)

            if state.is_generating:
                send_btn.disable()
                input_box.disable()

            def select_citation(cit: CitationDTO) -> None:
                state.selected_citation = cit
                render_messages()
                render_evidence()

            def open_citation_viewer(cit: CitationDTO) -> None:
                state.selected_citation = cit
                try:
                    evidence_dialog.close()
                except Exception:
                    pass
                open_source_viewer(
                    document_id=cit.document_id,
                    document_name=cit.document_name,
                    kb_id=cit.knowledge_base_id,
                    page_number=cit.page_number,
                    course_name=cit.course_name,
                    snippet=cit.snippet,
                )

            def open_evidence_for_message(target_msg: Any) -> None:
                evidence_container.clear()
                with evidence_container:
                    citations = getattr(target_msg, "citations", []) or []
                    render_evidence_panel(
                        citations=citations,
                        selected_citation=citations[0] if citations else None,
                        on_select=select_citation,
                        on_open_viewer=open_citation_viewer,
                        is_admin=is_admin,
                    )
                evidence_dialog.open()

            def handle_citation_click(idx_val: Any) -> None:
                try:
                    idx = int(idx_val)
                except (ValueError, TypeError):
                    return
                assistant_msgs = [m for m in state.chat_history if m.role == "assistant"]
                if not assistant_msgs:
                    return
                latest_msg = assistant_msgs[-1]
                if not latest_msg.citations or idx < 1 or idx > len(latest_msg.citations):
                    return
                open_citation_viewer(latest_msg.citations[idx - 1])

            ui.on("citation_click", lambda e: handle_citation_click(e.args))

            def render_evidence() -> None:
                evidence_container.clear()
                with evidence_container:
                    assistant_msgs = [m for m in state.chat_history if m.role == "assistant"]
                    citations = assistant_msgs[-1].citations if assistant_msgs else []
                    render_evidence_panel(
                        citations=citations,
                        selected_citation=state.selected_citation,
                        on_select=select_citation,
                        on_open_viewer=open_citation_viewer,
                        is_admin=is_admin,
                    )

            def render_messages() -> None:
                message_container.clear()
                with message_container:
                    if not state.chat_history:
                        with ui.column().classes(
                            "w-full py-12 items-center justify-center text-center"
                        ):
                            with ui.element("div").classes(
                                "w-14 h-14 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-sm mb-3.5"
                            ):
                                ui.icon("school", size="28px")
                            ui.label("RAG Assistant").classes(
                                "text-lg font-bold text-slate-900 tracking-tight"
                            )
                            ui.label(
                                "Type your question below. Answers are synthesized strictly from authorized university "
                                "textbooks, syllabi, and official regulations with verifiable page citations."
                            ).classes("text-xs text-slate-500 max-w-md mt-1.5 mb-6 leading-relaxed")

                            # Starter prompts
                            ui.label("SUGGESTED QUESTIONS").classes(
                                "text-[10px] font-bold text-slate-400 tracking-wider mb-2"
                            )
                            with ui.row().classes("gap-2 flex-wrap justify-center max-w-xl"):
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
                                        "text-xs text-slate-700 border-slate-200 bg-white hover:border-blue-400 hover:text-blue-700 hover:bg-blue-50/50 rounded-xl px-3 py-1.5 shadow-2xs transition-all"
                                    )
                    else:
                        user_initials = (
                            "".join(p[0].upper() for p in user.full_name.split()[:2])
                            if user and user.full_name
                            else "U"
                        )
                        for msg in state.chat_history:
                            if msg.role == "user":
                                with ui.row().classes("w-full justify-end items-end gap-2.5"):
                                    with ui.element("div").classes(
                                        "max-w-2xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-5 py-3.5 rounded-2xl rounded-tr-xs shadow-xs text-sm leading-relaxed font-sans select-text"
                                    ):
                                        ui.label(msg.content).classes(
                                            "text-white leading-relaxed font-medium"
                                        )
                                    with ui.element("div").classes(
                                        "w-8 h-8 rounded-full bg-slate-200 text-slate-700 flex items-center justify-center font-bold text-xs shrink-0 mb-0.5 shadow-2xs"
                                    ):
                                        ui.label(user_initials)
                            else:
                                with ui.row().classes("w-full justify-start items-start gap-2.5"):
                                    with ui.element("div").classes(
                                        "w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-2xs shrink-0 mt-1"
                                    ):
                                        ui.icon("school", size="18px")
                                    with ui.card().classes(
                                        "w-full max-w-3xl bg-white border border-slate-200/90 p-5 sm:p-6 rounded-2xl rounded-tl-xs shadow-xs gap-3"
                                    ):
                                        # Assistant Header Meta
                                        with ui.row().classes(
                                            "w-full justify-between items-center mb-0.5"
                                        ):
                                            with ui.row().classes("items-center gap-2"):
                                                ui.label("RAG Assistant").classes(
                                                    "text-xs font-bold text-slate-900"
                                                )
                                            if msg.total_pipeline_ms:
                                                with ui.badge(
                                                    color="slate-100", text_color="slate-700"
                                                ).classes(
                                                    "text-[10px] font-mono border border-slate-200 px-2 py-0.5"
                                                ):
                                                    ui.label(f"⚡ {msg.total_pipeline_ms:.0f}ms")

                                        # Sanitized Markdown Answer with Interactive Citation Links
                                        formatted_content = format_citation_links(
                                            msg.content, msg.citations
                                        )
                                        clean_content = sanitize_markdown_text(formatted_content)
                                        ui.markdown(clean_content).classes(
                                            "safe-markdown text-sm leading-relaxed text-slate-800"
                                        )

                                        # Source Citations with Provenance & Quick PDF View
                                        if msg.citations:
                                            with ui.column().classes(
                                                "w-full mt-3 pt-3 border-t border-slate-100 gap-2"
                                            ):
                                                with ui.row().classes(
                                                    "items-center justify-between w-full flex-wrap gap-2"
                                                ):
                                                    with ui.row().classes("items-center gap-1.5"):
                                                        ui.icon("verified", size="16px").classes(
                                                            "text-blue-600"
                                                        )
                                                        ui.label(
                                                            f"Grounding Sources ({len(msg.citations)})"
                                                        ).classes("text-xs font-bold text-slate-800")
                                                        ui.label(
                                                            "• Click card to read in PDF Viewer"
                                                        ).classes(
                                                            "text-[11px] text-slate-400 font-normal"
                                                        )
                                                    ui.button(
                                                        "Inspect Provenance",
                                                        icon="find_in_page",
                                                        on_click=lambda m=msg: open_evidence_for_message(m),
                                                    ).props("flat dense no-caps").classes(
                                                        "text-[11px] text-blue-700 hover:bg-blue-50 font-semibold"
                                                    )

                                                with ui.row().classes("w-full gap-2 flex-wrap"):
                                                    for idx, cit in enumerate(
                                                        msg.citations, start=1
                                                    ):
                                                        page_lbl = (
                                                            f"Page {cit.page_number}"
                                                            if cit.page_number is not None
                                                            else "Document"
                                                        )
                                                        chunk_lbl = (
                                                            f" • Chunk {cit.chunk_id[:8]}"
                                                            if cit.chunk_id
                                                            else ""
                                                        )
                                                        is_p = cit.document_name.lower().endswith(
                                                            ".pdf"
                                                        )
                                                        with (
                                                            ui.card()
                                                            .classes(
                                                                "flex-1 min-w-[240px] p-3 bg-slate-50 border border-slate-200/80 rounded-xl hover:border-blue-400 hover:bg-blue-50/30 transition-all cursor-pointer group shadow-2xs flex flex-col justify-between"
                                                            )
                                                            .tooltip(
                                                                f"Open '{cit.document_name}' at {page_lbl} in Source Viewer"
                                                            )
                                                            .on(
                                                                "click",
                                                                lambda c=cit: open_citation_viewer(
                                                                    c
                                                                ),
                                                            )
                                                        ):
                                                            with ui.row().classes(
                                                                "items-center justify-between w-full"
                                                            ):
                                                                with ui.row().classes(
                                                                    "items-center gap-1.5 min-w-0 flex-1"
                                                                ):
                                                                    ui.badge(
                                                                        str(idx), color="blue-600"
                                                                    ).classes(
                                                                        "text-[9px] font-bold px-1.5 py-0.5 rounded-md"
                                                                    )
                                                                    ui.label(
                                                                        cit.document_name
                                                                    ).classes(
                                                                        "text-xs font-semibold text-slate-800 group-hover:text-blue-800 truncate"
                                                                    )
                                                                with ui.badge(
                                                                    color="blue-100",
                                                                    text_color="blue-900",
                                                                ).classes(
                                                                    "text-[10px] font-semibold px-2 py-0.5 border border-blue-200 shrink-0 gap-1 items-center"
                                                                ):
                                                                    ui.icon(
                                                                        "picture_as_pdf"
                                                                        if is_p
                                                                        else "description",
                                                                        size="11px",
                                                                    ).classes(
                                                                        "text-rose-500"
                                                                        if is_p
                                                                        else "text-slate-500"
                                                                    )
                                                                    ui.label(
                                                                        f"Page {cit.page_number}"
                                                                        if cit.page_number
                                                                        else "Read"
                                                                    )

                                                            meta_text = f"{cit.course_name or 'Course'}{chunk_lbl}"
                                                            ui.label(meta_text).classes(
                                                                "text-[10px] text-slate-400 font-mono mt-1 truncate"
                                                            )
                                                            if cit.snippet:
                                                                ui.label(
                                                                    f'"{cit.snippet.strip()}"'
                                                                ).classes(
                                                                    "text-[11px] text-slate-600 italic line-clamp-1 mt-0.5 font-sans"
                                                                )

                        if state.is_generating:
                            with ui.row().classes("w-full justify-start items-center gap-2.5 py-1 px-1"):
                                with ui.element("div").classes(
                                    "w-7 h-7 rounded-lg bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-2xs shrink-0"
                                ):
                                    ui.icon("school", size="16px")
                                with ui.row().classes("items-center gap-2"):
                                    ui.spinner(size="xs", color="primary")
                                    ui.label("Thinking...").classes(
                                        "text-xs font-medium text-slate-500 animate-pulse tracking-wide"
                                    )

            # Initial render
            render_messages()
            render_evidence()
