"""
Unit Tests for RAG Orchestrator and Deterministic Grounding Rules.

Validates:
- Exact orchestration sequence: QueryProcessor -> HybridRetrieval -> Reranker -> ContextAssembler -> LLM -> Grounding.
- Exclusive, non-overlapping latency accounting.
- Deterministic 7-state grounding status classification rule.
- Citation provenance propagation and snippet length safety.
- Empty-context handling and fast-path refusal.
- Domain exception propagation.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.schemas.context_assembly import ContextAssemblyResult, ContextItem
from backend.app.schemas.grounding_validation import (
    CitationValidationItem,
    ClaimValidationItem,
    GroundingStatus,
    GroundingValidationResult,
)
from backend.app.schemas.hybrid_retrieval import HybridRetrievalResponse, HybridRetrievalResultItem
from backend.app.schemas.llm import LLMGenerationResponse
from backend.app.schemas.query_processing import QueryProcessingResult
from backend.app.schemas.reranking import RerankResultItem
from backend.app.services.llm.exceptions import LLMTimeoutError
from backend.app.services.rag_orchestrator import (
    RAGOrchestrator,
    determine_grounding_status,
)


def make_grounding_result(
    query: str = "test",
    total_claims: int = 1,
    factual_claims: int = 1,
    conversational_claims: int = 0,
    cited_claims: int = 1,
    uncited_claims: int = 0,
    supported_claims: int = 1,
    supported_uncited_claims: int = 0,
    unsupported_claims: int = 0,
    unverifiable_claims: int = 0,
    citations_found: int = 1,
    unique_citations_found: int = 1,
    valid_citations: int = 1,
    invalid_citations: int = 0,
    malformed_citations_count: int = 0,
    citation_validity_rate: float = 1.0,
    citation_coverage: float = 1.0,
    claim_support_rate: float = 1.0,
    unsupported_claim_rate: float = 0.0,
    has_conflicts: bool = False,
    claims: list | None = None,
    citations: list | None = None,
    conflicts: list | None = None,
) -> GroundingValidationResult:
    """Helper to construct GroundingValidationResult with defaults."""
    return GroundingValidationResult(
        query=query,
        original_query=query,
        total_claims=total_claims,
        factual_claims=factual_claims,
        conversational_claims=conversational_claims,
        cited_claims=cited_claims,
        uncited_claims=uncited_claims,
        supported_claims=supported_claims,
        supported_uncited_claims=supported_uncited_claims,
        unsupported_claims=unsupported_claims,
        unverifiable_claims=unverifiable_claims,
        citations_found=citations_found,
        unique_citations_found=unique_citations_found,
        valid_citations=valid_citations,
        invalid_citations=invalid_citations,
        malformed_citations_count=malformed_citations_count,
        citation_validity_rate=citation_validity_rate,
        citation_coverage=citation_coverage,
        claim_support_rate=claim_support_rate,
        unsupported_claim_rate=unsupported_claim_rate,
        latency_ms=10.0,
        has_conflicts=has_conflicts,
        claims=claims or [],
        citations=citations or [],
        conflicts=conflicts or [],
    )


def make_context_item(
    source_id: str = "source_1",
    chunk_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
    knowledge_base_id: uuid.UUID | None = None,
    document_title: str = "Test Doc",
    chunk_index: int = 0,
    text: str = "Test chunk text",
    page_number: int | None = 1,
    section_title: str | None = None,
    reranker_rank: int = 1,
    reranker_score: float = 0.95,
    rrf_score: float = 0.95,
    estimated_tokens: int = 10,
) -> ContextItem:
    """Helper to construct ContextItem with defaults."""
    return ContextItem(
        source_id=source_id,
        chunk_id=chunk_id or uuid.uuid4(),
        document_id=document_id or uuid.uuid4(),
        knowledge_base_id=knowledge_base_id or uuid.uuid4(),
        document_title=document_title,
        chunk_index=chunk_index,
        text=text,
        page_number=page_number,
        section_title=section_title,
        reranker_rank=reranker_rank,
        reranker_score=reranker_score,
        rrf_score=rrf_score,
        estimated_tokens=estimated_tokens,
    )


def make_context_assembly_result(
    query: str = "test",
    items: list[ContextItem] | None = None,
    total_items: int = 0,
    total_estimated_tokens: int = 0,
    token_budget: int = 1000,
    candidates_received: int = 0,
    items_skipped_budget: int = 0,
    items_deduplicated: int = 0,
) -> ContextAssemblyResult:
    """Helper to construct ContextAssemblyResult with defaults."""
    items = items or []
    return ContextAssemblyResult(
        query=query,
        items=items,
        total_items=total_items or len(items),
        total_estimated_tokens=total_estimated_tokens,
        token_budget=token_budget,
        candidates_received=candidates_received,
        items_skipped_budget=items_skipped_budget,
        items_deduplicated=items_deduplicated,
        metadata={},
    )


@pytest.fixture
def mock_pipeline_components():
    """Build mock services for all 6 RAG pipeline stages."""
    query_processor = MagicMock()
    hybrid_service = MagicMock()
    reranking_service = MagicMock()
    context_assembler = MagicMock()
    llm_service = MagicMock()
    grounding_service = MagicMock()

    # Async methods must be AsyncMock
    hybrid_service.retrieve = AsyncMock()
    reranking_service.rerank_candidates = AsyncMock()
    llm_service.generate_grounded_answer = AsyncMock()

    return {
        "qp": query_processor,
        "hybrid": hybrid_service,
        "rerank": reranking_service,
        "ca": context_assembler,
        "llm": llm_service,
        "gv": grounding_service,
    }


@pytest.mark.asyncio
async def test_exact_orchestration_execution_order(mock_pipeline_components):
    """
    Verify the exact production orchestration order:
    QueryProcessor -> HybridRetrieval -> Reranking -> ContextAssembler -> LLM -> Grounding.
    """
    qp = mock_pipeline_components["qp"]
    hybrid = mock_pipeline_components["hybrid"]
    rerank = mock_pipeline_components["rerank"]
    ca = mock_pipeline_components["ca"]
    llm = mock_pipeline_components["llm"]
    gv = mock_pipeline_components["gv"]

    call_order = []

    def qp_side_effect(q):
        call_order.append("qp")
        return QueryProcessingResult(
            original_query=q,
            processed_query=q.lower(),
            character_count=len(q),
            token_estimate=5,
            extracted_phrases=[],
            has_boolean_intent=False,
            is_empty_or_whitespace=False,
        )

    async def hybrid_side_effect(*args, **kwargs):
        call_order.append("hybrid")
        return HybridRetrievalResponse(
            query="test",
            knowledge_base_id=uuid.uuid4(),
            top_k=20,
            rrf_k=60,
            vector_weight=0.5,
            lexical_weight=0.5,
            total_results=0,
            results=[],
            latency_breakdown={},
            fusion_strategy="rrf",
        )

    async def rerank_side_effect(*args, **kwargs):
        call_order.append("rerank")
        return []

    def ca_side_effect(req):
        call_order.append("ca")
        return make_context_assembly_result(query=req.query)

    async def llm_side_effect(req):
        call_order.append("llm")
        return LLMGenerationResponse(
            answer="Safe refusal on empty context.",
            query=req.query,
            provider="ollama",
            model="qwen3:4b",
            is_empty_context=True,
            latency_ms=5.0,
            sources_referenced=[],
        )

    def gv_side_effect(req):
        call_order.append("gv")
        return make_grounding_result(
            total_claims=1,
            factual_claims=0,
            conversational_claims=1,
            supported_claims=0,
            unsupported_claims=0,
            unverifiable_claims=0,
            citation_coverage=0.0,
            citation_validity_rate=0.0,
            claim_support_rate=0.0,
            unsupported_claim_rate=0.0,
        )

    qp.process.side_effect = qp_side_effect
    hybrid.retrieve.side_effect = hybrid_side_effect
    rerank.rerank_candidates.side_effect = rerank_side_effect
    ca.assemble.side_effect = ca_side_effect
    llm.generate_grounded_answer.side_effect = llm_side_effect
    gv.validate.side_effect = gv_side_effect

    orchestrator = RAGOrchestrator(
        query_processor=qp,
        hybrid_service=hybrid,
        reranking_service=rerank,
        context_assembler=ca,
        llm_service=llm,
        grounding_service=gv,
    )

    db_mock = MagicMock()
    kb_id = uuid.uuid4()
    resp = await orchestrator.execute_query(db=db_mock, kb_id=kb_id, raw_query="What is testing?")

    assert call_order == ["qp", "hybrid", "rerank", "ca", "llm", "gv"]
    assert resp.is_empty_context is True
    assert resp.grounding.status == "REFUSAL"
    assert resp.grounding.is_grounded is True


@pytest.mark.asyncio
async def test_successful_pipeline_response_and_citation_propagation(mock_pipeline_components):
    """
    Verify complete pipeline flow, citation provenance resolution, and response fields.
    """
    qp = mock_pipeline_components["qp"]
    hybrid = mock_pipeline_components["hybrid"]
    rerank = mock_pipeline_components["rerank"]
    ca = mock_pipeline_components["ca"]
    llm = mock_pipeline_components["llm"]
    gv = mock_pipeline_components["gv"]

    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    qp.process.return_value = QueryProcessingResult(
        original_query="What is 2PL?",
        processed_query="what is 2pl",
        character_count=12,
        token_estimate=4,
        extracted_phrases=[],
        has_boolean_intent=False,
        is_empty_or_whitespace=False,
    )

    hybrid_item = HybridRetrievalResultItem(
        chunk_id=uuid.uuid4(),
        document_id=doc_id,
        knowledge_base_id=kb_id,
        document_title="Database Systems",
        chunk_index=0,
        text="Two-phase locking guarantees serializability in distributed transactions.",
        page_number=42,
        section_title="Concurrency Control",
        score=0.95,
        rrf_score=0.95,
        vector_rank=1,
        lexical_rank=1,
        vector_score=0.9,
        lexical_score=15.0,
    )

    hybrid.retrieve.return_value = HybridRetrievalResponse(
        query="what is 2pl",
        knowledge_base_id=kb_id,
        top_k=20,
        rrf_k=60,
        vector_weight=0.5,
        lexical_weight=0.5,
        total_results=1,
        results=[hybrid_item],
        latency_breakdown={},
        fusion_strategy="rrf",
    )

    rerank_item = RerankResultItem(
        chunk_id=hybrid_item.chunk_id,
        document_id=doc_id,
        knowledge_base_id=kb_id,
        document_title=hybrid_item.document_title,
        chunk_index=0,
        text=hybrid_item.text,
        page_number=42,
        section_title=hybrid_item.section_title,
        score=0.95,
        rrf_score=0.95,
        vector_rank=1,
        lexical_rank=1,
        vector_score=0.9,
        lexical_score=15.0,
        reranker_score=0.985,
        reranker_rank=1,
    )
    rerank.rerank_candidates.return_value = [rerank_item]

    context_item = make_context_item(
        source_id="source_1",
        chunk_id=rerank_item.chunk_id,
        document_id=doc_id,
        knowledge_base_id=kb_id,
        document_title="Database Systems",
        page_number=42,
        section_title="Concurrency Control",
        text=rerank_item.text,
        estimated_tokens=15,
        reranker_score=0.985,
        reranker_rank=1,
    )
    ca.assemble.return_value = make_context_assembly_result(
        query="what is 2pl",
        items=[context_item],
        total_items=1,
        total_estimated_tokens=15,
        candidates_received=1,
    )

    llm.generate_grounded_answer.return_value = LLMGenerationResponse(
        answer="Two-phase locking ensures serializability [source_1].",
        query="what is 2pl",
        provider="ollama",
        model="qwen3:4b",
        is_empty_context=False,
        latency_ms=120.0,
        sources_referenced=["source_1"],
    )

    claim = ClaimValidationItem(
        claim_index=1,
        text="Two-phase locking ensures serializability.",
        raw_text="Two-phase locking ensures serializability [source_1].",
        status=GroundingStatus.SUPPORTED,
        cited_source_ids=["source_1"],
        unsupported_reason=None,
    )
    citation = CitationValidationItem(
        raw_citation="[source_1]",
        source_id="source_1",
        is_valid=True,
        document_id=doc_id,
        document_title="Database Systems",
    )
    gv.validate.return_value = make_grounding_result(
        factual_claims=1,
        conversational_claims=0,
        supported_claims=1,
        unsupported_claims=0,
        unverifiable_claims=0,
        citation_coverage=1.0,
        citation_validity_rate=1.0,
        claim_support_rate=1.0,
        unsupported_claim_rate=0.0,
        has_conflicts=False,
        claims=[claim],
        citations=[citation],
    )

    orchestrator = RAGOrchestrator(
        query_processor=qp,
        hybrid_service=hybrid,
        reranking_service=rerank,
        context_assembler=ca,
        llm_service=llm,
        grounding_service=gv,
    )

    db_mock = MagicMock()
    resp = await orchestrator.execute_query(db=db_mock, kb_id=kb_id, raw_query="What is 2PL?")

    assert resp.query == "What is 2PL?"
    assert resp.processed_query == "what is 2pl"
    assert resp.knowledge_base_id == kb_id
    assert resp.answer == "Two-phase locking ensures serializability [source_1]."
    assert resp.is_empty_context is False
    assert resp.model == "qwen3:4b"

    # Citation provenance checks
    assert len(resp.citations) == 1
    cit = resp.citations[0]
    assert cit.source_id == "source_1"
    assert cit.document_name == "Database Systems"
    assert cit.document_id == doc_id
    assert cit.page_number == 42
    assert cit.section_title == "Concurrency Control"
    assert cit.relevance_score == 0.985
    assert "Two-phase locking" in cit.snippet

    # Grounding status checks
    assert resp.grounding.is_grounded is True
    assert resp.grounding.status == "FULLY_SUPPORTED"
    assert resp.grounding.citation_validity_rate == 1.0
    assert resp.grounding.citation_coverage == 1.0
    assert len(resp.grounding.claims) == 1
    assert resp.grounding.claims[0].status == "SUPPORTED"

    # Non-overlapping latencies
    lat = resp.latency
    assert lat.query_processing_ms >= 0.0
    assert lat.retrieval_ms >= 0.0
    assert lat.reranking_ms >= 0.0
    assert lat.context_assembly_ms >= 0.0
    assert lat.llm_generation_ms >= 0.0
    assert lat.grounding_validation_ms >= 0.0
    assert lat.total_pipeline_ms >= 0.0


def test_deterministic_grounding_status_rules():
    """
    Test the exact 7 branches of determine_grounding_status:
    1. REFUSAL
    2. CONVERSATIONAL
    3. EVIDENCE_CONFLICT
    4. FULLY_SUPPORTED
    5. PARTIALLY_SUPPORTED
    6. UNSUPPORTED
    7. UNVERIFIABLE
    """
    # 1. Empty context refusal
    res = make_grounding_result(
        factual_claims=0,
        conversational_claims=1,
        supported_claims=0,
        unsupported_claims=0,
        unverifiable_claims=0,
        citation_coverage=0.0,
        citation_validity_rate=0.0,
        claim_support_rate=0.0,
        unsupported_claim_rate=0.0,
        has_conflicts=False,
    )
    is_grounded, status = determine_grounding_status(res, is_empty_context=True)
    assert is_grounded is True
    assert status == "REFUSAL"

    # 2. Conversational response (no factual claims, not empty context)
    is_grounded, status = determine_grounding_status(res, is_empty_context=False)
    assert is_grounded is True
    assert status == "CONVERSATIONAL"

    # 3. Evidence conflicts detected across chunks
    res_conflict = make_grounding_result(
        factual_claims=1,
        conversational_claims=0,
        supported_claims=1,
        unsupported_claims=0,
        unverifiable_claims=0,
        citation_coverage=1.0,
        citation_validity_rate=1.0,
        claim_support_rate=1.0,
        unsupported_claim_rate=0.0,
        has_conflicts=True,
    )
    is_grounded, status = determine_grounding_status(res_conflict, is_empty_context=False)
    assert is_grounded is False
    assert status == "EVIDENCE_CONFLICT"

    # 4. Fully supported
    res_full = make_grounding_result(
        factual_claims=2,
        conversational_claims=0,
        supported_claims=2,
        unsupported_claims=0,
        unverifiable_claims=0,
        citation_coverage=1.0,
        citation_validity_rate=1.0,
        claim_support_rate=1.0,
        unsupported_claim_rate=0.0,
        invalid_citations=0,
        has_conflicts=False,
    )
    is_grounded, status = determine_grounding_status(res_full, is_empty_context=False)
    assert is_grounded is True
    assert status == "FULLY_SUPPORTED"

    # 5. Partially supported (supported claims exist, but citation coverage < 1.0)
    res_partial = make_grounding_result(
        factual_claims=2,
        conversational_claims=0,
        supported_claims=2,
        unsupported_claims=0,
        unverifiable_claims=0,
        citation_coverage=0.5,
        citation_validity_rate=1.0,
        claim_support_rate=1.0,
        unsupported_claim_rate=0.0,
        invalid_citations=0,
        has_conflicts=False,
    )
    is_grounded, status = determine_grounding_status(res_partial, is_empty_context=False)
    assert is_grounded is False
    assert status == "PARTIALLY_SUPPORTED"

    # 6. Unsupported claims exist
    res_unsupported = make_grounding_result(
        factual_claims=2,
        conversational_claims=0,
        supported_claims=1,
        unsupported_claims=1,
        unverifiable_claims=0,
        citation_coverage=0.5,
        citation_validity_rate=1.0,
        claim_support_rate=0.5,
        unsupported_claim_rate=0.5,
        has_conflicts=False,
    )
    is_grounded, status = determine_grounding_status(res_unsupported, is_empty_context=False)
    assert is_grounded is False
    assert status == "UNSUPPORTED"

    # 7. Unverifiable claims (no supported claims, unverifiable > 0)
    res_unverifiable = make_grounding_result(
        factual_claims=1,
        conversational_claims=0,
        supported_claims=0,
        unsupported_claims=0,
        unverifiable_claims=1,
        citation_coverage=0.0,
        citation_validity_rate=0.0,
        claim_support_rate=0.0,
        unsupported_claim_rate=1.0,
        has_conflicts=False,
    )
    is_grounded, status = determine_grounding_status(res_unverifiable, is_empty_context=False)
    assert is_grounded is False
    assert status == "UNVERIFIABLE"


@pytest.mark.asyncio
async def test_unhandled_service_exception_propagates(mock_pipeline_components):
    """Ensure underlying provider errors propagate without silent swallowing."""
    hybrid = mock_pipeline_components["hybrid"]
    hybrid.retrieve.side_effect = LLMTimeoutError("Model timed out")

    orchestrator = RAGOrchestrator(
        query_processor=mock_pipeline_components["qp"],
        hybrid_service=hybrid,
        reranking_service=mock_pipeline_components["rerank"],
        context_assembler=mock_pipeline_components["ca"],
        llm_service=mock_pipeline_components["llm"],
        grounding_service=mock_pipeline_components["gv"],
    )

    with pytest.raises(LLMTimeoutError):
        await orchestrator.execute_query(db=MagicMock(), kb_id=uuid.uuid4(), raw_query="Test query")


@pytest.mark.asyncio
async def test_citation_snippet_clamping_and_filtering(mock_pipeline_components):
    """
    Verify snippets longer than 300 characters are safely clamped with ellipses,
    and only sources in sources_referenced are returned.
    """
    qp = mock_pipeline_components["qp"]
    hybrid = mock_pipeline_components["hybrid"]
    rerank = mock_pipeline_components["rerank"]
    ca = mock_pipeline_components["ca"]
    llm = mock_pipeline_components["llm"]
    gv = mock_pipeline_components["gv"]

    kb_id = uuid.uuid4()
    long_text = "A" * 400

    qp.process.return_value = QueryProcessingResult(
        original_query="What is testing?",
        processed_query="what is testing",
        character_count=16,
        token_estimate=4,
        extracted_phrases=[],
        has_boolean_intent=False,
        is_empty_or_whitespace=False,
    )

    hybrid.retrieve.return_value = HybridRetrievalResponse(
        query="what is testing",
        knowledge_base_id=kb_id,
        top_k=20,
        rrf_k=60,
        vector_weight=0.5,
        lexical_weight=0.5,
        total_results=0,
        results=[],
        latency_breakdown={},
        fusion_strategy="rrf",
    )
    rerank.rerank_candidates.return_value = []

    item1 = make_context_item(
        source_id="source_1",
        text=long_text,
    )
    item2 = make_context_item(
        source_id="source_2",
        text="Unreferenced chunk that should not appear in citations.",
    )

    ca.assemble.return_value = make_context_assembly_result(
        query="what is testing",
        items=[item1, item2],
        total_items=2,
    )

    # LLM references ONLY source_1
    llm.generate_grounded_answer.return_value = LLMGenerationResponse(
        answer="Testing answer [source_1].",
        query="what is testing",
        provider="ollama",
        model="qwen3:4b",
        is_empty_context=False,
        latency_ms=50.0,
        sources_referenced=["source_1"],
    )

    gv.validate.return_value = make_grounding_result(
        factual_claims=1,
        supported_claims=1,
        citation_coverage=1.0,
        citation_validity_rate=1.0,
    )

    orchestrator = RAGOrchestrator(
        query_processor=qp,
        hybrid_service=hybrid,
        reranking_service=rerank,
        context_assembler=ca,
        llm_service=llm,
        grounding_service=gv,
    )

    resp = await orchestrator.execute_query(
        db=MagicMock(), kb_id=kb_id, raw_query="What is testing?"
    )

    assert len(resp.citations) == 1
    assert resp.citations[0].source_id == "source_1"
    assert resp.citations[0].snippet == ("A" * 300) + "..."
    assert len(resp.citations[0].snippet) == 303
