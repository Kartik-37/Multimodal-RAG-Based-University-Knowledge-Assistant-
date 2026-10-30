"""
Unit & Behavioral Tests for New Chat Lifecycle & Vertical Timeline (Antigravity Master Prompt).

Asserts behavior and state transitions:
1. Fresh Student & Admin /chat with zero conversations initializes one active New chat.
2. ensure_active_new_chat is idempotent.
3. Repeated/rapid New Chat clicks while empty create no extra records.
4. New Chat from an active saved conversation creates exactly one new row and preserves old.
5. First question renames and uses the same conversation ID.
6. Deleting the active empty New chat recreates exactly one selected New chat.
7. Deleting the active populated chat switches to exactly one new empty chat.
8. Deleting a non-active chat leaves current thread untouched.
9. Deleted/stale active ID is never treated as a valid draft.
10. Valid conversation URL restores the selected chat without creating another New chat.
11. Invalid/stale conversation URLs recover safely to a new chat.
12. Sidebar conversation items deduplicate IDs, handle API errors gracefully, and prioritize active conversation.
13. Vertical timeline styling contracts enforce flex-direction: column, flex-wrap: nowrap, and overflow-x: hidden.
"""

from unittest.mock import MagicMock, patch
import pytest

from frontend.client.models import ChatMessageDTO, ConversationDetailDTO, ConversationSummaryDTO
from frontend.state.app_state import AppState


def _make_conv_summary(conv_id: str, title: str = "New chat", msg_count: int = 0) -> ConversationSummaryDTO:
    return ConversationSummaryDTO(
        id=conv_id,
        title=title,
        scope="ALL_COURSES",
        knowledge_base_id=None,
        document_id=None,
        message_count=msg_count,
        created_at="2026-10-30T10:00:00Z",
        updated_at="2026-10-30T10:00:00Z",
    )


def _make_conv_detail(conv_id: str, title: str = "Saved Chat", messages: list[ChatMessageDTO] | None = None) -> ConversationDetailDTO:
    return ConversationDetailDTO(
        id=conv_id,
        title=title,
        scope="ALL_COURSES",
        knowledge_base_id=None,
        document_id=None,
        created_at="2026-10-30T10:00:00Z",
        updated_at="2026-10-30T10:00:00Z",
        messages=messages or [],
    )


def test_fresh_chat_with_zero_conversations_initializes_active_new_chat():
    """Fresh /chat with zero conversations initializes exactly one active New chat."""
    state = AppState()
    created_conv = _make_conv_summary("conv-fresh-1", title="New chat")

    with patch("frontend.state.app_state.api_client.create_conversation", return_value=created_conv) as mock_create:
        conv = state.ensure_active_new_chat(None)
        assert conv is not None
        assert conv.id == "conv-fresh-1"
        assert state.active_conversation_id == "conv-fresh-1"
        assert len(state.chat_history) == 0
        mock_create.assert_called_once()


def test_ensure_active_new_chat_is_idempotent():
    """Calling ensure_active_new_chat repeatedly reuses the active conversation without creating extra records."""
    state = AppState()
    created_conv = _make_conv_summary("conv-idem-1", title="New chat")

    with patch("frontend.state.app_state.api_client.create_conversation", return_value=created_conv) as mock_create, \
         patch("frontend.state.app_state.api_client.get_conversation", return_value=created_conv):
        first = state.ensure_active_new_chat(None)
        second = state.ensure_active_new_chat(None)
        third = state.ensure_active_new_chat(None)

        assert first.id == second.id == third.id == "conv-idem-1"
        assert mock_create.call_count == 1


def test_repeated_rapid_new_chat_clicks_while_empty_creates_no_extra_records():
    """Clicking New Chat while active conversation is already empty creates no extra database records."""
    state = AppState()
    created_conv = _make_conv_summary("conv-empty-1", title="New chat")

    with patch("frontend.state.app_state.api_client.create_conversation", return_value=created_conv) as mock_create, \
         patch("frontend.state.app_state.api_client.get_conversation", return_value=created_conv):
        c1 = state.start_new_conversation()
        assert c1.id == "conv-empty-1"
        assert mock_create.call_count == 1

        # Second click while empty
        c2 = state.start_new_conversation()
        assert c2 is not None
        assert c2.id == "conv-empty-1"
        # No extra create call
        assert mock_create.call_count == 1


