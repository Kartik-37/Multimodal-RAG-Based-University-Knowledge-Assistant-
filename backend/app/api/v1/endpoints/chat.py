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
    get_authorized_knowledge_base_ids,
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
    kb_id: uuid.UUID | list[uuid.UUID],
    question: str,
    user_id: uuid.UUID | None = None,
) -> ChatQueryResponse:
    """
    Execute RAG orchestration with strict error mapping and correlation context binding.
    """
    user_token = set_current_user_id(str(user_id)) if user_id else None
    if isinstance(kb_id, list):
        kb_str = str(kb_id[0]) if len(kb_id) == 1 else "global"
    else:
        kb_str = str(kb_id)
    kb_token = set_current_kb_id(kb_str)
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
    summary="Submit query to authorized knowledge base or global course materials",
)
async def query_knowledge_base_legacy(
    payload: ChatQueryRequest,
    current_user: AuthenticatedUser,
    db: DatabaseSession,
    orchestrator: Annotated[RAGOrchestrator, Depends(get_rag_orchestrator)],
    _rate_limit: RateLimitChat,
) -> ChatQueryResponse:
    """
    Submit a conversational query against authorized course material.
    - If knowledge_base_id is explicitly provided: Preserves exact scoped behavior and 404 isolation check.
    - If knowledge_base_id is omitted: Resolves all authorized knowledge bases for current_user.
    """
    if payload.knowledge_base_id is not None:
        # Exact backward-compatible scoped query: enforces multi-user isolation check (returns 404 if unauthorized)
        kb = get_authorized_knowledge_base(
            kb_id=payload.knowledge_base_id,
            current_user=current_user,
            db=db,
        )
        target_kb: uuid.UUID | list[uuid.UUID] = kb.id
    else:
        # Global query across all authorized active course materials
        authorized_kb_ids = get_authorized_knowledge_base_ids(current_user=current_user, db=db)
        if not authorized_kb_ids:
            # Student has 0 enrolled/authorized knowledge bases: immediate safe refusal
            from backend.app.schemas.chat import (
                ChatLatencyBreakdownDTO,
                GroundingSummaryDTO,
            )

            return ChatQueryResponse(
                query=payload.question,
                processed_query=payload.question,
                knowledge_base_id=None,
                answer="No course material is currently available to your account.",
                is_empty_context=True,
                citations=[],
                grounding=GroundingSummaryDTO(
                    is_grounded=True,
                    status="REFUSAL",
                    citation_validity_rate=0.0,
                    citation_coverage=0.0,
                    claim_support_rate=0.0,
                    unsupported_claim_rate=0.0,
                    has_conflicts=False,
                    claims=[],
                ),
                latency=ChatLatencyBreakdownDTO(
                    query_processing_ms=0.0,
                    retrieval_ms=0.0,
                    reranking_ms=0.0,
                    context_assembly_ms=0.0,
                    llm_generation_ms=0.0,
                    grounding_validation_ms=0.0,
                    total_pipeline_ms=0.0,
                ),
                model="system",
                metadata={"reason": "no_authorized_knowledge_bases"},
            )
        target_kb = authorized_kb_ids

    return await _execute_orchestrated_chat(
        orchestrator=orchestrator,
        db=db,
        kb_id=target_kb,
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
