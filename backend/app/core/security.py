"""
Security and Cryptography Services.

Provides Argon2id password hashing, verification, cryptographically secure
session token generation, and token SHA-256 hashing.

Security Decisions:
- Password hashing uses Argon2id with 64MB memory, 3 iterations, and 4 parallel threads,
  which provides state-of-the-art resistance against GPU/ASIC cracking attacks.
- Session tokens are generated using the OS CSPRNG (secrets.token_urlsafe).
- Only SHA-256 hashes of session tokens are stored in the database. If the database
  is compromised, raw credentials cannot be stolen to impersonate active users.
- Raw session tokens are never logged.
"""

import hashlib
import secrets
from datetime import datetime
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from backend.app.core.config import settings

# Argon2id password hasher instance configured with recommended OWASP parameters
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

SESSION_COOKIE_NAME = "session_id"


def get_password_hash(password: str) -> str:
    """
    Hash a plaintext password using Argon2id.
    Never stores or logs the plain password.
    """
    if not password:
        raise ValueError("Password cannot be empty.")
    return _hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against an Argon2id hash.
    Returns False on mismatch or corrupted hash format without leaking exception details.
    """
    if not plain_password or not hashed_password:
        return False
    try:
        return _hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def hash_session_token(raw_token: str) -> str:
    """
    Compute SHA-256 hex digest of a raw session token.
    This digest is what gets stored and queried in PostgreSQL.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_session_token() -> tuple[str, str]:
    """
    Generate a cryptographically secure session token and its SHA-256 digest.

    Returns:
        tuple[raw_token, token_hash_hex]:
        - raw_token: sent to browser via HttpOnly cookie.
        - token_hash_hex: stored in PostgreSQL user_sessions table.
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_session_token(raw_token)
    return raw_token, token_hash


def get_session_cookie_kwargs(expires_at: datetime) -> dict[str, Any]:
    """
    Standard security flags for session cookies.
    Enforces HttpOnly, SameSite=Lax, and conditional Secure flag.
    """
    return {
        "key": SESSION_COOKIE_NAME,
        "httponly": True,
        "samesite": "lax",
        "secure": not settings.DEBUG,  # True in production HTTPS, False for local HTTP
        "expires": expires_at,
        "path": "/",
    }
