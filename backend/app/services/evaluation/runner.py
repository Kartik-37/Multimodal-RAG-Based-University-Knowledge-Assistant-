"""
RAG Evaluation Benchmark Runner.

Executes an evaluation dataset across retrieval ablation stages (Vector, Lexical,
Hybrid RRF, Reranked), measures exclusive per-stage latencies, evaluates grounded
generation outputs, and produces comprehensive machine-readable benchmark reports.
"""

import platform
import sys
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.schemas.context_assembly import ContextAssemblyRequest
from backend.app.schemas.evaluation import (
    BenchmarkReport,
    EvaluationDataset,
    EvaluationQueryItem,
    PipelineLatencyBreakdown,
    QueryEvaluationResult,
    StageRetrievalMetrics,
)
from backend.app.schemas.grounding_validation import GroundingValidationRequest
from backend.app.schemas.hybrid_retrieval import HybridRetrievalResponse
from backend.app.schemas.llm import LLMGenerationRequest
from backend.app.schemas.reranking import RerankResponse, RerankResultItem
from backend.app.services.context_assembly import ContextAssembler, get_context_assembler
from backend.app.services.evaluation.failure_analyzer import FailureAnalyzer
from backend.app.services.evaluation.metrics import (
    calculate_statistics,
    hit_rate_at_k,
    is_chunk_relevant,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from backend.app.services.grounding.service import (
    GroundingValidationService,
    get_grounding_validation_service,
)
from backend.app.services.hybrid_retrieval import (
    HybridRetrievalService,
    get_hybrid_retrieval_service,
)
from backend.app.services.lexical_retrieval import (
    LexicalRetrievalService,
    get_lexical_retrieval_service,
)
from backend.app.services.llm.service import (
    LLMGenerationService,
    get_llm_generation_service,
)
from backend.app.services.query_processing import (
    QueryProcessor,
    get_query_processor,
)
from backend.app.services.reranking.service import (
    RerankingService,
    get_reranking_service,
)
from backend.app.services.retrieval import (
    VectorRetrievalService,
    get_retrieval_service,
)


class RAGEvaluationRunner:
    """
    Orchestrates the evaluation benchmark pipeline across retrieval, generation, and validation.
    """

    def __init__(
        self,
        query_processor: QueryProcessor | None = None,
        vector_service: VectorRetrievalService | None = None,
        lexical_service: LexicalRetrievalService | None = None,
        hybrid_service: HybridRetrievalService | None = None,
        reranking_service: RerankingService | None = None,
        context_assembler: ContextAssembler | None = None,
        llm_service: LLMGenerationService | None = None,
        grounding_service: GroundingValidationService | None = None,
        failure_analyzer: FailureAnalyzer | None = None,
    ) -> None:
        self.query_processor = query_processor or get_query_processor()
        self.vector_service = vector_service or get_retrieval_service()
        self.lexical_service = lexical_service or get_lexical_retrieval_service()
        self.hybrid_service = hybrid_service or get_hybrid_retrieval_service()
        self.reranking_service = reranking_service or get_reranking_service()
        self.context_assembler = context_assembler or get_context_assembler()
        self.llm_service = llm_service or get_llm_generation_service()
        self.grounding_service = grounding_service or get_grounding_validation_service()
        self.failure_analyzer = failure_analyzer or FailureAnalyzer()

    async def evaluate_query(
        self,
        query_item: EvaluationQueryItem,
        session: Session | None,
        knowledge_base_id: uuid.UUID,
        k_vector: int = settings.RAG_TOP_K_RETRIEVAL,
        k_lexical: int = settings.LEXICAL_TOP_K,
        k_rerank: int = settings.RAG_TOP_K_RERANK,
    ) -> QueryEvaluationResult:
        """
        Execute a single evaluation query across all pipeline stages with granular measurements.
        """
        t_pipeline_start = time.perf_counter()

        # 1. Step 11: Query Processing
        t0 = time.perf_counter()
        qp_res = self.query_processor.process(query_item.query)
        processed_query = qp_res.processed_query
        query_processing_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        # 2. Step 7: Vector Retrieval Only (Ablation Stage A)
        t0 = time.perf_counter()
        vector_res = await self.vector_service.retrieve(
            db=session,
            kb_id=knowledge_base_id,
            query=processed_query,
            top_k=k_vector,
        )
        vector_retrieval_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        # 3. Step 8: Lexical Retrieval Only (Ablation Stage B)
        t0 = time.perf_counter()
        lexical_res = self.lexical_service.retrieve(
            db=session,
            kb_id=knowledge_base_id,
            query=processed_query,
            top_k=k_lexical,
        )
        lexical_retrieval_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        # 4. Step 9: Hybrid Retrieval Fusion via RRF (Ablation Stage C)
        # To avoid double-counting, we time only the fusion calculation
        t0 = time.perf_counter()
        fused_candidates = self.hybrid_service.fuse_ranks(
            vector_results=vector_res.results,
            lexical_results=lexical_res.results,
            top_k=k_vector + k_lexical,
        )
        rrf_fusion_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        hybrid_res = HybridRetrievalResponse(
            query=processed_query,
            knowledge_base_id=knowledge_base_id,
            total_results=len(fused_candidates),
            results=fused_candidates,
            rrf_k=settings.RRF_K,
        )

        # 5. Step 10: CrossEncoder Reranking (Ablation Stage D)
        # Score candidates with CrossEncoder and sort strictly by score DESC
        t0 = time.perf_counter()
        texts = [candidate.text for candidate in hybrid_res.results]
        if texts:
            scores = await self.reranking_service.reranker_provider.compute_scores(
                query=processed_query,
                texts=texts,
            )
            paired = list(zip(scores, hybrid_res.results, strict=True))
            paired.sort(key=lambda item: (-item[0], item[1].chunk_index, str(item[1].chunk_id)))
            selected_paired = paired[:k_rerank]
            reranked_items = [
                RerankResultItem(
                    chunk_id=c.chunk_id,
                    document_id=c.document_id,
                    knowledge_base_id=c.knowledge_base_id,
                    document_title=c.document_title,
                    chunk_index=c.chunk_index,
                    text=c.text,
                    page_number=c.page_number,
                    section_title=c.section_title,
                    chunk_metadata=dict(c.chunk_metadata) if c.chunk_metadata else {},
                    rrf_score=c.rrf_score,
                    vector_rank=c.vector_rank,
                    lexical_rank=c.lexical_rank,
                    vector_contribution=c.vector_contribution,
                    lexical_contribution=c.lexical_contribution,
                    cosine_distance=c.cosine_distance,
                    similarity=c.similarity,
                    lexical_score=c.lexical_score,
                    reranker_score=float(score),
                    reranker_rank=rank_idx,
                )
                for rank_idx, (score, c) in enumerate(selected_paired, start=1)
            ]
        else:
            reranked_items = []

        reranking_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        rerank_res = RerankResponse(
            query=processed_query,
            knowledge_base_id=knowledge_base_id,
            model_name=self.reranking_service.reranker_provider.model_name,
            total_candidates_reranked=len(hybrid_res.results),
            total_results=len(reranked_items),
            results=reranked_items,
            rrf_k=settings.RRF_K,
        )

        # 6. Step 12: Context Assembly
        t0 = time.perf_counter()
        context_req = ContextAssemblyRequest(
            query=processed_query,
            original_query=query_item.query,
            candidates=rerank_res.results,
            token_budget=settings.MAX_CONTEXT_TOKENS,
            max_items=k_rerank,
        )
        assembled_context = self.context_assembler.assemble_context(context_req)
        context_assembly_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        # 7. Step 13: Grounded LLM Generation
        t0 = time.perf_counter()
        llm_req = LLMGenerationRequest(
            query=processed_query,
            original_query=query_item.query,
            context=assembled_context,
        )
        llm_res = await self.llm_service.generate_grounded_answer(llm_req)
        llm_generation_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        # 8. Step 14: Grounding & Citation Validation
        t0 = time.perf_counter()
        val_req = GroundingValidationRequest(
            response=llm_res,
            context=assembled_context,
        )
        grounding_res = self.grounding_service.validate(val_req)
        grounding_validation_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        total_pipeline_ms = round((time.perf_counter() - t_pipeline_start) * 1000.0, 2)

        # -------------------------------------------------------------
        # Chunk-Level Relevance Calculation Across Stages
        # -------------------------------------------------------------
        # Identify relevant chunks across candidate pools
        def _get_relevant_set(items: list[Any]) -> set[uuid.UUID]:
            rel: set[uuid.UUID] = set()
            for it in items:
                cid = getattr(it, "chunk_id", None)
                title = getattr(it, "document_title", "")
                text = getattr(it, "text", "")
                if cid and is_chunk_relevant(cid, title, text, query_item):
                    rel.add(cid)
            return rel

        # Stage A: Vector
        vector_ids = [it.chunk_id for it in vector_res.results]
        vector_rel = _get_relevant_set(vector_res.results)
        vector_metrics = StageRetrievalMetrics(
            stage_name="vector_only",
            candidate_k=len(vector_ids),
            evaluation_k=k_vector,
            hit_rate=hit_rate_at_k(vector_rel, vector_ids, k_vector),
            recall_at_k=recall_at_k(vector_rel, vector_ids, k_vector),
            precision_at_k=precision_at_k(vector_rel, vector_ids, k_vector),
            reciprocal_rank=reciprocal_rank(vector_rel, vector_ids, k_vector),
            latency_ms=vector_retrieval_ms,
        )

        # Stage B: Lexical
        lexical_ids = [it.chunk_id for it in lexical_res.results]
        lexical_rel = _get_relevant_set(lexical_res.results)
        lexical_metrics = StageRetrievalMetrics(
            stage_name="lexical_only",
            candidate_k=len(lexical_ids),
            evaluation_k=k_lexical,
            hit_rate=hit_rate_at_k(lexical_rel, lexical_ids, k_lexical),
            recall_at_k=recall_at_k(lexical_rel, lexical_ids, k_lexical),
            precision_at_k=precision_at_k(lexical_rel, lexical_ids, k_lexical),
            reciprocal_rank=reciprocal_rank(lexical_rel, lexical_ids, k_lexical),
            latency_ms=lexical_retrieval_ms,
        )

        # Stage C: Hybrid RRF
        hybrid_ids = [it.chunk_id for it in hybrid_res.results]
        hybrid_rel = _get_relevant_set(hybrid_res.results)
        hybrid_metrics = StageRetrievalMetrics(
            stage_name="hybrid_rrf",
            candidate_k=len(hybrid_ids),
            evaluation_k=k_rerank,
            hit_rate=hit_rate_at_k(hybrid_rel, hybrid_ids, k_rerank),
            recall_at_k=recall_at_k(hybrid_rel, hybrid_ids, k_rerank),
            precision_at_k=precision_at_k(hybrid_rel, hybrid_ids, k_rerank),
            reciprocal_rank=reciprocal_rank(hybrid_rel, hybrid_ids, k_rerank),
            latency_ms=rrf_fusion_ms,
        )

        # Stage D: Hybrid RRF + CrossEncoder Reranked
        rerank_ids = [it.chunk_id for it in rerank_res.results]
        rerank_rel = _get_relevant_set(rerank_res.results)
        reranked_metrics = StageRetrievalMetrics(
            stage_name="reranked",
            candidate_k=len(rerank_ids),
            evaluation_k=k_rerank,
            hit_rate=hit_rate_at_k(rerank_rel, rerank_ids, k_rerank),
            recall_at_k=recall_at_k(rerank_rel, rerank_ids, k_rerank),
            precision_at_k=precision_at_k(rerank_rel, rerank_ids, k_rerank),
            reciprocal_rank=reciprocal_rank(rerank_rel, rerank_ids, k_rerank),
            latency_ms=reranking_ms,
        )

        # -------------------------------------------------------------
        # Failure Analysis and Refusal Categorization
        # -------------------------------------------------------------
        retrieval_candidate_hit = bool(hybrid_rel)
        reranked_hit = bool(rerank_rel)

        (
            detected_failures,
            is_correct_refusal,
            is_false_refusal,
            is_ungrounded_answer,
            keyword_containment_passed,
        ) = self.failure_analyzer.analyze_query(
            query_item=query_item,
            retrieval_candidate_hit=retrieval_candidate_hit,
            reranked_hit=reranked_hit,
            grounding_result=grounding_res,
            answer=llm_res.answer,
            is_empty_context=llm_res.is_empty_context,
        )

        latency_breakdown = PipelineLatencyBreakdown(
            query_processing_ms=query_processing_ms,
            embedding_ms=0.0,  # Embedded within vector service
            vector_retrieval_ms=vector_retrieval_ms,
            lexical_retrieval_ms=lexical_retrieval_ms,
            rrf_fusion_ms=rrf_fusion_ms,
            reranking_ms=reranking_ms,
            context_assembly_ms=context_assembly_ms,
            llm_generation_ms=llm_generation_ms,
            grounding_validation_ms=grounding_validation_ms,
            total_pipeline_ms=total_pipeline_ms,
        )

        return QueryEvaluationResult(
            query_id=query_item.id,
            query=query_item.query,
            category=query_item.category,
            is_unanswerable=query_item.is_unanswerable,
            vector_metrics=vector_metrics,
            lexical_metrics=lexical_metrics,
            hybrid_metrics=hybrid_metrics,
            reranked_metrics=reranked_metrics,
            answer=llm_res.answer,
            is_empty_context=llm_res.is_empty_context,
            citation_validity_rate=grounding_res.citation_validity_rate,
            citation_coverage=grounding_res.citation_coverage,
            claim_support_rate=grounding_res.claim_support_rate,
            unsupported_claim_rate=grounding_res.unsupported_claim_rate,
            is_correct_refusal=is_correct_refusal,
            is_false_refusal=is_false_refusal,
            is_ungrounded_answer=is_ungrounded_answer,
            keyword_containment_passed=keyword_containment_passed,
            detected_failures=detected_failures,
            latency_breakdown=latency_breakdown,
        )

    async def evaluate_dataset(
        self,
        dataset: EvaluationDataset,
        session: Session | None,
        knowledge_base_id: uuid.UUID,
        k_vector: int = settings.RAG_TOP_K_RETRIEVAL,
        k_lexical: int = settings.LEXICAL_TOP_K,
        k_rerank: int = settings.RAG_TOP_K_RERANK,
    ) -> BenchmarkReport:
        """
        Execute benchmark evaluation over the full dataset and compile BenchmarkReport.
        """
        run_id = f"bench_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        timestamp = datetime.now(UTC).isoformat()

        query_results: list[QueryEvaluationResult] = []
        for item in dataset.items:
            res = await self.evaluate_query(
                query_item=item,
                session=session,
                knowledge_base_id=knowledge_base_id,
                k_vector=k_vector,
                k_lexical=k_lexical,
                k_rerank=k_rerank,
            )
            query_results.append(res)

        total_queries = len(query_results)

        # 1. Ablation Aggregates
        def _calc_stage_summary(
            metrics_list: list[StageRetrievalMetrics],
        ) -> dict[str, float]:
            if not metrics_list:
                return {
                    "mean_hit_rate": 0.0,
                    "mean_recall": 0.0,
                    "mean_precision": 0.0,
                    "mean_mrr": 0.0,
                }
            n = len(metrics_list)
            return {
                "mean_hit_rate": round(sum(m.hit_rate for m in metrics_list) / n, 4),
                "mean_recall": round(sum(m.recall_at_k for m in metrics_list) / n, 4),
                "mean_precision": round(sum(m.precision_at_k for m in metrics_list) / n, 4),
                "mean_mrr": round(sum(m.reciprocal_rank for m in metrics_list) / n, 4),
            }

        vector_summary = _calc_stage_summary([q.vector_metrics for q in query_results])
        lexical_summary = _calc_stage_summary([q.lexical_metrics for q in query_results])
        hybrid_summary = _calc_stage_summary([q.hybrid_metrics for q in query_results])
        reranked_summary = _calc_stage_summary([q.reranked_metrics for q in query_results])

        reranker_lift_mrr = round(reranked_summary["mean_mrr"] - hybrid_summary["mean_mrr"], 4)

        ablation_summary = {
            f"vector_only_k{k_vector}": vector_summary,
            f"lexical_only_k{k_lexical}": lexical_summary,
            f"hybrid_rrf_k{k_rerank}": hybrid_summary,
            f"reranked_k{k_rerank}": reranked_summary,
        }

        # 2. Grounding & Generation Aggregates
        mean_citation_validity = (
            round(sum(q.citation_validity_rate for q in query_results) / total_queries, 4)
            if total_queries
            else 0.0
        )
        mean_citation_coverage = (
            round(sum(q.citation_coverage for q in query_results) / total_queries, 4)
            if total_queries
            else 0.0
        )
        mean_claim_support = (
            round(sum(q.claim_support_rate for q in query_results) / total_queries, 4)
            if total_queries
            else 0.0
        )
        mean_unsupported_claim = (
            round(sum(q.unsupported_claim_rate for q in query_results) / total_queries, 4)
            if total_queries
            else 0.0
        )

        # 3. Refusal Rates
        unanswerable_queries = [q for q in query_results if q.is_unanswerable]
        answerable_queries = [q for q in query_results if not q.is_unanswerable]

        correct_refusal_rate = (
            round(
                sum(1 for q in unanswerable_queries if q.is_correct_refusal)
                / len(unanswerable_queries),
                4,
            )
            if unanswerable_queries
            else 0.0
        )
        false_refusal_rate = (
            round(
                sum(1 for q in answerable_queries if q.is_false_refusal) / len(answerable_queries),
                4,
            )
            if answerable_queries
            else 0.0
        )

        # 4. Latency Distributions
        latencies_total = [q.latency_breakdown.total_pipeline_ms for q in query_results]
        latencies_vector = [q.latency_breakdown.vector_retrieval_ms for q in query_results]
        latencies_lexical = [q.latency_breakdown.lexical_retrieval_ms for q in query_results]
        latencies_rerank = [q.latency_breakdown.reranking_ms for q in query_results]
        latencies_llm = [q.latency_breakdown.llm_generation_ms for q in query_results]
        latencies_grounding = [q.latency_breakdown.grounding_validation_ms for q in query_results]

        latency_summary = {
            "total_pipeline_ms": calculate_statistics(latencies_total),
            "vector_retrieval_ms": calculate_statistics(latencies_vector),
            "lexical_retrieval_ms": calculate_statistics(latencies_lexical),
            "reranking_ms": calculate_statistics(latencies_rerank),
            "llm_generation_ms": calculate_statistics(latencies_llm),
            "grounding_validation_ms": calculate_statistics(latencies_grounding),
        }

        # 5. Failure Taxonomy Counts
        failure_counts: dict[str, int] = {}
        for q in query_results:
            for fail in q.detected_failures:
                failure_counts[fail.value] = failure_counts.get(fail.value, 0) + 1

        # 6. Minimal Environment Metadata
        environment_meta = {
            "python_version": sys.version.split()[0],
            "os_platform": platform.platform(),
            "ollama_llm_model": settings.OLLAMA_LLM_MODEL,
            "ollama_embed_model": settings.OLLAMA_EMBED_MODEL,
            "reranker_model": settings.RERANKER_MODEL,
            "embedding_dim": settings.EMBEDDING_DIM,
            "rrf_k": settings.RRF_K,
            "max_context_tokens": settings.MAX_CONTEXT_TOKENS,
        }

        return BenchmarkReport(
            run_id=run_id,
            timestamp=timestamp,
            dataset_version=dataset.version,
            total_queries=total_queries,
            environment=environment_meta,
            ablation_summary=ablation_summary,
            reranker_lift_mrr=reranker_lift_mrr,
            mean_citation_validity_rate=mean_citation_validity,
            mean_citation_coverage=mean_citation_coverage,
            mean_claim_support_rate=mean_claim_support,
            mean_unsupported_claim_rate=mean_unsupported_claim,
            correct_refusal_rate=correct_refusal_rate,
            false_refusal_rate=false_refusal_rate,
            latency_summary=latency_summary,
            failure_counts=failure_counts,
            query_results=query_results,
        )
