"""
Integration Tests for Step 14 Grounding and Citation Validation.

Verifies end-to-end data contract flow from Step 12 ContextAssemblyResult
and Step 13 LLMGenerationResponse into Step 14 GroundingValidationService.
"""

import uuid

import pytest

from backend.app.schemas.context_assembly import ContextAssemblyResult, ContextItem
from backend.app.schemas.grounding_validation import (
    GroundingStatus,
    GroundingValidationRequest,
    GroundingValidationResult,
)
from backend.app.schemas.llm import (
    LLMGenerationRequest,
    LLMProviderResponse,
)
from backend.app.services.grounding.service import get_grounding_validation_service
from backend.app.services.llm.base import BaseLLMProvider
from backend.app.services.llm.service import LLMGenerationService


class MockStaticLLMProvider(BaseLLMProvider):
    """Deterministic mock provider simulating an LLM generation response."""

    def __init__(self, output_text: str) -> None:
        self.output_text = output_text

    @property
    def provider_name(self) -> str:
        return "mock_integration"

    @property
    def model_name(self) -> str:
        return "qwen3:4b"

    async def generate(
        self,
        system_instruction: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_output_tokens: int = 1024,
        timeout_seconds: float = 120.0,
    ) -> LLMProviderResponse:
        return LLMProviderResponse(
            content=self.output_text,
            model=self.model_name,
            prompt_tokens=150,
            output_tokens=60,
            total_duration_ms=45.0,
            safe_metadata={"mock": True},
        )


@pytest.mark.asyncio
async def test_grounding_validation_integration_pipeline() -> None:
    # 1. Step 12 Context Assembly Output
    chunk_1_id = uuid.uuid4()
    chunk_2_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    kb_id = uuid.uuid4()

    item1 = ContextItem(
        source_id="source_1",
        chunk_id=chunk_1_id,
        document_id=doc_id,
        knowledge_base_id=kb_id,
        document_title="Operating_Systems_BCA.pdf",
        chunk_index=0,
        text=(
            "First-Come First-Served (FCFS) scheduling executes jobs in order of arrival. "
            "It is a non-preemptive algorithm."
        ),
        page_number=12,
        section_title="CPU Scheduling",
        chunk_metadata={"section": "3.1"},
        reranker_rank=1,
        reranker_score=0.92,
        rrf_score=0.032,
        estimated_tokens=40,
    )
    item2 = ContextItem(
        source_id="source_2",
        chunk_id=chunk_2_id,
        document_id=doc_id,
        knowledge_base_id=kb_id,
        document_title="Operating_Systems_BCA.pdf",
        chunk_index=1,
        text=(
            "Round Robin (RR) scheduling allocates a fixed time quantum to each process. "
            "It is preemptive."
        ),
        page_number=14,
        section_title="Round Robin",
        chunk_metadata={"section": "3.2"},
        reranker_rank=2,
        reranker_score=0.85,
        rrf_score=0.028,
        estimated_tokens=35,
    )

    context = ContextAssemblyResult(
        query="explain fcfs and round robin",
        original_query="Explain FCFS and Round Robin?",
        items=[item1, item2],
        total_items=2,
        total_estimated_tokens=75,
        token_budget=1000,
        candidates_received=2,
        items_skipped_budget=0,
        items_deduplicated=0,
        metadata={"assembly": "ok"},
    )

    # 2. Step 13 Generation Execution
    simulated_model_answer = (
        "FCFS scheduling executes jobs strictly in order of arrival and is non-preemptive. [source_1] "
        "Round Robin allocates a fixed time quantum and is preemptive. [source_2] "
        "FCFS was invented in 1999. [source_1]"  # Unsupported hallucination (1999)
    )
    llm_service = LLMGenerationService(provider=MockStaticLLMProvider(simulated_model_answer))
    gen_request = LLMGenerationRequest(
        query="explain fcfs and round robin",
        original_query="Explain FCFS and Round Robin?",
        context=context,
    )
    llm_response = await llm_service.generate_grounded_answer(gen_request)

    assert llm_response.sources_referenced == ["source_1", "source_2"]

    # 3. Step 14 Validation Execution
    validation_service = get_grounding_validation_service()
    val_request = GroundingValidationRequest(response=llm_response, context=context)
    val_result = validation_service.validate(val_request)

    assert isinstance(val_result, GroundingValidationResult)
    assert val_result.query == "explain fcfs and round robin"
    assert val_result.total_claims == 3
    assert val_result.factual_claims == 3
    assert val_result.cited_claims == 3

    # Supported claims: first two
    assert val_result.supported_claims == 2
    # Third claim contains hallucinated 1999
    assert val_result.unsupported_claims == 1
    assert val_result.claims[2].status == GroundingStatus.UNSUPPORTED
    assert "1999" in (val_result.claims[2].unsupported_reason or "")

    # Citations
    assert val_result.citations_found == 3
    assert val_result.valid_citations == 3
    assert val_result.citation_validity_rate == 1.0
    assert val_result.citation_coverage == 1.0

    # Rates
    assert val_result.claim_support_rate == pytest.approx(2 / 3, 0.01)
    assert val_result.unsupported_claim_rate == pytest.approx(1 / 3, 0.01)
    assert val_result.latency_ms >= 0.0
