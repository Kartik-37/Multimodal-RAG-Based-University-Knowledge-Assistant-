"""
Conversation and Chat History Pydantic Schemas.

Defines client-safe DTOs for persistent conversation management,
message retrieval, and citation provenance retention.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatMessageResponseDTO(BaseModel):
    """
    Message item within a persistent conversation thread.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    is_grounded: bool | None = None
    grounding_status: str | None = None
    created_at: datetime


class ConversationSummaryDTO(BaseModel):
    """
    Compact conversation representation for history listing.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    scope: str = "ALL_COURSES"
    knowledge_base_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class ConversationDetailDTO(BaseModel):
    """
    Full conversation representation including all ordered messages.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    scope: str = "ALL_COURSES"
    knowledge_base_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageResponseDTO] = Field(default_factory=list)


class CreateConversationRequest(BaseModel):
    """
    Payload for creating a new persistent conversation thread.
    """

    title: str | None = Field(default=None, max_length=255)
    scope: str = Field(default="ALL_COURSES", max_length=50)
    knowledge_base_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
