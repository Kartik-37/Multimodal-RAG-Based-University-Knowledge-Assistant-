"""
Query Processing Pydantic Schemas.

Defines API data transfer models for raw search query submission and
deterministically processed query output with diagnostic metadata.
"""

from typing import Any

from pydantic import BaseModel, Field


class QueryProcessingRequest(BaseModel):
    """
    Request model for raw natural-language query processing.
    """

    query: str = Field(
        ...,
        description="Raw natural-language search query string from client.",
    )


class QueryProcessingResult(BaseModel):
    """
    Result model containing both the preserved original query, the deterministically
    normalized query for retrieval pipelines, and safe diagnostic metadata.
    """

    original_query: str = Field(
        ...,
        description="Exact raw user query string as received prior to normalization.",
    )
    processed_query: str = Field(
        ...,
        description="Deterministically normalized query string for retrieval and reranking.",
    )
    character_count: int = Field(
        ...,
        description="Character length of the processed query.",
    )
    token_estimate: int = Field(
        ...,
        description="Estimated token count of the processed query using deterministic token estimator.",
    )
    has_quotes: bool = Field(
        default=False,
        description="Diagnostic flag indicating whether the query contains quoted phrases.",
    )
    has_technical_tokens: bool = Field(
        default=False,
        description="Diagnostic flag indicating presence of technical tokens, programming symbols, or SQL keywords.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Safe diagnostic metadata regarding applied normalization transformations.",
    )
