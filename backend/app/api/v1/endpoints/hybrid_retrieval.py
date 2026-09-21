"""
Hybrid Retrieval API Endpoints.

Provides authenticated hybrid retrieval over document chunks within an authorized
knowledge base, combining dense vector search and PostgreSQL lexical full-text search
via Reciprocal Rank Fusion (RRF).
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.deps import (
    DatabaseSession,
    RateLimitRetrieval,
    get_authorized_knowledge_base,
)
from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.schemas.hybrid_retrieval import (
    HybridRetrievalRequest,
    HybridRetrievalResponse,
)
from backend.app.services.hybrid_retrieval import (
    HybridRetrievalError,
    HybridRetrievalProviderError,
    HybridRetrievalValidationError,
    get_hybrid_retrieval_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge-bases", tags=["hybrid-retrieval"])

AuthorizedKB = Annotated[KnowledgeBase, Depends(get_authorized_knowledge_base)]


@router.post(
    "/{kb_id}/hybrid-retrieve",
    response_model=HybridRetrievalResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve hybrid-ranked document chunks for an authorized knowledge base",
)
async def retrieve_knowledge_base_hybrid_chunks(
    kb: AuthorizedKB,
    payload: HybridRetrievalRequest,
    db: DatabaseSession,
    _rate_limit: RateLimitRetrieval,
) -> HybridRetrievalResponse:
    """
    Execute hybrid retrieval (dense vector + PostgreSQL full-text lexical)
    fused with Reciprocal Rank Fusion (RRF) against chunks in the specified knowledge base.

    Authorization:
    - ADMIN: Can search knowledge bases they administer.
    - STUDENT: Can search knowledge bases where explicit membership is granted.
    - Unauthorized or nonexistent knowledge base returns HTTP 404 (prevents existence leakage).
    - Unauthenticated request returns HTTP 401.
    """
    hybrid_service = get_hybrid_retrieval_service()

    try:
        response = await hybrid_service.retrieve(
            db=db,
            kb_id=kb.id,
            query=payload.query,
            top_k=payload.top_k,
        )
        return response
    except HybridRetrievalValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except HybridRetrievalProviderError as exc:
        logger.error("Embedding provider unavailable during hybrid retrieval: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding provider unavailable during hybrid retrieval. Please try again later.",
        ) from exc
    except HybridRetrievalError as exc:
        logger.error("Hybrid retrieval operation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Hybrid retrieval operation failed due to an internal server error.",
        ) from exc
