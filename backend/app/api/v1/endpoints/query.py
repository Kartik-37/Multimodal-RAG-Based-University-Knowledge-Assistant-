"""
Query Processing API Endpoints.

Provides authenticated deterministic search query processing and diagnostic analysis.
Prepares queries for retrieval and reranking pipelines without semantic rewriting.
"""

from fastapi import APIRouter, HTTPException, status

from backend.app.api.deps import AuthenticatedUser
from backend.app.schemas.query_processing import (
    QueryProcessingRequest,
    QueryProcessingResult,
)
from backend.app.services.query_processing import (
    QueryValidationError,
    get_query_processor,
)

router = APIRouter(prefix="/query", tags=["query"])


@router.post(
    "/process",
    response_model=QueryProcessingResult,
    status_code=status.HTTP_200_OK,
    summary="Deterministically process and normalize search query",
)
def process_user_query(
    current_user: AuthenticatedUser,
    payload: QueryProcessingRequest,
) -> QueryProcessingResult:
    """
    Deterministically normalize a user query for downstream retrieval and reranking.

    Operations:
    - Preserves the exact original query.
    - Strips dangerous non-printable control characters.
    - Applies Unicode NFKC normalization.
    - Standardizes internal whitespace (collapses tabs, newlines, multiple spaces).
    - Enforces authoritative length limits.
    - Preserves quotes, technical tokens, programming symbols, and punctuation.
    - Extracts diagnostic metadata (character count, estimated tokens, quote/technical flags).
    """
    processor = get_query_processor()
    try:
        return processor.process(payload.query)
    except QueryValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
