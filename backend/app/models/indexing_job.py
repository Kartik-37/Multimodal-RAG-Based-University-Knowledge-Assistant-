"""
Persistent Document Vector Indexing Job Model.

Tracks asynchronous vector indexing lifecycle, granular chunk progress (e.g. 16/33 chunks, 48%),
execution stages, timestamps, and diagnostic failure reasons.
Survives request and process lifecycles in PostgreSQL.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.document import Document
    from backend.app.models.knowledge_base import KnowledgeBase


class IndexingJobStatus(enum.StrEnum):
    """Lifecycle execution statuses for persistent indexing jobs."""

    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class IndexingJobStage(enum.StrEnum):
    """Detailed progress stages within vector indexing."""

    PREPARING = "PREPARING"
    EMBEDDING = "EMBEDDING"
    WRITING_VECTORS = "WRITING_VECTORS"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class IndexingJob(Base):
    """
    Persistent indexing job representing a vectorization and indexing task.
    """

    __tablename__ = "indexing_jobs"

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
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=IndexingJobStatus.QUEUED.value,
        index=True,
    )
    stage: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=IndexingJobStage.PREPARING.value,
    )
    total_chunks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    processed_chunks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    embedded_chunks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    indexed_chunks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    progress_percent: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
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
    document: Mapped["Document"] = relationship(
        "Document",
        foreign_keys=[document_id],
    )
    knowledge_base: Mapped["KnowledgeBase"] = relationship(
        "KnowledgeBase",
        foreign_keys=[knowledge_base_id],
    )
