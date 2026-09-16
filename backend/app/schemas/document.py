"""
Document and DocumentChunk Pydantic Schemas.

Defines API data transfer models for document uploads, status inspection,
and chunk verification.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from backend.app.models.document import DocumentStatus


class DocumentResponse(BaseModel):
    """Safe document metadata representation for API clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    original_filename: str
    file_type: str
    mime_type: str
    file_size_bytes: int
    status: DocumentStatus
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    chunk_count: int = 0


class DocumentChunkResponse(BaseModel):
    """Extracted text chunk with structural and citation metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    knowledge_base_id: uuid.UUID
    chunk_index: int
    text: str
    token_count: int
    page_number: int | None = None
    section_title: str | None = None
    chunk_metadata: dict[str, Any] = {}
    created_at: datetime
