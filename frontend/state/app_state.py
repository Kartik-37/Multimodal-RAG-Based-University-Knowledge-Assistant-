"""
Frontend Presentation State Management.

Maintains UI state across page views:
- Active knowledge base selection
- Selected citation evidence for detail view
- Active conversation message thread and persistent conversation tracking
- Decoupled background query synthesis and real cancellation
"""

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any

from frontend.client.api_client import _get_browser_session_id, api_client
from frontend.client.error_handler import normalize_error
from frontend.client.models import (
    ChatMessageDTO,
    CitationDTO,
    KnowledgeBaseDTO,
    UserDTO,
)


@dataclass
class ConversationGeneration:
    """Tracks the background generation lifecycle for an individual conversation thread."""

    conversation_id: str
    task: asyncio.Task[Any] | None
    status: str  # "queued", "generating", "completed", "error", "cancelled"
    question: str
    kb_id: str | None
    document_id: str | None
    scope: str
    error: str | None = None
    response: ChatMessageDTO | None = None
    generation_id: int = 0


class AppState:
    """Application state manager for presentation session."""

    def __init__(self) -> None:
        self._active_kb: KnowledgeBaseDTO | None = None
        self._selected_citation: CitationDTO | None = None
        self._chat_history: list[ChatMessageDTO] = []
        self._generations: dict[str, ConversationGeneration] = {}
        self._generation_counter: int = 0
        self._concurrency_lock: asyncio.Lock | None = None
        self._generation_error: str | None = None
        self._active_conversation_id: str | None = None
        self._listeners: list[Any] = []
        self._reader_context: dict[str, Any] = {}
        self._active_scope: str = "ALL_COURSES"
        self._active_kb_id: str | None = None
        self._active_doc_id: str | None = None

    @property
    def reader_context(self) -> dict[str, Any]:
        """Server-managed active reader session context (snippet, page, origin)."""
        return getattr(self, "_reader_context", {})

    def set_reader_context(
        self,
        document_id: str | None = None,
        document_name: str | None = None,
        page_number: int | None = None,
        kb_id: str | None = None,
        course_name: str | None = None,
        snippet: str | None = None,
        return_to: str | None = None,
        conv_id: str | None = None,
        citation: CitationDTO | None = None,
    ) -> None:
        """Store transient reader context safely in session state."""
        self._reader_context = {
            "document_id": document_id,
            "document_name": document_name,
            "page_number": page_number,
            "kb_id": kb_id,
            "course_name": course_name,
            "snippet": snippet,
            "return_to": return_to,
            "conv_id": conv_id,
            "citation": citation,
        }

    def subscribe(self, listener: Any) -> Any:
        """Register a callback for state changes (e.g. conversation switches)."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener) if listener in self._listeners else None

    def notify(self) -> None:
        """Notify all registered listeners of a state change."""
        for fn in list(self._listeners):
            try:
                fn()
            except Exception:
                pass

    @property
    def active_conversation_id(self) -> str | None:
        """Active persistent conversation UUID, or None if in draft new chat."""
        return self._active_conversation_id

    @active_conversation_id.setter
    def active_conversation_id(self, conv_id: str | None) -> None:
        self._active_conversation_id = conv_id

    @property
    def is_generating(self) -> bool:
        """Check if the currently active conversation is actively synthesizing an answer or queued."""
        conv_id = self._active_conversation_id
        if not conv_id:
            draft_gen = self._generations.get("__draft__")
            return draft_gen is not None and draft_gen.status in ("generating", "queued")
        gen = self._generations.get(conv_id)
        return gen is not None and gen.status in ("generating", "queued")

    @is_generating.setter
    def is_generating(self, value: bool) -> None:
        conv_id = self._active_conversation_id or "__draft__"
        if not value and conv_id in self._generations:
            self._generations[conv_id].status = "completed"

    def is_conversation_generating(self, conv_id: str | None) -> bool:
        """Check if a specific conversation is actively generating or queued."""
        if not conv_id:
            return False
        gen = self._generations.get(conv_id)
        return gen is not None and gen.status in ("generating", "queued")

    def get_generation_status(self, conv_id: str | None = None) -> str | None:
        """Get the generation status string for a conversation ('queued', 'generating', 'completed', etc.)."""
        target_id = conv_id or self._active_conversation_id or "__draft__"
        gen = self._generations.get(target_id)
        return gen.status if gen else None

    @property
    def active_scope(self) -> str:
        """Active question query scope ('ALL_COURSES', 'COURSE', 'DOCUMENT')."""
        return getattr(self, "_active_scope", "ALL_COURSES")

    @active_scope.setter
    def active_scope(self, value: str) -> None:
        self._active_scope = value

    @property
    def active_kb_id(self) -> str | None:
        """Active course ID filter, or None for ALL_COURSES."""
        return getattr(self, "_active_kb_id", None)

    @active_kb_id.setter
    def active_kb_id(self, value: str | None) -> None:
        self._active_kb_id = value

    @property
    def active_doc_id(self) -> str | None:
        """Active document ID filter, or None."""
        return getattr(self, "_active_doc_id", None)

    @active_doc_id.setter
    def active_doc_id(self, value: str | None) -> None:
        self._active_doc_id = value

    def set_scope(
        self,
        scope: str = "ALL_COURSES",
        kb_id: str | None = None,
        doc_id: str | None = None,
    ) -> None:
        """Update active scope, course ID, and document ID filter."""
        self._active_scope = scope
        self._active_kb_id = kb_id
        self._active_doc_id = doc_id

    def reset_scope(self) -> None:
        """Reset scope to ALL_COURSES."""
        self._active_scope = "ALL_COURSES"
        self._active_kb_id = None
        self._active_doc_id = None

    @property
    def generation_error(self) -> str | None:
        """Get background query generation error if any."""
        return self._generation_error

    def clear_generation_error(self) -> None:
        """Clear generation error state."""
        self._generation_error = None

    def start_background_generation(
        self,
        kb_id: str | None,
        question: str,
        document_id: str | None = None,
        scope: str = "ALL_COURSES",
        conversation_id: str | None = None,
    ) -> None:
        """
        Launch background query synthesis keyed strictly to its conversation identity.
        Continues executing in the background even if the user switches conversations or routes.
        """
        target_conv_id = conversation_id or self._active_conversation_id or "__draft__"

        # Check if this specific conversation is already generating or queued
        existing = self._generations.get(target_conv_id)
        if existing and existing.status in ("generating", "queued"):
            return

        self._generation_counter += 1
        current_gen_id = self._generation_counter

        gen = ConversationGeneration(
            conversation_id=target_conv_id,
            task=None,
            status="queued",
            question=question,
            kb_id=kb_id,
            document_id=document_id,
            scope=scope,
            error=None,
            response=None,
            generation_id=current_gen_id,
        )
        self._generations[target_conv_id] = gen
        self._generation_error = None

        # Capture the active session-bound client on the main event loop thread
        client = api_client.get_client() if hasattr(api_client, "get_client") else api_client._get_client()

        if self._concurrency_lock is None:
            self._concurrency_lock = asyncio.Lock()

        async def _run_async_query() -> None:
            # Concurrency limit: one active LLM query at a time to prevent Ollama thrashing,
            # while remaining queries queue cleanly and update status.
            try:
                async with self._concurrency_lock:
                    if gen.status == "cancelled" or gen.generation_id != current_gen_id:
                        return
                    gen.status = "generating"
                    self.notify()

                    resp = await asyncio.to_thread(
                        client.send_chat_message,
                        kb_id=kb_id,
                        question=question,
                        document_id=document_id,
                        scope=scope,
                        conversation_id=None if target_conv_id == "__draft__" else target_conv_id,
                    )

                    if gen.status == "cancelled" or gen.generation_id != current_gen_id:
                        return

                    resolved_conv_id = resp.conversation_id or target_conv_id
                    gen.status = "completed"
                    gen.response = resp

                    # If draft conversation received a real conversation_id from server
                    if target_conv_id == "__draft__" and resp.conversation_id:
                        self._generations[resp.conversation_id] = gen
                        if self._active_conversation_id in (None, "__draft__"):
                            self._active_conversation_id = resp.conversation_id

                    # If student or admin is currently viewing this conversation, update active thread and citations
                    if self._active_conversation_id == resolved_conv_id:
                        self._chat_history.append(resp)
                        if resp.citations:
                            self._selected_citation = resp.citations[0]

            except asyncio.CancelledError:
                gen.status = "cancelled"
                return
            except Exception as e:
                if gen.status == "cancelled" or gen.generation_id != current_gen_id:
                    return
                clean_err = normalize_error(e, context="chat")
                gen.status = "error"
                gen.error = clean_err
                err_msg = ChatMessageDTO(
                    id=f"msg-err-{uuid.uuid4().hex[:8]}",
                    role="assistant",
                    content=clean_err,
                    citations=[],
                )
                gen.response = err_msg

                if self._active_conversation_id == target_conv_id:
                    self._generation_error = clean_err
                    self._chat_history.append(err_msg)
            finally:
                if gen.generation_id == current_gen_id and gen.status in ("generating", "queued"):
                    gen.status = "completed"
                self.notify()

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            try:
                loop = asyncio.get_event_loop_policy().get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

        gen.task = loop.create_task(_run_async_query())
        self.notify()

    def stop_generating(self, conv_id: str | None = None) -> None:
        """
        Request immediate cancellation of in-progress answer generation for a specific conversation.
        Cancels only the target conversation's task without affecting other conversations.
        """
        target_id = conv_id or self._active_conversation_id or "__draft__"
        gen = self._generations.get(target_id)
        if not gen or gen.status not in ("generating", "queued"):
            return

        gen.status = "cancelled"
        if gen.task and not gen.task.done():
            gen.task.cancel()

        if self._active_conversation_id == target_id:
            stopped_msg = ChatMessageDTO(
                id=f"msg-stopped-{uuid.uuid4().hex[:8]}",
                role="assistant",
                content="*(Response generation stopped by user)*",
                citations=[],
            )
            self._chat_history.append(stopped_msg)

        self.notify()

    def start_new_conversation(self) -> Any:
        """
        Immediately create a new persistent conversation with title 'New chat'
        in the database, preserve active course/document scope, set as active,
        and notify listeners to update Recent Chats immediately.
        Does NOT cancel background generation in other conversations.
        """
        if self._active_conversation_id and len(self._chat_history) == 0:
            # Already in an empty new conversation; preserve it without creating duplicate empty rows
            self.notify()
            return None

        if getattr(self, "_is_creating_conversation", False):
            return None

        self._is_creating_conversation = True
        try:
            current_scope = self.active_scope
            current_kb_id = self.active_kb_id
            current_doc_id = self.active_doc_id

            new_conv = api_client.create_conversation(
                title="New chat",
                scope=current_scope,
                kb_id=current_kb_id,
                doc_id=current_doc_id,
            )
            self._active_conversation_id = new_conv.id
            self._chat_history = []
            self._selected_citation = None
            self._generation_error = None
            self.notify()
            return new_conv
        except Exception:
            self._active_conversation_id = None
            self._chat_history = []
            self._selected_citation = None
            self._generation_error = None
            self.notify()
            return None
        finally:
            self._is_creating_conversation = False

    def update_active_conversation_title(self, new_title: str) -> None:
        """
        Update the active conversation's title in persistent storage and notify listeners.
        """
        if not self._active_conversation_id:
            return
        clean_title = new_title.strip()
        if not clean_title:
            return
        try:
            api_client.update_conversation(
                self._active_conversation_id,
                title=clean_title,
            )
            self.notify()
        except Exception:
            pass

    def load_conversation(self, conv_id: str) -> None:
        """
        Load an existing saved conversation thread and its messages.
        Does NOT cancel background generation in previously active conversation.
        """
        detail = api_client.get_conversation(conv_id)
        self._active_conversation_id = detail.id
        self._chat_history = list(detail.messages)
        self._generation_error = None

        # Reconcile with any completed background generation not yet returned by detail API
        gen = self._generations.get(conv_id)
        if gen and gen.status == "completed" and gen.response:
            existing_ids = {m.id for m in self._chat_history}
            if gen.response.id not in existing_ids:
                self._chat_history.append(gen.response)

        if getattr(detail, "scope", None):
            self._active_scope = detail.scope
            self._active_kb_id = detail.knowledge_base_id
            self._active_doc_id = getattr(detail, "document_id", None)
        # Select latest citation if present
        latest_cits = [
            m.citations
            for m in reversed(self._chat_history)
            if m.role == "assistant" and m.citations
        ]
        self._selected_citation = latest_cits[0][0] if latest_cits else None
        self.notify()

    def delete_conversation(self, conv_id: str) -> bool:
        """
        Delete a conversation thread and reset active view if currently open.
        """
        success = api_client.delete_conversation(conv_id)
        if success and self._active_conversation_id == conv_id:
            self.start_new_conversation()
        else:
            self.notify()
        return success

    @property
    def current_user(self) -> UserDTO | None:
        """Get the currently logged in user from the API client."""
        return api_client.get_current_user()

    @property
    def is_admin(self) -> bool:
        """Check if current authenticated user has administrator privileges."""
        user = self.current_user
        return user is not None and user.role == "ADMIN"

    @property
    def active_kb(self) -> KnowledgeBaseDTO | None:
        """Get currently active knowledge base, defaulting to first available if none selected."""
        if self._active_kb is None:
            kbs = api_client.get_knowledge_bases()
            if kbs:
                self._active_kb = kbs[0]
        return self._active_kb

    @active_kb.setter
    def active_kb(self, kb: KnowledgeBaseDTO | None) -> None:
        """Set the active knowledge base."""
        self._active_kb = kb

    @property
    def selected_citation(self) -> CitationDTO | None:
        """Citation selected for detailed evidence inspection."""
        return self._selected_citation

    @selected_citation.setter
    def selected_citation(self, citation: CitationDTO | None) -> None:
        self._selected_citation = citation

    @property
    def chat_history(self) -> list[ChatMessageDTO]:
        """Conversation history for the active knowledge base."""
        return self._chat_history

    def add_user_message(self, text: str) -> ChatMessageDTO:
        """Append user question to conversation history."""
        msg = ChatMessageDTO(
            id=f"msg-user-{len(self._chat_history) + 1}",
            role="user",
            content=text,
            citations=[],
        )
        self._chat_history.append(msg)
        return msg

    def add_assistant_message(self, msg: ChatMessageDTO) -> None:
        """Append assistant response to conversation history."""
        self._chat_history.append(msg)

    def clear_chat(self) -> None:
        """Clear conversation history, reset scope to ALL_COURSES, and reset active conversation."""
        if self._active_conversation_id and self.is_generating:
            self.stop_generating(self._active_conversation_id)
        self._active_conversation_id = None
        self._chat_history.clear()
        self._selected_citation = None
        self._generation_error = None
        self._active_scope = "ALL_COURSES"
        self._active_kb_id = None
        self._active_doc_id = None
        self.notify()


_session_app_states: dict[str, AppState] = {}


class _SessionAppStateProxy:
    """Resolve one AppState instance per browser session."""

    def __init__(self) -> None:
        self._fallback_state = AppState()

    def _get_state(self) -> AppState:
        session_id = _get_browser_session_id()
        if not session_id:
            # Direct unit tests do not have an active NiceGUI client context.
            return self._fallback_state

        state_inst = _session_app_states.get(session_id)
        if state_inst is None:
            state_inst = AppState()
            _session_app_states[session_id] = state_inst
        return state_inst

    def reset_session_state(self) -> None:
        """Reset presentation state for active browser session."""
        session_id = _get_browser_session_id()
        if session_id and session_id in _session_app_states:
            _session_app_states.pop(session_id, None)
        else:
            self._fallback_state = AppState()

    @property
    def active_conversation_id(self) -> str | None:
        return self._get_state().active_conversation_id

    @active_conversation_id.setter
    def active_conversation_id(self, value: str | None) -> None:
        self._get_state().active_conversation_id = value

    @property
    def current_user(self) -> UserDTO | None:
        return self._get_state().current_user

    @property
    def is_admin(self) -> bool:
        return self._get_state().is_admin

    @property
    def active_kb(self) -> KnowledgeBaseDTO | None:
        return self._get_state().active_kb

    @active_kb.setter
    def active_kb(self, value: KnowledgeBaseDTO | None) -> None:
        self._get_state().active_kb = value

    @property
    def selected_citation(self) -> CitationDTO | None:
        return self._get_state().selected_citation

    @selected_citation.setter
    def selected_citation(self, value: CitationDTO | None) -> None:
        self._get_state().selected_citation = value

    @property
    def chat_history(self) -> list[ChatMessageDTO]:
        return self._get_state().chat_history

    def add_user_message(self, text: str) -> ChatMessageDTO:
        return self._get_state().add_user_message(text)

    def add_assistant_message(self, msg: ChatMessageDTO) -> None:
        self._get_state().add_assistant_message(msg)

    @property
    def is_generating(self) -> bool:
        return self._get_state().is_generating

    @is_generating.setter
    def is_generating(self, value: bool) -> None:
        self._get_state().is_generating = value

    def is_conversation_generating(self, conv_id: str | None) -> bool:
        return self._get_state().is_conversation_generating(conv_id)

    def get_generation_status(self, conv_id: str | None = None) -> str | None:
        return self._get_state().get_generation_status(conv_id)

    @property
    def generation_error(self) -> str | None:
        return self._get_state().generation_error

    def clear_generation_error(self) -> None:
        self._get_state().clear_generation_error()

    def start_background_generation(
        self,
        kb_id: str | None,
        question: str,
        document_id: str | None = None,
        scope: str = "ALL_COURSES",
        conversation_id: str | None = None,
    ) -> None:
        self._get_state().start_background_generation(
            kb_id=kb_id,
            question=question,
            document_id=document_id,
            scope=scope,
            conversation_id=conversation_id,
        )

    def stop_generating(self, conv_id: str | None = None) -> None:
        self._get_state().stop_generating(conv_id=conv_id)

    def start_new_conversation(self) -> Any:
        return self._get_state().start_new_conversation()

    def update_active_conversation_title(self, new_title: str) -> None:
        self._get_state().update_active_conversation_title(new_title)

    @property
    def active_scope(self) -> str:
        return self._get_state().active_scope

    @active_scope.setter
    def active_scope(self, value: str) -> None:
        self._get_state().active_scope = value

    @property
    def active_kb_id(self) -> str | None:
        return self._get_state().active_kb_id

    @active_kb_id.setter
    def active_kb_id(self, value: str | None) -> None:
        self._get_state().active_kb_id = value

    @property
    def active_doc_id(self) -> str | None:
        return self._get_state().active_doc_id

    @active_doc_id.setter
    def active_doc_id(self, value: str | None) -> None:
        self._get_state().active_doc_id = value

    def set_scope(
        self,
        scope: str = "ALL_COURSES",
        kb_id: str | None = None,
        doc_id: str | None = None,
    ) -> None:
        self._get_state().set_scope(scope, kb_id, doc_id)

    def reset_scope(self) -> None:
        self._get_state().reset_scope()

    def load_conversation(self, conv_id: str) -> None:
        self._get_state().load_conversation(conv_id)

    def delete_conversation(self, conv_id: str) -> bool:
        return self._get_state().delete_conversation(conv_id)

    def subscribe(self, listener: Any) -> Any:
        return self._get_state().subscribe(listener)

    def notify(self) -> None:
        self._get_state().notify()

    def clear_chat(self) -> None:
        self._get_state().clear_chat()

    @property
    def reader_context(self) -> dict[str, Any]:
        return self._get_state().reader_context

    def set_reader_context(
        self,
        document_id: str | None = None,
        document_name: str | None = None,
        page_number: int | None = None,
        kb_id: str | None = None,
        course_name: str | None = None,
        snippet: str | None = None,
        return_to: str | None = None,
        conv_id: str | None = None,
        citation: CitationDTO | None = None,
    ) -> None:
        self._get_state().set_reader_context(
            document_id=document_id,
            document_name=document_name,
            page_number=page_number,
            kb_id=kb_id,
            course_name=course_name,
            snippet=snippet,
            return_to=return_to,
            conv_id=conv_id,
            citation=citation,
        )


# Presentation state is scoped to the current NiceGUI browser client.
state = _SessionAppStateProxy()
