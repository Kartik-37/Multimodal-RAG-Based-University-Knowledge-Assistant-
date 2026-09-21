"""
Conversational RAG Query Endpoints.

Connects client requests to the application-level RAG orchestrator:
- Enforces role-based access control and tenant isolation (ADMIN or authorized STUDENT).
- Exposes canonical REST endpoint: POST /knowledge-bases/{kb_id}/chat
- Exposes backward-compatible legacy endpoint: POST /chat/query
- Maps domain exceptions cleanly to standard HTTP status codes without leaking internals.
"""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from backend.app.api.deps import (
    AuthenticatedUser,
    DatabaseSession,
    RateLimitChat,
    get_authorized_knowledge_base,
)
from backend.app.core.telemetry import (
    kb_id_ctx,
    set_current_kb_id,
    set_current_user_id,
    user_id_ctx,
)
from backend.app.schemas.chat import (
    ChatQueryRequest,
    ChatQueryResponse,
    KnowledgeBaseChatRequest,
)
from backend.app.services.hybrid_retrieval import (
    HybridRetrievalProviderError,
    HybridRetrievalValidationError,
)
from backend.app.services.llm.exceptions import (
    LLMConnectionError,
    LLMModelNotFoundError,
    LLMProviderError,
    LLMTimeoutError,
)
from backend.app.services.query_processing import QueryValidationError
from backend.app.services.rag_orchestrator import RAGOrchestrator, get_rag_orchestrator
from backend.app.services.reranking.exceptions import (
    RerankerProviderError,
    RerankerValidationError,
)
from backend.app.services.retrieval import (
    RetrievalProviderError,
    RetrievalValidationError,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


async def _execute_orchestrated_chat(
    orchestrator: RAGOrchestrator,
    db: DatabaseSession,
    kb_id: uuid.UUID,
    question: str,
    user_id: uuid.UUID | None = None,
) -> ChatQueryResponse:
    """
    Execute RAG orchestration with strict error mapping and correlation context binding.
    """
    user_token = set_current_user_id(str(user_id)) if user_id else None
    kb_token = set_current_kb_id(str(kb_id))
    try:
        return await orchestrator.execute_query(
            db=db,
            kb_id=kb_id,
            raw_query=question,
        )

    except (
        QueryValidationError,
        HybridRetrievalValidationError,
        RetrievalValidationError,
        RerankerValidationError,
    ) as exc:
        logger.warning("Pipeline validation error during chat: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except LLMTimeoutError as exc:
        logger.error("LLM generation timed out: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="LLM generation timed out. Please try again.",
        ) from exc
    except (
        LLMConnectionError,
        LLMModelNotFoundError,
        LLMProviderError,
        RerankerProviderError,
        HybridRetrievalProviderError,
        RetrievalProviderError,
    ) as exc:
        logger.error("Underlying provider failure during chat orchestration: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Underlying AI model provider is temporarily unavailable. Please try again later.",
        ) from exc
    except SQLAlchemyError as exc:
        logger.error("Database error during chat orchestration: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while processing the request.",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during chat orchestration: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during chat orchestration.",
        ) from exc
    finally:
        if user_token is not None:
            user_id_ctx.reset(user_token)
        kb_id_ctx.reset(kb_token)


@router.post(
    "/chat/query",
    response_model=ChatQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit query to authorized knowledge base (Legacy endpoint)",
)
async def query_knowledge_base_legacy(
    payload: ChatQueryRequest,
    current_user: AuthenticatedUser,
    db: DatabaseSession,
    orchestrator: Annotated[RAGOrchestrator, Depends(get_rag_orchestrator)],
    _rate_limit: RateLimitChat,
) -> ChatQueryResponse:
    """
    Submit a query against an authorized knowledge base with explicit KB ID in body.
    Maintains backward compatibility with earlier API consumers.
    """
    # Enforces multi-user isolation check: returns 404 if user has no access
    kb = get_authorized_knowledge_base(
        kb_id=payload.knowledge_base_id,
        current_user=current_user,
        db=db,
    )

    return await _execute_orchestrated_chat(
        orchestrator=orchestrator,
        db=db,
        kb_id=kb.id,
        question=payload.question,
        user_id=current_user.id,
    )


@router.post(
    "/knowledge-bases/{kb_id}/chat",
    response_model=ChatQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit query to authorized knowledge base (Canonical REST endpoint)",
)
async def chat_with_knowledge_base(
    kb_id: uuid.UUID,
    payload: KnowledgeBaseChatRequest,
    current_user: AuthenticatedUser,
    db: DatabaseSession,
    orchestrator: Annotated[RAGOrchestrator, Depends(get_rag_orchestrator)],
    _rate_limit: RateLimitChat,
) -> ChatQueryResponse:
    """
    Submit a query against an authorized knowledge base with KB ID in URL path.
    Canonical RESTful chat interface.
    """
    # Enforces multi-user isolation check: returns 404 if user has no access
    kb = get_authorized_knowledge_base(
        kb_id=kb_id,
        current_user=current_user,
        db=db,
    )

    return await _execute_orchestrated_chat(
        orchestrator=orchestrator,
        db=db,
        kb_id=kb.id,
        question=payload.question,
        user_id=current_user.id,
    )
