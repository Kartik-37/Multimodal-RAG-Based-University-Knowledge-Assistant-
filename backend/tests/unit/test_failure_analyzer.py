"""
Unit tests for Failure Mode and Refusal Analyzer.
"""

from backend.app.schemas.evaluation import EvaluationCategory, EvaluationQueryItem, FailureMode
from backend.app.schemas.grounding_validation import GroundingValidationResult
from backend.app.services.evaluation.failure_analyzer import FailureAnalyzer


def _mock_grounding_result(
    factual_claims: int = 1,
    unsupported_claims: int = 0,
    unverifiable_claims: int = 0,
    invalid_citations: int = 0,
    uncited_claims: int = 0,
    has_conflicts: bool = False,
) -> GroundingValidationResult:
    return GroundingValidationResult(
        query="test query",
        total_claims=factual_claims,
        factual_claims=factual_claims,
        conversational_claims=0,
        non_factual_claims=0,
        cited_claims=factual_claims - uncited_claims,
        uncited_claims=uncited_claims,
        supported_claims=max(0, factual_claims - unsupported_claims - unverifiable_claims),
        supported_uncited_claims=0,
        unsupported_claims=unsupported_claims,
        unverifiable_claims=unverifiable_claims,
        citations_found=factual_claims,
        unique_citations_found=1 if factual_claims > 0 else 0,
        valid_citations=factual_claims - invalid_citations,
        invalid_citations=invalid_citations,
        malformed_citations_count=0,
        citation_validity_rate=1.0 if invalid_citations == 0 else 0.0,
        citation_coverage=1.0 if uncited_claims == 0 else 0.0,
        claim_support_rate=1.0 if (unsupported_claims + unverifiable_claims == 0) else 0.0,
        unsupported_claim_rate=0.0 if (unsupported_claims + unverifiable_claims == 0) else 1.0,
        is_empty_context=False,
        has_conflicts=has_conflicts,
        detected_conflicts=[],
        claims=[],
        citations=[],
        validation_method="conservative_deterministic_heuristic_v1",
        latency_ms=1.5,
        metadata={},
    )


def test_unanswerable_query_correct_refusal() -> None:
    """Verify that an unanswerable query with empty context or no factual claims is marked as a correct refusal."""
    analyzer = FailureAnalyzer()
    query = EvaluationQueryItem(
        id="q_unans",
        query="What is the weather on Titan?",
        category=EvaluationCategory.NO_ANSWER,
        is_unanswerable=True,
        expected_relevant_doc_titles=[],
        expected_chunk_ids=[],
        expected_relevant_keywords=[],
    )

    failures, is_correct_refusal, is_false_refusal, is_ungrounded, kw_passed = (
        analyzer.analyze_query(
            query_item=query,
            retrieval_candidate_hit=False,
            reranked_hit=False,
            grounding_result=None,
            answer="I do not have enough information to answer.",
            is_empty_context=True,
        )
    )

    assert is_correct_refusal is True
    assert is_false_refusal is False
    assert is_ungrounded is False
    assert len(failures) == 0


def test_unanswerable_query_hallucination_refusal_failure() -> None:
    """Verify that an unanswerable query where model asserts factual claims is marked as refusal failure."""
    analyzer = FailureAnalyzer()
    query = EvaluationQueryItem(
        id="q_unans",
        query="What is the weather on Titan?",
        category=EvaluationCategory.NO_ANSWER,
        is_unanswerable=True,
        expected_relevant_doc_titles=[],
        expected_chunk_ids=[],
        expected_relevant_keywords=[],
    )

    grounding = _mock_grounding_result(factual_claims=2, unsupported_claims=2)
    failures, is_correct_refusal, is_false_refusal, is_ungrounded, _ = analyzer.analyze_query(
        query_item=query,
        retrieval_candidate_hit=False,
        reranked_hit=False,
        grounding_result=grounding,
        answer="Titan has liquid methane rain and cold nitrogen atmosphere.",
        is_empty_context=False,
    )

    assert is_correct_refusal is False
    assert is_ungrounded is True
    assert FailureMode.REFUSAL_FAILURE in failures


def test_answerable_query_retrieval_miss() -> None:
    """Verify that an answerable query missing from broad retrieval candidates is marked RETRIEVAL_MISS."""
    analyzer = FailureAnalyzer()
    query = EvaluationQueryItem(
        id="q_fact",
        query="What is FIFO?",
        category=EvaluationCategory.DIRECT_FACTUAL,
        is_unanswerable=False,
        expected_relevant_doc_titles=["OS.md"],
        expected_chunk_ids=[],
        expected_relevant_keywords=["First In First Out"],
    )

    failures, is_correct, is_false, is_ungrounded, _ = analyzer.analyze_query(
        query_item=query,
        retrieval_candidate_hit=False,
        reranked_hit=False,
        grounding_result=None,
        answer="I don't know.",
        is_empty_context=True,
    )

    assert FailureMode.RETRIEVAL_MISS in failures
    assert is_correct is False


