"""
Persistent Conversation & Thread Management Endpoints.

Provides authenticated CRUD operations for user conversations with
strict tenant isolation, ordering by recent activity, and cascade deletion.
"""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import selectinload

from backend.app.api.deps import AuthenticatedUser, DatabaseSession
from backend.app.models.conversation import ChatMessage, Conversation
from backend.app.schemas.conversation import (
    ChatMessageResponseDTO,
    ConversationDetailDTO,
    ConversationSummaryDTO,
    CreateConversationRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get(
    "",
    response_model=list[ConversationSummaryDTO],
    summary="List authenticated user's conversations",
)
def list_conversations(
    current_user: AuthenticatedUser,
    db: DatabaseSession,
) -> list[ConversationSummaryDTO]:
    """
    Retrieve all conversation threads owned by the authenticated user,
    ordered by last activity (updated_at descending).
    Strictly isolated: a user only sees their own conversations.
    """
    # Query conversations with message count subquery for efficiency
    msg_counts = (
        db.query(
            ChatMessage.conversation_id,
            func.count(ChatMessage.id).label("count"),
        )
        .group_by(ChatMessage.conversation_id)
        .subquery()
    )

    rows = (
        db.query(Conversation, func.coalesce(msg_counts.c.count, 0))
        .outerjoin(msg_counts, Conversation.id == msg_counts.c.conversation_id)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )

    summaries = []
    for conv, count in rows:
        summaries.append(
            ConversationSummaryDTO(
                id=conv.id,
                title=conv.title,
                scope=conv.scope,
                knowledge_base_id=conv.knowledge_base_id,
                message_count=int(count),
                created_at=conv.created_at,
                updated_at=conv.updated_at,
            )
        )
    return summaries


@router.post(
    "",
    response_model=ConversationDetailDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation thread",
)
def create_conversation(
    payload: CreateConversationRequest,
    current_user: AuthenticatedUser,
    db: DatabaseSession,
) -> ConversationDetailDTO:
    """
    Create a new persistent conversation thread owned by the authenticated user.
    """
    title = (payload.title or "").strip() or "New Conversation"
    if len(title) > 255:
        title = title[:252] + "..."

    conv = Conversation(
        user_id=current_user.id,
        title=title,
        scope=payload.scope or "ALL_COURSES",
        knowledge_base_id=payload.knowledge_base_id,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    return ConversationDetailDTO(
        id=conv.id,
        title=conv.title,
        scope=conv.scope,
        knowledge_base_id=conv.knowledge_base_id,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[],
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetailDTO,
    summary="Get conversation details and ordered message history",
)
def get_conversation(
    conversation_id: uuid.UUID,
    current_user: AuthenticatedUser,
    db: DatabaseSession,
) -> ConversationDetailDTO:
    """
    Retrieve full conversation and messages.
    Enforces strict user ownership: returns 404 if not found or unauthorized.
    """
    conv = (
        db.query(Conversation)
        .options(selectinload(Conversation.messages))
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
        .first()
    )
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    ordered_messages = sorted(conv.messages, key=lambda m: m.created_at)
    return ConversationDetailDTO(
        id=conv.id,
        title=conv.title,
        scope=conv.scope,
        knowledge_base_id=conv.knowledge_base_id,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[
            ChatMessageResponseDTO(
                id=m.id,
                conversation_id=m.conversation_id,
                role=m.role,
                content=m.content,
                citations=m.citations or [],
                is_grounded=m.is_grounded,
                grounding_status=m.grounding_status,
                created_at=m.created_at,
            )
            for m in ordered_messages
        ],
    )


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete conversation and associated messages",
)
def delete_conversation(
    conversation_id: uuid.UUID,
    current_user: AuthenticatedUser,
    db: DatabaseSession,
) -> dict[str, Any]:
    """
    Delete a conversation thread.
    Enforces strict ownership: returns 404 if not found or unauthorized.
    """
    conv = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
        .first()
    )
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    db.delete(conv)
    db.commit()
    return {"status": "deleted", "id": str(conversation_id)}
