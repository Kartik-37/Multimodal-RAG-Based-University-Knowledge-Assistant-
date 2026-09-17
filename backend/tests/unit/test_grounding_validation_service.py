"""
Unit Tests for GroundingValidationService.
"""

import uuid

from backend.app.schemas.context_assembly import ContextAssemblyResult, ContextItem
from backend.app.schemas.grounding_validation import (
    GroundingValidationRequest,
)
from backend.app.schemas.llm import LLMGenerationResponse
from backend.app.services.grounding.service import (
    GroundingValidationService,
    get_grounding_validation_service,
)


def _make_context(items_data: list[tuple[str, str]]) -> ContextAssemblyResult:
    items = []
    for idx, (sid, text) in enumerate(items_data):
        items.append(
            ContextItem(
                source_id=sid,
                chunk_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                knowledge_base_id=uuid.uuid4(),
                document_title=f"Doc_{sid}.pdf",
                chunk_index=idx,
                text=text,
                page_number=idx + 1,
                section_title="OS Concepts",
                chunk_metadata={},
                reranker_rank=idx + 1,
                reranker_score=0.9 - idx * 0.1,
                rrf_score=0.03,
                estimated_tokens=50,
            )
        )
    return ContextAssemblyResult(
        query="os concepts",
        items=items,
        total_items=len(items),
        total_estimated_tokens=len(items) * 50,
        token_budget=1000,
        candidates_received=len(items),
        items_skipped_budget=0,
        items_deduplicated=0,
    )


def test_grounding_validation_service_all_claims_supported() -> None:
    context = _make_context(
        [
            (
                "source_1",
                "First-Come First-Served is non-preemptive. Processes run in arrival order.",
            ),
            (
                "source_2",
                "Round Robin is preemptive and uses a defined time quantum for slicing.",
            ),
        ]
    )

    response = LLMGenerationResponse(
        answer=(
            "First-Come First-Served is non-preemptive and runs in arrival order. [source_1] "
            "Round Robin is preemptive and uses a time quantum. [source_2]"
        ),
        query="scheduling algorithms",
        original_query="scheduling algorithms",
        provider="ollama",
        model="qwen3:4b",
        sources_available=["source_1", "source_2"],
        sources_referenced=["source_1", "source_2"],
        is_empty_context=False,
        prompt_tokens=100,
        output_tokens=50,
        latency_ms=1200.0,
    )

    service = GroundingValidationService()
    request = GroundingValidationRequest(response=response, context=context)
    result = service.validate(request)

    assert result.total_claims == 2
    assert result.factual_claims == 2
    assert result.cited_claims == 2
    assert result.supported_claims == 2
    assert result.unsupported_claims == 0
    assert result.unverifiable_claims == 0
    assert result.citations_found == 2
    assert result.valid_citations == 2
    assert result.citation_validity_rate == 1.0
    assert result.citation_coverage == 1.0
    assert result.claim_support_rate == 1.0
    assert result.unsupported_claim_rate == 0.0


def test_grounding_validation_service_zero_citations_behavior() -> None:
    """
    Mandatory rule: An answer with zero citations must not receive 1.0;
    it must receive 0.0 for citation_validity_rate.
    """
    context = _make_context([("source_1", "FCFS is non-preemptive.")])

    response = LLMGenerationResponse(
        answer="FCFS is non-preemptive but I did not cite any source.",
        query="fcfs",
        provider="ollama",
        model="qwen3:4b",
        sources_available=["source_1"],
        sources_referenced=[],
        is_empty_context=False,
        latency_ms=500.0,
    )

    service = GroundingValidationService()
    request = GroundingValidationRequest(response=response, context=context)
    result = service.validate(request)

    assert result.citations_found == 0
    assert result.citation_validity_rate == 0.0
    assert result.citation_coverage == 0.0
    # The uncited claim is supported by context though
    assert result.supported_uncited_claims == 1


def test_grounding_validation_service_empty_context_refusal() -> None:
    """
    When is_empty_context=True and answer is the standard refusal,
    claim_support_rate should be 1.0, citation_coverage 0.0, zero unsupported claims.
    """
    context = ContextAssemblyResult(
        query="unknown topic",
        items=[],
        total_items=0,
        total_estimated_tokens=0,
        token_budget=1000,
        candidates_received=0,
        items_skipped_budget=0,
        items_deduplicated=0,
    )

    response = LLMGenerationResponse(
        answer="I could not find any relevant information in the available documents to answer your question.",
        query="unknown topic",
        provider="ollama",
        model="qwen3:4b",
        sources_available=[],
        sources_referenced=[],
        is_empty_context=True,
        latency_ms=0.0,
    )

    service = GroundingValidationService()
    request = GroundingValidationRequest(response=response, context=context)
    result = service.validate(request)

    assert result.is_empty_context is True
    assert result.factual_claims == 0
    assert result.conversational_claims == 1
    assert result.claim_support_rate == 1.0
    assert result.unsupported_claim_rate == 0.0
    assert result.citation_validity_rate == 0.0
    assert result.citation_coverage == 0.0


def test_grounding_validation_service_empty_answer_division_by_zero_safe() -> None:
    context = _make_context([("source_1", "Some text.")])

    response = LLMGenerationResponse(
        answer="",
        query="query",
        provider="ollama",
        model="qwen3:4b",
        sources_available=["source_1"],
        sources_referenced=[],
        is_empty_context=False,
        latency_ms=10.0,
    )

    service = GroundingValidationService()
    request = GroundingValidationRequest(response=response, context=context)
    result = service.validate(request)

    assert result.total_claims == 0
    assert result.factual_claims == 0
    assert result.citations_found == 0
    assert result.citation_validity_rate == 0.0
    assert result.citation_coverage == 0.0
    assert result.claim_support_rate == 0.0
    assert result.unsupported_claim_rate == 0.0


def test_grounding_validation_service_detects_evidence_conflict() -> None:
    # Two context chunks that provide opposing technical attributes for FCFS
    context = _make_context(
        [
            ("source_1", "FCFS is strictly non-preemptive scheduling."),
            ("source_2", "FCFS scheduling operates in a preemptive manner in special designs."),
        ]
    )

    response = LLMGenerationResponse(
        answer="FCFS scheduling is discussed across documents. [source_1]",
        query="fcfs",
        provider="ollama",
        model="qwen3:4b",
        sources_available=["source_1", "source_2"],
        sources_referenced=["source_1"],
        is_empty_context=False,
        latency_ms=500.0,
    )

    service = GroundingValidationService()
    request = GroundingValidationRequest(response=response, context=context)
    result = service.validate(request)

    assert result.has_conflicts is True
    assert len(result.detected_conflicts) == 1
    assert result.detected_conflicts[0].conflicting_topic == "FCFS"
    assert "preemptive" in result.detected_conflicts[0].conflict_description


def test_grounding_validation_service_singleton() -> None:
    s1 = get_grounding_validation_service()
    s2 = get_grounding_validation_service()
    assert s1 is s2
    assert isinstance(s1, GroundingValidationService)
