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

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from backend.app.api.deps import (
    AuthenticatedUser,
    DatabaseSession,
    RateLimitAuthLogin,
    RateLimitAuthRegister,
)
from backend.app.core.config import settings
from backend.app.core.security import (
    SESSION_COOKIE_NAME,
    generate_session_token,
    get_password_hash,
    get_session_cookie_kwargs,
    hash_session_token,
    verify_dummy_password,
    verify_password,
)
from backend.app.models.user import User, UserRole, UserSession
from backend.app.schemas.auth import (
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


@router.post(
    "/login",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and establish user session",
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
