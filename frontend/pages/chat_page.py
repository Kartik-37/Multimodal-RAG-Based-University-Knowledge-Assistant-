"""
Conversational RAG Chat & Search Presentation Page.

Editorial Academic Identity Workspace:
- Integrated Question Composer with internal Course Scope Selector
- Responsive Desktop Conversation History Sidebar & Mobile History Drawer
- First-class 'New Chat' action (replacing legacy Clear Chat)
- Real 'Stop Generating' action with instantaneous cancellation
- Message-stable citation-to-document provenance mapping
- Strict multi-tenant and role authorization isolation
"""

import html
from typing import Any

from nicegui import ui

from backend.app.core.permissions import Permission
from frontend.client.api_client import api_client
from frontend.client.citations import (
    SemanticCitationRef,
    group_citations_by_document,
    replace_citation_markers,
)
from frontend.client.content_safety import sanitize_markdown_text
from frontend.client.models import CitationDTO, KnowledgeBaseDTO
from frontend.components.evidence_panel import render_evidence_panel
from frontend.components.layout import has_admin_permission, page_layout
from frontend.components.source_viewer import open_source_viewer
from frontend.state.app_state import state


def generate_conversation_title(question: str) -> str:
    """Generate a clean, readable conversation title deterministically from the first question."""
    clean = " ".join(question.strip().split())
    if not clean:
        return "New chat"
    if len(clean) <= 80:
        return clean
    truncated = clean[:75]
    last_space = truncated.rfind(" ")
    if last_space > 40:
        truncated = truncated[:last_space]
    return truncated.rstrip(",;:- ") + "..."


def format_citation_links(
    text: str, citations: list[CitationDTO], message_id: str = ""
) -> str:
    """Format inline citations into interactive pills with stable message-id tracking."""
    if not citations or not text:
        return text

    def _render_pill(ref: SemanticCitationRef) -> str:
        idx = ref.index
        cit = ref.citation
        page_info = f" • Page {cit.page_number}" if cit.page_number else ""
        title_text = html.escape(
            f"View {cit.document_name}{page_info} in Source Viewer", quote=True
        )
        msg_attr = (
            f' data-message-id="{html.escape(message_id, quote=True)}"'
            if message_id
            else ""
        )
        return (
            f'<a href="#" data-citation-index="{idx}"{msg_attr} '
            f'title="{title_text}" '
            f'class="citation-pill inline-flex items-center px-1.5 py-0.5 mx-0.5 text-xs font-bold font-mono '
            f"text-gold bg-gold-light hover:bg-surface hover:text-primary-navy rounded cursor-pointer "
            f'no-underline border border-subtle transition-colors shadow-none">[{idx}]</a>'
        )

    return replace_citation_markers(text, citations, _render_pill)


