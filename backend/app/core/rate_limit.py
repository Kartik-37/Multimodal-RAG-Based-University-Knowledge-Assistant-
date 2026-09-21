"""
Core Rate Limiting and Abuse Protection Framework.

Provides:
- Strict server-side rate-limiting abstraction with endpoint-specific policies.
- Authoritative PostgreSQL-backed storage using atomic row-level conflict upserts
  (INSERT ... ON CONFLICT DO UPDATE RETURNING count), preventing race conditions.
- Thread-safe in-memory storage for unit testing and offline verification.
- Anti-spoofing client IP resolution strictly rejecting untrusted forwarded headers.
- Safe HTTP 429 Too Many Requests responses with Retry-After header.
- Security failure policies: Fail-Closed for authentication vs Fail-Open for standard RAG.
- Integration with Step 17 Telemetry framework.
"""

import ipaddress
import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.app.core.config import settings
from backend.app.core.telemetry import (
    get_current_kb_id,
    get_current_user_id,
    get_request_id,
    get_telemetry_manager,
)
from backend.app.schemas.telemetry import TelemetryEvent

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# 1. Rate Limiting Domain Models & Exceptions
# -------------------------------------------------------------------------


class RateLimitError(Exception):
    """Base exception for rate limiting subsystem."""

    pass


class RateLimitStorageError(RateLimitError):
    """Raised when the rate limit backend storage is unavailable or fails."""

    pass


@dataclass(frozen=True)
class RateLimitPolicy:
    """
    Configuration policy defining request quotas and windows for an endpoint.

    Invariants:
    - name: Unique policy identifier.
    - max_requests: Maximum allowed requests within window (>= 1).
    - window_seconds: Duration of the rate-limiting window in seconds (>= 1).
    - fail_closed: Whether storage failures reject requests (True) or allow (False).
    """

    name: str
    max_requests: int
    window_seconds: int
    fail_closed: bool = False

    def __post_init__(self) -> None:
        if self.max_requests < 1:
            raise ValueError(f"max_requests must be at least 1, got {self.max_requests}")
        if self.window_seconds < 1:
            raise ValueError(f"window_seconds must be at least 1, got {self.window_seconds}")


@dataclass(frozen=True)
class RateLimitResult:
    """
    Evaluation outcome of a rate-limit check.

    Invariants:
    - allowed: True if request is within quota, False if exceeded.
    - current_count: Number of requests recorded in the active window.
    - limit: Configured maximum requests.
    - remaining: Remaining allowed requests (>= 0).
    - retry_after: Seconds until the current window resets (0 if allowed).
    - window_seconds: Configured window duration.
    - reset_epoch: Unix epoch timestamp when the current window expires.
    """

    allowed: bool
    current_count: int
    limit: int
    remaining: int
    retry_after: int
    window_seconds: int
    reset_epoch: int


# -------------------------------------------------------------------------
# 2. Client IP Resolution & Anti-Spoofing
# -------------------------------------------------------------------------


def get_client_ip(request: Request, trusted_proxies: set[str] | None = None) -> str:
    """
    Deterministically resolve client IP address with anti-spoofing guarantees.

    Security Rules:
    1. Direct peer IP (request.client.host) is the only trusted source by default.
    2. Headers like X-Forwarded-For or Client-IP are COMPLETELY IGNORED unless
       the direct peer IP is in the explicit trusted_proxies allowlist.
    3. If peer is trusted, parses X-Forwarded-For from right to left, selecting
       the first untrusted IP to prevent header injection.
    4. Validates IP syntax to prevent injection attacks into rate-limit keys.
    """
    proxies = trusted_proxies if trusted_proxies is not None else settings.TRUSTED_PROXIES

    peer_ip = request.client.host if request.client and request.client.host else "127.0.0.1"

    # If direct peer is not in trusted proxies, NEVER trust client-supplied headers
    if peer_ip not in proxies:
        return peer_ip

    # Peer is a trusted reverse proxy; safely inspect X-Forwarded-For
    forwarded_for = request.headers.get("X-Forwarded-For")
    if not forwarded_for:
        return peer_ip

    # Split comma-separated chain
    hops = [h.strip() for h in forwarded_for.split(",") if h.strip()]
    if not hops:
        return peer_ip

    # Walk from right (nearest to proxy) to left to find first non-proxy client IP
    for hop in reversed(hops):
        try:
            # Validate IP format
            ip_obj = ipaddress.ip_address(hop)
            hop_str = str(ip_obj)
            if hop_str not in proxies:
                return hop_str
        except ValueError:
            # Malformed IP address; continue or fallback
            continue

    return peer_ip


