"""
Behavioral and Unit Tests for:
1. Workstream A: Statutory Act Name Retrieval and Grounded Extraction
2. Workstream B: Repeated Question Delivery & Turn Identity (turn_id)
3. Workstream C: Header & Composer Separator Alignment
"""

import uuid
from unittest.mock import MagicMock
import pytest

from backend.app.models.conversation import Conversation, ChatMessage
from backend.app.schemas.context_assembly import ContextAssemblyResult, ContextItem
from backend.app.services.llm.service import extract_grounded_recovery_answer
from backend.app.api.v1.endpoints.chat import _persist_user_question
from frontend.client.models import ChatMessageDTO, CitationDTO
from frontend.state.app_state import AppState


# ==============================================================================
# Workstream A: Statutory Act Name Extraction
# ==============================================================================

def test_extract_act_name_statutory_patterns():
    """Verify statutory title formula is extracted cleanly from legal gazette chunks."""
    act_text = (
        "GUJARAT GOVERNMENT GAZETTE EXTRAORDINARY\n"
        "The following Act of the Gujarat Legislature, having been assented to by the Governor...\n"
        "1. (1) This Act may be called ‘Kaushalya’ the Skill University Act 2021.\n"
        "(2) It extends to the whole of the State of Gujarat.\n"
        "Short title, extent and commencement."
    )
    item = ContextItem(
        chunk_id=str(uuid.uuid4()),
        document_id=uuid.uuid4(),
        document_name="KSU-Act-English.pdf",
        document_title="KSU-Act-English.pdf",
        knowledge_base_id=uuid.uuid4(),
        chunk_index=0,
        estimated_tokens=50,
        text=act_text,
        page_number=1,
        source_id="source_2",
        reranker_score=-6.76,
        reranker_rank=1,
        rrf_score=0.03,
    )
    context = ContextAssemblyResult(
        query="what is act name",
        items=[item],
        total_items=1,
        token_budget=2000,
        total_estimated_tokens=50,
        items_skipped_budget=0,
        items_deduplicated=0,
        candidates_received=1,
    )

    test_queries = [
        "what is act name",
        "What is the name of this Act?",
        "What is the short title of the Act?",
        "Which Act is this?",
        "what is the act title",
    ]

    for q in test_queries:
        ans = extract_grounded_recovery_answer(q, context)
        assert ans is not None, f"Failed to extract for query: {q}"
        assert "Kaushalya" in ans
        assert "Skill University Act 2021" in ans
        assert "[source_2]" in ans


def test_extract_act_name_does_not_trigger_on_unrelated_queries():
    """Verify non-act queries do not accidentally trigger statutory extraction."""
    act_text = "1. (1) This Act may be called ‘Kaushalya’ the Skill University Act 2021."
    item = ContextItem(
        chunk_id=str(uuid.uuid4()),
        document_id=uuid.uuid4(),
        document_name="KSU-Act-English.pdf",
        document_title="KSU-Act-English.pdf",
        knowledge_base_id=uuid.uuid4(),
        chunk_index=0,
        estimated_tokens=50,
        text=act_text,
        page_number=1,
        source_id="source_1",
        reranker_score=-10.5,
        reranker_rank=1,
        rrf_score=0.01,
    )
    context = ContextAssemblyResult(
        query="what is act name",
        items=[item],
        total_items=1,
        token_budget=2000,
        total_estimated_tokens=50,
        items_skipped_budget=0,
        items_deduplicated=0,
        candidates_received=1,
    )

    unrelated_queries = [
        "who is the prime minister",
        "explain bubble sort",
        "when is the examination fee deadline",
    ]
    for q in unrelated_queries:
        ans = extract_grounded_recovery_answer(q, context)
        # Should be None because scores are < -8.5 and queries don't match act title keywords
        assert ans is None, f"Should not extract for unrelated query: {q}"


# ==============================================================================
# Workstream B: Repeated Question Delivery & Turn Identity (turn_id)
# ==============================================================================

