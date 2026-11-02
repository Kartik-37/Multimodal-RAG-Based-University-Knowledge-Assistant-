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
from backend.app.schemas.query_understanding import QueryIntent, StructuredQuery
from backend.app.services.query_understanding import (
    AMBIGUOUS_CLARIFICATION_ANSWER,
    ASSISTANT_GREETING_ANSWER,
    ASSISTANT_HELP_ANSWER,
    ASSISTANT_IDENTITY_ANSWER,
    ASSISTANT_THANKS_ANSWER,
    QueryUnderstandingService,
    get_query_understanding_service,
)
from backend.app.services.relevance_gate import (
    QueryEvidenceRelevanceGate,
    get_relevance_gate,
)
from backend.app.services.answer_alignment import (
    AnswerAlignmentChecker,
    get_answer_alignment_checker,
)
from backend.app.services.llm.service import (
    INSUFFICIENT_COURSE_EVIDENCE_ANSWER,
    SAFE_INSUFFICIENT_EVIDENCE_ANSWER,
    LLMGenerationService,
    get_llm_generation_service,
)
from backend.app.services.query_processing import (
    QueryProcessor,
    get_query_processor,
)
from backend.app.services.document_summary_service import (
    DocumentSummaryService,
    get_document_summary_service,
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
        query_understanding: QueryUnderstandingService | None = None,
        relevance_gate: QueryEvidenceRelevanceGate | None = None,
        answer_alignment_checker: AnswerAlignmentChecker | None = None,
        document_summary_service: DocumentSummaryService | None = None,
    ) -> None:
        self.query_processor = query_processor or get_query_processor()
        self.hybrid_service = hybrid_service or get_hybrid_retrieval_service()
        self.reranking_service = reranking_service or get_reranking_service()
        self.context_assembler = context_assembler or get_context_assembler()
        self.llm_service = llm_service or get_llm_generation_service()
        self.grounding_service = grounding_service or get_grounding_validation_service()
        self.telemetry_manager = telemetry_manager or get_telemetry_manager()
        self.query_understanding = query_understanding or get_query_understanding_service()
        self.relevance_gate = relevance_gate or get_relevance_gate()
        self.answer_alignment_checker = answer_alignment_checker or get_answer_alignment_checker()
        self.document_summary_service = document_summary_service or get_document_summary_service()

    async def execute_query(
        self,
        db: Session,
        kb_id: uuid.UUID | list[uuid.UUID],
        raw_query: str,
        k_retrieval: int = settings.RAG_TOP_K_RETRIEVAL,
        k_rerank: int = settings.RAG_TOP_K_RERANK,
        token_budget: int = settings.MAX_CONTEXT_TOKENS,
        document_id: uuid.UUID | None = None,
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
            document_id: Optional UUID of a specific document to scope retrieval.

        Returns:
            ChatQueryResponse containing answer, citations, grounding summary, and latencies.
        """
        t_pipeline_start = time.perf_counter()
        stages: dict[str, RAGStageTelemetry] = {}
        current_stage: str = "query_processing"
        stage_t0: float = time.perf_counter()

        # Scoping resolution for top-level chat container
        if isinstance(kb_id, (list, tuple, set)):
            kb_ids_list = list(kb_id)
            response_kb_id = kb_ids_list[0] if len(kb_ids_list) == 1 else None
        else:
            response_kb_id = kb_id

        try:
            # -------------------------------------------------------------
            # 1. Step 11: Query Processing & Structured Query Understanding
            # -------------------------------------------------------------
            current_stage = "query_processing"
            stage_t0 = time.perf_counter()
            qp_res = self.query_processor.process(raw_query)
            processed_query = qp_res.processed_query
            structured_query = self.query_understanding.analyze(raw_query)
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
                    "query_intent": structured_query.intent.value,
                    "query_subject": structured_query.subject,
                },
            )

            # -------------------------------------------------------------
            # Pre-RAG Routing: Conversational / Identity / Greeting / Help
            # -------------------------------------------------------------
            if structured_query.is_conversational:
                if structured_query.intent == QueryIntent.IDENTITY:
                    ans_text = ASSISTANT_IDENTITY_ANSWER
                elif structured_query.intent == QueryIntent.GREETING:
                    ans_text = ASSISTANT_GREETING_ANSWER
                elif structured_query.intent == QueryIntent.HELP:
                    ans_text = ASSISTANT_HELP_ANSWER
                else:
                    ans_text = ASSISTANT_THANKS_ANSWER

                total_pipeline_ms = round((time.perf_counter() - t_pipeline_start) * 1000.0, 2)
                grounding_summary = GroundingSummaryDTO(
                    is_grounded=True,
                    status="CONVERSATIONAL",
                    citation_validity_rate=0.0,
                    citation_coverage=0.0,
                    claim_support_rate=0.0,
                    unsupported_claim_rate=0.0,
                    has_conflicts=False,
                    claims=[],
                )
                latency_breakdown = ChatLatencyBreakdownDTO(
                    query_processing_ms=query_processing_ms,
                    retrieval_ms=0.0,
                    reranking_ms=0.0,
                    context_assembly_ms=0.0,
                    llm_generation_ms=0.0,
                    grounding_validation_ms=0.0,
                    total_pipeline_ms=total_pipeline_ms,
                )
                return ChatQueryResponse(
                    query=raw_query,
                    processed_query=processed_query,
                    knowledge_base_id=response_kb_id,
                    answer=ans_text,
                    is_empty_context=False,
                    citations=[],
                    grounding=grounding_summary,
                    latency=latency_breakdown,
                    model="conversational_fast_path",
                    metadata={
                        "generation_mode": "conversational_fast_path",
                        "llm_invoked": False,
                        "provider": "system",
                        "model": "conversational_fast_path",
                        "prompt_tokens": 0,
                        "output_tokens": len(ans_text.split()),
                        "query_intent": structured_query.intent.value,
                        "query_subject": structured_query.subject,
                    },
                )

            # -------------------------------------------------------------
            # Pre-RAG Routing: Ambiguous Queries (Request Clarification)
            # -------------------------------------------------------------
            if structured_query.is_ambiguous:
                ans_text = structured_query.clarification_prompt or AMBIGUOUS_CLARIFICATION_ANSWER
                total_pipeline_ms = round((time.perf_counter() - t_pipeline_start) * 1000.0, 2)
                grounding_summary = GroundingSummaryDTO(
                    is_grounded=True,
                    status="REFUSAL",
                    citation_validity_rate=0.0,
                    citation_coverage=0.0,
                    claim_support_rate=0.0,
                    unsupported_claim_rate=0.0,
                    has_conflicts=False,
                    claims=[],
                )
                latency_breakdown = ChatLatencyBreakdownDTO(
                    query_processing_ms=query_processing_ms,
                    retrieval_ms=0.0,
                    reranking_ms=0.0,
                    context_assembly_ms=0.0,
                    llm_generation_ms=0.0,
                    grounding_validation_ms=0.0,
                    total_pipeline_ms=total_pipeline_ms,
                )
                return ChatQueryResponse(
                    query=raw_query,
                    processed_query=processed_query,
                    knowledge_base_id=response_kb_id,
                    answer=ans_text,
                    is_empty_context=True,
                    citations=[],
                    grounding=grounding_summary,
                    latency=latency_breakdown,
                    model="ambiguous_clarification",
                    metadata={
                        "generation_mode": "ambiguous_clarification",
                        "llm_invoked": False,
                        "provider": "system",
                        "model": "ambiguous_clarification",
                        "prompt_tokens": 0,
                        "output_tokens": len(ans_text.split()),
                        "query_intent": structured_query.intent.value,
                        "query_subject": structured_query.subject,
                    },
                )

            # -------------------------------------------------------------
            # Pre-RAG Routing: Out-of-Scope Queries (Truthful Refusal)
            # -------------------------------------------------------------
            if structured_query.is_out_of_scope:
                ans_text = INSUFFICIENT_COURSE_EVIDENCE_ANSWER
                total_pipeline_ms = round((time.perf_counter() - t_pipeline_start) * 1000.0, 2)
                grounding_summary = GroundingSummaryDTO(
                    is_grounded=True,
                    status="REFUSAL",
                    citation_validity_rate=0.0,
                    citation_coverage=0.0,
                    claim_support_rate=0.0,
                    unsupported_claim_rate=0.0,
                    has_conflicts=False,
                    claims=[],
                )
                latency_breakdown = ChatLatencyBreakdownDTO(
                    query_processing_ms=query_processing_ms,
                    retrieval_ms=0.0,
                    reranking_ms=0.0,
                    context_assembly_ms=0.0,
                    llm_generation_ms=0.0,
                    grounding_validation_ms=0.0,
                    total_pipeline_ms=total_pipeline_ms,
                )
                return ChatQueryResponse(
                    query=raw_query,
                    processed_query=processed_query,
                    knowledge_base_id=response_kb_id,
                    answer=ans_text,
                    is_empty_context=True,
                    citations=[],
                    grounding=grounding_summary,
                    latency=latency_breakdown,
                    model="out_of_scope_refusal",
                    metadata={
                        "generation_mode": "out_of_scope_refusal",
                        "llm_invoked": False,
                        "provider": "system",
                        "model": "out_of_scope_refusal",
                        "prompt_tokens": 0,
                        "output_tokens": len(ans_text.split()),
                        "query_intent": structured_query.intent.value,
                        "query_subject": structured_query.subject,
                    },
                )

            # -------------------------------------------------------------
            # Whole-Document Hierarchical Summary Routing
            # -------------------------------------------------------------
            if structured_query.requires_document_summary:
                target_doc = self.document_summary_service.resolve_target_document(
                    db=db,
                    kb_id=kb_id,
                    structured_query=structured_query,
                    document_id=document_id,
                )
                if target_doc:
                    return await self.document_summary_service.generate_document_summary(
                        db=db,
                        target_doc=target_doc,
                        structured_query=structured_query,
                        raw_query=raw_query,
                        query_processing_ms=query_processing_ms,
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
                document_id=document_id,
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
            # 3b. Query-to-Evidence Relevance Gating
            # -------------------------------------------------------------
            accepted_candidates, audit_log = self.relevance_gate.evaluate_candidates(
                structured_query=structured_query,
                candidates=reranked_items,
            )

            # -------------------------------------------------------------
            # 4. Step 12: Context Assembly
            # -------------------------------------------------------------
            current_stage = "context_assembly"
            stage_t0 = time.perf_counter()
            context_req = ContextAssemblyRequest(
                query=processed_query,
                original_query=raw_query,
                candidates=accepted_candidates,
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
                    "relevance_accepted_count": len(accepted_candidates),
                },
            )

            # -------------------------------------------------------------
            # 5. Step 13: Grounded LLM Generation
            # -------------------------------------------------------------
            current_stage = "llm_generation"
            stage_t0 = time.perf_counter()
            llm_req = LLMGenerationRequest(
                query=processed_query,
                original_query=raw_query,
                context=assembled_context,
            )
            llm_res = await self.llm_service.generate_grounded_answer(llm_req)

            # -------------------------------------------------------------
            # 5b. Answer-to-Question Alignment Validation
            # -------------------------------------------------------------
            is_aligned, align_reason = self.answer_alignment_checker.check_alignment(
                structured_query=structured_query,
                answer=llm_res.answer,
            )
            if not is_aligned:
                logger.warning("Answer alignment failed (%s) for query: %s", align_reason, raw_query)
                if assembled_context.total_items > 0:
                    try:
                        retry_req = LLMGenerationRequest(
                            query=processed_query + f" (Synthesize only facts about {structured_query.subject})",
                            original_query=raw_query,
                            context=assembled_context,
                        )
                        retry_res = await self.llm_service.generate_grounded_answer(retry_req)
                        retry_aligned, _ = self.answer_alignment_checker.check_alignment(
                            structured_query=structured_query,
                            answer=retry_res.answer,
                        )
                        if retry_aligned:
                            llm_res = retry_res
                            if llm_res.metadata:
                                llm_res.metadata["generation_mode"] = "llm_retry"
                        else:
                            llm_res = LLMGenerationResponse(
                                answer=INSUFFICIENT_COURSE_EVIDENCE_ANSWER,
                                query=processed_query,
                                original_query=raw_query,
                                provider=llm_res.provider,
                                model=llm_res.model,
                                sources_available=[it.source_id for it in assembled_context.items],
                                sources_referenced=[],
                                is_empty_context=True,
                                prompt_tokens=0,
                                output_tokens=len(INSUFFICIENT_COURSE_EVIDENCE_ANSWER.split()),
                                latency_ms=0.0,
                                metadata={
                                    "generation_mode": "insufficient_evidence_refusal",
                                    "llm_invoked": True,
                                    "reason": "alignment_failure",
                                },
                            )
                    except Exception:
                        pass

            llm_generation_ms = round((time.perf_counter() - stage_t0) * 1000.0, 2)

            gen_mode = (
                llm_res.metadata.get("generation_mode")
                or llm_res.metadata.get("path")
                or ("primary_llm" if not llm_res.is_empty_context else "insufficient_evidence_refusal")
            )
            llm_invoked = bool(llm_res.metadata.get("llm_invoked", gen_mode in ("primary_llm", "llm_retry")))

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
                    "generation_mode": gen_mode,
                    "llm_invoked": llm_invoked,
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
            context_item_map = {item.source_id.lower(): item for item in assembled_context.items}
            citations: list[CitationItem] = []

            # Only include citations that were referenced by the model in its response
            for src_tag in llm_res.sources_referenced:
                item = context_item_map.get(src_tag.lower())
                if item is not None:
                    snippet_text = item.text.strip()
                    if len(snippet_text) > 300:
                        snippet_text = snippet_text[:300] + "..."

                    modality = item.chunk_metadata.get("source_modality", "text") if item.chunk_metadata else "text"
                    v_type = item.chunk_metadata.get("visual_type") if item.chunk_metadata else None

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
                            source_modality=modality,
                            visual_type=v_type,
                        )
                    )

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
                metadata={
                    "generation_mode": gen_mode,
                    "llm_invoked": llm_invoked,
                    "provider": llm_res.provider,
                    "model": llm_res.model,
                    "prompt_tokens": llm_res.prompt_tokens,
                    "output_tokens": llm_res.output_tokens,
                    "relevance_summary": {
                        "retrieved_count": len(hybrid_res.results),
                        "reranked_count": len(reranked_items),
                        "accepted_count": len(accepted_candidates),
                        "assembled_count": assembled_context.total_items,
                    },
                    "query_intent": structured_query.intent.value,
                    "query_subject": structured_query.subject,
                },
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