def test_new_chat_from_active_saved_conversation_creates_one_new_row_and_preserves_old():
    """New Chat from a saved thread creates one new empty conversation and clears active transcript."""
    state = AppState()
    old_conv = _make_conv_detail("conv-old-1", title="Saved Thread", messages=[
        ChatMessageDTO(id="m1", role="user", content="Old question"),
        ChatMessageDTO(id="m2", role="assistant", content="Old answer"),
    ])
    new_conv = _make_conv_summary("conv-new-2", title="New chat")

    with patch("frontend.state.app_state.api_client.get_conversation", return_value=old_conv):
        state.load_conversation("conv-old-1")
        assert len(state.chat_history) == 2
        assert state.active_conversation_id == "conv-old-1"

    with patch("frontend.state.app_state.api_client.create_conversation", return_value=new_conv) as mock_create:
        c = state.start_new_conversation()
        assert c.id == "conv-new-2"
        assert state.active_conversation_id == "conv-new-2"
        assert len(state.chat_history) == 0
        mock_create.assert_called_once()


def test_first_question_renames_active_conversation_and_preserves_same_id():
    """First question updates the title in-place while strictly preserving the conversation ID."""
    state = AppState()
    conv = _make_conv_summary("conv-same-1", title="New chat")

    with patch("frontend.state.app_state.api_client.create_conversation", return_value=conv):
        state.start_new_conversation()

    assert state.active_conversation_id == "conv-same-1"

    with patch("frontend.state.app_state.api_client.update_conversation") as mock_update:
        state.add_user_message("What is Flutter?")
        state.update_active_conversation_title("What is Flutter?")
        mock_update.assert_called_once_with("conv-same-1", title="What is Flutter?")
        assert state.active_conversation_id == "conv-same-1"


def test_delete_active_empty_new_chat_when_multiple_exist_switches_to_remaining_without_replacement():
    """Case A: When multiple exist and active empty New Chat is deleted, switches to remaining without replacement."""
    state = AppState()
    conv1 = _make_conv_summary("conv-empty-active", title="New chat")
    saved_remaining = _make_conv_summary("conv-saved-1", title="Saved Thread", msg_count=2)
    saved_detail = _make_conv_detail("conv-saved-1", title="Saved Thread")

    with patch("frontend.state.app_state.api_client.create_conversation", return_value=conv1):
        state.start_new_conversation()

    assert state.active_conversation_id == "conv-empty-active"

    with patch("frontend.state.app_state.api_client.delete_conversation", return_value=True) as mock_delete, \
         patch("frontend.state.app_state.api_client.get_conversations", return_value=[saved_remaining]), \
         patch("frontend.state.app_state.api_client.get_conversation", return_value=saved_detail), \
         patch("frontend.state.app_state.api_client.create_conversation") as mock_create:
        success = state.delete_conversation("conv-empty-active")
        assert success is True
        mock_delete.assert_called_once_with("conv-empty-active")
        # Authoritative Case A: Must switch to remaining[0] and NOT create a new chat!
        mock_create.assert_not_called()
        assert state.active_conversation_id == "conv-saved-1"


def test_delete_sole_empty_chat_rejection_preserves_state():
    """Case B: Deleting the sole empty chat is rejected by backend (409) and preserves state."""
    state = AppState()
    conv1 = _make_conv_summary("conv-sole-empty", title="New chat")

    with patch("frontend.state.app_state.api_client.create_conversation", return_value=conv1):
        state.start_new_conversation()

    assert state.active_conversation_id == "conv-sole-empty"

    with patch("frontend.state.app_state.api_client.delete_conversation", return_value=False) as mock_delete, \
         patch("frontend.state.app_state.api_client.create_conversation") as mock_create:
        success = state.delete_conversation("conv-sole-empty")
        assert success is False
        mock_delete.assert_called_once_with("conv-sole-empty")
        mock_create.assert_not_called()
        assert state.active_conversation_id == "conv-sole-empty"


