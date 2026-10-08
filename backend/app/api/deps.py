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
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.permissions import Permission
from backend.app.core.rate_limit import (
    RateLimitPolicy,
    RateLimitResult,
    build_rate_limit_key,
    get_client_ip,
    get_rate_limiter,
)
from backend.app.core.security import SESSION_COOKIE_NAME, hash_session_token
from backend.app.db.session import get_db
from backend.app.models.document import Document
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseMember
from backend.app.models.user import AdminRole, User, UserRole, UserSession

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


DEFAULT_OPERATIONAL_PERMISSIONS: set[str] = {
    Permission.COURSE_VIEW.value,
    Permission.COURSE_CREATE.value,
    Permission.COURSE_EDIT.value,
    Permission.COURSE_DELETE.value,
    Permission.DOCUMENT_VIEW.value,
    Permission.DOCUMENT_UPLOAD.value,
    Permission.DOCUMENT_DELETE.value,
    Permission.DOCUMENT_PUBLISH.value,
    Permission.DOCUMENT_INDEX.value,
    Permission.DOCUMENT_INDEX_RETRY.value,
    Permission.ADMIN_CHAT.value,
    Permission.ADMIN_VIEW.value,
    Permission.ADMIN_CREATE.value,
}


def is_main_admin(user: User) -> bool:
    """Check if the user is a MAIN_ADMIN."""
    if user.role != UserRole.ADMIN:
        return False
    role_val = getattr(user, "admin_role", None)
    return role_val == AdminRole.MAIN_ADMIN or str(role_val) in (
        "MAIN_ADMIN",
        "AdminRole.MAIN_ADMIN",
    )


def check_user_permission(user: User, permission: Permission | str) -> bool:
    """
    Check if an authenticated user possesses the specified permission.
    - MAIN_ADMIN: Inherently has ALL permissions.
    - FACULTY_ADMIN: Strictly evaluated against user.permissions list.
    - Legacy / unassigned ADMIN: Has standard operational permissions for courses and documents.
    - STUDENT: Has no admin permissions.
    """
    if not user.is_active:
        return False
    if user.role != UserRole.ADMIN:
        return False
    if is_main_admin(user):
        return True

    perm_val = permission.value if isinstance(permission, Permission) else str(permission)
    role_val = getattr(user, "admin_role", None)

    # Faculty Admins with explicit role are strictly checked against assigned permissions
    if role_val == AdminRole.FACULTY_ADMIN or str(role_val) in (
        "FACULTY_ADMIN",
        "AdminRole.FACULTY_ADMIN",
    ):
        user_perms = user.permissions or []
        return perm_val in user_perms

    # Legacy / unassigned admin: check permissions or fallback to default operational permissions
    user_perms = user.permissions or []
    if user_perms:
        return perm_val in user_perms
    return perm_val in DEFAULT_OPERATIONAL_PERMISSIONS


def require_permission(permission: Permission):
    """
    FastAPI dependency factory enforcing server-side permission checks.
    """

    def _dependency(current_user: AuthenticatedAdmin) -> User:
        if not check_user_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Missing required permission '{permission.value}'.",
            )
        return current_user

    return _dependency


def require_student_or_admin(
    current_user: AuthenticatedUser,
) -> User:
    """
    Ensure the authenticated user holds a recognized role (STUDENT or ADMIN).
    """
    return current_user


