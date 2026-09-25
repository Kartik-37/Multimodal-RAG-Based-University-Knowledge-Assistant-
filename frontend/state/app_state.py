"""
Frontend Presentation State Management.

Maintains UI state across page views:
- Active knowledge base selection
- Selected citation evidence for detail view
- Active conversation message thread
"""

from frontend.client.api_client import _get_browser_session_id, api_client
from frontend.client.models import (
    ChatMessageDTO,
    CitationDTO,
    KnowledgeBaseDTO,
    UserDTO,
)


class AppState:
    """Application state manager for presentation session."""

    def __init__(self) -> None:
        self._active_kb: KnowledgeBaseDTO | None = None
        self._selected_citation: CitationDTO | None = None
        self._chat_history: list[ChatMessageDTO] = []

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
        """Reset conversation history."""
        self._chat_history.clear()
        self._selected_citation = None


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

    def clear_chat(self) -> None:
        self._get_state().clear_chat()


# Presentation state is scoped to the current NiceGUI browser client.
state = _SessionAppStateProxy()