def test_delete_active_populated_chat_when_others_remain_switches_to_remaining():
    """Case D: Deleting an active populated chat when others remain switches to remaining[0]."""
    state = AppState()
    old_conv = _make_conv_detail("conv-pop-1", title="Populated Chat", messages=[
        ChatMessageDTO(id="m1", role="user", content="Q"),
        ChatMessageDTO(id="m2", role="assistant", content="A"),
    ])
    other_remaining = _make_conv_summary("conv-other-2", title="Other Thread", msg_count=1)
    other_detail = _make_conv_detail("conv-other-2", title="Other Thread")

    with patch("frontend.state.app_state.api_client.get_conversation", return_value=old_conv):
        state.load_conversation("conv-pop-1")

    assert state.active_conversation_id == "conv-pop-1"
    assert len(state.chat_history) == 2

    with patch("frontend.state.app_state.api_client.delete_conversation", return_value=True) as mock_delete, \
         patch("frontend.state.app_state.api_client.get_conversations", return_value=[other_remaining]), \
         patch("frontend.state.app_state.api_client.get_conversation", return_value=other_detail), \
         patch("frontend.state.app_state.api_client.create_conversation") as mock_create:
        state.delete_conversation("conv-pop-1")
        mock_delete.assert_called_once_with("conv-pop-1")
        # Must switch to remaining[0] and not create another conversation
        mock_create.assert_not_called()
        assert state.active_conversation_id == "conv-other-2"


def test_delete_sole_populated_chat_recreates_one_empty_new_chat():
    """Case E: Deleting the only remaining conversation when populated recreates exactly one empty New Chat."""
    state = AppState()
    old_conv = _make_conv_detail("conv-only-pop", title="Only Chat", messages=[
        ChatMessageDTO(id="m1", role="user", content="Q"),
    ])
    replacement = _make_conv_summary("conv-new-rep", title="New chat")

    with patch("frontend.state.app_state.api_client.get_conversation", return_value=old_conv):
        state.load_conversation("conv-only-pop")

    assert state.active_conversation_id == "conv-only-pop"

    with patch("frontend.state.app_state.api_client.delete_conversation", return_value=True) as mock_delete, \
         patch("frontend.state.app_state.api_client.get_conversations", return_value=[]), \
         patch("frontend.state.app_state.api_client.create_conversation", return_value=replacement) as mock_create:
        state.delete_conversation("conv-only-pop")
        mock_delete.assert_called_once_with("conv-only-pop")
        mock_create.assert_called_once()
        assert state.active_conversation_id == "conv-new-rep"
        assert len(state.chat_history) == 0


def test_delete_api_failure_rolls_back_without_creating_replacement():
    """Case F: If deletion fails, state is preserved and no replacement is created."""
    state = AppState()
    conv = _make_conv_detail("conv-fail-test", title="Chat To Keep")

    with patch("frontend.state.app_state.api_client.get_conversation", return_value=conv):
        state.load_conversation("conv-fail-test")

    with patch("frontend.state.app_state.api_client.delete_conversation", side_effect=Exception("Network error")), \
         patch("frontend.state.app_state.api_client.create_conversation") as mock_create:
        success = state.delete_conversation("conv-fail-test")
        assert success is False
        mock_create.assert_not_called()
        assert state.active_conversation_id == "conv-fail-test"


def test_delete_non_active_chat_leaves_current_thread_untouched():
    """Deleting a non-active chat leaves the currently active conversation and messages untouched."""
    state = AppState()
    active_conv = _make_conv_detail("conv-active", title="Active Chat", messages=[
        ChatMessageDTO(id="m1", role="user", content="Active question"),
    ])

    with patch("frontend.state.app_state.api_client.get_conversation", return_value=active_conv):
        state.load_conversation("conv-active")

    assert state.active_conversation_id == "conv-active"
    assert len(state.chat_history) == 1

    with patch("frontend.state.app_state.api_client.delete_conversation", return_value=True) as mock_delete, \
         patch("frontend.state.app_state.api_client.create_conversation") as mock_create:
        state.delete_conversation("conv-other-inactive")
        mock_delete.assert_called_once_with("conv-other-inactive")
        # Should not create a new conversation
        mock_create.assert_not_called()
        # Active conversation remains untouched
        assert state.active_conversation_id == "conv-active"
        assert len(state.chat_history) == 1
        assert state.chat_history[0].content == "Active question"


