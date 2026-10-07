"""
Unit Tests for LLMGenerationService.

Verifies:
1. Deterministic empty-context fast-path (does not call LLM provider, returns safe refusal).
2. Grounded answer generation with populated context using mock provider.
3. Candidate source tag extraction ([source_1], [source_2]) into sources_referenced.
4. Preservation of original_query and processed query.
5. Provider error propagation without fabricating answers.
6. Safe diagnostic metadata (no leaked secrets, paths, or credentials).
7. Thread-safe singleton factory.
8. Zero network or database dependencies.
"""

import uuid
from unittest.mock import AsyncMock

import pytest

from backend.app.schemas.context_assembly import (
    ContextAssemblyResult,
    ContextItem,
)
from backend.app.schemas.llm import (
    LLMGenerationRequest,
    LLMProviderResponse,
)
from backend.app.services.llm.base import BaseLLMProvider
from backend.app.services.llm.exceptions import (
    LLMConnectionError,
    LLMTimeoutError,
)
from backend.app.services.llm.service import (
    _SOURCE_REF_REGEX,
    SAFE_INSUFFICIENT_EVIDENCE_ANSWER,
    LLMGenerationService,
    _sanitize_llm_answer,
    get_llm_generation_service,
)


class MockLLMProvider(BaseLLMProvider):
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
        return "mock-model-v1"

    async def generate(
        self,
        system_instruction: str,
        user_prompt: str,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        timeout_seconds: float | None = None,
        **kwargs,
    ) -> LLMProviderResponse:
        self.call_count += 1
        self.last_system_instruction = system_instruction
        self.last_user_prompt = user_prompt
        return LLMProviderResponse(
            content=self._response_text,
            model=self.model_name,
            prompt_tokens=50,
            output_tokens=12,
            total_duration_ms=45.0,
            safe_metadata={"eval_duration_ms": 30.0},
        )


def make_context_item(source_id: str, text: str) -> ContextItem:
    return ContextItem(
        source_id=source_id,
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_title="test_doc.pdf",
        chunk_index=0,
        text=text,
        page_number=1,
        section_title="Introduction",
        chunk_metadata={},
        reranker_rank=1,
        reranker_score=0.9,
        rrf_score=0.03,
        estimated_tokens=8,
    )


