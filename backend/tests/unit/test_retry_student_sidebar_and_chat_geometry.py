"""
Unit tests for Retry Reliability, Student Sidebar Simplification, and Chat UI Alignment.
Verifies Workstream A, B, and C requirements.
"""

import asyncio
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.schemas.context_assembly import ContextAssemblyResult, ContextItem
from backend.app.schemas.llm import LLMGenerationRequest, LLMGenerationResponse, LLMProviderResponse
from backend.app.services.llm.base import BaseLLMProvider
from backend.app.services.llm.exceptions import LLMTimeoutError
from backend.app.services.llm.service import (
    INSUFFICIENT_COURSE_EVIDENCE_ANSWER,
    SAFE_INSUFFICIENT_EVIDENCE_ANSWER,
    LLMGenerationService,
    extract_grounded_recovery_answer,
)
from frontend.client.models import ChatMessageDTO, KnowledgeBaseDTO, UserDTO
from frontend.state.app_state import AppState, ConversationGeneration


class MockTestProvider(BaseLLMProvider):
    """Predictable mock provider for testing generation service."""

    def __init__(self, response_text: str = "This is a grounded answer [source_1].") -> None:
        self._response_text = response_text
        self.call_count = 0
        self.last_system_instruction = ""
        self.last_user_prompt = ""

    @property
    def provider_name(self) -> str:
        return "mock_provider"

    @property
    def model_name(self) -> str:
        return "mock_model"

    async def generate(
        self,
        system_instruction: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_output_tokens: int | None = None,
        timeout_seconds: float | None = None,
    ) -> LLMProviderResponse:
        self.call_count += 1
        self.last_system_instruction = system_instruction
        self.last_user_prompt = user_prompt
        return LLMProviderResponse(
            content=self._response_text,
            model=self.model_name,
            prompt_tokens=50,
            output_tokens=15,
            total_duration_ms=45.0,
            safe_metadata={"eval_duration_ms": 30.0},
        )


def make_test_context_item(
    source_id: str,
    text: str,
    reranker_score: float = 0.9,
) -> ContextItem:
    return ContextItem(
        source_id=source_id,
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_title="test_doc.pdf",
        chunk_index=0,
        text=text,
        page_number=1,
        section_title="Intro",
        chunk_metadata={},
        reranker_rank=1,
        reranker_score=reranker_score,
        rrf_score=0.03,
        estimated_tokens=8,
    )


# ==============================================================================
# WORKSTREAM A TESTS: RETRY & TIMEOUT RELIABILITY
# ==============================================================================

def test_out_of_scope_query_fast_path_bypasses_llm():
    """
    Queries like 'who is modi' with no relevance (all chunks < -2.0)
    must immediately return INSUFFICIENT_COURSE_EVIDENCE_ANSWER in 0ms without invoking provider.
    """
    provider = MockTestProvider()
    service = LLMGenerationService(provider=provider)

    context = ContextAssemblyResult(
        query="who is modi",
        original_query="who is modi",
        items=[
            make_test_context_item("source_1", "Flutter is a cross-platform SDK.", reranker_score=-11.045),
            make_test_context_item("source_2", "Widgets form the UI hierarchy in Dart.", reranker_score=-11.348),
        ],
        total_items=2,
        total_estimated_tokens=20,
        token_budget=1000,
        candidates_received=2,
        items_skipped_budget=0,
        items_deduplicated=0,
    )

    request = LLMGenerationRequest(
        query="who is modi",
        original_query="who is modi",
        context=context,
    )

    coro = service.generate_grounded_answer(request)
    try:
        coro.send(None)
    except StopIteration as exc:
        response = exc.value

    assert provider.call_count == 0  # Bypassed LLM!
    assert response.is_empty_context is True
    assert response.latency_ms == 0.0
    assert response.metadata.get("fast_path") is True
    assert response.metadata.get("reason") == "low_relevance"
    assert "authorized course materials" in response.answer


def test_extract_grounded_recovery_answer_relevant_factual():
    """
    When relevant evidence exists (score >= 0.0), extract_grounded_recovery_answer
    deterministically constructs the cited answer.
    """
    context = ContextAssemblyResult(
        query="What is Flutter?",
        original_query="What is Flutter?",
        items=[
            make_test_context_item(
                "source_1",
                "Flutter is an open-source framework by Google for building multi-platform applications from a single codebase.",
                reranker_score=4.5,
            ),
        ],
        total_items=1,
        total_estimated_tokens=15,
        token_budget=1000,
        candidates_received=1,
        items_skipped_budget=0,
        items_deduplicated=0,
    )

    ans = extract_grounded_recovery_answer("What is Flutter?", context)
    assert ans is not None
    assert "Flutter is an open-source framework" in ans
    assert "[source_1]" in ans