def get_authorized_knowledge_bases(
    current_user: User,
    db: Session,
) -> list[KnowledgeBase]:
    """Return the canonical course set authorized for the current user.

    This is the single course-visibility rule used by dashboards, course lists,
    chat selectors, and global retrieval:
    - MAIN_ADMIN: every course.
    - FACULTY_ADMIN: courses they created or were explicitly assigned.
    - STUDENT: all courses/folders marked active or published by default.
    """
    user_id_val = current_user.id
    if isinstance(user_id_val, str):
        try:
            user_id_val = uuid.UUID(user_id_val)
        except (ValueError, AttributeError):
            pass

    role_val = getattr(current_user, "role", None)
    if hasattr(role_val, "value"):
        role_val = role_val.value
    role_str = str(role_val).upper() if role_val is not None else ""

    if role_str == "STUDENT" or role_val == UserRole.STUDENT:
        # Authoritative catalog policy:
        # - Any course that is active and student_visible is accessible to all students.
        # - Any active restricted course where the student has explicit membership is accessible.
        # - Inactive courses are strictly excluded.
        stmt = (
            select(KnowledgeBase)
            .outerjoin(
                KnowledgeBaseMember,
                and_(
                    KnowledgeBase.id == KnowledgeBaseMember.knowledge_base_id,
                    KnowledgeBaseMember.user_id == user_id_val,
                ),
            )
            .where(
                and_(
                    KnowledgeBase.is_active.is_(True),
                    or_(
                        KnowledgeBase.is_student_visible.is_(True),
                        KnowledgeBaseMember.user_id == user_id_val,
                    ),
                )
            )
            .distinct()
            .order_by(KnowledgeBase.created_at.desc())
        )
        return list(db.execute(stmt).scalars().all())

    if role_str == "ADMIN" or role_val == UserRole.ADMIN:
        if is_main_admin(current_user):
            stmt = select(KnowledgeBase).order_by(KnowledgeBase.created_at.desc())
        else:
            stmt = (
                select(KnowledgeBase)
                .outerjoin(
                    KnowledgeBaseMember,
                    KnowledgeBase.id == KnowledgeBaseMember.knowledge_base_id,
                )
                .where(
                    or_(
                        KnowledgeBase.created_by_id == user_id_val,
                        KnowledgeBaseMember.user_id == user_id_val,
                    )
                )
                .distinct()
                .order_by(KnowledgeBase.created_at.desc())
            )
        return list(db.execute(stmt).scalars().all())

    # Fallback default: all active/published courses without membership restriction
    stmt = select(KnowledgeBase)
    if "is_active" in KnowledgeBase.__table__.columns:
        stmt = stmt.where(KnowledgeBase.is_active.is_(True))
    elif "is_published" in KnowledgeBase.__table__.columns:
        stmt = stmt.where(KnowledgeBase.is_published.is_(True))
    stmt = stmt.order_by(KnowledgeBase.created_at.desc())
    return list(db.execute(stmt).scalars().all())


def get_authorized_document(
    document_id: uuid.UUID,
    current_user: User,
    db: Session,
    knowledge_base_id: uuid.UUID | None = None,
) -> Document:
    """Return one document only when its course and publication are authorized.

    Students can only see/query published documents in courses they are enrolled
    in. Administrators may inspect inactive/unindexed documents when their
    course/document permissions allow it. A supplied course ID is always
    checked against the document's actual parent course to prevent ID tampering.
    """
    doc = db.execute(select(Document).where(Document.id == document_id)).scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    if knowledge_base_id is not None and doc.knowledge_base_id != knowledge_base_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    # Course authorization is authoritative and intentionally returns 404 for
    # unauthorized resources to avoid leaking private course/document existence.
    get_authorized_knowledge_base(
        kb_id=doc.knowledge_base_id,
        current_user=current_user,
        db=db,
    )

    if current_user.role == UserRole.STUDENT and not doc.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    return doc