def register_chat_page() -> None:
    @ui.page("/chat")
    def chat_page(
        kb_id: str | None = None,
        q: str | None = None,
        preview_generating: str | None = None,
        conversation_id: str | None = None,
    ) -> None:
        user = state.current_user
        is_admin = bool(user and user.role == "ADMIN")
        can_admin_chat = is_admin or has_admin_permission(user, Permission.ADMIN_CHAT)

        with page_layout(
            title="",
            subtitle="",
            active_route="/chat",
            require_auth=True,
        ):
            if not user:
                return
            if conversation_id and conversation_id != state.active_conversation_id:
                try:
                    state.load_conversation(conversation_id)
                except Exception:
                    pass
            if is_admin and not can_admin_chat:
                with ui.column().classes("w-full py-16 items-center text-center"):
                    ui.icon("lock", size="2.5rem").classes("text-rose-700 mb-2")
                    ui.label("Admin Chat Not Authorized").classes(
                        "text-xl font-bold text-rose-700 font-editorial"
                    )
                    ui.label("You do not have administrative chat privileges.").classes(
                        "text-sm text-secondary-navy"
                    )
                return

            # Authoritative course and scope loading (never merged with unauthorized broader endpoints)
            kbs: list[KnowledgeBaseDTO] = []
            try:
                kbs = api_client.get_chat_scope_courses()
            except Exception:
                kbs = []

            requested_kb = (
                next((c for c in kbs if c.id == kb_id), None) if kb_id else None
            )
            if requested_kb:
                state.set_scope("COURSE", requested_kb.id)
            elif not state.active_conversation_id:
                state.reset_scope()

            active_scope: dict[str, Any] = {
                "scope": state.active_scope,
                "kb_id": state.active_kb_id,
                "doc_id": getattr(state, "active_doc_id", None),
                "docs": [],
                "selected_doc": None,
            }

            def load_docs_for_current_kb() -> None:
                if active_scope["kb_id"]:
                    try:
                        active_scope["docs"] = api_client.get_documents(
                            active_scope["kb_id"]
                        )
                    except Exception:
                        active_scope["docs"] = []
                else:
                    active_scope["docs"] = []

            if active_scope["kb_id"]:
                load_docs_for_current_kb()
            if active_scope.get("doc_id") and active_scope.get("docs"):
                active_scope["selected_doc"] = next((d for d in active_scope["docs"] if d.id == active_scope["doc_id"]), None)

            # Evidence Side Drawer / Modal
            evidence_dialog = ui.dialog().props("position=right")
            with evidence_dialog:
                with ui.card().classes(
                    "w-[94vw] md:w-[600px] h-full p-6 bg-surface-elevated flex flex-col rounded-none md:rounded-l border-l border-subtle"
                ):
                    with ui.row().classes(
                        "w-full items-center justify-between pb-4 border-b border-subtle mb-4"
                    ):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("find_in_page", size="20px").classes("text-gold")
                            ui.label("Evidence & Provenance").classes(
                                "text-lg font-bold text-primary-navy font-editorial"
                            )
                        ui.button(icon="close", on_click=evidence_dialog.close).props(
                            "flat round dense"
                        ).classes("text-secondary-navy hover:text-primary-navy")
                    evidence_container = ui.column().classes("w-full flex-1 overflow-y-auto")

            # ------------------------------------------------------------------
            # Main Conversational Workspace
            # ------------------------------------------------------------------
            with ui.column().classes(
                "w-full flex-1 flex flex-col justify-between overflow-hidden min-w-0 max-w-full h-full bg-canvas box-border"
            ).style("height: 100%; max-height: 100%;"):
                # Header
                header_container = ui.row().classes(
                    "w-full items-center justify-between px-3 sm:px-6 py-2 border-b border-subtle shrink-0 gap-2 bg-canvas min-w-0 max-w-full box-border"
                )

                # Conversation Scroll Area (Prohibit horizontal scrolling across chat viewport)
                with ui.column().classes(
                    "w-full flex-1 overflow-y-auto overflow-x-hidden min-h-0 py-3 px-3 sm:px-6 chat-scroll-area flex flex-col min-w-0 max-w-full box-border"
                ):
                    message_container = ui.column().classes(
                        "w-full max-w-3xl mx-auto gap-4 pb-8 flex-1 flex flex-col min-h-full min-w-0 max-w-full box-border"
                    )

                # Composer Outer Container
                with ui.column().classes(
                    "w-full shrink-0 pt-2 pb-3 px-3 sm:px-6 border-t border-subtle bg-canvas z-10 min-w-0 max-w-full box-border"
                ):
                    with ui.column().classes("w-full max-w-3xl mx-auto gap-1 min-w-0 max-w-full box-border"):
                        # Composer Card
                        with ui.card().classes(
                            "w-full p-2.5 sm:p-3 bg-surface-elevated border border-subtle rounded-xl shadow-none hover:border-gold/60 focus-within:border-gold transition-colors flex flex-col gap-2 min-w-0 max-w-full box-border"
                        ):
                            # Top Row: Input and Action Button (Send / Stop)
                            with ui.row().classes("w-full items-center gap-2 no-wrap pb-0.5 min-w-0"):
                                input_box = (
                                    ui.input(
                                        placeholder="Ask a question about your course materials..."
                                    )
                                    .props("dense borderless")
                                    .classes(
                                        "flex-1 text-sm sm:text-base text-primary-navy pl-1 sm:pl-2 font-sans placeholder:text-secondary-navy/60 min-w-0"
                                    )
                                )
                                action_btn_container = ui.row().classes(
                                    "items-center shrink-0"
                                )

                            # Bottom Toolbar: Integrated Scope Selector & Keyboard Hint
                            with ui.row().classes(
                                "w-full items-center justify-between pt-2.5 sm:pt-3 pb-0.5 border-t border-subtle/60 text-xs text-secondary-navy font-sans gap-2 flex-wrap min-w-0"
                            ):
                                composer_scope_container = ui.row().classes(
                                    "items-center gap-1.5 min-w-0 flex-1"
                                )
                                ui.label("Press Enter ↵ to ask").classes(
                                    "hidden sm:block text-secondary-navy/70 ml-auto shrink-0"
                                )

            # ------------------------------------------------------------------
            # Citation & Evidence Resolution
            # ------------------------------------------------------------------
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
                    return_to="/chat",
                    conv_id=state.active_conversation_id,
                )

            def select_citation(cit: CitationDTO) -> None:
                state.selected_citation = cit
                render_messages()
                render_evidence()

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

            def handle_citation_click(e: Any) -> None:
                args = e.args
                msg_id = ""
                idx = -1
                if isinstance(args, dict):
                    try:
                        idx = int(args.get("index", -1))
                    except (ValueError, TypeError):
                        idx = -1
                    msg_id = str(args.get("message_id") or "")
                elif isinstance(args, (int, str)):
                    try:
                        idx = int(args)
                    except (ValueError, TypeError):
                        idx = -1

                if idx <= 0:
                    return

                target_msg = None
                if msg_id:
                    target_msg = next(
                        (m for m in state.chat_history if getattr(m, "id", None) == msg_id),
                        None,
                    )

                if not target_msg:
                    assistant_msgs = [
                        m
                        for m in state.chat_history
                        if getattr(m, "role", "") == "assistant"
                        and getattr(m, "citations", None)
                    ]
                    if assistant_msgs:
                        target_msg = assistant_msgs[-1]

                if target_msg and getattr(target_msg, "citations", None):
                    citations = target_msg.citations
                    if 0 <= (idx - 1) < len(citations):
                        open_citation_viewer(citations[idx - 1])

            ui.on("citation_click", handle_citation_click)

            is_submitting = {"value": False}

            def on_custom_submit(e: Any) -> None:
                if is_submitting["value"] or state.is_generating:
                    return
                text = ""
                raw = getattr(e, "args", e)
                if isinstance(raw, list) and len(raw) > 0:
                    raw = raw[0]
                if isinstance(raw, str):
                    text = raw
                elif isinstance(raw, dict):
                    text = str(raw.get("question") or "")
                if text:
                    input_box.value = text
                    send_message(text)

            ui.on("submit_chat_question", on_custom_submit)

            def render_evidence() -> None:
                evidence_container.clear()
                with evidence_container:
                    assistant_msgs = [
                        m for m in state.chat_history if getattr(m, "role", "") == "assistant"
                    ]
                    render_evidence_panel(
                        citations=assistant_msgs[-1].citations if assistant_msgs else [],
                        selected_citation=state.selected_citation,
                        on_select=select_citation,
                        on_open_viewer=open_citation_viewer,
                        is_admin=is_admin,
                    )

            # ------------------------------------------------------------------
            # Stop Generating & Submit Actions
            # ------------------------------------------------------------------
            def handle_stop() -> None:
                state.stop_generating()
                is_submitting["value"] = False
                try:
                    input_box.enable()
                except Exception:
                    pass
                render_action_btn()
                render_messages()

            def is_scope_valid() -> tuple[bool, str]:
                if active_scope["scope"] == "COURSE" and not active_scope.get("kb_id"):
                    return False, "Please select a specific course before asking questions"
                if active_scope["scope"] == "DOCUMENT":
                    if not active_scope.get("kb_id"):
                        return False, "Please select a course before asking questions in Document scope"
                    if not active_scope.get("doc_id"):
                        return False, "Please select a specific document before asking questions"
                return True, ""

            def handle_retry() -> None:
                if is_submitting["value"] or state.is_generating:
                    return
                user_msgs = [m for m in state.chat_history if getattr(m, "role", "") == "user"]
                if not user_msgs:
                    return
                last_q = user_msgs[-1].content
                # Remove trailing error assistant message if present
                if state.chat_history and state.chat_history[-1].role == "assistant":
                    state.chat_history.pop()
                state.clear_generation_error()
                render_messages()
                state.start_background_generation(
                    kb_id=active_scope["kb_id"]
                    if active_scope["scope"] in ("COURSE", "DOCUMENT")
                    else None,
                    question=last_q,
                    document_id=active_scope["doc_id"]
                    if active_scope["scope"] == "DOCUMENT"
                    else None,
                    scope=active_scope["scope"],
                    conversation_id=state.active_conversation_id,
                )
                render_action_btn()

            def send_message(question_text: str) -> None:
                q_clean = question_text.strip()
                if not q_clean or is_submitting["value"] or state.is_generating:
                    return
                scope_valid, scope_reason = is_scope_valid()
                if not scope_valid:
                    ui.notify(scope_reason, type="warning")
                    return

                is_submitting["value"] = True
                try:
                    # 1. Immediately append user question to visible thread and clear composer
                    state.add_user_message(q_clean)
                    try:
                        input_box.value = ""
                        input_box.disable()
                    except Exception:
                        pass
                    render_action_btn()
                    render_messages()

                    # 2. If no active conversation exists, create one immediately
                    if not state.active_conversation_id:
                        initial_title = generate_conversation_title(q_clean)
                        try:
                            new_conv = api_client.create_conversation(
                                title=initial_title,
                                scope=active_scope["scope"],
                                kb_id=active_scope.get("kb_id"),
                                doc_id=active_scope.get("doc_id"),
                            )
                            state.active_conversation_id = new_conv.id
                            ui.run_javascript(f"window.history.replaceState({{}}, '', '/chat?conversation_id={new_conv.id}');")
                        except Exception:
                            pass
                    else:
                        # 3. If this is the first question in a 'New chat', update the title immediately
                        user_msgs = [m for m in state.chat_history if getattr(m, "role", "") == "user"]
                        if len(user_msgs) <= 1:
                            new_title = generate_conversation_title(q_clean)
                            state.update_active_conversation_title(new_title)

                    render_evidence()
                    state.start_background_generation(
                        kb_id=active_scope["kb_id"]
                        if active_scope["scope"] in ("COURSE", "DOCUMENT")
                        else None,
                        question=q_clean,
                        document_id=active_scope["doc_id"]
                        if active_scope["scope"] == "DOCUMENT"
                        else None,
                        scope=active_scope["scope"],
                        conversation_id=state.active_conversation_id,
                    )
                    render_action_btn()
                finally:
                    is_submitting["value"] = False

            def handle_submit() -> None:
                if is_submitting["value"] or state.is_generating:
                    return
                val = (input_box.value or "").strip()
                if not val:
                    return
                scope_valid, scope_reason = is_scope_valid()
                if not scope_valid:
                    ui.notify(scope_reason, type="warning")
                    return
                send_message(val)

            input_box.on("keydown.enter.prevent", handle_submit)

            def render_action_btn() -> None:
                action_btn_container.clear()
                with action_btn_container:
                    if state.is_generating:
                        # Stop Generating Action
                        (
                            ui.button(icon="stop", on_click=handle_stop)
                            .props("round dense")
                            .classes(
                                "w-9 h-9 sm:w-10 sm:h-10 bg-rose-700 text-white shrink-0 hover:bg-rose-800 transition-colors shadow-none"
                            )
                            .props('aria-label="Stop generating"')
                        )
                    else:
                        # Normal Send Action
                        scope_valid, scope_reason = is_scope_valid()
                        btn_cls = "w-9 h-9 sm:w-10 sm:h-10 bg-surface-navy text-inverted shrink-0 hover:bg-surface-navy/90 transition-transform shadow-none"
                        if not scope_valid:
                            btn_cls += " opacity-40 cursor-not-allowed"
                        btn = (
                            ui.button(icon="arrow_upward", on_click=handle_submit)
                            .props("round dense")
                            .classes(btn_cls)
                            .props('aria-label="Send question"')
                        )
                        if not scope_valid:
                            btn.props(f'title="{html.escape(scope_reason, quote=True)}"')

            # Polling Generation Status to toggle button & re-enable input
            was_generating = {"value": state.is_generating}

            def check_generation_status() -> None:
                is_active_conv_gen = (
                    state.is_conversation_generating(state.active_conversation_id)
                    if hasattr(state, "is_conversation_generating")
                    else state.is_generating
                )
                is_now = state.is_generating or is_active_conv_gen
                if was_generating["value"] != is_now:
                    was_generating["value"] = is_now
                    if not is_now:
                        is_submitting["value"] = False
                        try:
                            input_box.enable()
                        except Exception:
                            pass
                        if state.generation_error:
                            state.clear_generation_error()
                        render_action_btn()
                        render_messages()
                        render_evidence()
                    else:
                        render_action_btn()
                        render_messages()

            ui.timer(0.3, check_generation_status)

            # ------------------------------------------------------------------
            # Integrated Scope Selector (inside Question Composer)
            # ------------------------------------------------------------------
            def select_student_scope(scope_val: str, kb_val: str | None) -> None:
                active_scope["scope"] = scope_val
                active_scope["kb_id"] = kb_val
                state.set_scope(scope_val, kb_val)
                render_composer_scope()
                render_header()
                render_action_btn()

            def render_composer_scope() -> None:
                composer_scope_container.clear()
                with composer_scope_container:
                    if not is_admin:
                        is_all_courses = (
                            active_scope["scope"] == "ALL_COURSES"
                            or not active_scope.get("kb_id")
                        )
                        current_course = (
                            next((k for k in kbs if k.id == active_scope.get("kb_id")), None)
                            if not is_all_courses
                            else None
                        )
                        current_label = (
                            current_course.name if current_course else "All available courses"
                        )
                        pill_icon = "public" if is_all_courses else "menu_book"

                        # Scope Pill Selector Trigger inside composer bottom toolbar
                        btn_classes = (
                            "scope-selector-btn h-[38px] sm:h-[40px] px-3.5 sm:px-4 text-[13px] sm:text-sm font-medium "
                            "text-primary-navy bg-surface hover:bg-surface-elevated border "
                            + ("border-gold/70 bg-gold-light/30 " if not is_all_courses else "border-subtle ")
                            + "hover:border-gold/80 rounded-full transition-all shadow-none group flex items-center"
                        )
                        with (
                            ui.button()
                            .props("no-caps outline rounded")
                            .classes(btn_classes)
                            .props(f'title="{html.escape(current_label, quote=True)}"')
                            .props('aria-label="Search scope selector"')
                        ):
                            with ui.row().classes("items-center gap-2 no-wrap"):
                                ui.icon(pill_icon, size="16px").classes("text-gold shrink-0")
                                ui.label(current_label).classes(
                                    "max-w-[160px] xs:max-w-[220px] sm:max-w-[320px] md:max-w-[380px] truncate text-left font-sans text-[13px] sm:text-sm font-medium leading-none"
                                )
                                ui.icon("unfold_more", size="15px").classes(
                                    "text-secondary-navy/60 group-hover:text-gold transition-colors shrink-0"
                                )

                            # Attached Scope Popover Menu
                            with ui.menu().props(
                                'anchor="top start" self="bottom start" :offset="[0, 56]"'
                            ).classes(
                                "scope-popover-menu p-3 bg-surface-elevated border border-gold/30 shadow-xl rounded-2xl w-[320px] sm:w-[360px] max-w-[calc(100vw-2rem)]"
                            ) as scope_menu:
                                with ui.column().classes("w-full gap-1.5"):
                                    # Header & Reset to All
                                    with ui.row().classes(
                                        "w-full items-center justify-between px-1.5 pt-0.5 pb-1"
                                    ):
                                        ui.label("Course Search Scope").classes(
                                            "text-[11px] font-bold font-sans uppercase tracking-wider text-secondary-navy"
                                        )
                                        if not is_all_courses:
                                            ui.button(
                                                "Reset to All",
                                                on_click=lambda: (
                                                    scope_menu.close(),
                                                    select_student_scope("ALL_COURSES", None),
                                                ),
                                            ).props("flat dense no-caps").classes(
                                                "text-[11px] text-gold hover:text-primary-navy font-semibold p-0"
                                            )

                                    # Search Filter Input
                                    search_filter = (
                                        ui.input(placeholder="Search courses...")
                                        .props("dense outlined rounded clearable autofocus")
                                        .classes("w-full text-xs font-sans px-0.5 pb-1")
                                    )

                                    # Options Container
                                    options_container = ui.column().classes(
                                        "w-full max-h-56 overflow-y-auto gap-0.5"
                                    )

                                    def update_menu_options(query_filter: str = "") -> None:
                                        options_container.clear()
                                        with options_container:
                                            q_clean = query_filter.strip().lower()

                                            # 1. "All available courses" row
                                            if (
                                                not q_clean
                                                or "all" in q_clean
                                                or "course" in q_clean
                                            ):
                                                all_classes = (
                                                    "bg-surface font-semibold text-primary-navy border border-gold/40"
                                                    if is_all_courses
                                                    else "hover:bg-surface text-secondary-navy hover:text-primary-navy border border-transparent"
                                                )
                                                with (
                                                    ui.row()
                                                    .classes(
                                                        f"w-full items-center justify-between px-2.5 py-1.5 rounded-lg cursor-pointer transition-colors {all_classes}"
                                                    )
                                                    .on(
                                                        "click",
                                                        lambda: (
                                                            scope_menu.close(),
                                                            select_student_scope(
                                                                "ALL_COURSES", None
                                                            ),
                                                        ),
                                                    )
                                                ):
                                                    with ui.row().classes(
                                                        "items-center gap-2 min-w-0"
                                                    ):
                                                        ui.icon("public", size="15px").classes(
                                                            "text-gold shrink-0"
                                                            if is_all_courses
                                                            else "text-secondary-navy/70 shrink-0"
                                                        )
                                                        with ui.column().classes(
                                                            "gap-0 min-w-0"
                                                        ):
                                                            ui.label(
                                                                "All available courses"
                                                            ).classes(
                                                                "text-xs leading-tight font-sans"
                                                            )
                                                            ui.label(
                                                                "Search across all authorized courses"
                                                            ).classes(
                                                                "text-[10px] text-secondary-navy/70 leading-tight"
                                                            )
                                                    if is_all_courses:
                                                        ui.icon("check", size="16px").classes(
                                                            "text-gold shrink-0"
                                                        )

                                            ui.separator().classes("my-0.5 opacity-60")

                                            # 2. Individual courses
                                            filtered_kbs = [
                                                k
                                                for k in kbs
                                                if not q_clean
                                                or q_clean in k.name.lower()
                                                or (
                                                    k.description
                                                    and q_clean in k.description.lower()
                                                )
                                            ]

                                            if not filtered_kbs:
                                                if q_clean:
                                                    with ui.row().classes(
                                                        "w-full p-2.5 justify-center text-center"
                                                    ):
                                                        ui.label(
                                                            f'No courses match "{query_filter.strip()}"'
                                                        ).classes(
                                                            "text-xs text-secondary-navy italic"
                                                        )
                                                else:
                                                    with ui.row().classes(
                                                        "w-full p-2.5 justify-center text-center"
                                                    ):
                                                        ui.label(
                                                            "No additional courses available"
                                                        ).classes(
                                                            "text-xs text-secondary-navy italic"
                                                        )
                                            else:
                                                for k in filtered_kbs:
                                                    is_selected = (
                                                        not is_all_courses
                                                        and active_scope.get("kb_id") == k.id
                                                    )
                                                    row_classes = (
                                                        "bg-surface font-semibold text-primary-navy border border-gold/40"
                                                        if is_selected
                                                        else "hover:bg-surface text-secondary-navy hover:text-primary-navy border border-transparent"
                                                    )
                                                    with (
                                                        ui.row()
                                                        .classes(
                                                            f"w-full items-center justify-between px-2.5 py-1.5 rounded-lg cursor-pointer transition-colors {row_classes}"
                                                        )
                                                        .on(
                                                            "click",
                                                            lambda target_id=k.id: (
                                                                scope_menu.close(),
                                                                select_student_scope(
                                                                    "COURSE", target_id
                                                                ),
                                                            ),
                                                        )
                                                    ):
                                                        with ui.row().classes(
                                                            "items-center gap-2 min-w-0 flex-1"
                                                        ):
                                                            ui.icon(
                                                                "menu_book", size="15px"
                                                            ).classes(
                                                                "text-gold shrink-0"
                                                                if is_selected
                                                                else "text-secondary-navy/70 shrink-0"
                                                            )
                                                            with ui.column().classes(
                                                                "gap-0 min-w-0 flex-1"
                                                            ):
                                                                ui.label(k.name).classes(
                                                                    "text-xs leading-tight font-sans break-words"
                                                                )
                                                                doc_txt = (
                                                                    f"{k.document_count} documents"
                                                                    if k.document_count
                                                                    else "Course materials"
                                                                )
                                                                ui.label(doc_txt).classes(
                                                                    "text-[10px] text-secondary-navy/70 leading-tight"
                                                                )
                                                        if is_selected:
                                                            ui.icon("check", size="16px").classes(
                                                                "text-gold shrink-0"
                                                            )

                                    search_filter.on_value_change(
                                        lambda e: update_menu_options(e.value or "")
                                    )
                                    update_menu_options()
                    else:
                        # Polished Admin Scope Pill Trigger and Upward Popover Menu
                        admin_mode = active_scope.get("scope", "ALL_COURSES")
                        selected_kb = next((k for k in kbs if k.id == active_scope.get("kb_id")), None)

                        if admin_mode == "ALL_COURSES":
                            pill_label = "All Published Courses"
                            pill_icon = "public"
                            is_custom_scope = False
                        elif admin_mode == "COURSE":
                            pill_label = selected_kb.name if selected_kb else "Select Course..."
                            pill_icon = "menu_book"
                            is_custom_scope = True
                        else:  # DOCUMENT
                            pill_label = active_scope["selected_doc"].original_filename if active_scope.get("selected_doc") else "Select Document..."
                            pill_icon = "description"
                            is_custom_scope = True

                        btn_classes = (
                            "scope-selector-btn h-[38px] sm:h-[40px] px-3.5 sm:px-4 text-[13px] sm:text-sm font-medium "
                            "text-primary-navy bg-surface hover:bg-surface-elevated border "
                            + ("border-gold/70 bg-gold-light/30 " if is_custom_scope else "border-subtle ")
                            + "hover:border-gold/80 rounded-full transition-all shadow-none group flex items-center"
                        )
                        with (
                            ui.button()
                            .props("no-caps outline rounded")
                            .classes(btn_classes)
                            .props(f'title="{html.escape(pill_label, quote=True)}"')
                            .props('aria-label="Admin search scope selector"')
                        ):
                            with ui.row().classes("items-center gap-2 no-wrap"):
                                trigger_pill_icon = ui.icon(pill_icon, size="16px").classes("text-gold shrink-0")
                                trigger_pill_label = ui.label(pill_label).classes(
                                    "max-w-[160px] xs:max-w-[220px] sm:max-w-[320px] md:max-w-[380px] truncate text-left font-sans text-[13px] sm:text-sm font-medium leading-none"
                                )
                                ui.icon("unfold_more", size="15px").classes(
                                    "text-secondary-navy/60 group-hover:text-gold transition-colors shrink-0"
                                )

                            # Attached Upward-Opening Scope Popover Menu
                            with ui.menu().props(
                                'anchor="top start" self="bottom start" :offset="[0, 56]"'
                            ).classes(
                                "scope-popover-menu p-3 bg-surface-elevated border border-gold/30 shadow-xl rounded-2xl w-[320px] sm:w-[380px] max-w-[calc(100vw-2rem)]"
                            ) as admin_scope_menu:
                                menu_content_container = ui.column().classes("w-full gap-2")

                                def render_menu_content() -> None:
                                    menu_content_container.clear()
                                    cur_mode = active_scope.get("scope", "ALL_COURSES")
                                    cur_kb = next((k for k in kbs if k.id == active_scope.get("kb_id")), None)
                                    is_custom = cur_mode != "ALL_COURSES"

                                    # Update trigger button label and icon
                                    if cur_mode == "ALL_COURSES":
                                        trigger_pill_label.text = "All Published Courses"
                                        trigger_pill_icon.name = "public"
                                    elif cur_mode == "COURSE":
                                        trigger_pill_label.text = cur_kb.name if cur_kb else "Select Course..."
                                        trigger_pill_icon.name = "menu_book"
                                    else:
                                        trigger_pill_label.text = active_scope["selected_doc"].original_filename if active_scope.get("selected_doc") else "Select Document..."
                                        trigger_pill_icon.name = "description"

                                    with menu_content_container:
                                        # Header & Reset Action
                                        with ui.row().classes("w-full items-center justify-between px-1.5 pt-0.5 pb-1 border-b border-subtle/60"):
                                            ui.label("Admin Scope Mode").classes(
                                                "text-[11px] font-bold font-sans uppercase tracking-wider text-secondary-navy"
                                            )
                                            if is_custom:
                                                def reset_admin_scope():
                                                    active_scope["scope"] = "ALL_COURSES"
                                                    active_scope["kb_id"] = None
                                                    active_scope["doc_id"] = None
                                                    active_scope["selected_doc"] = None
                                                    state.reset_scope()
                                                    admin_scope_menu.close()
                                                    render_composer_scope()
                                                    render_header()
                                                    render_action_btn()
                                                ui.button(
                                                    "Reset to All",
                                                    on_click=reset_admin_scope,
                                                ).props("flat dense no-caps").classes(
                                                    "text-[11px] text-gold hover:text-primary-navy font-semibold p-0"
                                                )

                                        # 3 Segmented Scope Mode Buttons
                                        with ui.row().classes("w-full bg-surface p-1 rounded-xl gap-1"):
                                            def set_admin_mode(m: str):
                                                active_scope["scope"] = m
                                                if m == "ALL_COURSES":
                                                    active_scope["kb_id"] = None
                                                    active_scope["doc_id"] = None
                                                    active_scope["selected_doc"] = None
                                                    state.set_scope("ALL_COURSES", None, None)
                                                    admin_scope_menu.close()
                                                    render_composer_scope()
                                                elif m == "COURSE":
                                                    active_scope["doc_id"] = None
                                                    active_scope["selected_doc"] = None
                                                    if active_scope.get("kb_id") not in [k.id for k in kbs]:
                                                        active_scope["kb_id"] = None
                                                    state.set_scope("COURSE", active_scope.get("kb_id"), None)
                                                    render_menu_content()
                                                elif m == "DOCUMENT":
                                                    if active_scope.get("kb_id") not in [k.id for k in kbs]:
                                                        active_scope["kb_id"] = None
                                                        active_scope["doc_id"] = None
                                                        active_scope["selected_doc"] = None
                                                    else:
                                                        load_docs_for_current_kb()
                                                    state.set_scope("DOCUMENT", active_scope.get("kb_id"), active_scope.get("doc_id"))
                                                    render_menu_content()
                                                render_header()
                                                render_action_btn()

                                            for m_key, m_lbl, m_ic in [
                                                ("ALL_COURSES", "All Courses", "public"),
                                                ("COURSE", "Course", "menu_book"),
                                                ("DOCUMENT", "Document", "description"),
                                            ]:
                                                is_cur = (cur_mode == m_key)
                                                mode_cls = (
                                                    "flex-1 py-1.5 px-2 text-xs font-semibold rounded-lg text-center transition-all "
                                                    + ("bg-surface-navy text-inverted shadow-sm " if is_cur else "text-secondary-navy hover:text-primary-navy hover:bg-surface-elevated ")
                                                )
                                                with ui.row().classes(f"{mode_cls} items-center justify-center gap-1 cursor-pointer").on(
                                                    "click", lambda mk=m_key: set_admin_mode(mk)
                                                ):
                                                    ui.icon(m_ic, size="13px")
                                                    ui.label(m_lbl).classes("text-[11px]")

                                        # Content based on mode
                                        if cur_mode == "COURSE":
                                            with ui.column().classes("w-full gap-1 pt-1"):
                                                ui.label("Select Target Course:").classes("text-[11px] font-semibold text-secondary-navy px-1")
                                                admin_search = (
                                                    ui.input(placeholder="Search courses...")
                                                    .props("dense outlined rounded clearable autofocus")
                                                    .classes("w-full text-xs font-sans px-0.5 pb-1")
                                                )
                                                courses_container = ui.column().classes("w-full max-h-48 overflow-y-auto gap-0.5")

                                                def update_admin_course_list(q_text: str = "") -> None:
                                                    courses_container.clear()
                                                    q_c = q_text.strip().lower()
                                                    matched_kbs = [
                                                        k
                                                        for k in kbs
                                                        if not q_c
                                                        or q_c in k.name.lower()
                                                        or (k.description and q_c in k.description.lower())
                                                    ]
                                                    with courses_container:
                                                        if not matched_kbs:
                                                            ui.label(
                                                                f'No courses match "{q_text.strip()}"' if q_c else "No courses available"
                                                            ).classes("text-xs text-secondary-navy italic p-2 text-center")
                                                        for k in matched_kbs:
                                                            is_sel = (active_scope.get("kb_id") == k.id)
                                                            row_cls = (
                                                                "bg-surface font-semibold text-primary-navy border border-gold/40"
                                                                if is_sel
                                                                else "hover:bg-surface text-secondary-navy hover:text-primary-navy border border-transparent"
                                                            )
                                                            def select_course(cid=k.id):
                                                                active_scope["kb_id"] = cid
                                                                state.set_scope("COURSE", cid, None)
                                                                load_docs_for_current_kb()
                                                                admin_scope_menu.close()
                                                                render_composer_scope()
                                                                render_header()
                                                                render_action_btn()
                                                            with ui.row().classes(
                                                                f"w-full items-center justify-between px-2.5 py-1.5 rounded-lg cursor-pointer transition-colors {row_cls}"
                                                            ).on("click", select_course):
                                                                with ui.row().classes("items-center gap-2 min-w-0 flex-1"):
                                                                    ui.icon("menu_book", size="14px").classes("text-gold" if is_sel else "text-secondary-navy/70")
                                                                    with ui.column().classes("gap-0 min-w-0 flex-1"):
                                                                        ui.label(k.name).classes("text-xs font-sans truncate")
                                                                        doc_txt = f"{k.document_count} documents" if k.document_count else "Course materials"
                                                                        ui.label(doc_txt).classes("text-[10px] text-secondary-navy/70 leading-tight")
                                                                if is_sel:
                                                                    ui.icon("check", size="15px").classes("text-gold shrink-0")

                                                admin_search.on_value_change(lambda e: update_admin_course_list(e.value or ""))
                                                update_admin_course_list()
                                        elif cur_mode == "DOCUMENT":
                                            with ui.column().classes("w-full gap-1 pt-1"):
                                                ui.label("Course:").classes("text-[11px] font-semibold text-secondary-navy px-1")
                                                course_options = {k.id: k.name for k in kbs}
                                                def on_doc_kb_change(e: Any):
                                                    active_scope["kb_id"] = e.value
                                                    active_scope["doc_id"] = None
                                                    active_scope["selected_doc"] = None
                                                    state.set_scope("DOCUMENT", e.value, None)
                                                    load_docs_for_current_kb()
                                                    render_menu_content()
                                                    render_header()
                                                    render_action_btn()
                                                ui.select(
                                                    options=course_options,
                                                    value=active_scope.get("kb_id"),
                                                    on_change=on_doc_kb_change,
                                                    label="Select Course",
                                                ).props("dense outlined options-dense").classes("w-full text-xs font-sans")

                                                ui.label("Select Document:").classes("text-[11px] font-semibold text-secondary-navy px-1 pt-1")
                                                doc_container = ui.column().classes("w-full max-h-40 overflow-y-auto gap-0.5")
                                                with doc_container:
                                                    if not active_scope.get("kb_id"):
                                                        ui.label("Select a course above to view available documents").classes(
                                                            "text-xs text-secondary-navy italic px-2 py-1"
                                                        )
                                                    elif not active_scope["docs"]:
                                                        ui.label("No eligible documents available in this course").classes(
                                                            "text-xs text-rose-700 italic px-2 py-1"
                                                        )
                                                    else:
                                                        for doc_item in active_scope["docs"]:
                                                            is_doc_sel = (active_scope.get("doc_id") == doc_item.id)
                                                            row_cls = (
                                                                "bg-surface font-semibold text-primary-navy border border-gold/40"
                                                                if is_doc_sel
                                                                else "hover:bg-surface text-secondary-navy hover:text-primary-navy border border-transparent"
                                                            )
                                                            def select_doc(d=doc_item):
                                                                active_scope["doc_id"] = d.id
                                                                active_scope["selected_doc"] = d
                                                                state.set_scope("DOCUMENT", active_scope["kb_id"], d.id)
                                                                admin_scope_menu.close()
                                                                render_composer_scope()
                                                                render_header()
                                                                render_action_btn()
                                                            with ui.row().classes(
                                                                f"w-full items-center justify-between px-2.5 py-1.5 rounded-lg cursor-pointer transition-colors {row_cls}"
                                                            ).on("click", select_doc):
                                                                with ui.row().classes("items-center gap-2 min-w-0 flex-1"):
                                                                    ui.icon("description", size="14px").classes("text-gold" if is_doc_sel else "text-secondary-navy/70")
                                                                    ui.label(doc_item.original_filename).classes("text-xs font-sans truncate")
                                                                if is_doc_sel:
                                                                    ui.icon("check", size="15px").classes("text-gold shrink-0")

                                render_menu_content()

            # ------------------------------------------------------------------
            # Render Header (Identity & History Toggle & New Chat)
            # ------------------------------------------------------------------
            def render_header() -> None:
                header_container.clear()
                with header_container:
                    # Left: Identity Title & Scope Indicator
                    with ui.row().classes("items-center gap-2.5 min-w-0"):
                        base_title = "Admin Knowledge Chat" if is_admin else "Academic Knowledge Assistant"
                        ui.label(base_title).classes(
                            "text-base sm:text-lg font-bold font-editorial text-primary-navy tracking-tight truncate shrink-0"
                        )

                        active_title = None
                        if state.active_conversation_id:
                            try:
                                conv = api_client.get_conversation(state.active_conversation_id)
                                active_title = conv.title
                            except Exception:
                                pass

                        if active_title:
                            with ui.row().classes(
                                "items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-surface border border-subtle text-xs text-secondary-navy truncate max-w-[200px] sm:max-w-xs hidden sm:flex"
                            ):
                                ui.icon("chat_bubble_outline", size="12px").classes("text-gold shrink-0")
                                ui.label(active_title).classes("truncate font-sans text-[11px]")

                        # Scope badge if specific course selected
                        if active_scope.get("scope") == "COURSE" and active_scope.get("kb_id"):
                            course_obj = next((k for k in kbs if k.id == active_scope["kb_id"]), None)
                            badge_name = course_obj.name if course_obj else "Course Scope"
                            with ui.row().classes(
                                "items-center gap-1 px-2.5 py-0.5 rounded-full bg-gold-light border border-gold/40 text-[11px] font-medium text-primary-navy hidden sm:flex"
                            ):
                                ui.icon("menu_book", size="12px").classes("text-gold")
                                ui.label(badge_name).classes("truncate max-w-[150px]")
                        elif active_scope.get("scope") == "DOCUMENT" and active_scope.get("selected_doc"):
                            doc_name = active_scope["selected_doc"].original_filename
                            with ui.row().classes(
                                "items-center gap-1 px-2.5 py-0.5 rounded-full bg-gold-light border border-gold/40 text-[11px] font-medium text-primary-navy hidden sm:flex"
                            ):
                                ui.icon("description", size="12px").classes("text-gold")
                                ui.label(doc_name).classes("truncate max-w-[150px]")

                    # Header right spacer (New Chat is prominently placed in primary sidebar)
                    with ui.row().classes("items-center gap-2 ml-auto shrink-0"):
                        pass

            # ------------------------------------------------------------------
            # Render Messages & Academic Empty State
            # ------------------------------------------------------------------
            def render_messages() -> None:
                message_container.clear()
                with message_container:
                    if not state.chat_history:
                        # Academic empty state - centered in workspace
                        with ui.column().classes(
                            "w-full flex-1 flex flex-col justify-center items-center text-center max-w-xl mx-auto px-4 py-12 sm:py-20 my-auto gap-3"
                        ):
                            ui.icon("school", size="3rem").classes("text-gold mb-1 opacity-90")
                            ui.label("Academic Knowledge Assistant").classes(
                                "text-2xl sm:text-3xl md:text-4xl font-bold text-primary-navy font-editorial tracking-tight mb-1"
                            )
                            ui.label(
                                "Ask questions across official course syllabi, lecture notes, and university documents. "
                                "Every answer is synthesized exclusively from verified texts with clickable citations."
                            ).classes(
                                "text-xs sm:text-sm md:text-base text-secondary-navy leading-relaxed max-w-md mx-auto"
                            )
                    else:
                        for msg in state.chat_history:
                            if msg.role == "user":
                                with ui.row().classes("w-full justify-end items-end gap-3 min-w-0 max-w-full box-border"):
                                    with ui.element("div").classes(
                                        "max-w-2xl bg-surface-elevated border border-subtle text-primary-navy px-4 py-2.5 sm:px-5 sm:py-3 rounded-2xl rounded-tr-sm shadow-none min-w-0 box-border break-words"
                                    ):
                                        ui.label(msg.content).classes(
                                            "text-sm sm:text-base text-primary-navy font-sans leading-relaxed break-words whitespace-pre-wrap"
                                        )
                            else:
                                is_err = msg.id.startswith("msg-err-") or ("timed out" in (msg.content or "").lower() and not msg.citations)
                                if is_err:
                                    with ui.card().classes(
                                        "w-full max-w-3xl p-4 bg-rose-50/70 border border-rose-200 rounded-xl gap-2 shadow-none min-w-0 box-border"
                                    ):
                                        with ui.row().classes("items-center justify-between w-full"):
                                            with ui.row().classes("items-center gap-2"):
                                                ui.icon("error_outline", size="20px").classes("text-rose-700")
                                                ui.label("Answer Generation Issue").classes("text-xs font-bold text-rose-800 uppercase tracking-wider")
                                            ui.button(
                                                "Retry",
                                                icon="refresh",
                                                on_click=handle_retry,
                                            ).props("flat dense no-caps").classes("text-xs font-semibold text-rose-700 hover:text-rose-900 bg-rose-100/70 px-2.5 py-1 rounded-md")
                                        ui.label(msg.content).classes("text-sm text-rose-900 font-sans leading-relaxed break-words")
                                else:
                                    with ui.column().classes(
                                        "w-full max-w-3xl gap-2.5 bg-canvas py-1 min-w-0 max-w-full box-border"
                                    ):
                                        # Markdown answer content
                                        clean_content = sanitize_markdown_text(
                                            format_citation_links(
                                                msg.content, msg.citations, message_id=msg.id
                                            )
                                        )
                                        ui.markdown(clean_content).classes(
                                            "safe-markdown text-base sm:text-[16.5px] leading-relaxed text-primary-navy font-sans w-full min-w-0 max-w-full break-words"
                                        )

                                    # Cited Sources Tray
                                    if msg.citations:
                                        with ui.column().classes(
                                            "w-full mt-3 pt-2.5 border-t border-subtle/80 gap-2 min-w-0 max-w-full box-border"
                                        ):
                                            with ui.row().classes(
                                                "items-center justify-between w-full min-w-0"
                                            ):
                                                ui.label("Cited Sources").classes(
                                                    "text-[11px] font-semibold font-sans tracking-wider uppercase text-secondary-navy/80"
                                                )
                                                ui.button(
                                                    "Inspect Provenance",
                                                    icon="find_in_page",
                                                    on_click=lambda m=msg: open_evidence_for_message(m),
                                                ).props("flat dense no-caps").classes(
                                                    "text-xs font-semibold text-secondary-navy hover:text-gold"
                                                )

                                            doc_groups = group_citations_by_document(msg.citations)
                                            with ui.column().classes("w-full gap-2 min-w-0 max-w-full"):
                                                for group in doc_groups:
                                                    is_pdf = group.document_name.lower().endswith(".pdf")
                                                    doc_icon = "picture_as_pdf" if is_pdf else "description"
                                                    with (
                                                        ui.card()
                                                        .classes(
                                                            "w-full p-2.5 sm:p-3 bg-surface-elevated border border-subtle rounded-lg shadow-none gap-2 min-w-0 max-w-full box-border"
                                                        )
                                                    ):
                                                        with ui.row().classes(
                                                            "w-full items-start sm:items-center justify-between gap-2 min-w-0"
                                                        ):
                                                            with ui.row().classes(
                                                                "items-start sm:items-center gap-2 flex-1 min-w-0"
                                                            ):
                                                                ui.icon(doc_icon, size="16px").classes(
                                                                    "text-primary-navy shrink-0 mt-0.5 sm:mt-0"
                                                                )
                                                                ui.label(group.document_name).classes(
                                                                    "text-xs sm:text-sm font-semibold text-primary-navy break-all sm:break-words leading-tight"
                                                                )
                                                            if group.course_name:
                                                                ui.label(group.course_name).classes(
                                                                    "text-[10px] font-mono text-secondary-navy/80 shrink-0"
                                                                )

                                                        with ui.row().classes(
                                                            "w-full items-center gap-1.5 flex-wrap pt-0.5 min-w-0"
                                                        ):
                                                            for pref in group.pages:
                                                                if pref.page_number is not None:
                                                                    page_label = f"Page {pref.page_number}"
                                                                    title_hover = (
                                                                        f"View {group.document_name} (Page {pref.page_number}) in Source Viewer"
                                                                    )
                                                                else:
                                                                    page_label = "View Document"
                                                                    title_hover = (
                                                                        f"View {group.document_name} in Source Viewer"
                                                                    )
                                                                indices_str = ",".join(str(i) for i in pref.citation_indices)
                                                                with (
                                                                    ui.row()
                                                                    .classes(
                                                                        "items-center gap-1.5 px-2 py-1 bg-canvas hover:bg-surface border border-subtle hover:border-gold rounded cursor-pointer transition-colors"
                                                                    )
                                                                    .props(f'title="{html.escape(title_hover, quote=True)}"')
                                                                    .on(
                                                                        "click",
                                                                        lambda c=pref.citation: open_citation_viewer(c),
                                                                    )
                                                                ):
                                                                    ui.label(f"[{indices_str}]").classes(
                                                                        "text-[10px] font-mono font-bold text-gold shrink-0"
                                                                    )
                                                                    ui.label(page_label).classes(
                                                                        "text-xs font-medium text-primary-navy font-mono"
                                                                    )
                                                                    ui.icon("open_in_new", size="11px").classes(
                                                                        "text-secondary-navy/70 hover:text-gold shrink-0"
                                                                    )

                    gen_status = (
                        state.get_generation_status(state.active_conversation_id)
                        if hasattr(state, "get_generation_status")
                        else None
                    )
                    is_active_conv_gen = (
                        state.is_conversation_generating(state.active_conversation_id)
                        if hasattr(state, "is_conversation_generating")
                        else state.is_generating
                    )
                    if state.is_generating or is_active_conv_gen or gen_status:
                        status_msg = (
                            "Waiting in queue behind active query..."
                            if gen_status == "queued"
                            else "Synthesizing answer from verified texts..."
                        )
                        with ui.row().classes(
                            "items-center gap-3 py-2.5 px-4 bg-surface rounded-lg border border-subtle max-w-md mt-2 min-w-0"
                        ):
                            ui.spinner(size="1.25rem", color="primary-navy")
                            ui.label(status_msg).classes(
                                "text-xs font-semibold text-secondary-navy font-sans"
                            )

                ui.run_javascript("""
                    setTimeout(() => {
                        const sc = document.querySelector('.chat-scroll-area');
                        if (sc) { sc.scrollTo({ top: sc.scrollHeight, behavior: 'smooth' }); }
                    }, 200);
                """)

            def on_state_update() -> None:
                active_scope["scope"] = state.active_scope
                active_scope["kb_id"] = state.active_kb_id
                active_scope["doc_id"] = getattr(state, "active_doc_id", None)
                if active_scope["kb_id"]:
                    load_docs_for_current_kb()
                if active_scope["doc_id"] and active_scope["docs"]:
                    active_scope["selected_doc"] = next((d for d in active_scope["docs"] if d.id == active_scope["doc_id"]), None)
                else:
                    active_scope["selected_doc"] = None

                if not state.chat_history:
                    try:
                        input_box.value = ""
                        input_box.enable()
                    except Exception:
                        pass
                render_composer_scope()
                render_header()
                render_messages()
                render_evidence()
                render_action_btn()

            unsub_chat = state.subscribe(on_state_update)
            try:
                ui.context.client.on_disconnect(unsub_chat)
            except Exception:
                pass

            render_header()
            render_composer_scope()
            render_action_btn()
            render_messages()
            render_evidence()

            if q:
                input_box.value = q
                ui.timer(0.1, handle_submit, once=True)
            elif preview_generating == "1":
                state.is_generating = True
                if not state.chat_history:
                    state.add_user_message(
                        "Explain all course policies and examination grading in detail?"
                    )
                render_action_btn()
                render_messages()