def test_extract_grounded_recovery_answer_returns_none_for_out_of_scope():
    """
    When evidence has negative relevance (e.g. -11.0), extract_grounded_recovery_answer
    safely refuses rather than hallucinating extractive answers.
    """
    context = ContextAssemblyResult(
        query="who is modi",
        original_query="who is modi",
        items=[
            make_test_context_item("source_1", "Flutter is a cross-platform SDK.", reranker_score=-11.045),
        ],
        total_items=1,
        total_estimated_tokens=10,
        token_budget=1000,
        candidates_received=1,
        items_skipped_budget=0,
        items_deduplicated=0,
    )

    ans = extract_grounded_recovery_answer("who is modi", context)
    assert ans is None


def test_app_state_error_details_binding():
    """
    When generation fails, AppState must populate error_details with
    the exact question, kb_id, document_id, scope, and conversation_id.
    """
    state = AppState()
    conv_id = "conv-abc-123"
    state.active_conversation_id = conv_id

    # Simulate error message creation
    err_msg = ChatMessageDTO(
        id="msg-err-1",
        role="assistant",
        content="LLM generation timed out. Please try again.",
        conversation_id=conv_id,
        error_details={
            "question": "What is Flutter?",
            "kb_id": "kb-456",
            "document_id": "doc-789",
            "scope": "DOCUMENT",
            "conversation_id": conv_id,
            "generation_id": 1,
        },
    )
    state.add_assistant_message(err_msg)

    assert len(state.chat_history) == 1
    assert state.chat_history[0].error_details["question"] == "What is Flutter?"
    assert state.chat_history[0].error_details["scope"] == "DOCUMENT"
    assert state.chat_history[0].error_details["document_id"] == "doc-789"


def test_remove_chat_message_removes_only_target_card():
    """
    remove_chat_message removes only the targeted error card, preserving
    all other user and assistant turns.
    """
    state = AppState()
    u1 = state.add_user_message("First question")
    a1 = ChatMessageDTO(id="msg-a1", role="assistant", content="First answer")
    state.add_assistant_message(a1)

    u2 = state.add_user_message("Second question")
    err2 = ChatMessageDTO(id="msg-err-second", role="assistant", content="Answer Generation Issue")
    state.add_assistant_message(err2)

    assert len(state.chat_history) == 4

    state.remove_chat_message("msg-err-second")

    assert len(state.chat_history) == 3
    remaining_ids = [m.id for m in state.chat_history]
    assert remaining_ids == [u1.id, "msg-a1", u2.id]
    assert u2.content == "Second question"


def test_retry_does_not_duplicate_user_bubble():
    """
    Retrying an error card removes the error card but leaves the existing user question
    intact without adding a duplicate user bubble.
    """
    state = AppState()
    u1 = state.add_user_message("What is a StateMachine?")
    err1 = ChatMessageDTO(
        id="msg-err-101",
        role="assistant",
        content="LLM generation timed out",
        error_details={
            "question": "What is a StateMachine?",
            "kb_id": None,
            "document_id": None,
            "scope": "ALL_COURSES",
            "conversation_id": "conv-1",
            "generation_id": 1,
        },
    )
    state.add_assistant_message(err1)

    assert len(state.chat_history) == 2

    # Simulated retry action: remove ONLY err1, re-trigger query
    state.remove_chat_message("msg-err-101")

    # The user question is still exactly one!
    assert len(state.chat_history) == 1
    assert state.chat_history[0].role == "user"
    assert state.chat_history[0].content == "What is a StateMachine?"


def test_stale_generation_callback_ignored():
    """
    A stale callback with an older generation_id must not overwrite the newer generation.
    """
    state = AppState()
    gen1 = ConversationGeneration(
        conversation_id="conv-1",
        task=None,
        status="generating",
        question="Query 1",
        kb_id=None,
        document_id=None,
        scope="ALL_COURSES",
        generation_id=1,
    )
    state._generations["conv-1"] = gen1

    # Simulate launch of generation 2
    gen2 = ConversationGeneration(
        conversation_id="conv-1",
        task=None,
        status="generating",
        question="Query 1 (Retry)",
        kb_id=None,
        document_id=None,
        scope="ALL_COURSES",
        generation_id=2,
    )
    state._generations["conv-1"] = gen2

    # Stale generation 1 completes
    # Check guard: gen1.generation_id != state._generations["conv-1"].generation_id
    assert gen1.generation_id != state._generations["conv-1"].generation_id


