"""
Hybrid Retrieval Pydantic Schemas.

Defines API data transfer models for natural-language query requests,
hybrid retrieval results fused using Reciprocal Rank Fusion (RRF),
and diagnostic candidate provenance from dense vector and lexical branches.
"""

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.core.config import settings


class HybridRetrievalRequest(BaseModel):
    """
    Client request model for hybrid retrieval within an authorized knowledge base.
    """

    query: str = Field(
        ...,
        min_length=1,
        max_length=settings.RETRIEVAL_MAX_QUERY_LENGTH,
        description="Natural language query string.",
    )
    top_k: int = Field(
        default=settings.RAG_TOP_K_RETRIEVAL,
        ge=settings.RETRIEVAL_MIN_TOP_K,
        le=settings.RETRIEVAL_MAX_TOP_K,
        description="Maximum number of top hybrid-ranked chunks to return.",
    )

    @field_validator("query")
    @classmethod
    def validate_query_not_whitespace(cls, v: str) -> str:
        """Ensure search query is not purely whitespace."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Query string cannot be empty or whitespace only.")
        return stripped


class HybridRetrievalResultItem(BaseModel):
    """
    Individual retrieved document chunk fused via Reciprocal Rank Fusion (RRF)
    with structural provenance and diagnostic branch metrics.
    """

    model_config = ConfigDict(from_attributes=True)

    chunk_id: uuid.UUID = Field(
        ...,
        description="Unique identifier of the retrieved text chunk.",
    )
    document_id: uuid.UUID = Field(
        ...,
        description="Source document identifier.",
    )
    knowledge_base_id: uuid.UUID = Field(
        ...,
        description="Knowledge base identifier containing this chunk.",
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
        description="Normalized textual content of the chunk.",
    )
    page_number: int | None = Field(
        default=None,
        description="Source page number (1-indexed) if preserved from PDF/paged format.",
    )
    section_title: str | None = Field(
        default=None,
        description="Heading or section title if identified during parsing.",
    )
    chunk_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured provenance metadata (source offsets, token count, etc.).",
    )
    rrf_score: float = Field(
        ...,
        description="Reciprocal Rank Fusion score computed from candidate rank positions.",
    )
    vector_rank: int | None = Field(
        default=None,
        description="1-based candidate rank in dense vector retrieval branch, or None if not matched.",
    )
    lexical_rank: int | None = Field(
        default=None,
        description="1-based candidate rank in PostgreSQL lexical retrieval branch, or None if not matched.",
    )
    vector_contribution: float = Field(
        default=0.0,
        description="1 / (RRF_K + vector_rank) contribution to RRF score, or 0.0 if not matched.",
    )
    lexical_contribution: float = Field(
        default=0.0,
        description="1 / (RRF_K + lexical_rank) contribution to RRF score, or 0.0 if not matched.",
    )
    cosine_distance: float | None = Field(
        default=None,
        description="Diagnostic pgvector cosine distance if matched in vector branch.",
    )
    similarity: float | None = Field(
        default=None,
        description="Diagnostic cosine similarity (1.0 - cosine_distance) if matched in vector branch.",
    )
    lexical_score: float | None = Field(
        default=None,
        description="Diagnostic PostgreSQL ts_rank_cd cover density ranking score if matched in lexical branch.",
    )


class HybridRetrievalResponse(BaseModel):
    """
    Container response model returning ranked hybrid retrieval matches.
    """

    query: str = Field(
        ...,
        description="Normalized query string evaluated by the retrieval branches.",
    )
    knowledge_base_id: uuid.UUID = Field(
        ...,
        description="Knowledge base identifier searched.",
    )
    total_results: int = Field(
        ...,
        description="Number of fused chunks returned in this response.",
    )
    results: list[HybridRetrievalResultItem] = Field(
        default_factory=list,
        description="Fused document chunks sorted in descending order of RRF score.",
    )
    rrf_k: int = Field(
        default_factory=lambda: settings.RRF_K,
        description="RRF smoothing constant applied during reciprocal rank calculation.",
    )