def test_answerable_query_reranking_miss() -> None:
    """Verify that an answerable query found in candidates but dropped by reranker is marked RERANKING_MISS."""
    analyzer = FailureAnalyzer()
    query = EvaluationQueryItem(
        id="q_fact",
        query="What is FIFO?",
        category=EvaluationCategory.DIRECT_FACTUAL,
        is_unanswerable=False,
        expected_relevant_doc_titles=["OS.md"],
        expected_chunk_ids=[],
        expected_relevant_keywords=["First In First Out"],
    )

    failures, _, _, _, _ = analyzer.analyze_query(
        query_item=query,
        retrieval_candidate_hit=True,
        reranked_hit=False,
        grounding_result=None,
        answer="Some answer",
        is_empty_context=False,
    )

    assert FailureMode.RERANKING_MISS in failures
    assert FailureMode.RETRIEVAL_MISS not in failures


def test_answerable_query_false_refusal() -> None:
    """Verify that when evidence was retrieved but context was empty or refused, marked FALSE_REFUSAL."""
    analyzer = FailureAnalyzer()
    query = EvaluationQueryItem(
        id="q_fact",
        query="What is FIFO?",
        category=EvaluationCategory.DIRECT_FACTUAL,
        is_unanswerable=False,
        expected_relevant_doc_titles=["OS.md"],
        expected_chunk_ids=[],
        expected_relevant_keywords=["First In First Out"],
    )

    failures, _, is_false_refusal, _, _ = analyzer.analyze_query(
        query_item=query,
        retrieval_candidate_hit=True,
        reranked_hit=True,
        grounding_result=None,
        answer="I cannot answer this question.",
        is_empty_context=True,
    )

    assert is_false_refusal is True
    assert FailureMode.FALSE_REFUSAL in failures


def test_grounding_failure_modes_classification() -> None:
    """Verify that grounding validation defect states map accurately to failure taxonomy."""
    analyzer = FailureAnalyzer()
    query = EvaluationQueryItem(
        id="q_fact",
        query="Explain paging.",
        category=EvaluationCategory.DIRECT_FACTUAL,
        is_unanswerable=False,
        expected_relevant_doc_titles=["OS.md"],
        expected_chunk_ids=[],
        expected_relevant_keywords=["paging"],
    )

    grounding = _mock_grounding_result(
        factual_claims=3,
        unsupported_claims=1,
        unverifiable_claims=1,
        invalid_citations=1,
        uncited_claims=1,
        has_conflicts=True,
    )

    failures, _, _, _, _ = analyzer.analyze_query(
        query_item=query,
        retrieval_candidate_hit=True,
        reranked_hit=True,
        grounding_result=grounding,
        answer="Paging divides memory into frames [source_99].",
        is_empty_context=False,
    )

    assert FailureMode.UNSUPPORTED_ANSWER in failures
    assert FailureMode.UNVERIFIABLE_ANSWER in failures
    assert FailureMode.INVALID_CITATION in failures
    assert FailureMode.MISSING_CITATION in failures
    assert FailureMode.EVIDENCE_CONFLICT in failures


def test_keyword_containment_sanity_check() -> None:
    """Verify auxiliary keyword containment sanity check works as intended."""
    analyzer = FailureAnalyzer()
    query = EvaluationQueryItem(
        id="q_fact",
        query="Explain paging.",
        category=EvaluationCategory.DIRECT_FACTUAL,
        is_unanswerable=False,
        expected_relevant_doc_titles=["OS.md"],
        expected_chunk_ids=[],
        expected_relevant_keywords=["paging"],
        expected_answer_contains=["frame", "page table"],
    )

    _, _, _, _, kw_passed_true = analyzer.analyze_query(
        query_item=query,
        retrieval_candidate_hit=True,
        reranked_hit=True,
        grounding_result=None,
        answer="A page table maps logical pages to a physical frame.",
        is_empty_context=False,
    )
    assert kw_passed_true is True

    _, _, _, _, kw_passed_false = analyzer.analyze_query(
        query_item=query,
        retrieval_candidate_hit=True,
        reranked_hit=True,
        grounding_result=None,
        answer="Memory is divided into segments.",
        is_empty_context=False,
    )
    assert kw_passed_false is False
