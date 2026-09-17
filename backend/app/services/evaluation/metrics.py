"""
Deterministic Retrieval and Statistical Metrics Engine.

Computes mathematically bounded retrieval quality metrics (Recall@K, Precision@K,
HitRate@K, MRR), statistical distribution aggregates (mean, median, p95, min, max, std_dev),
and chunk-level relevance determination rules for evaluation benchmarks.

Design & Architectural Invariants:
1. Strict Chunk-Level Relevance Evaluation:
   - Evaluates relevance at the chunk level as retrieved by the system.
   - Supports explicit chunk UUIDs and deterministic title + keyword containment rules.
2. Mathematically Bounded Contracts:
   - All rates strictly bounded to [0.0, 1.0].
   - Explicit zero-division guards for K=0, empty relevance, and empty candidate lists.
3. Pure In-Memory Offline Math:
   - Uses standard library math without heavy external dependencies.
"""

import math
import uuid

from backend.app.schemas.evaluation import EvaluationQueryItem, MetricSummary


def is_chunk_relevant(
    chunk_id: uuid.UUID,
    doc_title: str,
    text: str,
    query_item: EvaluationQueryItem,
) -> bool:
    """
    Deterministically evaluate whether a retrieved chunk is relevant to an evaluation query.

    Relevance Rule:
    1. If the query is marked as unanswerable (is_unanswerable=True), no chunk is relevant.
    2. If expected_chunk_ids is specified, chunk_id must be in expected_chunk_ids.
    3. Otherwise, chunk is relevant if:
       a) chunk's document title matches one of expected_relevant_doc_titles (case-insensitive), AND
       b) chunk text contains at least one of expected_relevant_keywords (case-insensitive).
          (If expected_relevant_keywords is empty, title match alone satisfies condition b).
    """
    if query_item.is_unanswerable:
        return False

    if query_item.expected_chunk_ids:
        return chunk_id in query_item.expected_chunk_ids

    if not query_item.expected_relevant_doc_titles:
        return False

    title_lower = doc_title.lower()
    title_matches = any(
        exp_title.lower() in title_lower or title_lower in exp_title.lower()
        for exp_title in query_item.expected_relevant_doc_titles
    )
    if not title_matches:
        return False

    if query_item.expected_relevant_keywords:
        text_lower = text.lower()
        keyword_matches = any(
            kw.lower() in text_lower for kw in query_item.expected_relevant_keywords
        )
        return keyword_matches

    return True


def recall_at_k(
    relevant_ids: set[uuid.UUID],
    retrieved_ids: list[uuid.UUID],
    k: int,
) -> float:
    """
    Recall@K: Fraction of expected relevant chunks retrieved within top-K.

    Formula: |Retrieved@K ∩ Relevant| / |Relevant|
    Zero-cases:
      If |Relevant| == 0: 1.0 if |Retrieved@K| == 0 else 0.0.
      If K <= 0: 0.0.
    """
    if k <= 0:
        return 0.0

    if not relevant_ids:
        top_k = retrieved_ids[:k]
        return 1.0 if not top_k else 0.0

    top_k_set = set(retrieved_ids[:k])
    hits = len(top_k_set & relevant_ids)
    return round(hits / len(relevant_ids), 4)


def precision_at_k(
    relevant_ids: set[uuid.UUID],
    retrieved_ids: list[uuid.UUID],
    k: int,
) -> float:
    """
    Precision@K: Fraction of retrieved top-K chunks that are relevant.

    Formula: |Retrieved@K ∩ Relevant| / K
    Zero-case: 0.0 if K <= 0.
    """
    if k <= 0:
        return 0.0

    top_k_set = set(retrieved_ids[:k])
    hits = len(top_k_set & relevant_ids)
    return round(hits / k, 4)


def hit_rate_at_k(
    relevant_ids: set[uuid.UUID],
    retrieved_ids: list[uuid.UUID],
    k: int,
) -> float:
    """
    HitRate@K: 1.0 if at least one relevant chunk appears within top-K, else 0.0.
    """
    if k <= 0 or not relevant_ids:
        return 0.0

    top_k_set = set(retrieved_ids[:k])
    return 1.0 if bool(top_k_set & relevant_ids) else 0.0


def reciprocal_rank(
    relevant_ids: set[uuid.UUID],
    retrieved_ids: list[uuid.UUID],
    k: int,
) -> float:
    """
    Reciprocal Rank: 1 / rank of the first relevant chunk in top-K (1-indexed), else 0.0.
    """
    if k <= 0 or not relevant_ids:
        return 0.0

    for rank, item_id in enumerate(retrieved_ids[:k], start=1):
        if item_id in relevant_ids:
            return round(1.0 / rank, 4)

    return 0.0


def calculate_statistics(values: list[float]) -> MetricSummary:
    """
    Compute summary statistics (count, mean, median, p95, min, max, std_dev).

    Handles empty input safely by returning all 0.0 without raising ZeroDivisionError.
    """
    if not values:
        return MetricSummary(
            count=0,
            mean=0.0,
            median=0.0,
            p95=0.0,
            min=0.0,
            max=0.0,
            std_dev=0.0,
        )

    n = len(values)
    sorted_vals = sorted(values)
    mean_val = sum(sorted_vals) / n

    # Median (50th percentile)
    if n % 2 == 1:
        median_val = sorted_vals[n // 2]
    else:
        median_val = (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2.0

    # 95th Percentile (nearest rank method)
    p95_idx = min(n - 1, math.ceil(0.95 * n) - 1)
    p95_val = sorted_vals[max(0, p95_idx)]

    min_val = sorted_vals[0]
    max_val = sorted_vals[-1]

    # Sample standard deviation
    if n >= 2:
        variance = sum((x - mean_val) ** 2 for x in sorted_vals) / (n - 1)
        std_dev_val = math.sqrt(variance)
    else:
        std_dev_val = 0.0

    return MetricSummary(
        count=n,
        mean=round(mean_val, 4),
        median=round(median_val, 4),
        p95=round(p95_val, 4),
        min=round(min_val, 4),
        max=round(max_val, 4),
        std_dev=round(std_dev_val, 4),
    )
