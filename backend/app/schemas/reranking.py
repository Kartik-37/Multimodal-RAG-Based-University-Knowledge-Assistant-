"""
Reranking Pydantic Schemas.

Defines API data transfer models for natural-language query reranking requests,
CrossEncoder reranked results preserving full Step 9 hybrid retrieval provenance,
and diagnostic metadata.
"""

import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.core.config import settings
from backend.app.schemas.hybrid_retrieval import HybridRetrievalResultItem


class RerankRequest(BaseModel):
    """
    Client request model for reranking hybrid retrieval candidates within an
    authorized knowledge base.
    """

    query: str = Field(
        ...,
        min_length=1,
        max_length=settings.RETRIEVAL_MAX_QUERY_LENGTH,
        description="Natural language query string.",
    )
    candidate_limit: int = Field(
        default=settings.RAG_TOP_K_RETRIEVAL,
        ge=settings.RETRIEVAL_MIN_TOP_K,
        le=settings.RETRIEVAL_MAX_TOP_K,
        description="Maximum number of hybrid candidates to retrieve from Step 9 for reranking.",
    )
    top_k: int = Field(
        default=settings.RAG_TOP_K_RERANK,
        ge=settings.RETRIEVAL_MIN_TOP_K,
        le=settings.RETRIEVAL_MAX_TOP_K,
        description="Maximum number of top reranked chunks to return.",
    )

    @field_validator("query")
    @classmethod
    def validate_query_not_whitespace(cls, v: str) -> str:
        """Ensure search query is not purely whitespace."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Query string cannot be empty or whitespace only.")
        return stripped


class RerankResultItem(HybridRetrievalResultItem):
    """
    Individual retrieved document chunk after CrossEncoder reranking.
    Preserves all Step 9 hybrid retrieval provenance while adding raw
    CrossEncoder scoring and final rerank position.
    """

    model_config = ConfigDict(from_attributes=True)

    reranker_score: float = Field(
        ...,
        description="Raw finite CrossEncoder semantic relevance score.",
    )
    reranker_rank: int = Field(
        ...,
        description="1-based candidate rank after CrossEncoder reranking.",
    )


class RerankResponse(BaseModel):
    """
    Container response model returning CrossEncoder reranked chunks.
    """

    query: str = Field(
        ...,
        description="Normalized query string evaluated by the reranker.",
    )
    knowledge_base_id: uuid.UUID = Field(
        ...,
        description="Knowledge base identifier searched.",
    )
    model_name: str = Field(
        ...,
        description="Name or path of the CrossEncoder model utilized for reranking.",
    )
    total_candidates_reranked: int = Field(
        ...,
        description="Number of hybrid candidates evaluated by the CrossEncoder.",
    )
    total_results: int = Field(
        ...,
        description="Number of top reranked chunks returned in this response.",
    )
    results: list[RerankResultItem] = Field(
        default_factory=list,
        description="Reranked document chunks sorted in descending order of CrossEncoder score.",
    )
    rrf_k: int = Field(
        default_factory=lambda: settings.RRF_K,
        description="RRF smoothing constant applied during candidate generation.",
    )
