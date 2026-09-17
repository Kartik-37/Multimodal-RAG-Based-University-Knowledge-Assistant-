"""
RAG Pipeline Failure Mode and Refusal Analyzer.

Evaluates query execution results across retrieval, reranking, generation, and grounding
to categorize observed failures into a machine-readable failure taxonomy while cleanly
separating unanswerable query refusal fidelity from retrieval misses.
"""

from backend.app.schemas.evaluation import EvaluationQueryItem, FailureMode
from backend.app.schemas.grounding_validation import GroundingValidationResult


class FailureAnalyzer:
    """
    Categorizes failure modes and assesses refusal correctness.
    """

    def analyze_query(
        self,
        query_item: EvaluationQueryItem,
        retrieval_candidate_hit: bool,
        reranked_hit: bool,
        grounding_result: GroundingValidationResult | None,
        answer: str,
        is_empty_context: bool,
    ) -> tuple[list[FailureMode], bool, bool, bool, bool | None]:
        """
        Analyze an executed query and classify failure events.

        Returns:
            Tuple of:
            - detected_failures: list[FailureMode]
            - is_correct_refusal: bool
            - is_false_refusal: bool
            - is_ungrounded_answer: bool
            - keyword_containment_passed: bool | None (optional surface sanity check)
        """
        detected_failures: list[FailureMode] = []
        is_correct_refusal = False
        is_false_refusal = False
        is_ungrounded_answer = False

        # 1. Unanswerable Query Evaluation
        if query_item.is_unanswerable:
            # Model is expected to refuse
            has_factual_claims = grounding_result.factual_claims > 0 if grounding_result else False
            # Refusal indicated by empty-context flag or zero factual assertions with conversational response
            refusal_detected = is_empty_context or (not has_factual_claims and len(answer) > 0)

            if refusal_detected:
                is_correct_refusal = True
            else:
                # Fabricated answer without evidence
                is_ungrounded_answer = True
                detected_failures.append(FailureMode.REFUSAL_FAILURE)

        # 2. Answerable Query Evaluation
        else:
            # Check retrieval miss
            if not retrieval_candidate_hit:
                detected_failures.append(FailureMode.RETRIEVAL_MISS)
            elif not reranked_hit:
                # Found in broad candidates, but dropped out during reranking
                detected_failures.append(FailureMode.RERANKING_MISS)

            # Check false refusal (retrieved context was available, but model refused)
            if retrieval_candidate_hit and is_empty_context:
                is_false_refusal = True
                detected_failures.append(FailureMode.FALSE_REFUSAL)

        # 3. Grounding & Generation Failure Modes
        if grounding_result is not None and not is_correct_refusal:
            if grounding_result.unsupported_claims > 0:
                detected_failures.append(FailureMode.UNSUPPORTED_ANSWER)

            if grounding_result.unverifiable_claims > 0:
                detected_failures.append(FailureMode.UNVERIFIABLE_ANSWER)

            if grounding_result.invalid_citations > 0:
                detected_failures.append(FailureMode.INVALID_CITATION)

            if grounding_result.uncited_claims > 0 and grounding_result.factual_claims > 0:
                detected_failures.append(FailureMode.MISSING_CITATION)

            if grounding_result.has_conflicts:
                detected_failures.append(FailureMode.EVIDENCE_CONFLICT)

        # 4. Optional Keyword Containment Sanity Check
        # (Documented explicitly as an auxiliary surface check, NOT semantic accuracy)
        keyword_containment_passed: bool | None = None
        if query_item.expected_answer_contains:
            ans_lower = answer.lower()
            keyword_containment_passed = all(
                term.lower() in ans_lower for term in query_item.expected_answer_contains
            )

        return (
            detected_failures,
            is_correct_refusal,
            is_false_refusal,
            is_ungrounded_answer,
            keyword_containment_passed,
        )
