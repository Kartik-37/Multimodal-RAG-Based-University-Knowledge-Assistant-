"""
Grounding and Citation Validation Pydantic Schemas.

Defines data transfer models for evaluating citation accuracy, claim extraction,
and evidence grounding in generated LLM answers against assembled retrieval context.

Design & Architectural Invariants:
1. Conservative Deterministic Heuristic:
   - Evaluates whether generated claims have evidence characteristics consistent
     with the supplied context.
   - Does NOT prove that a claim is factually true in the real world.
   - Does NOT provide perfect semantic entailment detection.
   - Favors UNVERIFIABLE when confidence is insufficient, to avoid false claims of grounding.
2. Independent Citation Verification:
   - Validates citation syntax, source existence, duplicate mentions, and provenance mapping.
   - Answers with 0 citations receive citation_validity_rate = 0.0 (never 1.0).
3. Explicit Quantitative Metric Contracts:
   - All rate metrics strictly bounded to [0.0, 1.0].
   - Explicit zero-division handling for empty answers, no citations, and zero-claim edge cases.
"""

import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.core.config import settings
from backend.app.schemas.context_assembly import ContextAssemblyResult
from backend.app.schemas.llm import LLMGenerationResponse


class GroundingStatus(StrEnum):
    """
    Conservative grounding evaluation status for an individual claim.

    Status semantics:
    - SUPPORTED: Conservative heuristic identifies strong evidence characteristics
      (content word overlap >= threshold, matching numbers and key entities) in the cited chunk.
    - SUPPORTED_UNCITED: Conservative heuristic finds evidence characteristics in an available
      context chunk, but the claim lacks a citation marker in the text.
    - UNSUPPORTED: Claim cites a source (or makes assertions), but the cited source does not
      corroborate the claim, or contains contradictory numbers/entities.
    - UNVERIFIABLE: Claim cannot be verified from the supplied context with sufficient confidence
      under conservative deterministic heuristics.
    - CONVERSATIONAL: Conversational framing, preamble, transition, or refusal statement that does
      not assert a factual proposition.
    """

    SUPPORTED = "SUPPORTED"
    SUPPORTED_UNCITED = "SUPPORTED_UNCITED"
    UNSUPPORTED = "UNSUPPORTED"
    UNVERIFIABLE = "UNVERIFIABLE"
    CONVERSATIONAL = "CONVERSATIONAL"


class CitationValidationItem(BaseModel):
    """
    Validation record for a single citation occurrence extracted from the generated answer.
    """

    model_config = ConfigDict(from_attributes=True)

    raw_citation: str = Field(
        ...,
        description="Exact raw citation marker as found in the text (e.g. '[source_1]').",
    )
    source_id: str = Field(
        ...,
        description="Normalized source identifier (e.g. 'source_1').",
    )
    is_valid: bool = Field(
        ...,
        description="True if source_id exists in the retrieved ContextAssemblyResult.",
    )
    context_item_id: uuid.UUID | None = Field(
        default=None,
        description="Unique chunk_id of the matched ContextItem if valid.",
    )
    document_id: uuid.UUID | None = Field(
        default=None,
        description="Document identifier from the matched ContextItem.",
    )
    document_title: str | None = Field(
        default=None,
        description="Filename/title of the source document.",
    )
    page_number: int | None = Field(
        default=None,
        description="Source page number (1-indexed) if available.",
    )
    section_title: str | None = Field(
        default=None,
        description="Section heading if available.",
    )
    error_reason: str | None = Field(
        default=None,
        description="Reason for invalidity if source_id was not found in context.",
    )


class ClaimValidationItem(BaseModel):
    """
    Validation record for an individual sentence/statement extracted from the generated answer.
    """

    model_config = ConfigDict(from_attributes=True)

    claim_index: int = Field(
        ...,
        ge=1,
        description="1-based sequential index of the claim within the generated answer.",
    )
    text: str = Field(
        ...,
        description="Clean claim statement text with citation tags stripped.",
    )
    raw_text: str = Field(
        ...,
        description="Original sentence as it appeared in the generated answer.",
    )
    is_conversational: bool = Field(
        default=False,
        description="True if classified as conversational preamble, disclaimer, or refusal.",
    )
    cited_source_ids: list[str] = Field(
        default_factory=list,
        description="List of source identifiers cited directly in this claim statement.",
    )
    resolved_context_item_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description="Chunk UUIDs of valid cited context items.",
    )
    status: GroundingStatus = Field(
        ...,
        description="Conservative grounding status.",
    )
    overlap_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Content-word recall score against best matching or cited evidence chunk.",
    )
    supporting_evidence_snippets: list[str] = Field(
        default_factory=list,
        description="Extracted sentence(s) from the evidence chunk exhibiting highest overlap.",
    )
    unsupported_reason: str | None = Field(
        default=None,
        description="Diagnostic explanation when claim is UNSUPPORTED or UNVERIFIABLE.",
    )


class EvidenceConflictItem(BaseModel):
    """
    Record of a possible conflict detected between two evidence chunks.
    """

    model_config = ConfigDict(from_attributes=True)

    source_id_a: str = Field(..., description="First source identifier.")
    source_id_b: str = Field(..., description="Second source identifier.")
    conflicting_topic: str = Field(
        ..., description="Entity or topic where potential conflict was detected."
    )
    snippet_a: str = Field(..., description="Evidence excerpt from source A.")
    snippet_b: str = Field(..., description="Evidence excerpt from source B.")
    conflict_description: str = Field(
        ...,
        description="Conservative description of the observed discrepancy (e.g. conflicting numeric values or opposing attributes).",
    )


