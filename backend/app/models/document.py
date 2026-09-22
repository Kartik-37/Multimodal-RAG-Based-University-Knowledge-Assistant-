"""
Document and DocumentChunk Database Models.

Defines the PostgreSQL schema for ingested documents, their lifecycle status
(PENDING, PROCESSING, COMPLETED, FAILED), and extracted text chunks with
associated page numbers, structural headings, and citation metadata.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Computed,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.knowledge_base import KnowledgeBase


class DocumentStatus(enum.StrEnum):
    """
    Ingestion status lifecycle states for documents.

    Note: Step 5 terminates at COMPLETED (parsing, normalization, chunking).
    Vector indexing occurs as a distinct subsequent stage tracked by IndexingStatus.
    """

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class IndexingStatus(enum.StrEnum):
    """
    Vector indexing lifecycle states for documents.

    Maintains distinct separation from DocumentStatus (parsing & chunking).
    Allows vector indexing retries without re-parsing or re-chunking files.
    """

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Document(Base):
    """
    Represents an uploaded and managed source document within a KnowledgeBase.
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The client-provided original filename (used strictly for display and citations, never as a path)
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    # The internal unpredictable storage key on disk (e.g. storage/{kb_id}/{doc_id}.{ext})
    storage_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        unique=True,
        index=True,
    )
    # Canonical file type: pdf, docx, txt, md, csv
    file_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    # Cryptographic content hash (SHA-256) for deduplication and integrity
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", native_enum=True),
        nullable=False,
        default=DocumentStatus.PENDING,
        index=True,
    )
    # Vector indexing lifecycle status (independent from document ingestion status)
    indexing_status: Mapped[IndexingStatus] = mapped_column(
        Enum(IndexingStatus, name="indexing_status", native_enum=True),
        nullable=False,
        default=IndexingStatus.PENDING,
        index=True,
    )
    # Publication / retrieval eligibility flag (Step 21B)
    # Inactive documents remain stored for admins but never participate in student retrieval
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
        index=True,
    )
    # Diagnostic error details if ingestion/parsing fails
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    # Diagnostic error details if vector indexing fails
    indexing_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    # Timestamp when vector indexing completed successfully
    indexed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    knowledge_base: Mapped["KnowledgeBase"] = relationship(
        "KnowledgeBase",
        back_populates="documents",
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index",
    )


class DocumentChunk(Base):
    """
    Extracted textual chunk derived from a source document.

    Retains structural provenance including page numbers (for PDFs), section
    headings (for Markdown/DOCX), and estimated token counts.
    """

    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Deterministic sequential position of the chunk within the document
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    # The actual normalized text content of the chunk
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    # Estimated token count calculated via deterministic token estimator
    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    # Source page number (1-indexed, preserved for PDF/paged documents, None if unpaged)
    page_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    # Structural heading or section title if detected during parsing
    section_title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    # Structured provenance metadata (e.g. source offsets, table headers, etc.)
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    # 1024-dimensional dense vector representation (qwen3-embedding:0.6b via pgvector)
    # Nullable initially; populated upon vector indexing completion
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1024),
        nullable=True,
    )
    # PostgreSQL full-text search representation generated automatically from text
    searchable_text: Mapped[Any | None] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', text)", persisted=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_doc_chunk_index"),
        Index("ix_chunks_kb_doc", "knowledge_base_id", "document_id"),
        Index("ix_document_chunks_searchable_text", "searchable_text", postgresql_using="gin"),
    )

    # Relationships
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="chunks",
    )
