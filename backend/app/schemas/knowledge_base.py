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
    indexing_status: str = "PENDING"
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
    indexed_documents: int = 0
    indexing_documents: int = 0
    failed_documents: int = 0
    document_previews: list[CourseDocumentPreview]


class IndexingJobResponse(BaseModel):
    """Schema for persistent indexing job status and live progress reporting."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    document_id: uuid.UUID
    knowledge_base_id: uuid.UUID
    status: str
    stage: str
    total_chunks: int = 0
    processed_chunks: int = 0
    embedded_chunks: int = 0
    indexed_chunks: int = 0
    progress_percent: float = 0.0
    document_name: str | None = None
    course_name: str | None = None

    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    attempt_number: int = 1


class ComponentHealth(BaseModel):
    """Schema for individual system component health check."""

    name: str
    status: str  # "healthy" | "degraded" | "unavailable"
    message: str = ""


class SystemHealthResponse(BaseModel):
    """Schema for administrative system health overview."""

    status: str  # "healthy" | "degraded" | "unavailable"
    components: list[ComponentHealth]
    checked_at: datetime


class ActivityEventResponse(BaseModel):
    """Schema for chronological administrative audit/activity event."""

    id: str
    timestamp: datetime
    actor_name: str
    actor_email: str
    action: str
    resource_type: str
    resource_name: str
    status: str  # "SUCCESS" | "FAILED" | "IN_PROGRESS"
    details: str = ""