class GroundingValidationRequest(BaseModel):
    """
    Request model for validating citations and evidence grounding of an LLM generation.
    """

    model_config = ConfigDict(from_attributes=True)

    response: LLMGenerationResponse = Field(
        ...,
        description="Generated LLM response from Step 13.",
    )
    context: ContextAssemblyResult = Field(
        ...,
        description="Assembled evidence package from Step 12.",
    )
    min_overlap_threshold: float = Field(
        default_factory=lambda: settings.GROUNDING_MIN_OVERLAP_THRESHOLD,
        ge=0.0,
        le=1.0,
        description="Minimum content-word recall required to consider a claim supported by evidence.",
    )
    max_claims: int = Field(
        default_factory=lambda: settings.GROUNDING_MAX_CLAIMS_PER_ANSWER,
        ge=1,
        le=500,
        description="Maximum claims parsed and validated per answer.",
    )


class GroundingValidationResult(BaseModel):
    """
    Structured, machine-readable validation output evaluating citation validity,
    citation coverage, and evidence grounding metrics.

    All rates are strictly bounded to [0.0, 1.0].
    """

    model_config = ConfigDict(from_attributes=True)

    query: str = Field(..., description="Active search query.")
    original_query: str | None = Field(default=None, description="Raw user query if available.")

    # Claim breakdown
    total_claims: int = Field(
        ..., ge=0, description="Total sentences/claims extracted from answer."
    )
    factual_claims: int = Field(
        ..., ge=0, description="Number of propositional factual claims evaluated."
    )
    conversational_claims: int = Field(
        ..., ge=0, description="Number of conversational framing or refusal statements."
    )
    cited_claims: int = Field(
        ..., ge=0, description="Number of factual claims that include at least one citation."
    )
    uncited_claims: int = Field(
        ..., ge=0, description="Number of factual claims that lack citations."
    )
    supported_claims: int = Field(
        ..., ge=0, description="Number of factual claims evaluated as SUPPORTED by cited evidence."
    )
    supported_uncited_claims: int = Field(
        ...,
        ge=0,
        description="Number of factual claims supported by retrieved context but uncited.",
    )
    unsupported_claims: int = Field(
        ...,
        ge=0,
        description="Number of factual claims evaluated as UNSUPPORTED (cited source fails to corroborate).",
    )
    unverifiable_claims: int = Field(
        ...,
        ge=0,
        description="Number of factual claims that cannot be verified from available context.",
    )

    # Citation counts
    citations_found: int = Field(
        ..., ge=0, description="Total citation tag occurrences found in answer."
    )
    unique_citations_found: int = Field(
        ..., ge=0, description="Count of distinct citation tags referenced."
    )
    valid_citations: int = Field(
        ..., ge=0, description="Count of citation occurrences mapping to existing ContextItems."
    )
    invalid_citations: int = Field(
        ..., ge=0, description="Count of citation occurrences referencing nonexistent sources."
    )
    malformed_citations_count: int = Field(
        ..., ge=0, description="Count of malformed citation patterns detected."
    )

    # Metric rates (strictly [0.0, 1.0])
    citation_validity_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "valid_citations / citations_found if citations_found > 0, else 0.0. "
            "Measures precision of citation generation. An answer with 0 citations receives 0.0."
        ),
    )
    citation_coverage: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "cited_claims / factual_claims if factual_claims > 0, else 0.0. "
            "Measures completeness of attribution across factual claims. 0.0 if no claims cited."
        ),
    )
    claim_support_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "supported_claims / factual_claims if factual_claims > 0, else 0.0 "
            "(or 1.0 if empty-context refusal). Measures fraction of factual claims corroborated."
        ),
    )
    unsupported_claim_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "(unsupported_claims + unverifiable_claims) / factual_claims if factual_claims > 0, else 0.0. "
            "Measures the risk of hallucination or ungrounded extrapolation."
        ),
    )

    # Context & Conflict diagnostics
    is_empty_context: bool = Field(
        default=False,
        description="True if validation was performed on an empty-context response.",
    )
    has_conflicts: bool = Field(
        default=False,
        description="True if possible evidence conflicts were detected between context items.",
    )
    detected_conflicts: list[EvidenceConflictItem] = Field(
        default_factory=list,
        description="List of detected potential evidence conflicts.",
    )

    # Detailed collections
    claims: list[ClaimValidationItem] = Field(
        default_factory=list,
        description="Per-claim validation records.",
    )
    citations: list[CitationValidationItem] = Field(
        default_factory=list,
        description="Per-citation validation records.",
    )

    # Method & Performance
    validation_method: str = Field(
        default="conservative_deterministic_heuristic_v1",
        description="Identifier of the validation engine and version.",
    )
    latency_ms: float = Field(
        ...,
        ge=0.0,
        description="Total round-trip latency in milliseconds for running the validation pipeline.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Safe diagnostic metadata (strictly excluding credentials, secrets, or internal paths).",
    )
