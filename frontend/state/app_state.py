"""
Frontend Presentation State Management.

Maintains UI state across page views:
- Active knowledge base selection
- Selected citation evidence for detail view
- Active conversation message thread
"""

from frontend.client.api_client import api_client
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


# Shared presentation state singleton
state = AppState()
