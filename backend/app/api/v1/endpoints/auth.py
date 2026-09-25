"""
Authentication Endpoints.

Handles user registration, login, logout, and authenticated user identity retrieval.

Security Rules:
- Public registration strictly provisions STUDENT roles only. Extra fields are rejected.
- Passwords are validated and hashed using Argon2id.
- On login, a cryptographically secure token is generated, its SHA-256 hash is saved to PostgreSQL,
  and the raw token is returned in an HttpOnly cookie.
- Passwords and raw session tokens are never logged.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import and_, delete, func, select
from sqlalchemy.orm import Session

from backend.app.api.deps import (
    AuthenticatedAdmin,
    AuthenticatedUser,
    DatabaseSession,
    RateLimitAuthLogin,
    RateLimitAuthRegister,
    check_user_permission,
    is_main_admin,
)
from backend.app.core.config import settings
from backend.app.core.permissions import Permission
from backend.app.core.security import (
    SESSION_COOKIE_NAME,
    generate_session_token,
    get_password_hash,
    get_session_cookie_kwargs,
    hash_session_token,
    verify_dummy_password,
    verify_password,
)
from backend.app.models.user import AdminRole, User, UserRole, UserSession
from backend.app.schemas.auth import (
    AdminCreateRequest,
    AdminPermissionsUpdateRequest,
    AdminUserResponse,
    SessionResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new student account",
)
def register(
    payload: UserRegisterRequest,
    db: DatabaseSession,
    _rate_limit: RateLimitAuthRegister,
) -> UserResponse:
    """
    Register a new user account.
    CRITICAL SECURITY ENFORCEMENT:
    Public registration ALWAYS provisions a STUDENT account.
    Clients cannot specify, request, or escalate to ADMIN role.
    """
    clean_email = payload.email.strip().lower()

    # Check for existing account
    stmt = select(User).where(User.email == clean_email)
    existing_user = db.execute(stmt).scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    # Hash password with Argon2id
    password_hash = get_password_hash(payload.password)

    # Instantiate user with STUDENT role strictly
    user = User(
        email=clean_email,
        password_hash=password_hash,
        full_name=payload.full_name.strip(),
        role=UserRole.STUDENT,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return UserResponse.model_validate(user)


def authenticate_and_create_session(
    payload: UserLoginRequest,
    response: Response,
    db: Session,
    required_role: UserRole | None = None,
) -> SessionResponse:
    """
    Shared authentication and session creation service.

    Security & Role Decisions:
    - Mitigates timing attacks with dummy Argon2id hash verification on unknown emails.
    - Verifies password against user Argon2id hash before inspecting account role.
    - Rejects inactive accounts with a clear message.
    - If required_role is specified, enforces strict role matching:
      * required_role == UserRole.STUDENT: Rejects ADMIN accounts with HTTP 403:
        "This account belongs to the Administrator Portal. Please use Administrator Sign In."
      * required_role == UserRole.ADMIN: Rejects STUDENT accounts with HTTP 403:
        "This account does not have administrator access. Please use Student Sign In."
    - Session credentials are cryptographically generated and stored exclusively as SHA-256 hashes.
    """
    clean_email = payload.email.strip().lower()

    stmt = select(User).where(User.email == clean_email)
    user = db.execute(stmt).scalar_one_or_none()

    # Timing-difference mitigation: if user does not exist, execute dummy Argon2id verification
    if not user:
        verify_dummy_password(payload.password)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password against Argon2id hash for real user
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive. Please contact an administrator.",
        )

    # Server-side role enforcement for portal-specific authentication
    if required_role is not None:
        if required_role == UserRole.STUDENT and user.role != UserRole.STUDENT:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account belongs to the Administrator Portal. Please use Administrator Sign In.",
            )
        if required_role == UserRole.ADMIN and user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account does not have administrator access. Please use Student Sign In.",
            )

    # Generate secure random token and hash
    raw_token, token_hash = generate_session_token()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # Persist session hash in PostgreSQL (raw token is never stored in DB)
    session_record = UserSession(
        session_token_hash=token_hash,
        user_id=user.id,
        expires_at=expires_at,
    )
    db.add(session_record)
    db.commit()

    # Set secure HttpOnly cookie (raw token is never exposed in response headers)
    cookie_kwargs = get_session_cookie_kwargs(expires_at)
    response.set_cookie(value=raw_token, **cookie_kwargs)

    return SessionResponse(
        user=UserResponse.model_validate(user),
        expires_at=expires_at,
        message="Authenticated successfully",
    )


@router.post(
    "/login",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and establish user session (general/backward-compatible)",
)
def login(
    payload: UserLoginRequest,
    response: Response,
    db: DatabaseSession,
    _rate_limit: RateLimitAuthLogin,
) -> SessionResponse:
    """
    Authenticate user credentials against Argon2id hash.
    Establishes a server-managed session in PostgreSQL and sets an HttpOnly cookie.
    """
    return authenticate_and_create_session(
        payload=payload,
        response=response,
        db=db,
        required_role=None,
    )


@router.post(
    "/login/student",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate student for Student Portal",
)
def student_login(
    payload: UserLoginRequest,
    response: Response,
    db: DatabaseSession,
    _rate_limit: RateLimitAuthLogin,
) -> SessionResponse:
    """
    Authenticate student credentials strictly for the Student Portal.
    Rejects administrative accounts with explicit directional guidance.
    """
    return authenticate_and_create_session(
        payload=payload,
        response=response,
        db=db,
        required_role=UserRole.STUDENT,
    )


@router.post(
    "/login/admin",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate administrator for Administrator Portal",
)
def admin_login(
    payload: UserLoginRequest,
    response: Response,
    db: DatabaseSession,
    _rate_limit: RateLimitAuthLogin,
) -> SessionResponse:
    """
    Authenticate administrator credentials strictly for the Administrator Portal.
    Rejects non-administrator accounts with explicit directional guidance.
    """
    return authenticate_and_create_session(
        payload=payload,
        response=response,
        db=db,
        required_role=UserRole.ADMIN,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Terminate active session and clear cookie",
)
def logout(
    request: Request,
    response: Response,
    db: DatabaseSession,
) -> dict[str, str]:
    """
    Invalidate active session in PostgreSQL and clear the browser cookie.
    """
    raw_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            raw_token = auth_header[7:].strip()

    if raw_token:
        token_hash = hash_session_token(raw_token)
        stmt = select(UserSession).where(UserSession.session_token_hash == token_hash)
        session_record = db.execute(stmt).scalar_one_or_none()
        if session_record:
            db.delete(session_record)
            db.commit()

    # Clear cookie
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=not settings.DEBUG,
    )

    return {"message": "Logged out successfully."}


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get profile of the currently authenticated user",
)
def get_current_user_profile(
    current_user: AuthenticatedUser,
) -> UserResponse:
    """
    Return identity and role of currently authenticated user.
    """
    return UserResponse.model_validate(current_user)


@router.post(
    "/admin",
    response_model=AdminUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new administrator account (ADMIN only)",
)
def create_admin(
    payload: AdminCreateRequest,
    current_user: AuthenticatedAdmin,
    db: DatabaseSession,
) -> AdminUserResponse:
    """
    Provision a new administrator account.
    Restricted strictly to administrators with ADMIN_CREATE permission.
    Only MAIN_ADMIN can create another MAIN_ADMIN.
    """
    if not check_user_permission(current_user, Permission.ADMIN_CREATE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Missing required permission 'ADMIN_CREATE'.",
        )

    # Main Admin role creation policy: only a Main Admin can create another Main Admin
    if payload.admin_role == AdminRole.MAIN_ADMIN and not is_main_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a Main Admin can create another Main Admin account.",
        )

    # Validate permission names if provided
    valid_perms = {p.value for p in Permission}
    for perm in payload.permissions:
        if perm not in valid_perms:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid permission: '{perm}'.",
            )

    clean_email = payload.email.strip().lower()

    stmt = select(User).where(User.email == clean_email)
    existing_user = db.execute(stmt).scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    password_hash = get_password_hash(payload.password)

    user = User(
        email=clean_email,
        password_hash=password_hash,
        full_name=payload.full_name.strip(),
        role=UserRole.ADMIN,
        admin_role=payload.admin_role,
        permissions=payload.permissions if payload.admin_role == AdminRole.FACULTY_ADMIN else [],
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return AdminUserResponse.model_validate(user)


@router.get(
    "/admins",
    response_model=list[AdminUserResponse],
    status_code=status.HTTP_200_OK,
    summary="List all administrator accounts (ADMIN only)",
)
def list_admins(
    current_user: AuthenticatedAdmin,
    db: DatabaseSession,
) -> list[AdminUserResponse]:
    """
    List all administrator accounts.
    Restricted strictly to administrators with ADMIN_VIEW permission.
    """
    if not check_user_permission(current_user, Permission.ADMIN_VIEW):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Missing required permission 'ADMIN_VIEW'.",
        )

    stmt = select(User).where(User.role == UserRole.ADMIN).order_by(User.created_at.desc())
    admins = db.execute(stmt).scalars().all()
    return [AdminUserResponse.model_validate(a) for a in admins]


@router.patch(
    "/admins/{admin_id}/permissions",
    response_model=AdminUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update permissions for a faculty administrator",
)
def update_admin_permissions(
    admin_id: uuid.UUID,
    payload: AdminPermissionsUpdateRequest,
    current_user: AuthenticatedAdmin,
    db: DatabaseSession,
) -> AdminUserResponse:
    """
    Update permissions for a faculty administrator.
    Requires ADMIN_PERMISSION_MANAGE permission.
    Faculty admins cannot modify their own permissions.
    """
    if not check_user_permission(current_user, Permission.ADMIN_PERMISSION_MANAGE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Missing required permission 'ADMIN_PERMISSION_MANAGE'.",
        )

    target = db.execute(
        select(User).where(and_(User.id == admin_id, User.role == UserRole.ADMIN))
    ).scalar_one_or_none()

    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Administrator not found.",
        )

    # Prevent faculty admin self-escalation
    if target.id == current_user.id and not is_main_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Faculty administrators cannot modify their own permissions.",
        )

    # Validate permission names
    valid_perms = {p.value for p in Permission}
    for perm in payload.permissions:
        if perm not in valid_perms:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid permission: '{perm}'.",
            )

    target.permissions = payload.permissions
    db.commit()
    db.refresh(target)
    return AdminUserResponse.model_validate(target)


@router.patch(
    "/admins/{admin_id}/deactivate",
    response_model=AdminUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate an administrator account",
)
def deactivate_admin(
    admin_id: uuid.UUID,
    current_user: AuthenticatedAdmin,
    db: DatabaseSession,
) -> AdminUserResponse:
    """
    Deactivate an administrator account.
    Requires ADMIN_EDIT permission.
    Admins cannot deactivate themselves.
    The final active Main Admin cannot be deactivated.
    """
    if not check_user_permission(current_user, Permission.ADMIN_EDIT):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Missing required permission 'ADMIN_EDIT'.",
        )

    target = db.execute(
        select(User).where(and_(User.id == admin_id, User.role == UserRole.ADMIN))
    ).scalar_one_or_none()

    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Administrator not found.",
        )

    # Safety Rule 1: Admin cannot deactivate itself
    if target.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot deactivate their own account.",
        )

    # Safety Rule 3 & 5: The final active MAIN_ADMIN cannot be deactivated
    if is_main_admin(target):
        active_main_admins_count = db.execute(
            select(func.count(User.id)).where(
                and_(
                    User.role == UserRole.ADMIN,
                    User.admin_role == AdminRole.MAIN_ADMIN,
                    User.is_active.is_(True),
                )
            )
        ).scalar_one()

        if active_main_admins_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate the final active Main Admin account. At least one active Main Admin must remain.",
            )

    target.is_active = False

    # Revoke all active sessions for deactivated admin
    db.execute(delete(UserSession).where(UserSession.user_id == target.id))
    db.commit()
    db.refresh(target)
    return AdminUserResponse.model_validate(target)


@router.patch(
    "/admins/{admin_id}/activate",
    response_model=AdminUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Reactivate an administrator account",
)
def activate_admin(
    admin_id: uuid.UUID,
    current_user: AuthenticatedAdmin,
    db: DatabaseSession,
) -> AdminUserResponse:
    """
    Reactivate an administrator account.
    Requires ADMIN_EDIT permission.
    """
    if not check_user_permission(current_user, Permission.ADMIN_EDIT):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Missing required permission 'ADMIN_EDIT'.",
        )

    target = db.execute(
        select(User).where(and_(User.id == admin_id, User.role == UserRole.ADMIN))
    ).scalar_one_or_none()

    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Administrator not found.",
        )

    target.is_active = True
    db.commit()
    db.refresh(target)
    return AdminUserResponse.model_validate(target)


@router.delete(
    "/admins/{admin_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete an administrator account",
)
def delete_admin(
    admin_id: uuid.UUID,
    current_user: AuthenticatedAdmin,
    db: DatabaseSession,
) -> dict[str, str]:
    """
    Delete an administrator account.
    Requires ADMIN_DELETE permission.
    Admins cannot delete themselves.
    The final Main Admin cannot be deleted.
    """
    if not check_user_permission(current_user, Permission.ADMIN_DELETE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Missing required permission 'ADMIN_DELETE'.",
        )

    target = db.execute(
        select(User).where(and_(User.id == admin_id, User.role == UserRole.ADMIN))
    ).scalar_one_or_none()

    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Administrator not found.",
        )

    # Safety Rule 2: Admin cannot delete itself
    if target.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot delete their own account.",
        )

    # Safety Rule 4 & 5: The final MAIN_ADMIN cannot be deleted
    if is_main_admin(target):
        total_main_admins_count = db.execute(
            select(func.count(User.id)).where(
                and_(
                    User.role == UserRole.ADMIN,
                    User.admin_role == AdminRole.MAIN_ADMIN,
                )
            )
        ).scalar_one()

        if total_main_admins_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the final Main Admin account. At least one Main Admin must exist.",
            )

    # Delete sessions and user record
    db.execute(delete(UserSession).where(UserSession.user_id == target.id))
    db.delete(target)
    db.commit()

    return {
        "status": "deleted",
        "admin_id": str(admin_id),
        "message": "Administrator account deleted successfully.",
    }
