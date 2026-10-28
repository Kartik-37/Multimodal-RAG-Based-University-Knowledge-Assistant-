"""
Conversational RAG Query Endpoints.

Connects client requests to the application-level RAG orchestrator:
- Enforces role-based access control and tenant isolation (ADMIN or authorized STUDENT).
- Exposes canonical REST endpoint: POST /knowledge-bases/{kb_id}/chat
- Exposes backward-compatible legacy endpoint: POST /chat/query
- Maps domain exceptions cleanly to standard HTTP status codes without leaking internals.
"""

import json
import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from backend.app.api.deps import (
    AuthenticatedUser,
    DatabaseSession,
    RateLimitChat,
    check_user_permission,
    get_authorized_document,
    get_authorized_knowledge_base,
    get_authorized_knowledge_base_ids,
)
from backend.app.core.permissions import Permission
from backend.app.core.telemetry import (
    kb_id_ctx,
    set_current_kb_id,
    set_current_user_id,
    user_id_ctx,
)
from backend.app.models.conversation import ChatMessage, Conversation
from backend.app.models.document import IndexingStatus
from backend.app.models.user import UserRole
from backend.app.schemas.chat import (
    ChatLatencyBreakdownDTO,
    ChatQueryRequest,
    ChatQueryResponse,
    GroundingSummaryDTO,
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
    document_id: uuid.UUID | None = None,
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
            document_id=document_id,
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


def generate_conversation_title(question: str) -> str:
    """
    Generate a clean, readable conversation title deterministically from the first question.
    Preserves user wording, collapses whitespace, and cleanly bounds length without model latency.
    """
    clean = " ".join(question.strip().split())
    if not clean:
        return "New chat"
    if len(clean) <= 80:
        return clean
    truncated = clean[:75]
    last_space = truncated.rfind(" ")
    if last_space > 40:
        truncated = truncated[:last_space]
    return truncated.rstrip(",;:- ") + "..."


def _try_persist_turn(
    db: DatabaseSession,
    user_id: uuid.UUID,
    question: str,
    response: ChatQueryResponse,
    scope: str,
    active_conv: Conversation | None = None,
    kb_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
) -> None:
    """Safely persist conversation turn (user question and assistant response) with user ownership."""
    try:
        if active_conv is None:
            clean_title = generate_conversation_title(question)
            conv = Conversation(
                user_id=user_id,
                title=clean_title,
                scope=scope,
                knowledge_base_id=kb_id,
                document_id=document_id,
            )
            db.add(conv)
            db.flush()
        else:
            conv = active_conv
            prior_user_msgs = (
                db.query(ChatMessage)
                .filter(ChatMessage.conversation_id == conv.id, ChatMessage.role == "user")
                .count()
            )
            if prior_user_msgs == 0 or (conv.title or "").strip().lower() in ("new chat", "new conversation"):
                conv.title = generate_conversation_title(question)

        user_msg = ChatMessage(
            conversation_id=conv.id,
            role="user",
            content=question,
            citations=[],
        )
        db.add(user_msg)
        db.flush()

        citations_data = [
            c.model_dump(mode="json") if hasattr(c, "model_dump") else json.loads(json.dumps(c.dict(), default=str))
            for c in response.citations
        ]
        assistant_msg = ChatMessage(
            conversation_id=conv.id,
            role="assistant",
            content=response.answer,
            citations=citations_data,
            is_grounded=response.grounding.is_grounded,
            grounding_status=response.grounding.status,
        )
        db.add(assistant_msg)
        conv.updated_at = datetime.now(UTC)
        db.commit()
        response.metadata["conversation_id"] = str(conv.id)
    except Exception as exc:
        logger.warning("Could not persist chat turn to database: %s", exc)
        try:
            db.rollback()
        except Exception:
            pass


def resolve_conversational_query(
    raw_query: str,
    conversation: Conversation | None,
) -> str:
    """
    Resolve anaphoric or follow-up queries using immediate prior conversation context.
    Transforms queries like 'list that', 'explain that', 'tell me more', 'make it a table'
    into self-contained retrieval queries.
    """
    if not conversation or not conversation.messages:
        return raw_query

    q_strip = raw_query.strip()
    q_lower = q_strip.lower().rstrip(".?!")

    followup_verbs = (
        "list that",
        "list it",
        "list them",
        "list all of that",
        "list those",
        "list out that",
        "explain that",
        "explain it",
        "tell me more",
        "tell me about that",
        "what about that",
        "what about it",
        "make it a table",
        "show that",
        "show it",
        "show them",
        "expand on that",
        "give more details",
        "elaborate",
    )
    is_followup = any(q_lower == v or q_lower.startswith(v + " ") for v in followup_verbs)

    words = q_lower.split()
    if not is_followup and len(words) <= 4:
        if any(w in ("that", "it", "them", "this", "those") for w in words):
            is_followup = True

    if not is_followup:
        return raw_query

    user_msgs = [m for m in conversation.messages if m.role == "user"]
    if not user_msgs:
        return raw_query

    last_user_query = user_msgs[-1].content.strip()
    if "list" in q_lower:
        resolved = f"List all items and versions shown in {last_user_query}. Cite the source page."
    elif "explain" in q_lower:
        resolved = f"Explain in detail: {last_user_query}"
    elif "table" in q_lower:
        resolved = f"Present the details of {last_user_query} in a clear format."
    else:
        resolved = f"{last_user_query} - {raw_query}"

    logger.info("Resolved conversational follow-up query '%s' -> '%s'", raw_query, resolved)
    return resolved


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
    Supports ALL_COURSES, COURSE, and DOCUMENT scopes.
    """
    # 1. RBAC enforcement for administrators
    if current_user.role == UserRole.ADMIN and not check_user_permission(
        current_user, Permission.ADMIN_CHAT
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Missing required permission 'ADMIN_CHAT'.",
        )

    # 2. Conversation ownership verification if conversation_id was provided
    active_conv: Conversation | None = None
    if payload.conversation_id is not None:
        active_conv = (
            db.query(Conversation)
            .filter(
                Conversation.id == payload.conversation_id,
                Conversation.user_id == current_user.id,
            )
            .first()
        )
        if not active_conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found.",
            )

    target_document_id: uuid.UUID | None = None

    # 3. Scope validation and resolution. The explicit scope controls the
    # required identifiers; invalid combinations are rejected instead of
    # silently falling back to broader retrieval.
    valid_scopes = {"ALL_COURSES", "COURSE", "DOCUMENT"}
    scope = payload.scope or (
        "DOCUMENT"
        if payload.document_id is not None
        else "COURSE"
        if payload.knowledge_base_id is not None
        else "ALL_COURSES"
    )
    if scope not in valid_scopes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid chat scope. Use ALL_COURSES, COURSE, or DOCUMENT.",
        )

    if scope == "ALL_COURSES":
        if payload.knowledge_base_id is not None or payload.document_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ALL_COURSES scope cannot include knowledge_base_id or document_id.",
            )
        authorized_kb_ids = get_authorized_knowledge_base_ids(
            current_user=current_user,
            db=db,
        )
        if not authorized_kb_ids:
            refusal_resp = ChatQueryResponse(
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
            _try_persist_turn(
                db=db,
                user_id=current_user.id,
                question=payload.question,
                response=refusal_resp,
                scope=scope,
                active_conv=active_conv,
                kb_id=None,
            )
            return refusal_resp
        target_kb: uuid.UUID | list[uuid.UUID] = authorized_kb_ids

    elif scope == "COURSE":
        if payload.knowledge_base_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="COURSE scope requires knowledge_base_id.",
            )
        if payload.document_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="COURSE scope cannot include document_id.",
            )
        kb = get_authorized_knowledge_base(
            kb_id=payload.knowledge_base_id,
            current_user=current_user,
            db=db,
        )
        target_kb = kb.id

    else:  # DOCUMENT
        if payload.document_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="DOCUMENT scope requires document_id.",
            )
        if payload.knowledge_base_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="DOCUMENT scope requires knowledge_base_id.",
            )

        doc = get_authorized_document(
            document_id=payload.document_id,
            knowledge_base_id=payload.knowledge_base_id,
            current_user=current_user,
            db=db,
        )
        target_kb = doc.knowledge_base_id
        target_document_id = doc.id

        # Admins may inspect an unindexed document to diagnose its state, but
        # retrieval must refuse it until indexing is complete.
        if doc.indexing_status != IndexingStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Document '{doc.original_filename}' is not ready for retrieval "
                    "because vector indexing is not completed "
                    f"(status: {doc.indexing_status.value if hasattr(doc.indexing_status, 'value') else doc.indexing_status})."
                ),
            )

    retrieval_query = payload.question
    if active_conv is not None:
        retrieval_query = resolve_conversational_query(payload.question, active_conv)

    rag_response = await _execute_orchestrated_chat(
        orchestrator=orchestrator,
        db=db,
        kb_id=target_kb,
        question=retrieval_query,
        user_id=current_user.id,
        document_id=target_document_id,
    )
    rag_response.query = payload.question
    _try_persist_turn(
        db=db,
        user_id=current_user.id,
        question=payload.question,
        response=rag_response,
        scope=scope,
        active_conv=active_conv,
        kb_id=payload.knowledge_base_id,
        document_id=target_document_id,
    )
    return rag_response


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
    if current_user.role == UserRole.ADMIN and not check_user_permission(
        current_user, Permission.ADMIN_CHAT
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Missing required permission 'ADMIN_CHAT'.",
        )

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
