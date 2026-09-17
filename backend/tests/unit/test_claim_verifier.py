"""
Unit Tests for Conservative Deterministic ClaimVerifier.
"""

import uuid

from backend.app.schemas.context_assembly import ContextAssemblyResult, ContextItem
from backend.app.schemas.grounding_validation import GroundingStatus
from backend.app.services.grounding.claim_verifier import ClaimVerifier
from backend.app.services.grounding.sentence_splitter import ExtractedClaim


def _make_dummy_context_item(
    source_id: str,
    text: str,
    title: str = "Operating_Systems.pdf",
) -> ContextItem:
    return ContextItem(
        source_id=source_id,
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_title=title,
        chunk_index=0,
        text=text,
        page_number=1,
        section_title="CPU Scheduling",
        chunk_metadata={},
        reranker_rank=1,
        reranker_score=0.88,
        rrf_score=0.03,
        estimated_tokens=50,
    )


def test_claim_verifier_supported_claim() -> None:
    chunk_text = (
        "First-Come First-Served (FCFS) is a non-preemptive CPU scheduling algorithm. "
        "Processes are dispatched in the strict order of their arrival in the ready queue."
    )
    item = _make_dummy_context_item("source_1", chunk_text)
    context = ContextAssemblyResult(
        query="what is fcfs",
        items=[item],
        total_items=1,
        total_estimated_tokens=50,
        token_budget=1000,
        candidates_received=1,
        items_skipped_budget=0,
        items_deduplicated=0,
    )
    context_map = {"source_1": item}

    verifier = ClaimVerifier(min_overlap_threshold=0.5)
    claim = ExtractedClaim(
        claim_index=1,
        text="FCFS is a non-preemptive scheduling algorithm that dispatches processes in arrival order.",
        raw_text="FCFS is a non-preemptive scheduling algorithm that dispatches processes in arrival order. [source_1]",
        is_conversational=False,
        cited_source_ids=["source_1"],
    )

    result = verifier.verify_claim(claim, context, context_map)
    assert result.status == GroundingStatus.SUPPORTED
    assert result.overlap_score >= 0.5
    assert len(result.supporting_evidence_snippets) > 0
    assert "FCFS" in result.supporting_evidence_snippets[0]


def test_claim_verifier_detects_numeric_hallucination() -> None:
    chunk_text = "The system was designed in 1950 by research engineers."
    item = _make_dummy_context_item("source_1", chunk_text)
    context = ContextAssemblyResult(
        query="when was system designed",
        items=[item],
        total_items=1,
        total_estimated_tokens=30,
        token_budget=1000,
        candidates_received=1,
        items_skipped_budget=0,
        items_deduplicated=0,
    )
    context_map = {"source_1": item}

    verifier = ClaimVerifier(min_overlap_threshold=0.5)
    # Model hallucinated 1970 instead of 1950
    claim = ExtractedClaim(
        claim_index=1,
        text="The system was designed in 1970 by research engineers.",
        raw_text="The system was designed in 1970 by research engineers. [source_1]",
        is_conversational=False,
        cited_source_ids=["source_1"],
    )

    result = verifier.verify_claim(claim, context, context_map)
    assert result.status == GroundingStatus.UNSUPPORTED
    assert "1970" in (result.unsupported_reason or "")


def test_claim_verifier_detects_acronym_mismatch() -> None:
    chunk_text = "FCFS executes processes in arrival order."
    item = _make_dummy_context_item("source_1", chunk_text)
    context = ContextAssemblyResult(
        query="scheduling algorithms",
        items=[item],
        total_items=1,
        total_estimated_tokens=30,
        token_budget=1000,
        candidates_received=1,
        items_skipped_budget=0,
        items_deduplicated=0,
    )
    context_map = {"source_1": item}

    verifier = ClaimVerifier(min_overlap_threshold=0.5)
    # Model mentions SJF which does not appear in source_1
    claim = ExtractedClaim(
        claim_index=1,
        text="SJF executes processes in arrival order.",
        raw_text="SJF executes processes in arrival order. [source_1]",
        is_conversational=False,
        cited_source_ids=["source_1"],
    )

    result = verifier.verify_claim(claim, context, context_map)
    assert result.status == GroundingStatus.UNSUPPORTED
    assert "SJF" in (result.unsupported_reason or "")


def test_claim_verifier_supported_uncited_claim() -> None:
    chunk_text = (
        "Virtual memory allows the execution of processes that are not completely in memory."
    )
    item = _make_dummy_context_item("source_1", chunk_text)
    context = ContextAssemblyResult(
        query="virtual memory",
        items=[item],
        total_items=1,
        total_estimated_tokens=30,
        token_budget=1000,
        candidates_received=1,
        items_skipped_budget=0,
        items_deduplicated=0,
    )
    context_map = {"source_1": item}

    verifier = ClaimVerifier(min_overlap_threshold=0.5)
    # Claim lacks citation tag but is present in context
    claim = ExtractedClaim(
        claim_index=1,
        text="Virtual memory allows execution of processes not completely in memory.",
        raw_text="Virtual memory allows execution of processes not completely in memory.",
        is_conversational=False,
        cited_source_ids=[],
    )

    result = verifier.verify_claim(claim, context, context_map)
    assert result.status == GroundingStatus.SUPPORTED_UNCITED
    assert result.overlap_score >= 0.5


def test_claim_verifier_unverifiable_claim_favors_conservative_stance() -> None:
    chunk_text = (
        "Paging is a memory management scheme that eliminates the need for contiguous allocation."
    )
    item = _make_dummy_context_item("source_1", chunk_text)
    context = ContextAssemblyResult(
        query="paging",
        items=[item],
        total_items=1,
        total_estimated_tokens=30,
        token_budget=1000,
        candidates_received=1,
        items_skipped_budget=0,
        items_deduplicated=0,
    )
    context_map = {"source_1": item}

    verifier = ClaimVerifier(min_overlap_threshold=0.5)
    # Completely unrelated statement
    claim = ExtractedClaim(
        claim_index=1,
        text="Relational databases use B-Trees for primary index clustering.",
        raw_text="Relational databases use B-Trees for primary index clustering. [source_1]",
        is_conversational=False,
        cited_source_ids=["source_1"],
    )

    result = verifier.verify_claim(claim, context, context_map)
    # Favor UNVERIFIABLE rather than declaring support
    assert result.status == GroundingStatus.UNVERIFIABLE


def test_claim_verifier_conversational_claim() -> None:
    context = ContextAssemblyResult(
        query="query",
        items=[],
        total_items=0,
        total_estimated_tokens=0,
        token_budget=1000,
        candidates_received=0,
        items_skipped_budget=0,
        items_deduplicated=0,
    )
    verifier = ClaimVerifier()
    claim = ExtractedClaim(
        claim_index=1,
        text="Based on the provided documents, here is the answer.",
        raw_text="Based on the provided documents, here is the answer.",
        is_conversational=True,
        cited_source_ids=[],
    )

    result = verifier.verify_claim(claim, context, {})
    assert result.status == GroundingStatus.CONVERSATIONAL
    assert result.is_conversational is True
    assert result.overlap_score == 0.0
