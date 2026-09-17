"""
RAG Evaluation and Benchmarking Pydantic Schemas.

Defines strongly-typed data contracts for:
1. Evaluation query definitions and datasets.
2. Chunk-level retrieval relevance rules.
3. Stage-by-stage retrieval ablation measurements.
4. Generation and grounding evaluation metrics.
5. Refusal vs. retrieval failure classification.
6. Granular per-stage exclusive latency benchmarks.
7. Machine-readable benchmark reports and failure distributions.
"""

import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvaluationCategory(StrEnum):
    """Category classification for evaluation benchmark queries."""

    DIRECT_FACTUAL = "DIRECT_FACTUAL"
    MULTI_DOCUMENT = "MULTI_DOCUMENT"
    NO_ANSWER = "NO_ANSWER"
    AMBIGUOUS = "AMBIGUOUS"
    TECHNICAL_NUMERICAL = "TECHNICAL_NUMERICAL"
    CITATION_GROUNDING = "CITATION_GROUNDING"


class EvaluationQueryItem(BaseModel):
    """
    Individual benchmark query specification with chunk-level relevance expectations.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique query identifier (e.g. 'eval_q01').")
    query: str = Field(..., description="Raw user query string to benchmark.")
    category: EvaluationCategory = Field(..., description="Evaluation query category.")
    expected_relevant_doc_titles: list[str] = Field(
        default_factory=list,
        description="Document titles/filenames expected to contain relevant chunks.",
    )
    expected_chunk_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description="Optional list of explicit chunk UUIDs known to be relevant.",
    )
    expected_relevant_keywords: list[str] = Field(
        default_factory=list,
        description="Key domain terms expected to be present within relevant chunks.",
    )
    expected_answer_contains: list[str] = Field(
        default_factory=list,
        description=(
            "Optional list of expected domain terms for sanity checking answer content. "
            "NOTE: Substring containment is a surface sanity check only, NOT a measure of "
            "factual truth or semantic entailment."
        ),
    )
    is_unanswerable: bool = Field(
        default=False,
        description="True if query cannot be answered from the corpus (testing refusal).",
    )
    description: str = Field(default="", description="Explanatory description of the query's goal.")


class EvaluationDataset(BaseModel):
    """
    Container for a versioned, reproducible benchmark query collection.
    """

    model_config = ConfigDict(from_attributes=True)

    version: str = Field(default="1.0.0", description="Dataset semantic version string.")
    name: str = Field(default="bca_rag_benchmark_v1", description="Dataset identifier.")
    description: str = Field(default="", description="Human-readable overview of benchmark scope.")
    created_at: str = Field(..., description="ISO-8601 creation timestamp.")
    items: list[EvaluationQueryItem] = Field(
        default_factory=list, description="List of benchmark query items."
    )


class StageRetrievalMetrics(BaseModel):
    """
    Retrieval quality metrics for an individual ablation stage.
    """

    model_config = ConfigDict(from_attributes=True)

    stage_name: str = Field(
        ...,
        description="Name of retrieval stage (e.g. 'vector_only', 'lexical_only', 'hybrid_rrf', 'reranked').",
    )
    candidate_k: int = Field(
        ..., ge=0, description="Total candidates retrieved/produced by this stage."
    )
    evaluation_k: int = Field(
        ..., ge=1, description="Cut-off rank K applied for metric calculations."
    )
    hit_rate: float = Field(
        ..., ge=0.0, le=1.0, description="1.0 if >=1 relevant chunk in top-K, else 0.0."
    )
    recall_at_k: float = Field(
        ..., ge=0.0, le=1.0, description="Fraction of expected relevant chunks retrieved in top-K."
    )
    precision_at_k: float = Field(
        ..., ge=0.0, le=1.0, description="Fraction of top-K chunks that are relevant."
    )
    reciprocal_rank: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Reciprocal of the 1-based rank of the first relevant chunk.",
    )
    latency_ms: float = Field(
        ..., ge=0.0, description="Exclusive latency in milliseconds for this stage."
    )


class PipelineLatencyBreakdown(BaseModel):
    """
    Exclusive latency breakdown across pipeline stages without nested double-counting.
    """

    model_config = ConfigDict(from_attributes=True)

    query_processing_ms: float = Field(
        default=0.0, ge=0.0, description="Exclusive query normalization duration."
    )
    embedding_ms: float = Field(
        default=0.0, ge=0.0, description="Exclusive query embedding duration."
    )
    vector_retrieval_ms: float = Field(
        default=0.0, ge=0.0, description="Exclusive pgvector search duration."
    )
    lexical_retrieval_ms: float = Field(
        default=0.0, ge=0.0, description="Exclusive PostgreSQL full-text search duration."
    )
    rrf_fusion_ms: float = Field(
        default=0.0, ge=0.0, description="Exclusive Reciprocal Rank Fusion calculation duration."
    )
    reranking_ms: float = Field(
        default=0.0, ge=0.0, description="Exclusive CrossEncoder inference duration."
    )
    context_assembly_ms: float = Field(
        default=0.0, ge=0.0, description="Exclusive context selection and deduplication duration."
    )
    llm_generation_ms: float = Field(
        default=0.0, ge=0.0, description="Exclusive LLM completion duration."
    )
    grounding_validation_ms: float = Field(
        default=0.0, ge=0.0, description="Exclusive Step 14 citation/grounding evaluation duration."
    )
    total_pipeline_ms: float = Field(
        default=0.0, ge=0.0, description="End-to-end wall-clock duration from query to validation."
    )


class FailureMode(StrEnum):
    """Taxonomy of observed RAG pipeline failure modes."""

    RETRIEVAL_MISS = "RETRIEVAL_MISS"
    RERANKING_MISS = "RERANKING_MISS"
    UNSUPPORTED_ANSWER = "UNSUPPORTED_ANSWER"
    UNVERIFIABLE_ANSWER = "UNVERIFIABLE_ANSWER"
    INVALID_CITATION = "INVALID_CITATION"
    MISSING_CITATION = "MISSING_CITATION"
    REFUSAL_FAILURE = "REFUSAL_FAILURE"
    FALSE_REFUSAL = "FALSE_REFUSAL"
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"


class QueryEvaluationResult(BaseModel):
    """
    Granular evaluation result for a single query across all stages.
    """

    model_config = ConfigDict(from_attributes=True)

    query_id: str = Field(..., description="Benchmark query ID.")
    query: str = Field(..., description="Query text.")
    category: EvaluationCategory = Field(..., description="Query category.")
    is_unanswerable: bool = Field(..., description="True if query is expected unanswerable.")

    # Retrieval ablations
    vector_metrics: StageRetrievalMetrics
    lexical_metrics: StageRetrievalMetrics
    hybrid_metrics: StageRetrievalMetrics
    reranked_metrics: StageRetrievalMetrics

    # Generation & Grounding (from Step 14)
    answer: str = Field(default="", description="Generated answer text.")
    is_empty_context: bool = Field(default=False, description="True if empty context occurred.")
    citation_validity_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Citation validity rate."
    )
    citation_coverage: float = Field(default=0.0, ge=0.0, le=1.0, description="Citation coverage.")
    claim_support_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Claim support rate."
    )
    unsupported_claim_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Unsupported claim rate."
    )

    # Refusal vs Failure separation
    is_correct_refusal: bool = Field(
        default=False,
        description="True if unanswerable query was correctly refused with safe message.",
    )
    is_false_refusal: bool = Field(
        default=False,
        description="True if answerable query with retrieved context was incorrectly refused.",
    )
    is_ungrounded_answer: bool = Field(
        default=False,
        description="True if unanswerable query received a fabricated ungrounded answer.",
    )

    # Optional sanity check
    keyword_containment_passed: bool | None = Field(
        default=None,
        description=(
            "Surface check verifying expected domain terms in answer. "
            "NOT a measure of semantic correctness."
        ),
    )

    # Failure modes & Latencies
    detected_failures: list[FailureMode] = Field(default_factory=list)
    latency_breakdown: PipelineLatencyBreakdown


class MetricSummary(BaseModel):
    """Summary statistics (mean, median, p95, min, max, std dev) for a numeric metric."""

    model_config = ConfigDict(from_attributes=True)

    count: int = Field(..., ge=0)
    mean: float = Field(default=0.0)
    median: float = Field(default=0.0)
    p95: float = Field(default=0.0)
    min: float = Field(default=0.0)
    max: float = Field(default=0.0)
    std_dev: float = Field(default=0.0)


class BenchmarkReport(BaseModel):
    """
    Comprehensive, machine-readable RAG benchmark evaluation report.
    """

    model_config = ConfigDict(from_attributes=True)

    run_id: str = Field(..., description="Unique benchmark execution identifier.")
    timestamp: str = Field(..., description="ISO-8601 UTC timestamp of execution.")
    dataset_version: str = Field(..., description="Evaluated dataset version.")
    total_queries: int = Field(..., ge=0, description="Total queries benchmarked.")

    # Environment & Model Metadata
    environment: dict[str, Any] = Field(
        default_factory=dict,
        description="Safe execution environment metadata (OS, Python version, app parameters).",
    )

    # Stage Ablation Summaries
    ablation_summary: dict[str, dict[str, float]] = Field(
        default_factory=dict,
        description="Comparative retrieval metrics (HitRate, Recall, Precision, MRR) across Vector, Lexical, Hybrid, and Reranked stages.",
    )
    reranker_lift_mrr: float = Field(
        default=0.0, description="Delta in MRR achieved by CrossEncoder over Hybrid RRF."
    )

    # Grounding & Generation Aggregates
    mean_citation_validity_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    mean_citation_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    mean_claim_support_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    mean_unsupported_claim_rate: float = Field(default=0.0, ge=0.0, le=1.0)

    # Refusal Quality
    correct_refusal_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fraction of unanswerable queries correctly refused.",
    )
    false_refusal_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fraction of answerable queries incorrectly refused.",
    )

    # Latency Distributions (Per stage)
    latency_summary: dict[str, MetricSummary] = Field(
        default_factory=dict,
        description="Per-stage latency statistics (exclusive timings).",
    )

    # Failure Taxonomy Distribution
    failure_counts: dict[str, int] = Field(
        default_factory=dict, description="Count of occurrences per FailureMode."
    )

    # Detailed per-query results
    query_results: list[QueryEvaluationResult] = Field(default_factory=list)