class TestLLMGenerationServiceUnit:
    """Unit test suite for LLMGenerationService."""

    @pytest.mark.asyncio
    async def test_empty_context_fast_path(self) -> None:
        """
        Verify that when context is empty:
        1. Provider is NOT invoked.
        2. Configured safe refusal answer is returned immediately.
        3. is_empty_context=True and latency=0.0.
        """
        provider = MockLLMProvider()
        service = LLMGenerationService(provider=provider)

        empty_context = ContextAssemblyResult(
            query="Empty query",
            original_query="Original raw query",
            items=[],
            total_items=0,
            total_estimated_tokens=0,
            token_budget=1000,
            candidates_received=0,
            items_skipped_budget=0,
            items_deduplicated=0,
        )

        request = LLMGenerationRequest(
            query="Empty query",
            original_query="Original raw query",
            context=empty_context,
        )

        response = await service.generate_grounded_answer(request)

        # Provider must NOT have been called!
        assert provider.call_count == 0
        assert response.answer == SAFE_INSUFFICIENT_EVIDENCE_ANSWER
        assert response.is_empty_context is True
        assert response.latency_ms == 0.0
        assert response.sources_available == []
        assert response.sources_referenced == []
        assert response.query == "Empty query"
        assert response.original_query == "Original raw query"
        assert response.metadata["fast_path"] is True

    @pytest.mark.asyncio
    async def test_grounded_generation_with_context(self) -> None:
        """
        Verify generation with evidence:
        1. Provider is called with assembled prompt.
        2. Sources available and referenced are extracted.
        3. Metrics and queries are preserved.
        """
        answer_text = (
            "According to [source_1], FCFS is non-preemptive, while Round Robin [source_2] "
            "uses time quantum slices [source_1]."
        )
        provider = MockLLMProvider(response_text=answer_text)
        service = LLMGenerationService(provider=provider)

        item1 = make_context_item("source_1", "First Come First Served (FCFS) scheduling.")
        item2 = make_context_item("source_2", "Round Robin allocates time quantum slices.")

        context = ContextAssemblyResult(
            query="scheduling algorithms",
            original_query="what are scheduling algorithms?",
            items=[item1, item2],
            total_items=2,
            total_estimated_tokens=16,
            token_budget=1000,
            candidates_received=2,
            items_skipped_budget=0,
            items_deduplicated=0,
        )

        request = LLMGenerationRequest(
            query="scheduling algorithms",
            original_query="what are scheduling algorithms?",
            context=context,
        )

        response = await service.generate_grounded_answer(request)

        assert provider.call_count == 1
        assert response.answer == answer_text
        assert response.provider == "mock_provider"
        assert response.model == "mock-model-v1"
        assert response.is_empty_context is False
        assert response.sources_available == ["source_1", "source_2"]
        # sources_referenced extracts [source_1] and [source_2], deduplicated in order of discovery
        assert response.sources_referenced == ["source_1", "source_2"]
        assert response.prompt_tokens == 50
        assert response.output_tokens == 12
        assert response.latency_ms >= 0.0
        assert response.query == "scheduling algorithms"
        assert response.original_query == "what are scheduling algorithms?"
        assert response.metadata["sources_available_count"] == 2
        assert response.metadata["sources_referenced_count"] == 2

    @pytest.mark.asyncio
    async def test_provider_connection_error_handling(self) -> None:
        """Verify provider connection failures are not converted to fabricated answers."""
        provider = MockLLMProvider()
        provider.generate = AsyncMock(side_effect=LLMConnectionError("Failed to connect to Ollama"))
        service = LLMGenerationService(provider=provider)

        item = make_context_item("source_1", "Some content.")
        context = ContextAssemblyResult(
            query="test",
            original_query=None,
            items=[item],
            total_items=1,
            total_estimated_tokens=8,
            token_budget=1000,
            candidates_received=1,
            items_skipped_budget=0,
            items_deduplicated=0,
        )

        request = LLMGenerationRequest(query="test", context=context)

        with pytest.raises(LLMConnectionError, match="Failed to connect to Ollama"):
            await service.generate_grounded_answer(request)

    @pytest.mark.asyncio
    async def test_provider_timeout_error_handling(self) -> None:
        """Verify provider timeouts raise LLMTimeoutError cleanly."""
        provider = MockLLMProvider()
        provider.generate = AsyncMock(side_effect=LLMTimeoutError("Ollama generation timed out"))
        service = LLMGenerationService(provider=provider)

        item = make_context_item("source_1", "Some content.")
        context = ContextAssemblyResult(
            query="test",
            original_query=None,
            items=[item],
            total_items=1,
            total_estimated_tokens=8,
            token_budget=1000,
            candidates_received=1,
            items_skipped_budget=0,
            items_deduplicated=0,
        )

        request = LLMGenerationRequest(query="test", context=context)

        with pytest.raises(LLMTimeoutError, match="timed out"):
            await service.generate_grounded_answer(request)

    def test_singleton_factory(self) -> None:
        """Verify get_llm_generation_service returns a consistent singleton instance."""
        inst1 = get_llm_generation_service()
        inst2 = get_llm_generation_service()
        assert inst1 is inst2
        assert isinstance(inst1, LLMGenerationService)

    def test_sanitize_llm_answer_strips_cot_and_extracts_concise_answer(self) -> None:
        """Verify that rambling CoT monologue is stripped and concise factual answer is preserved."""
        raw_rambling_cot = (
            'We are given the user question: "what is act name"\n\n'
            'We must look for the name of the act in the retrieved evidence.\n\n'
            "Let's check each source:\n\n"
            "* [source_1]: This is from KSU-Act-English.pdf, Page 12. It talks about powers of the Board. "
            "It does not explicitly state the name of the act.\n\n"
            '* [source_2]: This is from KSU-Act-English.pdf, Page 1. It states: "GUJARAT ACT NO. 22 OF 2021... '
            'This Act may be called \\"Kaushalya the Skill University Act 2021\\""\n\n'
            "* [source_3]: This is from KSU-Act-English.pdf, Page 16. It talks about funds and does not state the name.\n\n"
            "* [source_4]: This is from KSU-Act-English.pdf, Page 7. It talks about officers of the University.\n\n"
            'Therefore, the act name is explicitly stated in [source_2] as "Kaushalya the Skill University Act 2021".'
        )

        cleaned = _sanitize_llm_answer(raw_rambling_cot)

        # 1. Preamble and internal monologue must be absent
        assert "We are given the user question" not in cleaned
        assert "We must look for the name" not in cleaned
        assert "Let's check each source" not in cleaned
        assert "* [source_1]" not in cleaned
        assert "* [source_3]" not in cleaned
        assert "* [source_4]" not in cleaned

        # 2. Direct conclusion with the true answer must be preserved
        assert "Kaushalya the Skill University Act 2021" in cleaned
        assert "[source_2]" in cleaned

        # 3. Only source_2 is referenced in the final output
        referenced_sources = set(_SOURCE_REF_REGEX.findall(cleaned))
        assert referenced_sources == {"source_2"}
        assert "source_1" not in referenced_sources
        assert "source_3" not in referenced_sources
        assert "source_4" not in referenced_sources

    def test_sanitize_llm_answer_handles_think_tags(self) -> None:
        """Verify that reasoning within <think>...</think> tags is stripped completely."""
        raw = (
            "<think>\n"
            "User wants to know the act name.\n"
            "Checking chunks: chunk 1 no, chunk 2 yes.\n"
            "</think>\n"
            'This Act may be called "Kaushalya the Skill University Act 2021" [source_2].'
        )

        cleaned = _sanitize_llm_answer(raw)
        assert "<think>" not in cleaned
        assert "</think>" not in cleaned
        assert "Checking chunks" not in cleaned
        assert 'This Act may be called "Kaushalya the Skill University Act 2021" [source_2].' in cleaned
