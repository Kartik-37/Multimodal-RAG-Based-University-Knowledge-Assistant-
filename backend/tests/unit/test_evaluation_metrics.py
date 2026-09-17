"""
Unit Tests for Retrieval and Statistical Evaluation Metrics.
"""

import uuid

import pytest

from backend.app.schemas.evaluation import EvaluationCategory, EvaluationQueryItem
from backend.app.services.evaluation.metrics import (
    calculate_statistics,
    hit_rate_at_k,
    is_chunk_relevant,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


def test_recall_at_k_normal_case() -> None:
    id1, id2, id3, id4, id5 = [uuid.uuid4() for _ in range(5)]
    relevant = {id1, id2, id3}
    retrieved = [id1, id4, id2, id5]  # Hits: id1, id2 (2 hits out of 3 relevant)

    assert recall_at_k(relevant, retrieved, k=4) == pytest.approx(2 / 3, 0.001)
    assert recall_at_k(relevant, retrieved, k=1) == pytest.approx(1 / 3, 0.001)
    assert recall_at_k(relevant, retrieved, k=2) == pytest.approx(1 / 3, 0.001)


def test_recall_at_k_zero_division_safeguards() -> None:
    id1 = uuid.uuid4()
    # No relevant items defined: should return 1.0 if nothing retrieved, 0.0 if something retrieved
    assert recall_at_k(set(), [], k=5) == 1.0
    assert recall_at_k(set(), [id1], k=5) == 0.0
    # K <= 0
    assert recall_at_k({id1}, [id1], k=0) == 0.0
    assert recall_at_k({id1}, [id1], k=-1) == 0.0


def test_precision_at_k_normal_case() -> None:
    id1, id2, id3, id4, id5 = [uuid.uuid4() for _ in range(5)]
    relevant = {id1, id2}
    retrieved = [id1, id3, id4, id2, id5]  # Top 4: id1, id3, id4, id2 -> 2 relevant out of 4

    assert precision_at_k(relevant, retrieved, k=4) == 0.5
    assert precision_at_k(relevant, retrieved, k=1) == 1.0
    assert precision_at_k(relevant, retrieved, k=0) == 0.0


def test_hit_rate_at_k() -> None:
    id1, id2, id3 = [uuid.uuid4() for _ in range(3)]
    relevant = {id1}
    retrieved = [id2, id3, id1]

    assert hit_rate_at_k(relevant, retrieved, k=2) == 0.0
    assert hit_rate_at_k(relevant, retrieved, k=3) == 1.0
    assert hit_rate_at_k(relevant, retrieved, k=0) == 0.0
    assert hit_rate_at_k(set(), retrieved, k=3) == 0.0


def test_reciprocal_rank() -> None:
    id1, id2, id3, id4 = [uuid.uuid4() for _ in range(4)]
    relevant = {id3}

    # Rank 1
    assert reciprocal_rank(relevant, [id3, id1, id2], k=3) == 1.0
    # Rank 2
    assert reciprocal_rank(relevant, [id1, id3, id2], k=3) == 0.5
    # Rank 3
    assert reciprocal_rank(relevant, [id1, id2, id3], k=3) == pytest.approx(1 / 3, 0.001)
    # Not in top-2
    assert reciprocal_rank(relevant, [id1, id2, id3], k=2) == 0.0
    # No matches
    assert reciprocal_rank(relevant, [id1, id2, id4], k=3) == 0.0
    # Zero cases
    assert reciprocal_rank(set(), [id1], k=5) == 0.0
    assert reciprocal_rank({id1}, [id1], k=0) == 0.0


def test_calculate_statistics() -> None:
    # Empty list
    empty_stats = calculate_statistics([])
    assert empty_stats.count == 0
    assert empty_stats.mean == 0.0
    assert empty_stats.std_dev == 0.0

    # Single element list
    single_stats = calculate_statistics([10.0])
    assert single_stats.count == 1
    assert single_stats.mean == 10.0
    assert single_stats.median == 10.0
    assert single_stats.min == 10.0
    assert single_stats.max == 10.0
    assert single_stats.std_dev == 0.0

    # Multi-element list
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    stats = calculate_statistics(values)
    assert stats.count == 5
    assert stats.mean == 30.0
    assert stats.median == 30.0
    assert stats.min == 10.0
    assert stats.max == 50.0
    assert stats.p95 == 50.0
    assert stats.std_dev > 0.0


def test_is_chunk_relevant_rules() -> None:
    cid = uuid.uuid4()
    query_item = EvaluationQueryItem(
        id="q1",
        query="What is FCFS?",
        category=EvaluationCategory.DIRECT_FACTUAL,
        expected_relevant_doc_titles=["Operating_Systems.txt"],
        expected_relevant_keywords=["FCFS", "Scheduling"],
        is_unanswerable=False,
    )

    # 1. Matching title and keyword
    assert (
        is_chunk_relevant(
            cid,
            "Operating_Systems.txt",
            "FCFS scheduling algorithm executes in arrival order.",
            query_item,
        )
        is True
    )

    # 2. Matching title, missing keyword
    assert (
        is_chunk_relevant(
            cid,
            "Operating_Systems.txt",
            "Memory management schemes like paging are discussed here.",
            query_item,
        )
        is False
    )

    # 3. Mismatched title
    assert (
        is_chunk_relevant(
            cid,
            "Database_Systems.docx",
            "FCFS scheduling is not relevant to databases.",
            query_item,
        )
        is False
    )

    # 4. Explicit chunk UUID takes priority if provided
    query_with_explicit_id = EvaluationQueryItem(
        id="q2",
        query="test",
        category=EvaluationCategory.DIRECT_FACTUAL,
        expected_chunk_ids=[cid],
        is_unanswerable=False,
    )
    assert is_chunk_relevant(cid, "Any_Doc.pdf", "Any text", query_with_explicit_id) is True
    assert (
        is_chunk_relevant(uuid.uuid4(), "Any_Doc.pdf", "Any text", query_with_explicit_id) is False
    )

    # 5. Unanswerable query is never relevant
    unanswerable_query = EvaluationQueryItem(
        id="q3",
        query="Martian physics?",
        category=EvaluationCategory.NO_ANSWER,
        expected_relevant_doc_titles=["Operating_Systems.txt"],
        is_unanswerable=True,
    )
    assert (
        is_chunk_relevant(
            cid, "Operating_Systems.txt", "Some relevant-looking text.", unanswerable_query
        )
        is False
    )
