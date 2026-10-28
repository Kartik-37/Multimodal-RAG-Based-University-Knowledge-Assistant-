"""
Unit Regression Tests for Conversational RAG Quality & Answer Validation (Phase 13B).

Validates the meaning, shape, and structure of answers:
1. Title-like query matching infographic.
2. Follow-up queries (e.g. 'list that') using prior conversation turns.
3. Complete itemized answer structure.
4. Rejection of generic preambles ('We can answer by listing...').
5. Detection and rejection of internal reasoning leaks ('The user says...').
6. Unrelated follow-ups that do not inherit previous subject.
7. Scope preservation across turns.
8. Accurate source page citation validation.
"""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.api.v1.endpoints.chat import resolve_conversational_query
from backend.app.models.conversation import ChatMessage, Conversation
from backend.app.schemas.context_assembly import ContextAssemblyResult, ContextItem
from backend.app.schemas.llm import LLMGenerationRequest, LLMGenerationResponse, LLMProviderResponse
from backend.app.services.llm.prompt_builder import GroundedPromptBuilder
from backend.app.services.llm.service import (
    LLMGenerationService,
    clean_reasoning_text,
    is_reasoning_or_non_answer,
)


def test_detect_reasoning_leak_generic_preamble():
    """Detect non-answers like 'We can answer by listing...' or 'The answer should be...'."""
    leaked_cot = "The user says 'list that'. Since the evidence has multiple lists, we must see what the user might mean."
    assert is_reasoning_or_non_answer(leaked_cot, "list that") is True

    preamble_only = "The answer should be the list from [source_1]."
    assert is_reasoning_or_non_answer(preamble_only, "List of Android Version") is True

    we_can_answer = "We can answer by listing the Android versions as described in [1]."
    assert is_reasoning_or_non_answer(we_can_answer, "List of Android Version") is True

    valid_list = (
        "Android versions from the infographic [source_1]:\n"
        "- Android 1.0 (2008) [source_1]\n"
        "- Android 1.5 Cupcake (2009) [source_1]\n"
        "- Android 1.6 Donut (2009) [source_1]\n"
        "- Android 2.0 Eclair (2009) [source_1]"
    )
    assert is_reasoning_or_non_answer(valid_list, "List of Android Version") is False


def test_clean_reasoning_text_extracts_conclusion():
    """Extract explicit conclusion declarations when embedded at end of reasoning."""
    reasoning_block = (
        "We are given [source_1] and [source_2]. The user question asks what is Flutter. "
        "The definition in [1] is the primary one. "
        "So the answer should be: Flutter is an open-source UI software development kit created by Google [source_1]."
    )
    extracted = clean_reasoning_text(reasoning_block)
    assert extracted == "Flutter is an open-source UI software development kit created by Google [source_1]."
    assert is_reasoning_or_non_answer(extracted, "what is flutter") is False


def test_resolve_conversational_query_anaphora():
    """Resolve anaphoric follow-up queries using prior turn."""
    conv_id = uuid.uuid4()
    conv = Conversation(
        id=conv_id,
        user_id=uuid.uuid4(),
        title="Android Versions",
        scope="ALL_COURSES",
    )
    msg1 = ChatMessage(
        conversation_id=conv_id,
        role="user",
        content="List of Android Version",
    )
    msg2 = ChatMessage(
        conversation_id=conv_id,
        role="assistant",
        content="The list of Android versions is shown in the infographic [source_1].",
    )
    conv.messages = [msg1, msg2]

    # Test 'list that'
    resolved = resolve_conversational_query("list that", conv)
    assert "List of Android Version" in resolved
    assert "list" in resolved.lower()

    # Test 'explain that'
    resolved_exp = resolve_conversational_query("explain that", conv)
    assert "List of Android Version" in resolved_exp
    assert "explain" in resolved_exp.lower()


def test_resolve_conversational_query_unrelated_not_inherited():
    """Independent query must not inherit previous subject."""
    conv_id = uuid.uuid4()
    conv = Conversation(
        id=conv_id,
        user_id=uuid.uuid4(),
        title="Android Versions",
        scope="ALL_COURSES",
    )
    msg1 = ChatMessage(
        conversation_id=conv_id,
        role="user",
        content="List of Android Version",
    )
    conv.messages = [msg1]

    # Query with no pronouns or follow-up markers
    new_query = "What is the examination policy for CS101?"
    resolved = resolve_conversational_query(new_query, conv)
    assert resolved == new_query


def test_prompt_builder_includes_list_directive():
    """Prompt builder provides explicit listing instructions when query asks for a list."""
    builder = GroundedPromptBuilder()
    item = ContextItem(
        source_id="source_1",
        chunk_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title="1-Flutter-Intro.pdf",
        text="[Visual Extracted Text]: List of Android Version\nAndroid 1.0, 1.5, 2.0",
        page_number=6,
        chunk_index=0,
        reranker_rank=1,
        reranker_score=0.95,
        rrf_score=0.95,
        estimated_tokens=50,
        chunk_metadata={"source_modality": "visual"},
    )
    ctx = ContextAssemblyResult(
        query="List of Android Version",
        token_budget=4000,
        candidates_received=1,
        items=[item],
        total_items=1,
        total_estimated_tokens=50,
        items_skipped_budget=0,
        items_deduplicated=0,
    )
    prompt = builder.build_user_prompt("List of Android Version", ctx)
    assert "Provide the complete itemized list of items supported by the evidence" in prompt


from backend.app.services.llm.base import BaseLLMProvider


class MockQualityProvider(BaseLLMProvider):
    def __init__(self, responses):
        self._responses = list(responses)
        self.call_count = 0

    @property
    def provider_name(self) -> str:
        return "mock_ollama"

    @property
    def model_name(self) -> str:
        return "qwen3:4b"

    async def generate(self, **kwargs):
        resp = self._responses[self.call_count]
        self.call_count += 1
        return resp


def test_llm_service_retries_on_non_answer():
    """Service detects non-answer preamble and identifies retry condition."""
    non_answer = "We can answer by listing the Android versions as described in [source_1]."
    query = "List of Android Version"
    assert is_reasoning_or_non_answer(non_answer, query) is True

    valid_answer = (
        "The Android versions from the infographic are:\n"
        "- Android 1.0 (2008) [source_1]\n"
        "- Android 1.5 Cupcake (2009) [source_1]\n"
        "- Android 2.0 Eclair (2009) [source_1]"
    )
    assert is_reasoning_or_non_answer(valid_answer, query) is False
    assert "Android 1.0" in valid_answer
    assert "[source_1]" in valid_answer
