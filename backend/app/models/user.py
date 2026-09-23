"""
User and Session Database Models.

Defines the User entity with role-based access control (ADMIN, STUDENT)
and the UserSession entity for server-managed session lifecycle.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseMember


class UserRole(enum.StrEnum):
    """
    Role definitions for application authorization.
    ADMIN: Can create/manage knowledge bases, upload documents, query, and grant access.
    STUDENT: Read-only access to authorized knowledge bases; can query RAG and inspect citations.
    """

    ADMIN = "ADMIN"
    STUDENT = "STUDENT"


class AdminRole(enum.StrEnum):
    """
    Hierarchical sub-roles for administrators.
    MAIN_ADMIN: Super-administrator with full permissions.
    FACULTY_ADMIN: Subordinate administrator with granular, configurable permissions.
    """

    MAIN_ADMIN = "MAIN_ADMIN"
    FACULTY_ADMIN = "FACULTY_ADMIN"


class User(Base):
    """
    User account model.
    Enforces uniqueness on email, stores Argon2id password hash, and tracks active status.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=True),
        default=UserRole.STUDENT,
        nullable=False,
    )
    admin_role: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        default=None,
        index=True,
    )
    permissions: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
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
    sessions: Mapped[list["UserSession"]] = relationship(
        "UserSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    owned_knowledge_bases: Mapped[list["KnowledgeBase"]] = relationship(
        "KnowledgeBase",
        back_populates="creator",
        cascade="all, delete-orphan",
        foreign_keys="KnowledgeBase.created_by_id",
    )
    knowledge_base_memberships: Mapped[list["KnowledgeBaseMember"]] = relationship(
        "KnowledgeBaseMember",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserSession(Base):
    """
    Server-managed browser session.
    Stores ONLY the SHA-256 hex digest of the raw session token for credential protection.
    """

    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="sessions")
