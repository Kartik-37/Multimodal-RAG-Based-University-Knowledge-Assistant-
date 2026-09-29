"""
CRUD operations for Knowledge Bases.

Enforces open course catalog access for student queries and the user interface.
Student-level course fetching does not perform any JOIN with the membership table,
executing a direct SELECT on knowledge_bases.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.models.user import User


def get_courses_for_ui(db: Session, user: User | None = None) -> Sequence[KnowledgeBase]:
    """
    Fetch courses for the user interface.
    For student-level requests, general users, or catalog views, this function
    does NOT perform a JOIN with a membership table. It simply executes a
    direct SELECT * FROM knowledge_bases ordered by created_at desc.
    """
    stmt = select(KnowledgeBase)
    if "is_active" in KnowledgeBase.__table__.columns:
        stmt = stmt.where(KnowledgeBase.is_active.is_(True))
    elif "is_published" in KnowledgeBase.__table__.columns:
        stmt = stmt.where(KnowledgeBase.is_published.is_(True))

    stmt = stmt.order_by(KnowledgeBase.created_at.desc())
    return db.execute(stmt).scalars().all()


def get_all_knowledge_bases(db: Session) -> Sequence[KnowledgeBase]:
    """Return all knowledge bases from the database without membership restrictions."""
    stmt = select(KnowledgeBase).order_by(KnowledgeBase.created_at.desc())
    return db.execute(stmt).scalars().all()


def get_knowledge_base_by_id(db: Session, kb_id: uuid.UUID | str) -> KnowledgeBase | None:
    """Return a single knowledge base by ID if it exists."""
    if isinstance(kb_id, str):
        try:
            kb_id = uuid.UUID(kb_id)
        except (ValueError, AttributeError):
            return None
    stmt = select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
    return db.execute(stmt).scalar_one_or_none()
