"""
Data Transfer Objects (DTOs) for Frontend Presentation Layer.

Provides typed models representing user sessions, knowledge bases, documents,
conversations, and citation evidence. Keeps UI code decoupled from backend DB models.
"""

from pydantic import BaseModel, Field


class UserDTO(BaseModel):
    """User account representation in frontend state."""

    id: str
    email: str
    full_name: str
    role: str = "STUDENT"


class KnowledgeBaseDTO(BaseModel):
    """Knowledge base representation."""

    id: str
    name: str
    description: str = ""
    document_count: int = 0
    created_at: str = ""


class DocumentDTO(BaseModel):
    """Document representation in frontend knowledge view."""

    id: str
    kb_id: str
    filename: str
    file_type: str
    file_size_bytes: int = 0
    status: str = "PENDING"  # PENDING, PROCESSING, COMPLETED, FAILED
    error_message: str | None = None
    chunk_count: int = 0
    created_at: str = ""


class CitationDTO(BaseModel):
    """Retrieved source citation with provenance metadata."""

    document_name: str
    page_number: int | None = None
    chunk_id: str
    relevance_score: float = Field(default=0.0, description="Rerank or fusion score")
    snippet: str


class ChatMessageDTO(BaseModel):
    """Chat message in conversational RAG interface."""

    id: str
    role: str  # 'user' | 'assistant'
    content: str
    citations: list[CitationDTO] = Field(default_factory=list)
    created_at: str = ""
