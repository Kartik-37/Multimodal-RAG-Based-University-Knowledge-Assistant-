"""
RAG Orchestration Application Service.

Connects the full RAG pipeline across Steps 7–15:
Query Processing (Step 11)
  → Hybrid Retrieval (Step 9, internally orchestrating Vector Step 7 + Lexical Step 8 + RRF)
  → CrossEncoder Reranking (Step 10)
  → Context Assembly (Step 12)
  → Grounded LLM Generation (Step 13)
  → Grounding & Citation Validation (Step 14)
  → Response Packaging with Provenance and Exclusive Latencies.
"""

import logging
import threading
import time
import uuid

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.telemetry import (
    TelemetryManager,
    categorize_exception,
    get_current_user_id,
    get_request_id,
    get_telemetry_manager,
    sanitize_string,
)
from backend.app.schemas.chat import (
    ChatLatencyBreakdownDTO,
    ChatQueryResponse,
    CitationItem,
    ClaimSummaryDTO,
    GroundingSummaryDTO,
)
from backend.app.schemas.context_assembly import ContextAssemblyRequest
from backend.app.schemas.grounding_validation import (
    GroundingValidationRequest,
    GroundingValidationResult,
)
from backend.app.schemas.llm import LLMGenerationRequest
from backend.app.schemas.telemetry import (
    RAGPipelineTelemetry,
    RAGStageTelemetry,
)
from backend.app.services.context_assembly import ContextAssembler, get_context_assembler
from backend.app.services.grounding.service import (
    GroundingValidationService,
    get_grounding_validation_service,
)
from backend.app.services.hybrid_retrieval import (
    HybridRetrievalService,
    get_hybrid_retrieval_service,
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

logger = logging.getLogger(__name__)


def determine_grounding_status(
    grounding_res: GroundingValidationResult,
    is_empty_context: bool,
) -> tuple[bool, str]:
    """
    Deterministic rule evaluating overall grounding status based on Step 14 results.

    The rule distinguishes:
    - FULLY_SUPPORTED: All factual claims supported by cited context, valid citations, 0 conflicts.
    - PARTIALLY_SUPPORTED: Some claims supported, but some claims lack citations, are unverifiable, or have partial evidence.
    - UNSUPPORTED: At least one factual claim is contradicted or unsupported by the context.
    - UNVERIFIABLE: Claims cannot be verified with sufficient confidence under conservative heuristics.
    - REFUSAL: Model produced an empty-context fast-path or safe refusal without ungrounded factual assertions.
    - CONVERSATIONAL: Conversational framing/preamble with zero factual assertions.
    - EVIDENCE_CONFLICT: Potential evidence conflicts detected across retrieved context chunks.

    Returns:
        (is_grounded: bool, status: str)
        NOTE: Evaluated via conservative deterministic heuristics. Does NOT prove real-world factual truth.
    """
    # 1. Empty context refusal or zero-claim refusal response
    if is_empty_context or (
        grounding_res.factual_claims == 0 and grounding_res.conversational_claims > 0
    ):
        if grounding_res.unsupported_claims == 0 and grounding_res.unverifiable_claims == 0:
            return True, "REFUSAL" if is_empty_context else "CONVERSATIONAL"

    # 2. Conflicting evidence detected across retrieved chunks
    if grounding_res.has_conflicts:
        return False, "EVIDENCE_CONFLICT"

    # 3. Answer asserts factual claims
    if grounding_res.factual_claims > 0:
        # If any claim is directly unsupported or contradictory
        if grounding_res.unsupported_claims > 0:
            return False, "UNSUPPORTED"

        # If any claim is unverifiable under conservative heuristics
        if grounding_res.unverifiable_claims > 0:
            if grounding_res.supported_claims > 0:
                return False, "PARTIALLY_SUPPORTED"
            return False, "UNVERIFIABLE"

        # All factual claims are corroborated by context
        if grounding_res.supported_claims > 0:
            # Check citation coverage and validity
            if (
                grounding_res.citation_coverage == 1.0
                and grounding_res.citation_validity_rate == 1.0
                and grounding_res.invalid_citations == 0
            ):
                return True, "FULLY_SUPPORTED"
            else:
                return False, "PARTIALLY_SUPPORTED"

    # 4. Purely conversational / preamble
    if grounding_res.total_claims > 0 and grounding_res.factual_claims == 0:
        return True, "CONVERSATIONAL"

    return False, "UNVERIFIABLE"


class RAGOrchestrator:
    """
    Central orchestration service executing the production RAG pipeline.
    """

    def __init__(
        self,
        query_processor: QueryProcessor | None = None,
        hybrid_service: HybridRetrievalService | None = None,
        reranking_service: RerankingService | None = None,
        context_assembler: ContextAssembler | None = None,
        llm_service: LLMGenerationService | None = None,
        grounding_service: GroundingValidationService | None = None,
        telemetry_manager: TelemetryManager | None = None,
    ) -> None:
        self.query_processor = query_processor or get_query_processor()
        self.hybrid_service = hybrid_service or get_hybrid_retrieval_service()
        self.reranking_service = reranking_service or get_reranking_service()
        self.context_assembler = context_assembler or get_context_assembler()
        self.llm_service = llm_service or get_llm_generation_service()
        self.grounding_service = grounding_service or get_grounding_validation_service()
        self.telemetry_manager = telemetry_manager or get_telemetry_manager()

    async def execute_query(
        self,
        db: Session,
        kb_id: uuid.UUID | list[uuid.UUID],
        raw_query: str,
        k_retrieval: int = settings.RAG_TOP_K_RETRIEVAL,
        k_rerank: int = settings.RAG_TOP_K_RERANK,
        token_budget: int = settings.MAX_CONTEXT_TOKENS,
    ) -> ChatQueryResponse:
        """
        Execute the complete 9-stage RAG pipeline for an authorized knowledge base query or global query.

        Args:
            db: Active SQLAlchemy session.
            kb_id: Authorized knowledge base UUID or list of authorized UUIDs.
            raw_query: Natural-language query string from user.
            k_retrieval: Number of hybrid candidates to retrieve.
            k_rerank: Number of top reranked chunks to select for context.
            token_budget: Maximum tokens permitted in assembled context.

        Returns:
            ChatQueryResponse containing answer, citations, grounding summary, and latencies.
        """
        t_pipeline_start = time.perf_counter()
        stages: dict[str, RAGStageTelemetry] = {}
        current_stage: str = "query_processing"
        stage_t0: float = time.perf_counter()

        try:
            # -------------------------------------------------------------
            # 1. Step 11: Query Processing
            # -------------------------------------------------------------
            current_stage = "query_processing"
            stage_t0 = time.perf_counter()
            qp_res = self.query_processor.process(raw_query)
            processed_query = qp_res.processed_query
            query_processing_ms = round((time.perf_counter() - stage_t0) * 1000.0, 2)
            stages["query_processing"] = RAGStageTelemetry(
                stage_name="query_processing",
                status="SUCCESS",
                duration_ms=query_processing_ms,
                candidate_count=qp_res.token_estimate,
                attributes={
                    "char_count": qp_res.character_count,
                    "token_estimate": qp_res.token_estimate,
                    "has_quotes": qp_res.has_quotes,
                    "has_technical_tokens": qp_res.has_technical_tokens,
                },
            )

            # -------------------------------------------------------------
            # 2. Step 9: Hybrid Retrieval (Orchestrating Vector + Lexical + RRF)
            # -------------------------------------------------------------
            current_stage = "hybrid_retrieval"
            stage_t0 = time.perf_counter()
            hybrid_res = await self.hybrid_service.retrieve(
                db=db,
                kb_id=kb_id,
                query=processed_query,
                top_k=k_retrieval,
            )
            retrieval_ms = round((time.perf_counter() - stage_t0) * 1000.0, 2)
            stages["hybrid_retrieval"] = RAGStageTelemetry(
                stage_name="hybrid_retrieval",
                status="SUCCESS",
                duration_ms=retrieval_ms,
                candidate_count=len(hybrid_res.results),
                attributes={
                    "top_k_requested": k_retrieval,
                    "results_count": len(hybrid_res.results),
                },
            )

            # -------------------------------------------------------------
            # 3. Step 10: CrossEncoder Reranking
            # -------------------------------------------------------------
            current_stage = "reranking"
            stage_t0 = time.perf_counter()
            reranked_items = await self.reranking_service.rerank_candidates(
                query=processed_query,
                candidates=hybrid_res.results,
                top_k=k_rerank,
            )
            reranking_ms = round((time.perf_counter() - stage_t0) * 1000.0, 2)
            stages["reranking"] = RAGStageTelemetry(
                stage_name="reranking",
                status="SUCCESS",
                duration_ms=reranking_ms,
                candidate_count=len(reranked_items),
                attributes={
                    "candidates_in": len(hybrid_res.results),
                    "top_k_requested": k_rerank,
                    "reranked_count": len(reranked_items),
                },
            )

            # -------------------------------------------------------------
            # 4. Step 12: Context Assembly
            # -------------------------------------------------------------
            current_stage = "context_assembly"
            stage_t0 = time.perf_counter()
            context_req = ContextAssemblyRequest(
                query=processed_query,
                original_query=raw_query,
                candidates=reranked_items,
                token_budget=token_budget,
                max_items=k_rerank,
            )
            assembled_context = self.context_assembler.assemble(context_req)
            context_assembly_ms = round((time.perf_counter() - stage_t0) * 1000.0, 2)
            stages["context_assembly"] = RAGStageTelemetry(
                stage_name="context_assembly",
                status="SUCCESS",
                duration_ms=context_assembly_ms,
                candidate_count=assembled_context.total_items,
                attributes={
                    "total_tokens": assembled_context.total_estimated_tokens,
                    "skipped_budget_count": assembled_context.items_skipped_budget,
                    "deduplicated_count": assembled_context.items_deduplicated,
                    "is_empty": (assembled_context.total_items == 0),
                },
            )

            # -------------------------------------------------------------
            # 5. Step 13: Grounded LLM Generation (Deterministic Empty-Context Fast-Path)
            # -------------------------------------------------------------
            current_stage = "llm_generation"
            stage_t0 = time.perf_counter()
            llm_req = LLMGenerationRequest(
                query=processed_query,
                original_query=raw_query,
                context=assembled_context,
            )
            llm_res = await self.llm_service.generate_grounded_answer(llm_req)
            llm_generation_ms = round((time.perf_counter() - stage_t0) * 1000.0, 2)
            stages["llm_generation"] = RAGStageTelemetry(
                stage_name="llm_generation",
                status="SUCCESS",
                duration_ms=llm_generation_ms,
                candidate_count=len(llm_res.sources_referenced),
                attributes={
                    "model": llm_res.model,
                    "provider": llm_res.provider,
                    "prompt_tokens": llm_res.prompt_tokens,
                    "output_tokens": llm_res.output_tokens,
                    "is_empty_context": llm_res.is_empty_context,
                    "sources_referenced_count": len(llm_res.sources_referenced),
                },
            )

            # -------------------------------------------------------------
            # 6. Step 14: Grounding & Citation Validation
            # -------------------------------------------------------------
            current_stage = "grounding_validation"
            stage_t0 = time.perf_counter()
            val_req = GroundingValidationRequest(
                response=llm_res,
                context=assembled_context,
            )
            grounding_res = self.grounding_service.validate(val_req)
            grounding_validation_ms = round((time.perf_counter() - stage_t0) * 1000.0, 2)
            stages["grounding_validation"] = RAGStageTelemetry(
                stage_name="grounding_validation",
                status="SUCCESS",
                duration_ms=grounding_validation_ms,
                candidate_count=grounding_res.factual_claims,
                attributes={
                    "total_claims": grounding_res.total_claims,
                    "factual_claims": grounding_res.factual_claims,
                    "supported_claims": grounding_res.supported_claims,
                    "unsupported_claims": grounding_res.unsupported_claims,
                    "unverifiable_claims": grounding_res.unverifiable_claims,
                    "has_conflicts": grounding_res.has_conflicts,
                    "citation_validity_rate": grounding_res.citation_validity_rate,
                    "citation_coverage": grounding_res.citation_coverage,
                },
            )

            total_pipeline_ms = round((time.perf_counter() - t_pipeline_start) * 1000.0, 2)

            # -------------------------------------------------------------
            # 7. Grounding Status & Claim Summaries
            # -------------------------------------------------------------
            is_grounded, grounding_status_str = determine_grounding_status(
                grounding_res=grounding_res,
                is_empty_context=llm_res.is_empty_context,
            )

            claim_dtos = [
                ClaimSummaryDTO(
                    claim_text=c.text,
                    status=c.status.value,
                    cited_source=c.cited_source_ids[0] if c.cited_source_ids else None,
                    rationale=c.unsupported_reason or "",
                )
                for c in grounding_res.claims
            ]

            grounding_summary = GroundingSummaryDTO(
                is_grounded=is_grounded,
                status=grounding_status_str,
                citation_validity_rate=grounding_res.citation_validity_rate,
                citation_coverage=grounding_res.citation_coverage,
                claim_support_rate=grounding_res.claim_support_rate,
                unsupported_claim_rate=grounding_res.unsupported_claim_rate,
                has_conflicts=grounding_res.has_conflicts,
                claims=claim_dtos,
            )

            latency_breakdown = ChatLatencyBreakdownDTO(
                query_processing_ms=query_processing_ms,
                retrieval_ms=retrieval_ms,
                reranking_ms=reranking_ms,
                context_assembly_ms=context_assembly_ms,
                llm_generation_ms=llm_generation_ms,
                grounding_validation_ms=grounding_validation_ms,
                total_pipeline_ms=total_pipeline_ms,
            )

            # -------------------------------------------------------------
            # 8. Citation Provenance Packaging
            # -------------------------------------------------------------
            context_item_map = {item.source_id: item for item in assembled_context.items}
            citations: list[CitationItem] = []

            # Only include citations that were referenced by the model in its response
            for src_tag in llm_res.sources_referenced:
                item = context_item_map.get(src_tag)
                if item is not None:
                    snippet_text = item.text.strip()
                    if len(snippet_text) > 300:
                        snippet_text = snippet_text[:300] + "..."

                    citations.append(
                        CitationItem(
                            source_id=item.source_id,
                            document_name=item.document_title,
                            document_id=item.document_id,
                            knowledge_base_id=item.knowledge_base_id,
                            chunk_id=str(item.chunk_id),
                            page_number=item.page_number,
                            section_title=item.section_title,
                            relevance_score=item.reranker_score,
                            snippet=snippet_text,
                        )
                    )

            # Scoping resolution for top-level chat container
            if isinstance(kb_id, (list, tuple, set)):
                kb_ids_list = list(kb_id)
                response_kb_id = kb_ids_list[0] if len(kb_ids_list) == 1 else None
            else:
                response_kb_id = kb_id

            # -------------------------------------------------------------
            # 9. Emit Structured Pipeline Telemetry
            # -------------------------------------------------------------
            pipeline_telemetry = RAGPipelineTelemetry(
                request_id=get_request_id(),
                user_id=get_current_user_id(),
                knowledge_base_id=str(response_kb_id) if response_kb_id else "global",
                status="SUCCESS",
                total_duration_ms=total_pipeline_ms,
                stages=stages,
                retrieval_candidate_count=len(hybrid_res.results),
                reranked_candidate_count=len(reranked_items),
                assembled_context_count=assembled_context.total_items,
                is_empty_context=llm_res.is_empty_context,
                is_refusal=grounding_status_str == "REFUSAL",
                grounding_status=grounding_status_str,
                citation_count=len(citations),
                model=llm_res.model,
                attributes={
                    "is_grounded": is_grounded,
                    "token_budget": token_budget,
                },
            )
            self.telemetry_manager.record_pipeline_event(pipeline_telemetry)

            return ChatQueryResponse(
                query=raw_query,
                processed_query=processed_query,
                knowledge_base_id=response_kb_id,
                answer=llm_res.answer,
                is_empty_context=llm_res.is_empty_context,
                citations=citations,
                grounding=grounding_summary,
                latency=latency_breakdown,
                model=llm_res.model,
                metadata={},
            )

        except Exception as exc:
            total_pipeline_ms = round((time.perf_counter() - t_pipeline_start) * 1000.0, 2)
            err_cat = categorize_exception(exc)
            stage_dur_ms = round((time.perf_counter() - stage_t0) * 1000.0, 2)
            stages[current_stage] = RAGStageTelemetry(
                stage_name=current_stage,
                status="FAILURE",
                duration_ms=stage_dur_ms,
                error_category=err_cat,
                attributes={"exception_type": exc.__class__.__name__},
            )
            pipeline_telemetry = RAGPipelineTelemetry(
                request_id=get_request_id(),
                user_id=get_current_user_id(),
                knowledge_base_id=str(kb_id),
                status="FAILURE",
                total_duration_ms=total_pipeline_ms,
                stages=stages,
                error_category=err_cat,
                attributes={
                    "failed_stage": current_stage,
                    "exception_type": exc.__class__.__name__,
                    "error_message": sanitize_string(str(exc)),
                },
            )
            self.telemetry_manager.record_pipeline_event(pipeline_telemetry)
            raise exc


# Global singleton instance and factory
_default_rag_orchestrator: RAGOrchestrator | None = None
_orchestrator_lock = threading.Lock()


def get_rag_orchestrator() -> RAGOrchestrator:
    """
    FastAPI dependency returning the global singleton RAGOrchestrator.
    """
    global _default_rag_orchestrator
    if _default_rag_orchestrator is None:
        with _orchestrator_lock:
            if _default_rag_orchestrator is None:
                _default_rag_orchestrator = RAGOrchestrator()
    return _default_rag_orchestrator
