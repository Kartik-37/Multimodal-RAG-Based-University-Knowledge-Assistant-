"""
Reranking API Endpoints.

Provides authenticated CrossEncoder reranking over document chunks within an authorized
knowledge base, taking candidates from Step 9 hybrid retrieval and sorting them
by semantic relevance using a local CrossEncoder model.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.deps import (
    DatabaseSession,
    RateLimitRetrieval,
    get_authorized_knowledge_base,
)
from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.schemas.reranking import (
    RerankRequest,
    RerankResponse,
)
from backend.app.services.reranking import (
    RerankerError,
    RerankerProviderError,
    RerankerValidationError,
    get_reranking_service,
)

router = APIRouter(prefix="/knowledge-bases", tags=["reranking"])

AuthorizedKB = Annotated[KnowledgeBase, Depends(get_authorized_knowledge_base)]


@router.post(
    "/{kb_id}/rerank",
    response_model=RerankResponse,
    status_code=status.HTTP_200_OK,
    summary="Rerank hybrid retrieval candidate chunks using local CrossEncoder",
)
async def rerank_knowledge_base_chunks(
    kb: AuthorizedKB,
    payload: RerankRequest,
    db: DatabaseSession,
    _rate_limit: RateLimitRetrieval,
) -> RerankResponse:
    """
    Execute CrossEncoder reranking on candidate chunks retrieved from hybrid retrieval
    (vector + lexical RRF) within the specified knowledge base.

    Authorization:
    - ADMIN: Can search and rerank knowledge bases they administer.
    - STUDENT: Can search and rerank knowledge bases where explicit membership is granted.
    - Unauthorized or nonexistent knowledge base returns HTTP 404 (prevents existence leakage).
    - Unauthenticated request returns HTTP 401.
    """
    reranking_service = get_reranking_service()

    try:
        response = await reranking_service.rerank(
            db=db,
            kb_id=kb.id,
            query=payload.query,
            candidate_limit=payload.candidate_limit,
            top_k=payload.top_k,
        )
        return response
    except RerankerValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except RerankerProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Inference provider unavailable during reranking: {exc}",
        ) from exc
    except RerankerError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reranking operation failed: {exc}",
        ) from exc
