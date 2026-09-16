"""
Context Assembly Pydantic Schemas.

Defines internal domain data transfer models for packaging Step 10 CrossEncoder
reranked candidates into a token-budgeted, deduplicated, provenance-preserving
context package for downstream prompt construction.
"""

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.core.config import settings
from backend.app.schemas.reranking import RerankResultItem


class ContextItem(BaseModel):
    """
    Individual selected evidence chunk within the assembled context.

    Preserves the exact raw chunk text and full retrieval provenance
    (document title, page number, section title, CrossEncoder rank & score,
    RRF score, metadata) along with a sequential source identifier
    and estimated token count.
    """

    model_config = ConfigDict(from_attributes=True)

    source_id: str = Field(
        ...,
        description="Sequential 1-based source identifier formatted for attribution (e.g. 'source_1').",
    )
    chunk_id: uuid.UUID = Field(
        ...,
        description="Unique identifier of the source document chunk.",
    )
    document_id: uuid.UUID = Field(
        ...,
        description="Identifier of the source document.",
    )
    knowledge_base_id: uuid.UUID = Field(
        ...,
        description="Knowledge base containing the source document.",
    )
    document_title: str = Field(
        ...,
        description="Human-readable filename of the source document.",
    )
    chunk_index: int = Field(
        ...,
        description="Sequential zero-based index of the chunk within the document.",
    )
    text: str = Field(
        ...,
        description="Exact, unmodified textual content of the chunk.",
    )
    page_number: int | None = Field(
        default=None,
        description="Source page number (1-indexed) if preserved from paged formats.",
    )
    section_title: str | None = Field(
        default=None,
        description="Heading or section title if identified during parsing.",
    )
    chunk_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured provenance metadata from ingestion.",
    )
    reranker_rank: int = Field(
        ...,
        description="1-based candidate rank from Step 10 CrossEncoder reranking.",
    )
    reranker_score: float = Field(
        ...,
        description="Raw finite semantic relevance score from CrossEncoder.",
    )
    rrf_score: float = Field(
        ...,
        description="Step 9 Reciprocal Rank Fusion score.",
    )
    estimated_tokens: int = Field(
        ...,
        ge=0,
        description="Estimated token count for this chunk using TokenEstimator.",
    )


class ContextAssemblyRequest(BaseModel):
    """
    Request model for assembling context from Step 10 reranked candidates.
    """

    model_config = ConfigDict(from_attributes=True)

    query: str = Field(
        ...,
        min_length=1,
        description="Query string associated with this context assembly (typically Step 11 processed query).",
    )
    original_query: str | None = Field(
        default=None,
        description="Raw user query prior to query processing if available.",
    )
    candidates: list[RerankResultItem] = Field(
        default_factory=list,
        description="Ranked candidate chunks from Step 10 CrossEncoder reranking.",
    )
    token_budget: int = Field(
        default_factory=lambda: settings.MAX_CONTEXT_TOKENS,
        ge=1,
        description="Maximum token budget permitted for the assembled context.",
    )
    max_items: int = Field(
        default_factory=lambda: settings.RAG_TOP_K_RERANK,
        ge=1,
        description="Maximum number of context items to select.",
    )
    knowledge_base_id: uuid.UUID | None = Field(
        default=None,
        description="Optional knowledge base identifier for candidate integrity validation.",
    )


class ContextAssemblyResult(BaseModel):
    """
    Container response model for assembled context.

    Provides ordered context items, token accounting, candidate diagnostics,
    and preserved query metadata.
    """

    model_config = ConfigDict(from_attributes=True)

    query: str = Field(
        ...,
        description="Query associated with this context assembly.",
    )
    original_query: str | None = Field(
        default=None,
        description="Raw user query prior to query processing if available.",
    )
    items: list[ContextItem] = Field(
        default_factory=list,
        description="Selected, deduplicated context items within the token budget.",
    )
    total_items: int = Field(
        ...,
        ge=0,
        description="Number of context items selected.",
    )
    total_estimated_tokens: int = Field(
        ...,
        ge=0,
        description="Total estimated tokens across all selected items.",
    )
    token_budget: int = Field(
        ...,
        ge=1,
        description="Token budget applied for this assembly.",
    )
    candidates_received: int = Field(
        ...,
        ge=0,
        description="Total number of candidates provided to the assembler.",
    )
    items_skipped_budget: int = Field(
        ...,
        ge=0,
        description="Number of candidates skipped due to exceeding the remaining token budget.",
    )
    items_deduplicated: int = Field(
        ...,
        ge=0,
        description="Number of duplicate candidates skipped (by chunk_id or content hash).",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Diagnostic metadata and assembly execution parameters.",
    )
