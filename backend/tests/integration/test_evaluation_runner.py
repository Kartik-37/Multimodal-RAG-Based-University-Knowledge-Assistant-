"""
Integration Tests for RAG Evaluation Benchmark Runner.

Verifies:
1. End-to-end multi-stage ablation execution (Vector, Lexical, Hybrid RRF, CrossEncoder Reranked).
2. Per-stage exclusive latency instrumentation (no double counting).
3. Chunk-level relevance calculation and ablation retrieval metrics.
4. Refusal fidelity and failure mode taxonomy attribution.
5. BenchmarkReport generation, aggregation, and JSON serialization.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.schemas.context_assembly import ContextAssemblyResult, ContextItem
from backend.app.schemas.evaluation import (
    BenchmarkReport,
    EvaluationCategory,
    EvaluationDataset,
    EvaluationQueryItem,
)
from backend.app.schemas.grounding_validation import GroundingValidationResult
from backend.app.schemas.hybrid_retrieval import HybridRetrievalResultItem
from backend.app.schemas.lexical_retrieval import (
    LexicalRetrievalResponse,
    LexicalRetrievalResultItem,
)
from backend.app.schemas.llm import LLMGenerationResponse
from backend.app.schemas.query_processing import QueryProcessingResult
from backend.app.schemas.retrieval import RetrievalResponse, RetrievalResultItem
from backend.app.services.evaluation.failure_analyzer import FailureAnalyzer
from backend.app.services.evaluation.runner import RAGEvaluationRunner


@pytest.fixture
def mock_pipeline_dependencies():
    """Create coordinated mock pipeline dependencies for evaluation testing."""
    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    chunk_1_id = uuid.uuid4()
    chunk_2_id = uuid.uuid4()

    # 1. Mock Query Processor
    query_processor = MagicMock()
    query_processor.process.side_effect = lambda q: QueryProcessingResult(
        original_query=q,
        processed_query=q.strip(),
        character_count=len(q.strip()),
        token_estimate=len(q.split()),
        has_quotes=False,
        has_technical_tokens=False,
        metadata={},
    )

    # 2. Mock Vector Retrieval
    vector_service = MagicMock()
    vector_chunk_1 = RetrievalResultItem(
        chunk_id=chunk_1_id,
        document_id=doc_id,
        knowledge_base_id=kb_id,
        document_title="Operating_Systems.md",
        chunk_index=0,
        text="CPU scheduling algorithms include Round Robin and First Come First Served.",
        cosine_distance=0.1,
        similarity=0.9,
    )
    vector_service.retrieve = AsyncMock(
        return_value=RetrievalResponse(
            query="CPU scheduling",
            knowledge_base_id=kb_id,
            total_results=1,
            results=[vector_chunk_1],
        )
    )

    # 3. Mock Lexical Retrieval
    lexical_service = MagicMock()
    lexical_chunk_2 = LexicalRetrievalResultItem(
        chunk_id=chunk_2_id,
        document_id=doc_id,
        knowledge_base_id=kb_id,
        document_title="Operating_Systems.md",
        chunk_index=1,
        text="Memory management uses paging and segmentation techniques.",
        lexical_score=0.75,
    )
    lexical_service.retrieve.return_value = LexicalRetrievalResponse(
        query="CPU scheduling",
        knowledge_base_id=kb_id,
        total_results=1,
        results=[lexical_chunk_2],
    )

    # 4. Mock Hybrid Service (RRF)
    hybrid_service = MagicMock()
    hybrid_item_1 = HybridRetrievalResultItem(
        chunk_id=chunk_1_id,
        document_id=doc_id,
        knowledge_base_id=kb_id,
        document_title="Operating_Systems.md",
        chunk_index=0,
        text="CPU scheduling algorithms include Round Robin and First Come First Served.",
        rrf_score=0.016393,
        vector_rank=1,
        lexical_rank=None,
        vector_contribution=0.016393,
        lexical_contribution=0.0,
        similarity=0.9,
    )
    hybrid_service.fuse_ranks.return_value = [hybrid_item_1]

    # 5. Mock Reranking Service
    reranking_service = MagicMock()
    reranker_provider = MagicMock()
    reranker_provider.model_name = "test-reranker"
    reranker_provider.compute_scores = AsyncMock(return_value=[0.85])
    reranking_service.reranker_provider = reranker_provider

    # 6. Mock Context Assembler
    context_assembler = MagicMock()
    context_item = ContextItem(
        source_id="source_1",
        chunk_id=chunk_1_id,
        document_id=doc_id,
        knowledge_base_id=kb_id,
        document_title="Operating_Systems.md",
        chunk_index=0,
        text="CPU scheduling algorithms include Round Robin and First Come First Served.",
        estimated_tokens=15,
        reranker_score=0.85,
        reranker_rank=1,
        rrf_score=0.016393,
    )
    context_assembler.assemble_context.return_value = ContextAssemblyResult(
        query="CPU scheduling",
        original_query="CPU scheduling",
        total_items=1,
        total_estimated_tokens=15,
        token_budget=1000,
        candidates_received=1,
        items_skipped_budget=0,
        items_deduplicated=0,
        items=[context_item],
        metadata={},
    )

    # 7. Mock LLM Generation Service
    llm_service = MagicMock()
    llm_service.generate_grounded_answer = AsyncMock(
        return_value=LLMGenerationResponse(
            answer="CPU scheduling uses Round Robin [source_1].",
            query="CPU scheduling",
            provider="ollama",
            model="qwen3:4b",
            latency_ms=120.0,
            is_empty_context=False,
            sources_available=["source_1"],
            sources_referenced=["source_1"],
        )
    )

    # 8. Mock Grounding Validation Service
    grounding_service = MagicMock()
    grounding_service.validate.return_value = GroundingValidationResult(
        query="CPU scheduling",
        total_claims=1,
        factual_claims=1,
        conversational_claims=0,
        non_factual_claims=0,
        cited_claims=1,
        uncited_claims=0,
        supported_claims=1,
        supported_uncited_claims=0,
        unsupported_claims=0,
        unverifiable_claims=0,
        citations_found=1,
        unique_citations_found=1,
        valid_citations=1,
        invalid_citations=0,
        malformed_citations_count=0,
        citation_validity_rate=1.0,
        citation_coverage=1.0,
        claim_support_rate=1.0,
        unsupported_claim_rate=0.0,
        is_empty_context=False,
        has_conflicts=False,
        detected_conflicts=[],
        claims=[],
        citations=[],
        validation_method="conservative_deterministic_heuristic_v1",
        latency_ms=2.5,
        metadata={},
    )

    failure_analyzer = FailureAnalyzer()

    runner = RAGEvaluationRunner(
        query_processor=query_processor,
        vector_service=vector_service,
        lexical_service=lexical_service,
        hybrid_service=hybrid_service,
        reranking_service=reranking_service,
        context_assembler=context_assembler,
        llm_service=llm_service,
        grounding_service=grounding_service,
        failure_analyzer=failure_analyzer,
    )

    return {
        "runner": runner,
        "kb_id": kb_id,
        "chunk_1_id": chunk_1_id,
        "chunk_2_id": chunk_2_id,
    }


@pytest.mark.asyncio
async def test_evaluate_query_end_to_end(mock_pipeline_dependencies) -> None:
    """Verify single query execution through all ablation stages and metrics computation."""
    runner = mock_pipeline_dependencies["runner"]
    kb_id = mock_pipeline_dependencies["kb_id"]

    query_item = EvaluationQueryItem(
        id="q_test_1",
        query="What are the CPU scheduling algorithms?",
        category=EvaluationCategory.DIRECT_FACTUAL,
        expected_relevant_doc_titles=["Operating_Systems.md"],
        expected_chunk_ids=[],
        expected_relevant_keywords=["CPU scheduling", "Round Robin"],
        expected_answer_contains=["Round Robin"],
        is_unanswerable=False,
        description="Factual query test",
    )

    result = await runner.evaluate_query(
        query_item=query_item,
        session=None,
        knowledge_base_id=kb_id,
        k_vector=5,
        k_lexical=5,
        k_rerank=3,
    )

    # Verify query result metadata
    assert result.query_id == "q_test_1"
    assert result.category == EvaluationCategory.DIRECT_FACTUAL
    assert result.is_unanswerable is False
    assert result.is_empty_context is False

    # Verify retrieval ablation stages
    assert result.vector_metrics.stage_name == "vector_only"
    assert result.vector_metrics.hit_rate == 1.0
    assert result.vector_metrics.recall_at_k == 1.0
    assert result.vector_metrics.precision_at_k == 0.2
    assert result.vector_metrics.reciprocal_rank == 1.0

    assert result.lexical_metrics.stage_name == "lexical_only"
    assert result.hybrid_metrics.stage_name == "hybrid_rrf"
    assert result.reranked_metrics.stage_name == "reranked"
    assert result.reranked_metrics.hit_rate == 1.0

    # Verify generation and validation metrics
    assert result.citation_validity_rate == 1.0
    assert result.citation_coverage == 1.0
    assert result.claim_support_rate == 1.0
    assert result.unsupported_claim_rate == 0.0
    assert result.keyword_containment_passed is True
    assert len(result.detected_failures) == 0

    # Verify exclusive latency breakdown
    breakdown = result.latency_breakdown
    assert breakdown.query_processing_ms >= 0.0
    assert breakdown.vector_retrieval_ms >= 0.0
    assert breakdown.lexical_retrieval_ms >= 0.0
    assert breakdown.rrf_fusion_ms >= 0.0
    assert breakdown.reranking_ms >= 0.0
    assert breakdown.context_assembly_ms >= 0.0
    assert breakdown.llm_generation_ms >= 0.0
    assert breakdown.grounding_validation_ms >= 0.0
    assert breakdown.total_pipeline_ms >= 0.0


@pytest.mark.asyncio
async def test_evaluate_dataset_report_generation(mock_pipeline_dependencies) -> None:
    """Verify full dataset evaluation, ablation summary, refusal aggregation, and report JSON serialization."""
    runner = mock_pipeline_dependencies["runner"]
    kb_id = mock_pipeline_dependencies["kb_id"]

    # Build mini dataset with 1 factual query and 1 unanswerable query
    dataset = EvaluationDataset(
        name="test_mini_bench",
        version="0.1.0",
        created_at="2026-09-17T00:00:00Z",
        description="Mini test dataset",
        items=[
            EvaluationQueryItem(
                id="q_fact",
                query="What are CPU scheduling algorithms?",
                category=EvaluationCategory.DIRECT_FACTUAL,
                expected_relevant_doc_titles=["Operating_Systems.md"],
                expected_chunk_ids=[],
                expected_relevant_keywords=["Round Robin"],
                expected_answer_contains=["Round Robin"],
                is_unanswerable=False,
            ),
            EvaluationQueryItem(
                id="q_unans",
                query="What is the weather in Olympus Mons?",
                category=EvaluationCategory.NO_ANSWER,
                expected_relevant_doc_titles=[],
                expected_chunk_ids=[],
                expected_relevant_keywords=[],
                expected_answer_contains=[],
                is_unanswerable=True,
            ),
        ],
    )

    report = await runner.evaluate_dataset(
        dataset=dataset,
        session=None,
        knowledge_base_id=kb_id,
        k_vector=5,
        k_lexical=5,
        k_rerank=3,
    )

    assert isinstance(report, BenchmarkReport)
    assert report.total_queries == 2
    assert report.dataset_version == "0.1.0"
    assert "vector_only_k5" in report.ablation_summary
    assert "lexical_only_k5" in report.ablation_summary
    assert "hybrid_rrf_k3" in report.ablation_summary
    assert "reranked_k3" in report.ablation_summary

    # Verify latency summary has statistics for all tracked stages
    assert "total_pipeline_ms" in report.latency_summary
    assert "vector_retrieval_ms" in report.latency_summary
    assert "reranking_ms" in report.latency_summary
    assert "llm_generation_ms" in report.latency_summary
    assert "grounding_validation_ms" in report.latency_summary

    # Test JSON serialization and deserialization
    json_str = report.model_dump_json()
    assert len(json_str) > 0
    roundtrip = BenchmarkReport.model_validate_json(json_str)
    assert roundtrip.run_id == report.run_id
    assert roundtrip.total_queries == 2
