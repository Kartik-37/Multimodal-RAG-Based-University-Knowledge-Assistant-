"""
Vector Retrieval Pydantic Schemas.

Defines API data transfer models for natural-language query requests,
vector search results with structural provenance, and cosine distance/similarity
metrics calculated directly from pgvector.
"""

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.core.config import settings


class RetrievalRequest(BaseModel):
    """
    Client request model for vector retrieval within an authorized knowledge base.
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
        description="Maximum number of top vector-matched chunks to return.",
    )

    @field_validator("query")
    @classmethod
    def validate_query_not_whitespace(cls, v: str) -> str:
        """Ensure search query is not purely whitespace."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Query string cannot be empty or whitespace only.")
        return stripped


class RetrievalResultItem(BaseModel):
    """
    Individual retrieved document chunk with vector similarity score and structural provenance.
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
    cosine_distance: float = Field(
        ...,
        description="Raw pgvector cosine distance (<=> operator). 0.0 indicates exact identity.",
    )
    similarity: float = Field(
        ...,
        description="Direct cosine similarity computed as (1.0 - cosine_distance). Higher is more similar.",
    )


class RetrievalResponse(BaseModel):
    """
    Container response model returning ranked vector retrieval matches.
    """

    query: str = Field(
        ...,
        description="The submitted search query.",
    )
    knowledge_base_id: uuid.UUID | None = Field(
        default=None,
        description="Target knowledge base identifier searched, or None if global.",
    )
    total_results: int = Field(
        ...,
        description="Number of chunks returned in this retrieval result set.",
    )
    results: list[RetrievalResultItem] = Field(
        default_factory=list,
        description="Ordered list of retrieved chunks (lowest cosine distance / highest similarity first).",
    )
