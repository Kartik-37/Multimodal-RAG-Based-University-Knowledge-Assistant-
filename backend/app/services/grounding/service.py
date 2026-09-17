"""
Grounding and Citation Validation Orchestration Service.

Coordinates sentence splitting, citation syntax and provenance verification,
conservative deterministic heuristic claim grounding, and inter-chunk conflict detection
to produce structured, machine-readable validation results for downstream evaluation.

Design & Architectural Invariants:
1. Conservative Deterministic Heuristic Grounding:
   - Measures whether generated claims have evidence characteristics consistent with
     the supplied context.
   - Does NOT prove that a claim is factually true in the real world.
   - Does NOT provide perfect semantic entailment detection.
   - Favors UNVERIFIABLE when confidence is insufficient, avoiding false claims of grounding.
2. Mathematically Bounded Metric Contracts:
   - citation_validity_rate = valid_citations / citations_found if citations_found > 0 else 0.0.
     (Zero-citation answers receive 0.0, never 1.0).
   - citation_coverage = cited_claims / factual_claims if factual_claims > 0 else 0.0.
   - claim_support_rate = supported_claims / factual_claims if factual_claims > 0 else (1.0 if empty context refusal else 0.0).
   - unsupported_claim_rate = (unsupported_claims + unverifiable_claims) / factual_claims if factual_claims > 0 else 0.0.
3. Security & Operational Safety:
   - Operates purely in-memory on validated request and context payloads.
   - Zero database calls, zero external API calls.
   - Bounded against pathological answer sizes.
"""

import threading
import time

from backend.app.schemas.grounding_validation import (
    GroundingStatus,
    GroundingValidationRequest,
    GroundingValidationResult,
)
from backend.app.services.grounding.citation_validator import CitationValidator
from backend.app.services.grounding.claim_verifier import ClaimVerifier
from backend.app.services.grounding.conflict_detector import ConflictDetector
from backend.app.services.grounding.sentence_splitter import SentenceSplitter


