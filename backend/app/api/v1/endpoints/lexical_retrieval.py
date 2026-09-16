"""
Lexical Retrieval API Endpoints.

Provides authenticated PostgreSQL full-text lexical search over document chunks within an
authorized knowledge base using native tsvector and ts_rank_cd facilities.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.deps import (
    DatabaseSession,
    get_authorized_knowledge_base,
)
from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.schemas.lexical_retrieval import (
    LexicalRetrievalRequest,
    LexicalRetrievalResponse,
)
from backend.app.services.lexical_retrieval import (
    LexicalRetrievalError,
    LexicalRetrievalValidationError,
    get_lexical_retrieval_service,
)

router = APIRouter(prefix="/knowledge-bases", tags=["lexical-retrieval"])

AuthorizedKB = Annotated[KnowledgeBase, Depends(get_authorized_knowledge_base)]


@router.post(
    "/{kb_id}/lexical-retrieve",
    response_model=LexicalRetrievalResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve lexically matched document chunks for an authorized knowledge base",
)
def retrieve_knowledge_base_lexical_chunks(
    kb: AuthorizedKB,
    payload: LexicalRetrievalRequest,
    db: DatabaseSession,
) -> LexicalRetrievalResponse:
    """
    Execute PostgreSQL full-text lexical search against chunks in the specified knowledge base.

    Authorization:
    - ADMIN: Can search knowledge bases they administer.
    - STUDENT: Can search knowledge bases where explicit membership is granted.
    - Unauthorized or nonexistent knowledge base returns HTTP 404.
    - Unauthenticated request returns HTTP 401.
    """
    lexical_service = get_lexical_retrieval_service()

    try:
        response = lexical_service.retrieve(
            db=db,
            kb_id=kb.id,
            query=payload.query,
            top_k=payload.top_k,
        )
        return response
    except LexicalRetrievalValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except LexicalRetrievalError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lexical retrieval operation failed: {exc}",
        ) from exc