def build_rate_limit_key(prefix: str, identifier: str, policy_name: str) -> str:
    """
    Construct a collision-resistant rate-limit key.

    Format: <prefix>:<identifier>:<policy_name>
    Examples:
    - 'ip:192.168.1.50:auth_login'
    - 'user:123e4567-e89b-12d3-a456-426614174000:chat'
    """
    clean_id = identifier.strip().lower()
    return f"{prefix}:{clean_id}:{policy_name}"


# -------------------------------------------------------------------------
# 3. Rate Limit Storage Abstraction
# -------------------------------------------------------------------------


class BaseRateLimitStorage(ABC):
    """Abstract interface for rate-limit state backends."""

    @abstractmethod
    def check_and_consume(self, key: str, policy: RateLimitPolicy) -> RateLimitResult:
        """
        Atomically increment counter for key in the active window and evaluate policy.

        Must guarantee race-condition freedom under concurrent requests.
        """
        pass

    @abstractmethod
    def reset(self, key: str) -> None:
        """Reset rate-limit counter for a given key (useful for tests)."""
        pass

    @abstractmethod
    def cleanup_expired(self, before: datetime | None = None) -> int:
        """Prune expired window records and return count of deleted records."""
        pass


class PostgresRateLimitStorage(BaseRateLimitStorage):
    """
    Authoritative PostgreSQL-backed rate limit storage.

    Concurrency Design:
    Uses PostgreSQL row-level locks during ON CONFLICT DO UPDATE:
    INSERT INTO rate_limit_entries (key, window_bucket, count, expires_at, created_at, updated_at)
    VALUES (:key, :window_bucket, 1, :expires_at, now(), now())
    ON CONFLICT (key, window_bucket)
    DO UPDATE SET count = rate_limit_entries.count + 1, updated_at = now()
    RETURNING count;

    Because PostgreSQL acquires a row-level write lock on the conflicting row,
    simultaneous requests are serialized deterministically with zero read-then-write
    race conditions. Each concurrent transaction observes a distinct, monotonically
    incremented count.

    Transaction Isolation:
    Executes in a dedicated short-lived connection committing immediately via engine.connect(),
    ensuring that business transaction rollbacks or HTTP 429 exceptions cannot rollback
    rate-limit counter increments.
    """

    def __init__(self, db_engine: Any = None) -> None:
        self._engine = db_engine

    def _get_engine(self) -> Any:
        if self._engine is not None:
            return self._engine
        # Dynamic import to respect test fixture engine rebinding
        from backend.app.db.session import engine

        return engine

    def check_and_consume(self, key: str, policy: RateLimitPolicy) -> RateLimitResult:
        now_ts = time.time()
        window_bucket = int(now_ts // policy.window_seconds)
        window_end_ts = (window_bucket + 1) * policy.window_seconds
        expires_at = datetime.fromtimestamp(
            window_end_ts + policy.window_seconds,
            tz=UTC,
        )

        query = text("""
            INSERT INTO rate_limit_entries (key, window_bucket, count, expires_at, created_at, updated_at)
            VALUES (:key, :window_bucket, 1, :expires_at, now(), now())
            ON CONFLICT (key, window_bucket)
            DO UPDATE SET
                count = rate_limit_entries.count + 1,
                updated_at = now()
            RETURNING count;
        """)

        try:
            with self._get_engine().connect() as conn:
                with conn.begin():
                    result = conn.execute(
                        query,
                        {
                            "key": key,
                            "window_bucket": window_bucket,
                            "expires_at": expires_at,
                        },
                    )
                    count = result.scalar_one()

            allowed = count <= policy.max_requests
            remaining = max(0, policy.max_requests - count)
            retry_after = 0 if allowed else max(1, int(window_end_ts - now_ts))

            return RateLimitResult(
                allowed=allowed,
                current_count=count,
                limit=policy.max_requests,
                remaining=remaining,
                retry_after=retry_after,
                window_seconds=policy.window_seconds,
                reset_epoch=int(window_end_ts),
            )
        except (SQLAlchemyError, Exception) as exc:
            logger.warning(
                "PostgresRateLimitStorage failure for key '%s': %s",
                key,
                exc,
            )
            raise RateLimitStorageError(f"Database rate-limit storage failure: {exc}") from exc

    def reset(self, key: str) -> None:
        try:
            with self._get_engine().connect() as conn:
                with conn.begin():
                    conn.execute(
                        text("DELETE FROM rate_limit_entries WHERE key = :key"),
                        {"key": key},
                    )
        except Exception as exc:
            logger.warning("PostgresRateLimitStorage reset failed: %s", exc)

    def cleanup_expired(self, before: datetime | None = None) -> int:
        threshold = before or datetime.now(UTC)
        try:
            with self._get_engine().connect() as conn:
                with conn.begin():
                    result = conn.execute(
                        text("DELETE FROM rate_limit_entries WHERE expires_at < :threshold"),
                        {"threshold": threshold},
                    )
                    return result.rowcount or 0
        except Exception as exc:
            logger.warning("PostgresRateLimitStorage cleanup failed: %s", exc)
            return 0


class InMemoryRateLimitStorage(BaseRateLimitStorage):
    """
    Thread-safe in-memory rate-limit store for unit tests, offline benchmarking,
    and storage failure simulation.
    """

    def __init__(self) -> None:
        self._counts: dict[tuple[str, int], int] = {}
        self._lock = threading.Lock()
        self.simulate_failure: bool = False

    def check_and_consume(self, key: str, policy: RateLimitPolicy) -> RateLimitResult:
        if self.simulate_failure:
            raise RateLimitStorageError("Simulated in-memory storage failure.")

        now_ts = time.time()
        window_bucket = int(now_ts // policy.window_seconds)
        window_end_ts = (window_bucket + 1) * policy.window_seconds

        with self._lock:
            bucket_key = (key, window_bucket)
            current = self._counts.get(bucket_key, 0) + 1
            self._counts[bucket_key] = current

        allowed = current <= policy.max_requests
        remaining = max(0, policy.max_requests - current)
        retry_after = 0 if allowed else max(1, int(window_end_ts - now_ts))

        return RateLimitResult(
            allowed=allowed,
            current_count=current,
            limit=policy.max_requests,
            remaining=remaining,
            retry_after=retry_after,
            window_seconds=policy.window_seconds,
            reset_epoch=int(window_end_ts),
        )

    def reset(self, key: str) -> None:
        with self._lock:
            keys_to_del = [k for k in self._counts if k[0] == key]
            for k in keys_to_del:
                del self._counts[k]

    def cleanup_expired(self, before: datetime | None = None) -> int:
        now_bucket = int(time.time() // 60)
        with self._lock:
            initial = len(self._counts)
            self._counts = {k: v for k, v in self._counts.items() if k[1] >= now_bucket - 1}
            return initial - len(self._counts)


# -------------------------------------------------------------------------
# 4. Rate Limiter Manager & Telemetry Integration
# -------------------------------------------------------------------------


class RateLimiter:
    """
    Orchestrates policy enforcement, storage dispatch, telemetry logging,
    and HTTP 429 response emission.
    """

    def __init__(self, storage: BaseRateLimitStorage | None = None) -> None:
        if storage is not None:
            self._storage = storage
        elif settings.RATE_LIMIT_STORAGE_TYPE == "memory":
            self._storage = InMemoryRateLimitStorage()
        else:
            self._storage = PostgresRateLimitStorage()

    @property
    def storage(self) -> BaseRateLimitStorage:
        return self._storage

    def set_storage(self, storage: BaseRateLimitStorage) -> None:
        self._storage = storage

    def check(
        self,
        key: str,
        policy: RateLimitPolicy,
        request: Request | None = None,
        user_id: str | None = None,
        kb_id: str | None = None,
    ) -> RateLimitResult:
        """
        Evaluate rate limit against configured policy.

        Returns RateLimitResult on success.
        Raises HTTPException(429) if quota exceeded.
        Handles storage errors according to policy.fail_closed.
        Emits Step 17 telemetry events in all cases without leaking sensitive data.
        """
        if not settings.RATE_LIMIT_ENABLED:
            now_ts = time.time()
            return RateLimitResult(
                allowed=True,
                current_count=0,
                limit=policy.max_requests,
                remaining=policy.max_requests,
                retry_after=0,
                window_seconds=policy.window_seconds,
                reset_epoch=int(now_ts + policy.window_seconds),
            )

        req_id = get_request_id()
        current_user = user_id or get_current_user_id()
        current_kb = kb_id or get_current_kb_id()

        try:
            result = self._storage.check_and_consume(key=key, policy=policy)
        except RateLimitStorageError as exc:
            # Emit storage error telemetry event
            try:
                event = TelemetryEvent(
                    event_name="rate_limit",
                    request_id=req_id,
                    user_id=current_user,
                    knowledge_base_id=current_kb,
                    status="FAILURE",
                    error_category="RATE_LIMIT_STORAGE_ERROR",
                    attributes={
                        "policy": policy.name,
                        "rate_limit_status": "RATE_LIMIT_STORAGE_ERROR",
                        "fail_closed": policy.fail_closed,
                        "error": str(exc),
                    },
                )
                get_telemetry_manager().record_event(event)
            except Exception:
                pass

            if policy.fail_closed:
                logger.error(
                    "Rate limit storage error on fail-closed policy '%s': %s",
                    policy.name,
                    exc,
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Service temporarily unavailable due to security subsystem fault.",
                ) from exc

            # Fail-open: allow request with warning
            logger.warning(
                "Rate limit storage error on fail-open policy '%s'. Allowing request.",
                policy.name,
            )
            now_ts = time.time()
            return RateLimitResult(
                allowed=True,
                current_count=1,
                limit=policy.max_requests,
                remaining=policy.max_requests - 1,
                retry_after=0,
                window_seconds=policy.window_seconds,
                reset_epoch=int(now_ts + policy.window_seconds),
            )

        # Record telemetry event (allowed vs rejected)
        status_label = "RATE_LIMIT_ALLOWED" if result.allowed else "RATE_LIMIT_REJECTED"
        try:
            event = TelemetryEvent(
                event_name="rate_limit",
                request_id=req_id,
                user_id=current_user,
                knowledge_base_id=current_kb,
                status="SUCCESS" if result.allowed else "FAILURE",
                error_category=None if result.allowed else "RATE_LIMIT_EXCEEDED",
                attributes={
                    "policy": policy.name,
                    "rate_limit_status": status_label,
                    "limit": result.limit,
                    "current_count": result.current_count,
                    "remaining": result.remaining,
                    "retry_after": result.retry_after,
                    "window_seconds": result.window_seconds,
                },
            )
            get_telemetry_manager().record_event(event)
        except Exception:
            pass

        if not result.allowed:
            logger.warning(
                "Rate limit exceeded for policy '%s' on key '%s'. Retry-After: %ds",
                policy.name,
                key,
                result.retry_after,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Please try again in {result.retry_after} seconds.",
                headers={"Retry-After": str(result.retry_after)},
            )

        return result


# Singleton rate limiter instance
_global_rate_limiter: RateLimiter | None = None
_rate_limiter_lock = threading.Lock()


def get_rate_limiter() -> RateLimiter:
    """FastAPI dependency returning the shared RateLimiter singleton."""
    global _global_rate_limiter
    if _global_rate_limiter is None:
        with _rate_limiter_lock:
            if _global_rate_limiter is None:
                _global_rate_limiter = RateLimiter()
    return _global_rate_limiter