def get_authorized_knowledge_base(
    kb_id: uuid.UUID | str,
    current_user: AuthenticatedUser,
    db: DatabaseSession,
) -> KnowledgeBase:
    """
    Retrieve a knowledge base ensuring strict multi-user access isolation.

    Access Rules:
    - MAIN_ADMIN: Can access any knowledge base in the system.
    - FACULTY_ADMIN: Can access knowledge bases they created or where they were granted membership.
    - STUDENT: Can access any active or published knowledge base as long as the course exists.
    - If unauthorized: Returns HTTP 404 to avoid leaking knowledge base existence.
    """
    if isinstance(kb_id, str):
        try:
            kb_id = uuid.UUID(kb_id)
        except (ValueError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge base not found.",
            ) from None

    role_val = getattr(current_user, "role", None)
    if hasattr(role_val, "value"):
        role_val = role_val.value
    role_str = str(role_val).upper() if role_val is not None else ""

    if role_str == "STUDENT" or role_val == UserRole.STUDENT:
        # Student access: active student-visible courses by default, or active restricted courses with membership
        stmt = (
            select(KnowledgeBase)
            .outerjoin(
                KnowledgeBaseMember,
                and_(
                    KnowledgeBase.id == KnowledgeBaseMember.knowledge_base_id,
                    KnowledgeBaseMember.user_id == current_user.id,
                ),
            )
            .where(
                and_(
                    KnowledgeBase.id == kb_id,
                    KnowledgeBase.is_active.is_(True),
                    or_(
                        KnowledgeBase.is_student_visible.is_(True),
                        KnowledgeBaseMember.user_id == current_user.id,
                    ),
                )
            )
        )
        kb = db.execute(stmt).scalar_one_or_none()
    elif role_str == "ADMIN" or role_val == UserRole.ADMIN:
        if is_main_admin(current_user):
            stmt = select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
        else:
            # Faculty Admin: creator or member
            stmt = (
                select(KnowledgeBase)
                .outerjoin(
                    KnowledgeBaseMember,
                    KnowledgeBase.id == KnowledgeBaseMember.knowledge_base_id,
                )
                .where(
                    and_(
                        KnowledgeBase.id == kb_id,
                        or_(
                            KnowledgeBase.created_by_id == current_user.id,
                            KnowledgeBaseMember.user_id == current_user.id,
                        ),
                    )
                )
            )
        kb = db.execute(stmt).scalar_one_or_none()
    else:
        stmt = select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
        if "is_active" in KnowledgeBase.__table__.columns:
            stmt = stmt.where(KnowledgeBase.is_active.is_(True))
        elif "is_published" in KnowledgeBase.__table__.columns:
            stmt = stmt.where(KnowledgeBase.is_published.is_(True))
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
    - MAIN_ADMIN: Can manage all knowledge bases.
    - FACULTY_ADMIN: Can manage knowledge bases they created or where they were granted membership.
    """
    if is_main_admin(current_user):
        stmt = select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
    else:
        stmt = (
            select(KnowledgeBase)
            .outerjoin(
                KnowledgeBaseMember,
                KnowledgeBase.id == KnowledgeBaseMember.knowledge_base_id,
            )
            .where(
                and_(
                    KnowledgeBase.id == kb_id,
                    or_(
                        KnowledgeBase.created_by_id == current_user.id,
                        KnowledgeBaseMember.user_id == current_user.id,
                    ),
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


def get_authorized_knowledge_base_ids(
    current_user: User,
    db: Session,
) -> list[uuid.UUID]:
    """Return UUIDs from the canonical course authorization mechanism."""
    return [kb.id for kb in get_authorized_knowledge_bases(current_user, db)]


# =============================================================================
# Rate Limiting & Abuse Protection Dependencies (Step 18)
# =============================================================================


def check_rate_limit_auth_login(request: Request) -> RateLimitResult:
    """Rate-limit check for unauthenticated login attempts (IP-based, Fail-Closed)."""
    client_ip = get_client_ip(request)
    key = build_rate_limit_key("ip", client_ip, "auth_login")
    policy = RateLimitPolicy(
        name="auth_login",
        max_requests=settings.RATE_LIMIT_LOGIN_MAX_REQUESTS,
        window_seconds=settings.RATE_LIMIT_LOGIN_WINDOW_SECONDS,
        fail_closed=settings.RATE_LIMIT_AUTH_FAIL_CLOSED,
    )
    return get_rate_limiter().check(key=key, policy=policy, request=request)


def check_rate_limit_auth_register(request: Request) -> RateLimitResult:
    """Rate-limit check for unauthenticated registration attempts (IP-based, Fail-Closed)."""
    client_ip = get_client_ip(request)
    key = build_rate_limit_key("ip", client_ip, "auth_register")
    policy = RateLimitPolicy(
        name="auth_register",
        max_requests=settings.RATE_LIMIT_REGISTER_MAX_REQUESTS,
        window_seconds=settings.RATE_LIMIT_REGISTER_WINDOW_SECONDS,
        fail_closed=settings.RATE_LIMIT_AUTH_FAIL_CLOSED,
    )
    return get_rate_limiter().check(key=key, policy=policy, request=request)


def check_rate_limit_chat(
    current_user: AuthenticatedUser,
    request: Request,
) -> RateLimitResult:
    """
    Rate-limit check for authenticated chat RAG operations.
    Strict Ordering: Depends on AuthenticatedUser first, ensuring unauthenticated
    requests return 401 without consuming any user quota.
    """
    key = build_rate_limit_key("user", str(current_user.id), "chat")
    policy = RateLimitPolicy(
        name="chat",
        max_requests=settings.RATE_LIMIT_CHAT_MAX_REQUESTS,
        window_seconds=settings.RATE_LIMIT_CHAT_WINDOW_SECONDS,
        fail_closed=settings.RATE_LIMIT_EXPENSIVE_FAIL_CLOSED,
    )
    return get_rate_limiter().check(
        key=key,
        policy=policy,
        request=request,
        user_id=str(current_user.id),
    )


def check_rate_limit_retrieval(
    current_user: AuthenticatedUser,
    request: Request,
) -> RateLimitResult:
    """
    Rate-limit check for authenticated vector/lexical/hybrid/rerank operations.
    Strict Ordering: Evaluates AuthenticatedUser first before quota deduction.
    """
    key = build_rate_limit_key("user", str(current_user.id), "retrieval")
    policy = RateLimitPolicy(
        name="retrieval",
        max_requests=settings.RATE_LIMIT_RETRIEVAL_MAX_REQUESTS,
        window_seconds=settings.RATE_LIMIT_RETRIEVAL_WINDOW_SECONDS,
        fail_closed=settings.RATE_LIMIT_EXPENSIVE_FAIL_CLOSED,
    )
    return get_rate_limiter().check(
        key=key,
        policy=policy,
        request=request,
        user_id=str(current_user.id),
    )


def check_rate_limit_upload(
    current_user: AuthenticatedAdmin,
    request: Request,
) -> RateLimitResult:
    """
    Rate-limit check for document upload operations.
    Strict Ordering: Evaluates AuthenticatedAdmin first before quota deduction.
    """
    key = build_rate_limit_key("user", str(current_user.id), "upload")
    policy = RateLimitPolicy(
        name="upload",
        max_requests=settings.RATE_LIMIT_UPLOAD_MAX_REQUESTS,
        window_seconds=settings.RATE_LIMIT_UPLOAD_WINDOW_SECONDS,
        fail_closed=settings.RATE_LIMIT_EXPENSIVE_FAIL_CLOSED,
    )
    return get_rate_limiter().check(
        key=key,
        policy=policy,
        request=request,
        user_id=str(current_user.id),
    )


def check_rate_limit_indexing(
    current_user: AuthenticatedAdmin,
    request: Request,
) -> RateLimitResult:
    """
    Rate-limit check for document indexing operations.
    Strict Ordering: Evaluates AuthenticatedAdmin first before quota deduction.
    """
    key = build_rate_limit_key("user", str(current_user.id), "indexing")
    policy = RateLimitPolicy(
        name="indexing",
        max_requests=settings.RATE_LIMIT_INDEXING_MAX_REQUESTS,
        window_seconds=settings.RATE_LIMIT_INDEXING_WINDOW_SECONDS,
        fail_closed=settings.RATE_LIMIT_EXPENSIVE_FAIL_CLOSED,
    )
    return get_rate_limiter().check(
        key=key,
        policy=policy,
        request=request,
        user_id=str(current_user.id),
    )


RateLimitAuthLogin = Annotated[RateLimitResult, Depends(check_rate_limit_auth_login)]
RateLimitAuthRegister = Annotated[RateLimitResult, Depends(check_rate_limit_auth_register)]
RateLimitChat = Annotated[RateLimitResult, Depends(check_rate_limit_chat)]
RateLimitRetrieval = Annotated[RateLimitResult, Depends(check_rate_limit_retrieval)]
RateLimitUpload = Annotated[RateLimitResult, Depends(check_rate_limit_upload)]
RateLimitIndexing = Annotated[RateLimitResult, Depends(check_rate_limit_indexing)]