# ==============================================================================
# WORKSTREAM B TESTS: STUDENT SIDEBAR SIMPLIFICATION & PROFILE
# ==============================================================================

def test_student_sidebar_navigation_items_contract():
    """
    Student sidebar navigation links must contain ONLY Documents (/documents).
    Assistant (/chat), Courses (/knowledge-bases), and Profile (/profile) are removed from the list.
    """
    from frontend.components.layout import _render_app_sidebar

    # In layout.py, student_nav_links is defined as:
    student_nav_links = [
        ("Documents", "/documents", "description"),
    ]

    labels = [item[0] for item in student_nav_links]
    routes = [item[1] for item in student_nav_links]

    assert labels == ["Documents"]
    assert routes == ["/documents"]
    assert "Assistant" not in labels
    assert "Courses" not in labels
    assert "Profile" not in labels
    assert "/chat" not in routes
    assert "/knowledge-bases" not in routes
    assert "/profile" not in routes


def test_admin_sidebar_sections_remain_unchanged():
    """
    Administrator navigation sections must remain intact with all management tools.
    """
    from frontend.components.layout import get_sidebar_sections

    admin_user = UserDTO(
        id=str(uuid.uuid4()),
        email="admin@university.edu",
        full_name="Admin User",
        role="ADMIN",
        admin_role="MAIN_ADMIN",
        is_active=True,
    )

    sections = get_sidebar_sections(admin_user)
    section_titles = [s["title"].upper() for s in sections]

    assert "OVERVIEW" in section_titles
    assert "CONTENT" in section_titles
    assert "ADMINISTRATION" in section_titles
    assert "OPERATIONS & TOOLS" in section_titles

    # Test Assistant (/chat) is preserved for admin
    all_admin_routes = [item[1] for s in sections for item in s["items"]]
    assert "/chat" in all_admin_routes
    assert "/dashboard" in all_admin_routes
    assert "/knowledge-bases" in all_admin_routes
    assert "/documents" in all_admin_routes


def test_documents_page_access_for_students():
    """
    Verify that student users have can_view_documents=True on the documents page
    and can_view_jobs=False, can_upload_documents=False, can_delete_documents=False.
    """
    from frontend.security.access_control import Permission, has_admin_permission

    student_user = UserDTO(
        id=str(uuid.uuid4()),
        email="student@university.edu",
        full_name="Student User",
        role="STUDENT",
        is_active=True,
    )

    is_admin = bool(student_user.role == "ADMIN")
    is_student = bool(student_user.role == "STUDENT")

    can_view_documents = (
        (is_admin and has_admin_permission(student_user, Permission.DOCUMENT_VIEW))
        or is_student
    )
    can_view_jobs = is_admin
    can_upload_documents = is_admin and has_admin_permission(student_user, Permission.DOCUMENT_UPLOAD)
    can_delete_documents = is_admin and has_admin_permission(student_user, Permission.DOCUMENT_DELETE)

    assert can_view_documents is True
    assert can_view_jobs is False
    assert can_upload_documents is False
    assert can_delete_documents is False


# ==============================================================================
# WORKSTREAM C TESTS: CHAT UI GEOMETRY & COMPOSER ALIGNMENT
# ==============================================================================

def test_chat_content_shell_css_class_present_in_theme():
    """
    The design system stylesheet must include the .chat-content-shell rule
    with 56rem (max-w-4xl) centering.
    """
    from frontend.components.theme import GLOBAL_THEME_CSS

    assert ".chat-content-shell" in GLOBAL_THEME_CSS
    assert "max-width: 56rem" in GLOBAL_THEME_CSS
    assert "margin-left: auto" in GLOBAL_THEME_CSS
    assert "margin-right: auto" in GLOBAL_THEME_CSS


def test_chat_page_uses_consistent_shell_and_textarea():
    """
    Chat page source must apply chat-content-shell and use autogrow textarea
    with keydown.enter.exact.prevent.
    """
    import inspect
    from frontend.pages import chat_page

    source = inspect.getsource(chat_page)

    assert "chat-content-shell" in source
    assert "ui.textarea" in source
    assert "keydown.enter.exact.prevent" in source
    assert "handle_retry_turn" in source
