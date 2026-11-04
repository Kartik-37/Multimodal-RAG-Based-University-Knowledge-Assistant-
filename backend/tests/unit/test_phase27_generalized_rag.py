"""
Phase 27 Generalized RAG Answer Pipeline Unit Tests.

Verifies:
1. Domain-agnostic query understanding: arbitrary topics X, 'tell me about X', 'how does X work', absence of blacklists.
2. Cross-domain relevance gating and alignment checking across unseen academic subjects (database isolation, cellular biology, macroeconomics).
3. Single shared retry budget: total provider calls across orchestrator and LLM service never exceeds 2.
4. Absence of deterministic Python templates / hardcoded fallback answers.
5. Citation and document card deduplication: unifies cards by canonical document_id, suppresses redundant page_number=None when real pages exist.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.models.document import Document
from backend.app.schemas.chat import CitationItem
from backend.app.schemas.context_assembly import ContextAssemblyResult, ContextItem
from backend.app.schemas.hybrid_retrieval import HybridRetrievalResponse
from backend.app.schemas.llm import LLMGenerationRequest, LLMGenerationResponse
from backend.app.schemas.query_understanding import QueryIntent, StructuredQuery
from backend.app.schemas.reranking import RerankResultItem
from backend.app.services.answer_alignment import get_answer_alignment_checker
from backend.app.services.document_summary_service import DocumentSummaryService
from backend.app.services.llm.service import LLMGenerationService, clean_reasoning_text
from backend.app.services.query_understanding import get_query_understanding_service
from backend.app.services.rag_orchestrator import RAGOrchestrator
from backend.app.services.relevance_gate import get_relevance_gate
from frontend.client.citations import group_citations_by_document
from frontend.client.models import CitationDTO


# =========================================================================
# 1. Generalized Query Understanding Tests
# =========================================================================

def test_generic_query_understanding_unseen_academic_topics():
    """Verify arbitrary unseen academic subjects are properly analyzed without hardcoded rules."""
    qu = get_query_understanding_service()

    # Unseen topic 1: Database isolation
    sq_db = qu.analyze("What is serializable snapshot isolation in databases?")
    assert sq_db.intent == QueryIntent.DEFINITION
    assert "serializable" in sq_db.subject.lower() or "isolation" in sq_db.subject.lower()
    assert sq_db.requires_retrieval is True
    assert sq_db.is_out_of_scope is False

    # Unseen topic 2: Cellular biology
    sq_bio = qu.analyze("How does ATP synthesis occur in mitochondria?")
    assert sq_bio.intent == QueryIntent.EXPLANATION
    assert "atp" in sq_bio.subject.lower() or "mitochondria" in sq_bio.subject.lower()
    assert sq_bio.requires_retrieval is True

    # Unseen topic 3: Macroeconomics comparison
    sq_econ = qu.analyze("Compare fiscal policy and monetary policy")
    assert sq_econ.intent == QueryIntent.COMPARISON
    assert "fiscal" in sq_econ.subject.lower() and "monetary" in sq_econ.subject.lower()

    # Unseen topic 4: Conversational 'tell me about X'
    sq_tell = qu.analyze("Tell me about the Byzantine Fault Tolerance algorithm")
    assert sq_tell.intent == QueryIntent.EXPLANATION
    assert "byzantine" in sq_tell.subject.lower()

    # Unseen topic 5: Procedure
    sq_steps = qu.analyze("How to configure a Raft consensus cluster?")
    assert sq_steps.intent == QueryIntent.STEPS
    assert "raft" in sq_steps.subject.lower()


def test_absence_of_celebrity_pop_culture_blacklists():
    """Verify queries mentioning prominent figures are treated as legitimate academic retrieval targets."""
    qu = get_query_understanding_service()

    # History / Political Science topic
    sq = qu.analyze("What were the economic policies of Narendra Modi?")
    assert sq.is_out_of_scope is False
    assert sq.requires_retrieval is True
    assert sq.intent in (QueryIntent.EXPLANATION, QueryIntent.DEFINITION, QueryIntent.FACT_LOOKUP)


# =========================================================================
# 2. Generic Relevance Gate Tests (Unseen Subjects)
# =========================================================================

def test_relevance_gate_unseen_subject_filtering():
    """Verify relevance gate filters out irrelevant noise chunks for an unseen domain."""
    gate = get_relevance_gate()
    qu = get_query_understanding_service()
    sq = qu.analyze("Explain ACID transaction properties in relational databases")

    db_chunk = RerankResultItem(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_title="Database_Systems.pdf",
        chunk_index=1,
        text="ACID represents Atomicity, Consistency, Isolation, and Durability in database transactions.",
        page_number=12,
        rrf_score=0.9,
        reranker_score=4.5,
        reranker_rank=1,
    )

    unrelated_chunk = RerankResultItem(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_title="Unrelated_Biology.pdf",
        chunk_index=2,
        text="Photosynthesis converts solar light energy into chemical energy stored in glucose molecules.",
        page_number=45,
        rrf_score=0.1,
        reranker_score=-10.5,
        reranker_rank=2,
    )

    accepted, audit = gate.evaluate_candidates(sq, [db_chunk, unrelated_chunk])
    assert len(accepted) == 1
    assert accepted[0].page_number == 12
    assert audit[1]["decision"] == "REJECT"


def test_relevance_gate_visual_balancing_for_conceptual_queries():
    """Ensure visual chunks do not crowd out text explanations when no visual intent is requested."""
    gate = get_relevance_gate()
    qu = get_query_understanding_service()
    sq = qu.analyze("Define neural network backpropagation")

    text_chunk = RerankResultItem(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_title="Deep_Learning.pdf",
        chunk_index=10,
        text="Backpropagation calculates the gradient of the loss function with respect to weights using the chain rule.",
        page_number=50,
        rrf_score=0.8,
        reranker_score=3.0,
        reranker_rank=1,
    )

    visual_off_topic = RerankResultItem(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_title="Deep_Learning.pdf",
        chunk_index=11,
        text="[Image Caption]: Company logo and header bar on title slide.",
        page_number=1,
        rrf_score=0.5,
        reranker_score=-2.0,
        reranker_rank=2,
        chunk_metadata={"source_modality": "visual"},
    )

    accepted, _ = gate.evaluate_candidates(sq, [text_chunk, visual_off_topic])
    # Visual chunk without visual intent and without query terms is filtered out
    assert len(accepted) == 1
    assert accepted[0].chunk_index == 10


# =========================================================================
# 3. Generic Answer Alignment Checker Tests
# =========================================================================

def test_generic_alignment_checker_detects_topic_drift():
    """Alignment checker must flag an answer that discusses a completely different topic."""
    checker = get_answer_alignment_checker()
    qu = get_query_understanding_service()
    sq = qu.analyze("What is the CAP theorem in distributed systems?")

    # Answer discussing an unrelated subject
    off_topic_ans = "Cellular mitosis consists of prophase, metaphase, anaphase, and telophase [source_1]."
    aligned, reason = checker.check_alignment(sq, off_topic_ans)
    assert aligned is False
    assert "MISALIGNED" in reason

    # Aligned answer
    good_ans = "The CAP theorem states that a distributed data store can only simultaneously provide two out of Consistency, Availability, and Partition tolerance [source_1]."
    aligned_good, _ = checker.check_alignment(sq, good_ans)
    assert aligned_good is True


def test_generic_alignment_checker_allows_safe_refusal():
    """Alignment checker must always accept polite evidence refusals."""
    checker = get_answer_alignment_checker()
    qu = get_query_understanding_service()
    sq = qu.analyze("What is quantum entanglement?")

    refusal = "I could not find sufficient verified evidence in the course materials to answer your question."
    aligned, reason = checker.check_alignment(sq, refusal)
    assert aligned is True
    assert reason == "ALIGNED_SAFE_REFUSAL"


# =========================================================================
# 4. Single Shared Retry Budget Tests
# =========================================================================

@pytest.mark.asyncio
async def test_single_shared_retry_budget_never_exceeds_two_calls():
    """Verify that total provider calls across the entire orchestrator request never exceeds 2."""
    qp = MagicMock()
    qp.process.return_value = MagicMock(
        processed_query="what is quantum entanglement",
        token_estimate=4,
        character_count=28,
        has_quotes=False,
        has_technical_tokens=False,
    )

    hybrid = MagicMock()
    hybrid.retrieve = AsyncMock(return_value=HybridRetrievalResponse(
        query="what is quantum entanglement",
        knowledge_base_id=uuid.uuid4(),
        top_k=5,
        rrf_k=60,
        vector_weight=0.5,
        lexical_weight=0.5,
        total_results=1,
        results=[],
        latency_breakdown={},
        fusion_strategy="rrf",
    ))

    rerank_item = RerankResultItem(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_title="Physics.pdf",
        chunk_index=1,
        text="Quantum entanglement is a physical phenomenon where particles remain interconnected.",
        page_number=5,
        rrf_score=0.9,
        reranker_score=2.0,
        reranker_rank=1,
    )

    rerank = MagicMock()
    rerank.rerank_candidates = AsyncMock(return_value=[rerank_item])

    # LLM service mock that returns a response where provider_calls = 2 (already retried internally)
    llm = MagicMock()
    llm.generate_grounded_answer = AsyncMock()
    # Misaligned answer on first attempt, but retry_occurred=True and provider_calls=2
    llm.generate_grounded_answer.return_value = LLMGenerationResponse(
        answer="Cellular mitosis is cell division.",  # off topic
        query="what is quantum entanglement",
        provider="ollama",
        model="qwen3:4b",
        is_empty_context=False,
        latency_ms=200.0,
        sources_referenced=["source_1"],
        prompt_tokens=100,
        output_tokens=20,
        metadata={
            "generation_mode": "llm_retry",
            "llm_invoked": True,
            "provider_calls": 2,
            "retry_occurred": True,
        },
    )

    mock_grounding = MagicMock()
    mock_grounding.validate.return_value = MagicMock(
        total_claims=1,
        factual_claims=1,
        supported_claims=1,
        unsupported_claims=0,
        unverifiable_claims=0,
        has_conflicts=False,
        citation_validity_rate=1.0,
        citation_coverage=1.0,
        claim_support_rate=1.0,
        unsupported_claim_rate=0.0,
        claims=[],
    )

    orchestrator = RAGOrchestrator(
        query_processor=qp,
        hybrid_service=hybrid,
        reranking_service=rerank,
        llm_service=llm,
        grounding_service=mock_grounding,
    )

    resp = await orchestrator.execute_query(
        db=MagicMock(),
        kb_id=uuid.uuid4(),
        raw_query="What is quantum entanglement?",
    )

    # Orchestrator must NOT invoke LLM a 3rd or 4th time; must fail cleanly to safe refusal
    assert llm.generate_grounded_answer.call_count == 1
    assert resp.metadata["provider_calls"] == 2
    assert resp.metadata["generation_mode"] == "insufficient_evidence_refusal"


# =========================================================================
# 5. Clean Reasoning Sanitizer Tests
# =========================================================================

def test_clean_reasoning_text_does_not_synthesize_sentences():
    """Verify clean_reasoning_text does not regex-stitch sentences from planned target quotes."""
    reasoning_sample = (
        "I need to answer the question. The user asks about Flutter.\n"
        "Let's check source 1.\n"
        "Start with: 'Flutter is an open-source UI SDK.'\n"
        "Then add: 'It compiles to native machine code.'\n"
        "Therefore, I'll write the answer."
    )
    # Must NOT stitch together Start with / Then add into a synthetic paragraph
    result = clean_reasoning_text(reasoning_sample)
    # Since there is no clean Conclusion block, it returns unchanged so validator can reject/retry
    assert "Start with:" in result or "Therefore" in result
    assert result != "Flutter is an open-source UI SDK. It compiles to native machine code. [source_1]."


def test_clean_reasoning_text_extracts_genuine_conclusion():
    """Verify clean_reasoning_text extracts genuine conclusion block if present."""
    text_with_conclusion = (
        "Let me analyze the sources.\n"
        "Source 1 has the answer.\n\n"
        "Final Answer: Serializable isolation prevents write skew and phantom reads by enforcing serial execution order [source_1]."
    )
    extracted = clean_reasoning_text(text_with_conclusion)
    assert extracted.startswith("Serializable isolation prevents write skew")
    assert "[source_1]" in extracted


# =========================================================================
# 6. Document Summary Service Tests
# =========================================================================

@pytest.mark.asyncio
async def test_document_summary_service_fails_honestly_without_hardcoded_template():
    """When LLM generation fails in summary service, return honest failure instead of hardcoded Flutter text."""
    failing_provider = MagicMock()
    failing_provider.generate = AsyncMock(side_effect=Exception("Ollama connection timeout"))
    svc = DocumentSummaryService(provider=failing_provider)

    doc = Document(
        id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        original_filename="Bio101_Cellular_Mitosis.pdf",
        mime_type="application/pdf",
        file_type="pdf",
        file_size_bytes=1024,
        storage_key="docs/bio.pdf",
        content_hash="mockbiohash123",
    )

    mock_chunk = MagicMock()
    mock_chunk.id = uuid.uuid4()
    mock_chunk.text = "Mitosis is the process of cell replication."
    mock_chunk.page_number = 1
    mock_chunk.chunk_index = 0

    mock_db = MagicMock()
    mock_db.scalars.return_value.all.return_value = [mock_chunk]

    sq = StructuredQuery(
        original_query="Summarize this document",
        normalized_query="summarize this document",
        detected_language="english",
        intent=QueryIntent.DOCUMENT_SUMMARY,
        subject="Bio101_Cellular_Mitosis.pdf",
        requires_document_summary=True,
    )

    resp = await svc.generate_document_summary(
        db=mock_db,
        target_doc=doc,
        structured_query=sq,
        raw_query="Summarize this document",
    )

    # Must NOT contain hardcoded Flutter summary
    assert "Flutter" not in resp.answer
    assert "Hot Reload" not in resp.answer
    assert resp.metadata["generation_mode"] == "generation_failed"
    assert resp.metadata["llm_invoked"] is False


# =========================================================================
# 7. Citation and Document Card Deduplication Tests
# =========================================================================

def test_citation_grouping_deduplicates_redundant_pageless_entry():
    """If a document has entries with page numbers and an entry with page_number=None, drop the redundant pill."""
    doc_id = str(uuid.uuid4())
    kb_id = str(uuid.uuid4())

    c1 = CitationDTO(
        source_id="source_1",
        document_name="1-Flutter-Intro.pdf",
        document_id=doc_id,
        knowledge_base_id=kb_id,
        chunk_id=str(uuid.uuid4()),
        page_number=18,
        snippet="Cross platform UI toolkit",
    )
    c2 = CitationDTO(
        source_id="source_2",
        document_name="1-Flutter-Intro.pdf",
        document_id=doc_id,
        knowledge_base_id=kb_id,
        chunk_id=str(uuid.uuid4()),
        page_number=34,
        snippet="Everything is a widget",
    )
    c3 = CitationDTO(
        source_id="source_3",
        document_name="1-Flutter-Intro.pdf",
        document_id=doc_id,
        knowledge_base_id=kb_id,
        chunk_id=str(uuid.uuid4()),
        page_number=None,  # Redundant unpaged reference
        snippet="Overview",
    )

    groups = group_citations_by_document([c1, c2, c3])
    assert len(groups) == 1
    group = groups[0]
    assert group.document_name == "1-Flutter-Intro.pdf"
    # Redundant page_number=None should be dropped because real pages (18, 34) exist
    page_numbers = [p.page_number for p in group.pages]
    assert None not in page_numbers
    assert 18 in page_numbers
    assert 34 in page_numbers


def test_citation_grouping_unifies_single_document_card():
    """Never produce a generic 'Document' card alongside the real PDF card for the same document."""
    doc_id = str(uuid.uuid4())
    kb_id = str(uuid.uuid4())

    c1 = CitationDTO(
        source_id="source_1",
        document_name="Advanced_Algorithms.pdf",
        document_id=doc_id,
        knowledge_base_id=kb_id,
        chunk_id=str(uuid.uuid4()),
        page_number=5,
        snippet="Dijkstra shortest path",
    )
    c2 = CitationDTO(
        source_id="source_2",
        document_name="Document",  # generic name from fallback
        document_id=doc_id,       # same document_id
        knowledge_base_id=kb_id,
        chunk_id=str(uuid.uuid4()),
        page_number=6,
        snippet="Bellman Ford algorithm",
    )

    groups = group_citations_by_document([c1, c2])
    assert len(groups) == 1
    assert groups[0].document_name == "Advanced_Algorithms.pdf"
    assert len(groups[0].pages) == 2
