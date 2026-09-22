"""
Chat and RAG Orchestration Pydantic Schemas.

Defines API data transfer models for natural-language chat queries,
citation provenance, conservative grounding summaries, latency accounting,
and client-safe responses.
"""

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.core.config import settings


class KnowledgeBaseChatRequest(BaseModel):
    """
    Request model for conversational RAG queries targeting a path-specified knowledge base.
    """

    model_config = ConfigDict(populate_by_name=True)

    question: str = Field(
        ...,
        min_length=1,
        max_length=settings.RETRIEVAL_MAX_QUERY_LENGTH,
        alias="query",
        description="Natural language user question.",
    )

    @field_validator("question")
    @classmethod
    def validate_question_not_whitespace(cls, v: str) -> str:
        """Ensure question contains non-whitespace characters."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Question cannot be empty or whitespace only.")
        return stripped


class ChatQueryRequest(KnowledgeBaseChatRequest):
    """
    Request model for conversational RAG queries with explicit or omitted KB ID in payload.
    When knowledge_base_id is omitted, queries across all authorized active course materials.
    """

    knowledge_base_id: uuid.UUID | None = Field(
        default=None,
        description="Target authorized knowledge base UUID, or None for global search.",
    )


class CitationItem(BaseModel):
    """
    Verified citation reference with structural document provenance.
    """

    model_config = ConfigDict(from_attributes=True)

    source_id: str = Field(
        ...,
        description="Source attribution tag (e.g. 'source_1').",
    )
    document_name: str = Field(
        ...,
        description="Human-readable filename of the source document.",
    )
    document_id: uuid.UUID = Field(
        ...,
        description="Unique identifier of the source document.",
    )
    knowledge_base_id: uuid.UUID | None = Field(
        default=None,
        description="Unique identifier of the knowledge base containing the source document.",
    )
    chunk_id: str = Field(
        ...,
        description="String identifier of the specific retrieved chunk.",
    )
    page_number: int | None = Field(
        default=None,
        description="1-based page number if available.",
    )
    section_title: str | None = Field(
        default=None,
        description="Section heading if identified during parsing.",
    )
    relevance_score: float = Field(
        default=0.0,
        description="CrossEncoder reranking score or fusion score.",
    )
    snippet: str = Field(
        ...,
        description="Verbatim text excerpt from the cited chunk.",
    )


class ClaimSummaryDTO(BaseModel):
    """
    Verified claim item with status and rationale.
    """

    claim_text: str = Field(
        ...,
        description="Text of the individual generated claim.",
    )
    status: str = Field(
        ...,
        description="Grounding status: SUPPORTED, SUPPORTED_UNCITED, UNSUPPORTED, UNVERIFIABLE, or CONVERSATIONAL.",
    )
    cited_source: str | None = Field(
        default=None,
        description="Cited source marker if present.",
    )
    rationale: str = Field(
        default="",
        description="Evaluation rationale.",
    )


class GroundingSummaryDTO(BaseModel):
    """
    Conservative grounding evaluation summary.

    NOTE: Evaluated via conservative deterministic heuristics.
    Does NOT prove real-world factual truth.
    """

    is_grounded: bool = Field(
        ...,
        description="True if the response is fully corroborated by evidence or is a safe refusal.",
    )
    status: str = Field(
        ...,
        description="Grounding assessment status: FULLY_SUPPORTED, PARTIALLY_SUPPORTED, UNSUPPORTED, UNVERIFIABLE, REFUSAL, CONVERSATIONAL, or EVIDENCE_CONFLICT.",
    )
    citation_validity_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Ratio of valid citations to total citations found (0.0 if zero citations found).",
    )
    citation_coverage: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Ratio of cited factual claims to total factual claims (0.0 if zero factual claims).",
    )
    claim_support_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Proportion of factual claims corroborated by context.",
    )
    unsupported_claim_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Proportion of factual claims unsupported or unverifiable.",
    )
    has_conflicts: bool = Field(
        default=False,
        description="True if potential conflicting evidence was detected between retrieved chunks.",
    )
    claims: list[ClaimSummaryDTO] = Field(
        default_factory=list,
        description="List of verified claim summaries.",
    )


class ChatLatencyBreakdownDTO(BaseModel):
    """
    Non-overlapping exclusive stage latencies in milliseconds.
    """

    query_processing_ms: float = Field(
        ...,
        ge=0.0,
        description="Latency for deterministic query normalization.",
    )
    retrieval_ms: float = Field(
        ...,
        ge=0.0,
        description="Inclusive latency for HybridRetrievalService (vector + lexical search + RRF).",
    )
    reranking_ms: float = Field(
        ...,
        ge=0.0,
        description="Latency for CrossEncoder semantic reranking.",
    )
    context_assembly_ms: float = Field(
        ...,
        ge=0.0,
        description="Latency for token budgeting and deduplication.",
    )
    llm_generation_ms: float = Field(
        ...,
        ge=0.0,
        description="Latency for grounded LLM answer generation.",
    )
    grounding_validation_ms: float = Field(
        ...,
        ge=0.0,
        description="Latency for citation and grounding verification.",
    )
    total_pipeline_ms: float = Field(
        ...,
        ge=0.0,
        description="Total round-trip pipeline wall-clock latency.",
    )


class ChatQueryResponse(BaseModel):
    """
    Client-safe response payload returned from conversational query.
    """

    model_config = ConfigDict(from_attributes=True)

    query: str = Field(
        ...,
        description="Original user query as submitted.",
    )
    processed_query: str = Field(
        ...,
        description="Normalized query utilized across retrieval pipelines.",
    )
    knowledge_base_id: uuid.UUID | None = Field(
        default=None,
        description="Knowledge base identifier queried, or None if global.",
    )
    answer: str = Field(
        ...,
        description="Grounded generated answer text or safe refusal message.",
    )
    is_empty_context: bool = Field(
        ...,
        description="True if generation occurred on empty/insufficient context.",
    )
    citations: list[CitationItem] = Field(
        default_factory=list,
        description="Verified citation references with provenance metadata.",
    )
    grounding: GroundingSummaryDTO = Field(
        ...,
        description="Safe summary of citation and evidence grounding assessment.",
    )
    latency: ChatLatencyBreakdownDTO = Field(
        ...,
        description="Non-overlapping exclusive latency breakdown for pipeline stages.",
    )
    model: str = Field(
        ...,
        description="Name of the LLM generation model used.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Safe diagnostic metadata (strictly excluding credentials, secrets, or internal paths).",
    )
