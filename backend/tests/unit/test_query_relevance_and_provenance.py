"""
Comprehensive Unit Tests for Phase 22:
- Structured Query Understanding (Intent classification, entity detection, pre-retrieval routing)
- Query-to-Evidence Relevance Gating (Subject/Entity matching, hard negative rejection)
- Answer-to-Question Alignment (Detecting entity drift like iPhones in widget answers)
- Generation Provenance and Telemetry (Honest tracking of primary_llm, fast paths, refusals)
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.schemas.context_assembly import ContextAssemblyResult, ContextItem
from backend.app.schemas.grounding_validation import GroundingStatus, GroundingValidationResult
from backend.app.schemas.hybrid_retrieval import HybridRetrievalResponse, HybridRetrievalResultItem
from backend.app.schemas.llm import LLMGenerationRequest, LLMGenerationResponse
from backend.app.schemas.query_understanding import QueryIntent, StructuredQuery
from backend.app.schemas.reranking import RerankResultItem
from backend.app.services.answer_alignment import AnswerAlignmentChecker, get_answer_alignment_checker
from backend.app.services.llm.service import (
    INSUFFICIENT_COURSE_EVIDENCE_ANSWER,
    LLMGenerationService,
    extract_grounded_recovery_answer,
)
from backend.app.services.query_understanding import (
    ASSISTANT_IDENTITY_ANSWER,
    QueryUnderstandingService,
    get_query_understanding_service,
)
from backend.app.services.rag_orchestrator import RAGOrchestrator
from backend.app.services.relevance_gate import QueryEvidenceRelevanceGate, get_relevance_gate


# =========================================================================
# 1. Structured Query Understanding Tests
# =========================================================================

def test_conversational_identity_routing():
    """Verify assistant identity and greeting queries are identified before retrieval."""
    service = get_query_understanding_service()

    for q in ("What is your name?", "who are you?", "Tell me your name", "what's your name"):
        sq = service.analyze(q)
        assert sq.intent == QueryIntent.IDENTITY
        assert sq.subject == "assistant"
        assert sq.is_conversational is True
        assert sq.requires_retrieval is False

    for q in ("Hello", "hi", "good morning", "Hey"):
        sq = service.analyze(q)
        assert sq.intent == QueryIntent.GREETING
        assert sq.is_conversational is True
        assert sq.requires_retrieval is False

    for q in ("help", "what can you do?"):
        sq = service.analyze(q)
        assert sq.intent == QueryIntent.HELP
        assert sq.is_conversational is True
        assert sq.requires_retrieval is False


def test_out_of_scope_query_routing():
    """Verify pop-culture / political / non-course queries are routed to out-of-scope."""
    service = get_query_understanding_service()

    for q in ("Who is Narendra Modi?", "Who is Virat Kohli?", "who is kahli?", "who is Donald Trump?"):
        sq = service.analyze(q)
        assert sq.intent == QueryIntent.OUT_OF_SCOPE
        assert sq.is_out_of_scope is True
        assert sq.requires_retrieval is False


def test_ambiguous_query_routing():
    """Verify bare ambiguous queries request clarification."""
    service = get_query_understanding_service()

    for q in ("list", "widgets", "versions", "devices", "show list"):
        sq = service.analyze(q)
        assert sq.intent == QueryIntent.AMBIGUOUS
        assert sq.is_ambiguous is True
        assert sq.requires_retrieval is False
        assert sq.clarification_prompt is not None


def test_academic_entity_query_classification():
    """Verify academic queries accurately capture subjects, properties, and entity types."""
    service = get_query_understanding_service()

    # Widget queries
    sq_widget_list = service.analyze("List of widgets")
    assert sq_widget_list.intent == QueryIntent.LIST
    assert sq_widget_list.subject == "flutter_widget"
    assert sq_widget_list.target_entity_type == "widget"
    assert sq_widget_list.requires_retrieval is True

    sq_widget_cat = service.analyze("Which widget categories are mentioned in the notes?")
    assert sq_widget_cat.intent == QueryIntent.FACT_LOOKUP
    assert sq_widget_cat.subject == "flutter_widget"
    assert sq_widget_cat.target_entity_type == "widget_category"

    sq_widget_def = service.analyze("What is a widget in Flutter?")
    assert sq_widget_def.intent == QueryIntent.DEFINITION
    assert sq_widget_def.subject == "flutter_widget"

    # iOS devices query
    sq_ios = service.analyze("List of supported iOS devices")
    assert sq_ios.intent == QueryIntent.LIST
    assert sq_ios.subject == "ios_device"
    assert sq_ios.target_entity_type == "device"

    # Android versions query
    sq_android = service.analyze("List of Android versions")
    assert sq_android.intent == QueryIntent.LIST
    assert sq_android.subject == "android_version"
    assert sq_android.target_entity_type == "version"

    # Act title query
    sq_act = service.analyze("What is the Act name?")
    assert sq_act.intent == QueryIntent.FACT_LOOKUP
    assert sq_act.subject == "act_title"
    assert sq_act.target_entity_type == "act"


# =========================================================================
# 2. Query-to-Evidence Relevance Gate Tests
# =========================================================================

def test_relevance_gate_rejects_iphones_for_widgets():
    """Page 8 iOS list must be rejected when query asks for widgets."""
    gate = get_relevance_gate()
    sq = get_query_understanding_service().analyze("List of widgets")

    chunk_widget = RerankResultItem(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_title="1-Flutter-Intro.pdf",
        chunk_index=33,
        text="Everything is a Widget. In Flutter, almost everything in the user interface is a widget.",
        page_number=34,
        score=0.9,
        rrf_score=0.9,
        vector_rank=1,
        lexical_rank=1,
        vector_score=0.9,
        lexical_score=10.0,
        reranker_score=1.5,
        reranker_rank=1,
    )

    chunk_iphones = RerankResultItem(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_title="1-Flutter-Intro.pdf",
        chunk_index=38,
        text="[Visible Text & Labels]: iOS 26 Compatibility, iPhone 16e, iPhone 16, iPhone 16 Pro",
        page_number=8,
        score=0.5,
        rrf_score=0.5,
        vector_rank=2,
        lexical_rank=2,
        vector_score=0.5,
        lexical_score=5.0,
        reranker_score=-3.0,
        reranker_rank=2,
    )

    accepted, audit = gate.evaluate_candidates(sq, [chunk_widget, chunk_iphones])

    assert len(accepted) == 1
    assert accepted[0].page_number == 34
    assert any("IPHONES_NOT_WIDGETS" in log["reason"] for log in audit)


def test_relevance_gate_accepts_iphones_for_ios_devices():
    """Page 8 iOS list must be accepted when query asks for supported iOS devices."""
    gate = get_relevance_gate()
    sq = get_query_understanding_service().analyze("List of supported iOS devices")

    chunk_iphones = RerankResultItem(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_title="1-Flutter-Intro.pdf",
        chunk_index=38,
        text="[Visible Text & Labels]: iOS 26 Compatibility, iPhone 16e, iPhone 16, iPhone 16 Pro",
        page_number=8,
        score=0.9,
        rrf_score=0.9,
        vector_rank=1,
        lexical_rank=1,
        vector_score=0.9,
        lexical_score=10.0,
        reranker_score=8.0,
        reranker_rank=1,
    )

    chunk_widget = RerankResultItem(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_title="1-Flutter-Intro.pdf",
        chunk_index=33,
        text="Everything is a Widget. In Flutter, almost everything in the user interface is a widget.",
        page_number=34,
        score=0.2,
        rrf_score=0.2,
        vector_rank=2,
        lexical_rank=2,
        vector_score=0.2,
        lexical_score=2.0,
        reranker_score=-9.0,
        reranker_rank=2,
    )

    accepted, audit = gate.evaluate_candidates(sq, [chunk_iphones, chunk_widget])

    assert len(accepted) == 1
    assert accepted[0].page_number == 8


# =========================================================================
# 3. Answer Alignment Checker Tests
# =========================================================================

def test_alignment_checker_rejects_iphones_in_widget_answer():
    """Answer alignment checker flags an answer listing iPhones when question asked for widgets."""
    checker = get_answer_alignment_checker()
    sq = get_query_understanding_service().analyze("List of widgets")

    bad_answer = "Based on [source_1], the following items are listed: - iPhone 16e - iPhone 16 [source_1]."
    aligned, reason = checker.check_alignment(sq, bad_answer)
    assert aligned is False
    assert reason == "MISALIGNED_IPHONES_IN_WIDGET_ANSWER"

    good_answer = (
        "In Flutter, 'Everything is a Widget' [source_1]. The notes mention Material widgets and "
        "Cupertino widgets [source_2], but do not enumerate individual built-in widget class names."
    )
    aligned_good, _ = checker.check_alignment(sq, good_answer)
    assert aligned_good is True


# =========================================================================
# 4. End-to-End Orchestrator Provenance Tests
# =========================================================================

@pytest.mark.asyncio
async def test_conversational_identity_provenance():
    """'What is your name?' must return assistant identity with llm_invoked=False and no document search."""
    qp = MagicMock()
    qp.process.return_value = MagicMock(processed_query="what is your name", token_estimate=4, character_count=18, has_quotes=False, has_technical_tokens=False)

    orchestrator = RAGOrchestrator(
        query_processor=qp,
        hybrid_service=MagicMock(),
        reranking_service=MagicMock(),
        llm_service=MagicMock(),
    )
    resp = await orchestrator.execute_query(db=MagicMock(), kb_id=uuid.uuid4(), raw_query="What is your name?")

    assert resp.answer == ASSISTANT_IDENTITY_ANSWER
    assert resp.citations == []
    assert resp.metadata["generation_mode"] == "conversational_fast_path"
    assert resp.metadata["llm_invoked"] is False
    assert resp.grounding.status == "CONVERSATIONAL"


@pytest.mark.asyncio
async def test_out_of_scope_query_provenance():
    """'Who is Narendra Modi?' must return honest refusal with llm_invoked=False."""
    qp = MagicMock()
    qp.process.return_value = MagicMock(processed_query="who is narendra modi", token_estimate=4, character_count=21, has_quotes=False, has_technical_tokens=False)

    orchestrator = RAGOrchestrator(
        query_processor=qp,
        hybrid_service=MagicMock(),
        reranking_service=MagicMock(),
        llm_service=MagicMock(),
    )
    resp = await orchestrator.execute_query(db=MagicMock(), kb_id=uuid.uuid4(), raw_query="Who is Narendra Modi?")

    assert resp.answer == INSUFFICIENT_COURSE_EVIDENCE_ANSWER
    assert resp.citations == []
    assert resp.metadata["generation_mode"] == "out_of_scope_refusal"
    assert resp.metadata["llm_invoked"] is False
    assert resp.grounding.status == "REFUSAL"


@pytest.mark.asyncio
async def test_widget_query_relevance_gate_and_provenance():
    """
    For 'List of widgets', ensure:
    - iPhone chunks are rejected by relevance gate.
    - Accepted candidate count is passed to assembled context.
    - Provenance metadata is fully recorded.
    """
    qp = MagicMock()
    qp.process.return_value = MagicMock(processed_query="list of widgets", token_estimate=3, character_count=15, has_quotes=False, has_technical_tokens=False)

    hybrid = MagicMock()
    hybrid.retrieve = AsyncMock()
    hybrid.retrieve.return_value = HybridRetrievalResponse(
        query="list of widgets",
        knowledge_base_id=uuid.uuid4(),
        top_k=20,
        rrf_k=60,
        vector_weight=0.5,
        lexical_weight=0.5,
        total_results=2,
        results=[],
        latency_breakdown={},
        fusion_strategy="rrf",
    )

    rerank = MagicMock()
    rerank.rerank_candidates = AsyncMock()

    chunk_widget = RerankResultItem(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_title="1-Flutter-Intro.pdf",
        chunk_index=33,
        text="Everything is a Widget. In Flutter, almost everything in the user interface is a widget.",
        page_number=34,
        score=0.9,
        rrf_score=0.9,
        vector_rank=1,
        lexical_rank=1,
        vector_score=0.9,
        lexical_score=10.0,
        reranker_score=1.5,
        reranker_rank=1,
    )
    chunk_iphones = RerankResultItem(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_title="1-Flutter-Intro.pdf",
        chunk_index=38,
        text="[Visible Text & Labels]: iOS 26 Compatibility, iPhone 16e, iPhone 16, iPhone 16 Pro",
        page_number=8,
        score=0.5,
        rrf_score=0.5,
        vector_rank=2,
        lexical_rank=2,
        vector_score=0.5,
        lexical_score=5.0,
        reranker_score=-3.0,
        reranker_rank=2,
    )
    rerank.rerank_candidates.return_value = [chunk_widget, chunk_iphones]

    llm = MagicMock()
    llm.generate_grounded_answer = AsyncMock()
    llm.generate_grounded_answer.return_value = LLMGenerationResponse(
        answer="Flutter defines 'Everything is a Widget' [source_1]. The notes do not enumerate built-in widget class names.",
        query="list of widgets",
        provider="ollama",
        model="qwen3:4b",
        is_empty_context=False,
        latency_ms=150.0,
        sources_referenced=["source_1"],
        prompt_tokens=450,
        output_tokens=35,
        metadata={"generation_mode": "primary_llm", "llm_invoked": True},
    )

    orchestrator = RAGOrchestrator(
        query_processor=qp,
        hybrid_service=hybrid,
        reranking_service=rerank,
        llm_service=llm,
    )

    resp = await orchestrator.execute_query(db=MagicMock(), kb_id=uuid.uuid4(), raw_query="List of widgets")

    assert "iPhone" not in resp.answer
    assert resp.metadata["generation_mode"] == "primary_llm"
    assert resp.metadata["llm_invoked"] is True
    assert resp.metadata["relevance_summary"]["accepted_count"] == 1
    assert resp.metadata["relevance_summary"]["reranked_count"] == 2