class GroundingValidationService:
    """
    Orchestration service for citation validation and evidence grounding evaluation.
    """

    def __init__(
        self,
        sentence_splitter: SentenceSplitter | None = None,
        citation_validator: CitationValidator | None = None,
        claim_verifier: ClaimVerifier | None = None,
        conflict_detector: ConflictDetector | None = None,
    ) -> None:
        self.sentence_splitter = sentence_splitter or SentenceSplitter()
        self.citation_validator = citation_validator or CitationValidator()
        self.claim_verifier = claim_verifier or ClaimVerifier()
        self.conflict_detector = conflict_detector or ConflictDetector()

    def validate(self, request: GroundingValidationRequest) -> GroundingValidationResult:
        """
        Validate citations and evidence grounding of a generated answer.

        Args:
            request: Validated GroundingValidationRequest containing LLM response
                     and Step 12 assembled context package.

        Returns:
            GroundingValidationResult with per-claim classifications, citation provenance,
            conflict alerts, and quantitative rates.
        """
        start_time = time.perf_counter()

        answer = request.response.answer
        context = request.context

        # 1. Validate Citations
        citation_analysis = self.citation_validator.validate(answer=answer, context=context)

        # 2. Extract Claim Segments
        extracted_claims = self.sentence_splitter.split(text=answer)

        # Build lookup map from lowercased source_id to ContextItem
        context_map = {item.source_id.lower(): item for item in context.items}

        # 3. Verify Each Claim
        claim_items = []
        for claim in extracted_claims:
            claim_item = self.claim_verifier.verify_claim(
                claim=claim, context=context, context_map=context_map
            )
            claim_items.append(claim_item)

        # 4. Detect Evidence Conflicts
        detected_conflicts = self.conflict_detector.detect_conflicts(context=context)

        # 5. Aggregate Counts
        total_claims = len(claim_items)
        factual_claims = sum(1 for c in claim_items if not c.is_conversational)
        conversational_claims = sum(1 for c in claim_items if c.is_conversational)
        cited_claims = sum(
            1 for c in claim_items if not c.is_conversational and len(c.cited_source_ids) > 0
        )
        uncited_claims = sum(
            1 for c in claim_items if not c.is_conversational and len(c.cited_source_ids) == 0
        )
        supported_claims = sum(1 for c in claim_items if c.status == GroundingStatus.SUPPORTED)
        supported_uncited_claims = sum(
            1 for c in claim_items if c.status == GroundingStatus.SUPPORTED_UNCITED
        )
        unsupported_claims = sum(1 for c in claim_items if c.status == GroundingStatus.UNSUPPORTED)
        unverifiable_claims = sum(
            1 for c in claim_items if c.status == GroundingStatus.UNVERIFIABLE
        )

        # 6. Calculate Metric Rates (Strictly bounded [0.0, 1.0])
        # Citation Validity Rate:
        # valid_citations / citations_found when citations_found > 0, otherwise 0.0
        # (An answer with zero citations receives 0.0, never 1.0).
        if citation_analysis.citations_found > 0:
            citation_validity_rate = round(
                citation_analysis.valid_citations / citation_analysis.citations_found, 4
            )
        else:
            citation_validity_rate = 0.0

        # Citation Coverage:
        # cited_claims / factual_claims when factual_claims > 0, otherwise 0.0
        # (0.0 when factual claims exist but none cited; 0.0 if no factual claims).
        if factual_claims > 0:
            citation_coverage = round(cited_claims / factual_claims, 4)
        else:
            citation_coverage = 0.0

        # Claim Support Rate:
        # supported_claims / factual_claims when factual_claims > 0,
        # or 1.0 if empty-context refusal (handled fast-path with 0 factual claims), otherwise 0.0.
        if factual_claims > 0:
            claim_support_rate = round(supported_claims / factual_claims, 4)
        elif request.response.is_empty_context:
            claim_support_rate = 1.0
        else:
            claim_support_rate = 0.0

        # Unsupported Claim Rate:
        # (unsupported_claims + unverifiable_claims) / factual_claims when factual_claims > 0, otherwise 0.0
        if factual_claims > 0:
            unsupported_claim_rate = round(
                (unsupported_claims + unverifiable_claims) / factual_claims, 4
            )
        else:
            unsupported_claim_rate = 0.0

        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        metadata = {
            "min_overlap_threshold": request.min_overlap_threshold,
            "max_claims_bound": request.max_claims,
            "is_empty_context": request.response.is_empty_context,
            "context_items_count": len(context.items),
        }

        return GroundingValidationResult(
            query=request.response.query,
            original_query=request.response.original_query,
            total_claims=total_claims,
            factual_claims=factual_claims,
            conversational_claims=conversational_claims,
            cited_claims=cited_claims,
            uncited_claims=uncited_claims,
            supported_claims=supported_claims,
            supported_uncited_claims=supported_uncited_claims,
            unsupported_claims=unsupported_claims,
            unverifiable_claims=unverifiable_claims,
            citations_found=citation_analysis.citations_found,
            unique_citations_found=citation_analysis.unique_citations_found,
            valid_citations=citation_analysis.valid_citations,
            invalid_citations=citation_analysis.invalid_citations,
            malformed_citations_count=citation_analysis.malformed_citations_count,
            citation_validity_rate=citation_validity_rate,
            citation_coverage=citation_coverage,
            claim_support_rate=claim_support_rate,
            unsupported_claim_rate=unsupported_claim_rate,
            is_empty_context=request.response.is_empty_context,
            has_conflicts=bool(detected_conflicts),
            detected_conflicts=detected_conflicts,
            claims=claim_items,
            citations=citation_analysis.items,
            validation_method="conservative_deterministic_heuristic_v1",
            latency_ms=latency_ms,
            metadata=metadata,
        )


# Global singleton instance
_grounding_validation_service: GroundingValidationService | None = None
_service_init_lock = threading.Lock()


def get_grounding_validation_service() -> GroundingValidationService:
    """
    Return the singleton GroundingValidationService instance.
    """
    global _grounding_validation_service
    if _grounding_validation_service is None:
        with _service_init_lock:
            if _grounding_validation_service is None:
                _grounding_validation_service = GroundingValidationService()
    return _grounding_validation_service
