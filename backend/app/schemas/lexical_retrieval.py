"""
Lexical Retrieval Pydantic Schemas.

Defines API data transfer models for natural-language query requests,
lexical search results with structural provenance, and PostgreSQL-native
full-text relevance scores (ts_rank_cd).
"""

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.core.config import settings


class LexicalRetrievalRequest(BaseModel):
    """
    Client request model for lexical retrieval within an authorized knowledge base.
    """

    query: str = Field(
        ...,
        min_length=1,
        max_length=settings.LEXICAL_MAX_QUERY_LENGTH,
        description="Natural language search query.",
    )
    top_k: int = Field(
        default=settings.LEXICAL_TOP_K,
        ge=settings.RETRIEVAL_MIN_TOP_K,
        le=settings.RETRIEVAL_MAX_TOP_K,
        description="Maximum number of top lexical matches to return.",
    )

    @field_validator("query")
    @classmethod
    def validate_query_not_whitespace(cls, v: str) -> str:
        """Ensure search query is not purely whitespace."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Query string cannot be empty or whitespace only.")
        return stripped


class LexicalRetrievalResultItem(BaseModel):
    """
    Individual retrieved document chunk with PostgreSQL full-text lexical score
    and structural provenance metadata.
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
    lexical_score: float = Field(
        ...,
        description="PostgreSQL full-text cover density ranking score (ts_rank_cd). Higher is stronger.",
    )


class LexicalRetrievalResponse(BaseModel):
    """
    Container response model returning ranked lexical full-text matches.
    """

    query: str = Field(
        ...,
        description="The submitted search query.",
    )
    knowledge_base_id: uuid.UUID = Field(
        ...,
        description="Target knowledge base identifier searched.",
    )
    total_results: int = Field(
        ...,
        description="Number of chunks returned in this lexical retrieval result set.",
    )
    results: list[LexicalRetrievalResultItem] = Field(
        default_factory=list,
        description="Ordered list of retrieved chunks (highest lexical_score first).",
    )
