"""
FastAPI Authentication and Authorization Dependencies.

Enforces server-side identity verification, role-based access control (RBAC),
and multi-user tenant isolation.

Security Decisions:
- Client-supplied user IDs, roles, and ownership attributes are completely untrusted.
  Identity and permissions are strictly resolved from server-side database records.
- Session tokens in cookies or Authorization headers are hashed (SHA-256) before lookup;
  raw credentials are never logged or stored.
- Multi-user isolation queries prevent cross-user data leakage. When a user requests a
  resource they are not authorized to view, HTTP 404 is returned instead of 403 to avoid
  confirming the existence of other users' private resources.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from backend.app.core.security import SESSION_COOKIE_NAME, hash_session_token
from backend.app.db.session import get_db
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseMember
from backend.app.models.user import User, UserRole, UserSession

# Type alias for database session dependency
DatabaseSession = Annotated[Session, Depends(get_db)]


def get_current_user_optional(
    request: Request,
    db: DatabaseSession,
) -> User | None:
    """
    Resolve the current user from an active session if present.
    Extracts raw session token from the HttpOnly cookie or Authorization Bearer header,
    computes its SHA-256 hash, and verifies session validity in PostgreSQL.
    """
    raw_token: str | None = request.cookies.get(SESSION_COOKIE_NAME)

    # Fallback to Authorization: Bearer <token> for automated API test clients
    if not raw_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            raw_token = auth_header[7:].strip()

    if not raw_token:
        return None

    token_hash = hash_session_token(raw_token)
    now = datetime.now(UTC)

    stmt = select(UserSession).where(
        and_(
            UserSession.session_token_hash == token_hash,
            UserSession.expires_at > now,
        )
    )
    session_record = db.execute(stmt).scalar_one_or_none()

    if not session_record:
        return None

    # Retrieve user and verify active status
    user_stmt = select(User).where(User.id == session_record.user_id)
    user = db.execute(user_stmt).scalar_one_or_none()

    if not user or not user.is_active:
        return None

    return user


# Type alias for optional user
OptionalCurrentUser = Annotated[User | None, Depends(get_current_user_optional)]


def require_authenticated_user(
    current_user: OptionalCurrentUser,
) -> User:
    """
    Ensure the request originates from an authenticated, active user.
    Raises HTTP 401 Unauthorized if unauthenticated.
    """
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


# Type alias for required authenticated user
AuthenticatedUser = Annotated[User, Depends(require_authenticated_user)]


def require_admin(
    current_user: AuthenticatedUser,
) -> User:
    """
    Ensure the authenticated user holds the ADMIN role.
    Raises HTTP 403 Forbidden if a STUDENT attempts access.
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required for this operation.",
        )
    return current_user


# Type alias for required admin user
AuthenticatedAdmin = Annotated[User, Depends(require_admin)]


def require_student_or_admin(
    current_user: AuthenticatedUser,
) -> User:
    """
    Ensure the authenticated user holds a recognized role (STUDENT or ADMIN).
    """
    return current_user


def get_authorized_knowledge_base(
    kb_id: uuid.UUID,
    current_user: AuthenticatedUser,
    db: DatabaseSession,
) -> KnowledgeBase:
    """
    Retrieve a knowledge base ensuring strict multi-user access isolation.

    Access Rules:
    - ADMIN: Can access knowledge bases they created.
    - STUDENT: Can only access knowledge bases where explicit membership was granted.
    - If unauthorized: Returns HTTP 404 to avoid leaking knowledge base existence.
    """
    if current_user.role == UserRole.ADMIN:
        # Admin can view knowledge bases they own/manage
        stmt = select(KnowledgeBase).where(
            and_(
                KnowledgeBase.id == kb_id,
                KnowledgeBase.created_by_id == current_user.id,
            )
        )
        kb = db.execute(stmt).scalar_one_or_none()
    else:
        # Student access requires explicit membership grant
        stmt = (
            select(KnowledgeBase)
            .join(
                KnowledgeBaseMember,
                KnowledgeBase.id == KnowledgeBaseMember.knowledge_base_id,
            )
            .where(
                and_(
                    KnowledgeBase.id == kb_id,
                    KnowledgeBaseMember.user_id == current_user.id,
                )
            )
        )
        kb = db.execute(stmt).scalar_one_or_none()

    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found.",
        )

    return kb


def require_knowledge_base_admin(
    kb_id: uuid.UUID,
    current_user: AuthenticatedAdmin,
    db: DatabaseSession,
) -> KnowledgeBase:
    """
    Ensure the current user is an ADMIN with management rights over this specific knowledge base.
    """
    stmt = select(KnowledgeBase).where(
        and_(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.created_by_id == current_user.id,
        )
    )
    kb = db.execute(stmt).scalar_one_or_none()
    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found.",
        )
    return kb
