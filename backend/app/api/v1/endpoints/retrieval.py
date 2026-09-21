"""
Vector Retrieval API Endpoints.

Provides authenticated vector similarity search over document chunks within an
authorized knowledge base using pgvector.
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
from backend.app.schemas.retrieval import RetrievalRequest, RetrievalResponse
from backend.app.services.retrieval import (
    RetrievalError,
    RetrievalProviderError,
    RetrievalValidationError,
    get_retrieval_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge-bases", tags=["retrieval"])

AuthorizedKB = Annotated[KnowledgeBase, Depends(get_authorized_knowledge_base)]


@router.post(
    "/{kb_id}/retrieve",
    response_model=RetrievalResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve vector-matched document chunks for an authorized knowledge base",
)
async def retrieve_knowledge_base_chunks(
    kb: AuthorizedKB,
    payload: RetrievalRequest,
    db: DatabaseSession,
    _rate_limit: RateLimitRetrieval,
) -> RetrievalResponse:
    """
    Execute dense vector search against chunks in the specified knowledge base.

    Authorization:
    - ADMIN: Can search knowledge bases they administer.
    - STUDENT: Can search knowledge bases where explicit membership is granted.
    - Unauthorized or nonexistent knowledge base returns HTTP 404.
    - Unauthenticated request returns HTTP 401.
    """
    retrieval_service = get_retrieval_service()

    try:
        response = await retrieval_service.retrieve(
            db=db,
            kb_id=kb.id,
            query=payload.query,
            top_k=payload.top_k,
        )
        return response
    except RetrievalValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except RetrievalProviderError as exc:
        logger.error("Embedding provider unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding provider unavailable. Please try again later.",
        ) from exc
    except RetrievalError as exc:
        logger.error("Retrieval operation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Retrieval operation failed due to an internal server error.",
        ) from exc