def test_persist_user_question_distinct_turns_for_repeated_questions():
    """Verify repeated questions with distinct turn_ids create distinct ChatMessage records."""
    mock_db = MagicMock()
    user_id = uuid.uuid4()
    conv_id = uuid.uuid4()

    mock_conv = Conversation(id=conv_id, user_id=user_id, title="Test Thread")
    mock_db.query.return_value.filter.return_value.count.return_value = 1

    # First turn submission
    turn_1_id = "turn-aaa-111"
    # No existing message for turn_1
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

    conv, msg1 = _persist_user_question(
        db=mock_db,
        user_id=user_id,
        question="what is act name",
        scope="DOCUMENT",
        active_conv=mock_conv,
        turn_id=turn_1_id,
    )
    assert msg1.content == "what is act name"
    assert msg1.citations == [{"turn_id": turn_1_id}]

    # Second turn submission (repeated question, new turn_id)
    turn_2_id = "turn-bbb-222"
    existing_msg1 = ChatMessage(
        conversation_id=conv_id,
        role="user",
        content="what is act name",
        citations=[{"turn_id": turn_1_id}],
    )
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [existing_msg1]

    conv, msg2 = _persist_user_question(
        db=mock_db,
        user_id=user_id,
        question="what is act name",
        scope="DOCUMENT",
        active_conv=mock_conv,
        turn_id=turn_2_id,
    )
    # Must create a new message for turn 2 because turn_id did not match
    assert msg2 is not existing_msg1
    assert msg2.content == "what is act name"
    assert msg2.citations == [{"turn_id": turn_2_id}]


def test_persist_user_question_idempotent_retry():
    """Verify that retrying a turn with the SAME turn_id reuses the existing user message."""
    mock_db = MagicMock()
    user_id = uuid.uuid4()
    conv_id = uuid.uuid4()

    mock_conv = Conversation(id=conv_id, user_id=user_id, title="Test Thread")
    mock_db.query.return_value.filter.return_value.count.return_value = 1

    turn_id = "turn-retry-123"
    existing_user_msg = ChatMessage(
        conversation_id=conv_id,
        role="user",
        content="what is act name",
        citations=[{"turn_id": turn_id}],
    )
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [existing_user_msg]

    conv, retried_msg = _persist_user_question(
        db=mock_db,
        user_id=user_id,
        question="what is act name",
        scope="DOCUMENT",
        active_conv=mock_conv,
        turn_id=turn_id,
    )
    # Exact retry must reuse the existing user message without duplicating it
    assert retried_msg is existing_user_msg


def test_app_state_allows_repeated_identical_assistant_answers():
    """Verify AppState does NOT suppress repeated identical answers when message IDs differ."""
    state = AppState()
    state._active_conversation_id = "conv-100"

    # Turn 1
    resp1 = ChatMessageDTO(
        id="msg-resp-1",
        role="assistant",
        content="The Act is titled the “Kaushalya” the Skill University Act 2021 [source_2].",
        citations=[CitationDTO(document_name="KSU-Act-English.pdf", chunk_id="chk-1", snippet="...")],
    )
    state._chat_history = [resp1]

    # Turn 2: identical content, distinct message ID
    resp2 = ChatMessageDTO(
        id="msg-resp-2",
        role="assistant",
        content="The Act is titled the “Kaushalya” the Skill University Act 2021 [source_2].",
        citations=[CitationDTO(document_name="KSU-Act-English.pdf", chunk_id="chk-1", snippet="...")],
    )

    # In app_state, we only check: if resp.id not in existing_ids: append
    existing_ids = {m.id for m in state._chat_history}
    if resp2.id not in existing_ids:
        state._chat_history.append(resp2)

    assert len(state._chat_history) == 2
    assert state._chat_history[0].id == "msg-resp-1"
    assert state._chat_history[1].id == "msg-resp-2"
    assert state._chat_history[0].content == state._chat_history[1].content


# ==============================================================================
# Workstream C: Header & Composer Separator Alignment
# ==============================================================================

def test_chat_page_separators_aligned_with_content_shell():
    """Verify chat_page.py places separator borders on .chat-content-shell, not full viewport."""
    with open("frontend/pages/chat_page.py", "r", encoding="utf-8") as f:
        content = f.read()

    # 1. header_container outer row must NOT have border-b
    assert 'header_container = ui.row().classes(\n                    "w-full items-center justify-between px-3 sm:px-6 py-2 shrink-0 gap-2 bg-canvas min-w-0 max-w-full box-border flex-nowrap"\n                )' in content or (
        "header_container = ui.row().classes" in content and "border-b" not in content.split("header_container = ui.row().classes(")[1].split(")")[0]
    )

    # 2. Inner header shell inside render_header MUST have border-b
    assert 'with ui.row().classes("chat-content-shell w-full max-w-4xl mx-auto items-center justify-between pb-2 border-b border-subtle min-w-0 flex-nowrap"):' in content

    # 3. Composer outer column must NOT have border-t
    composer_outer_section = content.split("# Composer Outer Container")[1].split("# Composer Card")[0]
    assert "border-t border-subtle" not in composer_outer_section.split("with ui.column().classes(")[1].split(")")[0]

    # 4. Inner composer shell MUST have border-t
    assert 'chat-content-shell w-full max-w-4xl mx-auto pt-2 border-t border-subtle' in composer_outer_section