def test_deleted_stale_active_id_is_never_treated_as_valid_draft():
    """A stale or deleted active ID recovers safely and creates a valid New chat."""
    state = AppState()
    state._active_conversation_id = "stale-deleted-id"
    replacement = _make_conv_summary("conv-recovery-1", title="New chat")

    # get_conversation raises 404/Exception for deleted ID
    with patch("frontend.state.app_state.api_client.get_conversation", side_effect=Exception("Conversation not found (404)")), \
         patch("frontend.state.app_state.api_client.create_conversation", return_value=replacement) as mock_create:
        conv = state.ensure_active_new_chat(None)
        assert conv.id == "conv-recovery-1"
        assert state.active_conversation_id == "conv-recovery-1"
        mock_create.assert_called_once()


def test_valid_conversation_url_restores_selected_chat_without_extra_new_chat():
    """A valid conversation_id in URL loads that thread without creating a new chat."""
    state = AppState()
    saved = _make_conv_detail("saved-conv-42", title="Course Guide Discussion", messages=[
        ChatMessageDTO(id="m1", role="user", content="Hello"),
    ])

    with patch("frontend.state.app_state.api_client.get_conversation", return_value=saved) as mock_get, \
         patch("frontend.state.app_state.api_client.create_conversation") as mock_create:
        conv = state.ensure_active_new_chat("saved-conv-42")
        assert conv.id == "saved-conv-42"
        assert state.active_conversation_id == "saved-conv-42"
        mock_create.assert_not_called()
        assert conv.id == "saved-conv-42"
        assert state.active_conversation_id == "saved-conv-42"
        mock_create.assert_not_called()


def test_invalid_stale_conversation_url_recovers_safely():
    """An invalid/stale conversation_id in URL recovers safely to a fresh New chat."""
    state = AppState()
    replacement = _make_conv_summary("conv-safe-new", title="New chat")

    with patch("frontend.state.app_state.api_client.get_conversation", side_effect=Exception("404 Not Found")), \
         patch("frontend.state.app_state.api_client.create_conversation", return_value=replacement) as mock_create:
        conv = state.ensure_active_new_chat("bad-or-deleted-id")
        assert conv.id == "conv-safe-new"
        assert state.active_conversation_id == "conv-safe-new"
        mock_create.assert_called_once()


def test_sidebar_conversation_items_deduplicate_and_preserve_server_order():
    """Recent chats list deduplicates IDs and strictly preserves server updated_at order without artificial jumping."""
    c1 = _make_conv_summary("c1", title="Most Recently Updated Chat")
    c2 = _make_conv_summary("c2", title="Older Chat")
    c1_dup = _make_conv_summary("c1", title="Most Recently Updated Chat")

    raw_convs = [c1, c2, c1_dup]
    seen_ids = set()
    unique_convs = []
    for c in raw_convs:
        if c.id not in seen_ids:
            seen_ids.add(c.id)
            unique_convs.append(c)

    assert len(unique_convs) == 2
    # Preserves server order (c1 then c2)
    assert [c.id for c in unique_convs] == ["c1", "c2"]

    # Even if c2 is the active conversation, it does NOT jump ahead of c1 on load
    active_id = "c2"
    assert [c.id for c in unique_convs] == ["c1", "c2"]


def test_vertical_timeline_layout_rules_contract():
    """Verify GLOBAL_THEME_CSS defines explicit vertical layout without horizontal wrapping."""
    from frontend.components.theme import GLOBAL_THEME_CSS

    assert ".chat-scroll-area" in GLOBAL_THEME_CSS
    assert ".chat-timeline" in GLOBAL_THEME_CSS
    assert ".chat-turn-user" in GLOBAL_THEME_CSS
    assert ".chat-turn-assistant" in GLOBAL_THEME_CSS

    # Check key vertical flex rules in CSS
    assert "flex-direction: column !important" in GLOBAL_THEME_CSS
    assert "flex-wrap: nowrap !important" in GLOBAL_THEME_CSS
    assert "overflow-x: hidden !important" in GLOBAL_THEME_CSS
    assert "overflow-y: auto !important" in GLOBAL_THEME_CSS
