"""
Knowledge Base Pydantic Schemas.

Defines schemas for creating, viewing, and managing knowledge base corpora and memberships.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeBaseCreate(BaseModel):
    """Schema for creating a new knowledge base (ADMIN only)."""

    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)


class KnowledgeBaseResponse(BaseModel):
    """Schema for knowledge base representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    created_by_id: uuid.UUID
    created_at: datetime


class AddMemberRequest(BaseModel):
    """Schema for adding a student member to an existing knowledge base (ADMIN only)."""

    user_id: uuid.UUID


class MemberResponse(BaseModel):
    """Schema for confirmed membership grant."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    user_id: uuid.UUID
    granted_at: datetime


class CourseDocumentPreview(BaseModel):
    """Schema for compact course document preview."""

    id: uuid.UUID
    filename: str
    file_type: str
    status: str
    is_active: bool


class CourseSummaryResponse(BaseModel):
    """Schema for course summary with document counts and previews."""

    id: uuid.UUID
    name: str
    description: str
    created_at: datetime
    total_documents: int
    active_documents: int
    inactive_documents: int
    document_previews: list[CourseDocumentPreview]
