"""
SQLAlchemy Domain Models Package.

Exports all ORM entities for centralized imports and Alembic migration autogeneration.
"""

from backend.app.models.document import Document, DocumentChunk, DocumentStatus, IndexingStatus
from backend.app.models.indexing_job import IndexingJob, IndexingJobStage, IndexingJobStatus
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseMember
from backend.app.models.rate_limit import RateLimitEntry
from backend.app.models.user import AdminRole, User, UserRole, UserSession

__all__ = [
    "User",
    "UserRole",
    "AdminRole",
    "UserSession",
    "KnowledgeBase",
    "KnowledgeBaseMember",
    "Document",
    "DocumentChunk",
    "DocumentStatus",
    "IndexingStatus",
    "IndexingJob",
    "IndexingJobStatus",
    "IndexingJobStage",
    "RateLimitEntry",
]
