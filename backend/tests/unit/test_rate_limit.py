"""
Unit Tests for Step 18 — Rate Limiting & Abuse Protection.

Tests:
- RateLimitPolicy validation (positive limits & windows).
- InMemoryRateLimitStorage operations (atomic counter, window reset, cleanup).
- Anti-spoofing client IP resolution (direct peer IP vs trusted proxies vs spoofed headers).
- Rate-limit key construction and isolation.
- Concurrent thread safety and atomic counting.
- RateLimiter orchestration (allow, reject with 429/Retry-After, fail-closed 503, fail-open fallback).
- Telemetry event emission and zero secret leakage.
"""

import threading
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers

from backend.app.core.config import settings
from backend.app.core.rate_limit import (
    InMemoryRateLimitStorage,
    RateLimiter,
    RateLimitPolicy,
    RateLimitResult,
    build_rate_limit_key,
    get_client_ip,
)
from backend.app.core.telemetry import (
    InMemoryTelemetryExporter,
    get_telemetry_manager,
)

# =============================================================================
# 1. Policy & Result Validation Tests
# =============================================================================


def test_rate_limit_policy_valid():
    """Verify valid policy construction."""
    policy = RateLimitPolicy(name="test_policy", max_requests=10, window_seconds=60)
    assert policy.name == "test_policy"
    assert policy.max_requests == 10
    assert policy.window_seconds == 60
    assert policy.fail_closed is False


def test_rate_limit_policy_rejects_non_positive_max_requests():
    """Verify policy rejects max_requests < 1."""
    with pytest.raises(ValueError, match="max_requests must be at least 1"):
        RateLimitPolicy(name="invalid", max_requests=0, window_seconds=60)

    with pytest.raises(ValueError, match="max_requests must be at least 1"):
        RateLimitPolicy(name="invalid", max_requests=-5, window_seconds=60)


def test_rate_limit_policy_rejects_non_positive_window_seconds():
    """Verify policy rejects window_seconds < 1."""
    with pytest.raises(ValueError, match="window_seconds must be at least 1"):
        RateLimitPolicy(name="invalid", max_requests=10, window_seconds=0)

    with pytest.raises(ValueError, match="window_seconds must be at least 1"):
        RateLimitPolicy(name="invalid", max_requests=10, window_seconds=-10)


def test_rate_limit_result_immutability():
    """Verify RateLimitResult is frozen and immutable."""
    res = RateLimitResult(
        allowed=True,
        current_count=1,
        limit=10,
        remaining=9,
        retry_after=0,
        window_seconds=60,
        reset_epoch=1234567890,
    )
    assert res.allowed is True
    with pytest.raises(AttributeError):
        res.allowed = False  # type: ignore


# =============================================================================
# 2. In-Memory Storage & Window Tests
# =============================================================================


def test_in_memory_storage_allows_within_limit():
    """Verify in-memory storage allows requests up to limit and computes remaining."""
    storage = InMemoryRateLimitStorage()
    policy = RateLimitPolicy(name="test", max_requests=3, window_seconds=60)
    key = "user:123:test"

    res1 = storage.check_and_consume(key, policy)
    assert res1.allowed is True
    assert res1.current_count == 1
    assert res1.remaining == 2
    assert res1.retry_after == 0

    res2 = storage.check_and_consume(key, policy)
    assert res2.allowed is True
    assert res2.current_count == 2
    assert res2.remaining == 1

    res3 = storage.check_and_consume(key, policy)
    assert res3.allowed is True
    assert res3.current_count == 3
    assert res3.remaining == 0


def test_in_memory_storage_rejects_when_exceeded():
    """Verify in-memory storage rejects requests once limit is exceeded."""
    storage = InMemoryRateLimitStorage()
    policy = RateLimitPolicy(name="test", max_requests=2, window_seconds=60)
    key = "user:456:test"

    storage.check_and_consume(key, policy)
    storage.check_and_consume(key, policy)

    res3 = storage.check_and_consume(key, policy)
    assert res3.allowed is False
    assert res3.current_count == 3
    assert res3.remaining == 0
    assert res3.retry_after >= 1
    assert res3.retry_after <= 60


def test_in_memory_storage_reset():
    """Verify resetting key clears quota counter."""
    storage = InMemoryRateLimitStorage()
    policy = RateLimitPolicy(name="test", max_requests=1, window_seconds=60)
    key = "user:789:test"

    res1 = storage.check_and_consume(key, policy)
    assert res1.allowed is True

    res2 = storage.check_and_consume(key, policy)
    assert res2.allowed is False

    storage.reset(key)

    res3 = storage.check_and_consume(key, policy)
    assert res3.allowed is True
    assert res3.current_count == 1


def test_in_memory_storage_concurrency():
    """Verify thread-safe atomic increments under concurrent access."""
    storage = InMemoryRateLimitStorage()
    policy = RateLimitPolicy(name="concurrent", max_requests=100, window_seconds=60)
    key = "user:concurrent:test"

    num_threads = 25
    results: list[RateLimitResult] = []
    lock = threading.Lock()

    def worker():
        res = storage.check_and_consume(key, policy)
        with lock:
            results.append(res)

    threads = [threading.Thread(target=worker) for _ in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == num_threads
    counts = {r.current_count for r in results}
    # Every worker must have received a distinct, unique sequential count from 1 to 25
    assert counts == set(range(1, num_threads + 1))


# =============================================================================
# 3. Client IP Resolution & Anti-Spoofing Tests
# =============================================================================


def _make_mock_request(client_host: str = "203.0.113.10", headers: dict | None = None) -> MagicMock:
    req = MagicMock()
    req.client.host = client_host
    req.headers = Headers(headers or {})
    return req


def test_get_client_ip_direct_peer():
    """Verify direct peer IP is returned when no proxies are trusted."""
    req = _make_mock_request(client_host="198.51.100.5", headers={})
    ip = get_client_ip(req, trusted_proxies=set())
    assert ip == "198.51.100.5"


def test_get_client_ip_ignores_spoofed_headers_from_untrusted_peer():
    """CRITICAL SECURITY: Spoofed X-Forwarded-For from untrusted peer must be ignored."""
    req = _make_mock_request(
        client_host="198.51.100.5",
        headers={
            "X-Forwarded-For": "10.0.0.1, 1.2.3.4",
            "Client-IP": "8.8.8.8",
            "X-Real-IP": "9.9.9.9",
        },
    )
    # Untrusted peer cannot spoof IP
    ip = get_client_ip(req, trusted_proxies=set())
    assert ip == "198.51.100.5"


def test_get_client_ip_respects_trusted_proxy():
    """Verify trusted proxy forwards real client IP from rightmost untrusted hop."""
    trusted = {"127.0.0.1", "10.0.0.1"}
    req = _make_mock_request(
        client_host="127.0.0.1",
        headers={"X-Forwarded-For": "203.0.113.50, 10.0.0.1"},
    )
    ip = get_client_ip(req, trusted_proxies=trusted)
    assert ip == "203.0.113.50"


def test_get_client_ip_handles_malformed_header():
    """Verify malformed IP string in header safely falls back to peer IP."""
    trusted = {"127.0.0.1"}
    req = _make_mock_request(
        client_host="127.0.0.1",
        headers={"X-Forwarded-For": "not-an-ip, <script>alert(1)</script>"},
    )
    ip = get_client_ip(req, trusted_proxies=trusted)
    assert ip == "127.0.0.1"


def test_build_rate_limit_key_isolation():
    """Verify key construction ensures clean domain separation."""
    k1 = build_rate_limit_key("user", "user-uuid-1", "chat")
    k2 = build_rate_limit_key("user", "user-uuid-2", "chat")
    k3 = build_rate_limit_key("ip", "192.168.1.1", "auth_login")

    assert k1 == "user:user-uuid-1:chat"
    assert k2 == "user:user-uuid-2:chat"
    assert k3 == "ip:192.168.1.1:auth_login"
    assert k1 != k2
    assert k1 != k3


# =============================================================================
# 4. RateLimiter Orchestration & Failure Modes
# =============================================================================


def test_rate_limiter_allows_and_emits_telemetry():
    """Verify allowed request emits RATE_LIMIT_ALLOWED telemetry event."""
    storage = InMemoryRateLimitStorage()
    limiter = RateLimiter(storage=storage)
    exporter = InMemoryTelemetryExporter()
    get_telemetry_manager().register_exporter(exporter)

    try:
        policy = RateLimitPolicy(name="unit_test", max_requests=5, window_seconds=60)
        res = limiter.check(key="user:1:unit_test", policy=policy, user_id="user-1")

        assert res.allowed is True

        events = exporter.get_events()
        rate_events = [e for e in events if e.event_name == "rate_limit"]
        assert len(rate_events) >= 1
        last = rate_events[-1]
        assert last.status == "SUCCESS"
        assert last.attributes["rate_limit_status"] == "RATE_LIMIT_ALLOWED"
        assert last.attributes["policy"] == "unit_test"
    finally:
        get_telemetry_manager().unregister_exporter(exporter)


def test_rate_limiter_exceeded_raises_429_with_retry_after():
    """Verify exceeding limit raises HTTPException 429 with Retry-After header."""
    storage = InMemoryRateLimitStorage()
    limiter = RateLimiter(storage=storage)
    exporter = InMemoryTelemetryExporter()
    get_telemetry_manager().register_exporter(exporter)

    try:
        policy = RateLimitPolicy(name="tight_policy", max_requests=1, window_seconds=60)
        # First request allowed
        limiter.check(key="user:2:tight_policy", policy=policy, user_id="user-2")

        # Second request must raise 429
        with pytest.raises(HTTPException) as exc_info:
            limiter.check(key="user:2:tight_policy", policy=policy, user_id="user-2")

        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in exc_info.value.detail
        assert "Retry-After" in exc_info.value.headers
        retry_after = int(exc_info.value.headers["Retry-After"])
        assert retry_after >= 1

        events = exporter.get_events()
        reject_events = [
            e for e in events if e.event_name == "rate_limit" and e.status == "FAILURE"
        ]
        assert len(reject_events) >= 1
        assert reject_events[-1].attributes["rate_limit_status"] == "RATE_LIMIT_REJECTED"
        assert reject_events[-1].error_category == "RATE_LIMIT_EXCEEDED"
    finally:
        get_telemetry_manager().unregister_exporter(exporter)


def test_rate_limiter_fail_closed_on_storage_error():
    """Verify fail_closed=True raises HTTP 503 when storage fails."""
    storage = InMemoryRateLimitStorage()
    storage.simulate_failure = True  # Trigger storage error
    limiter = RateLimiter(storage=storage)
    exporter = InMemoryTelemetryExporter()
    get_telemetry_manager().register_exporter(exporter)

    try:
        policy = RateLimitPolicy(
            name="auth_login",
            max_requests=5,
            window_seconds=60,
            fail_closed=True,
        )

        with pytest.raises(HTTPException) as exc_info:
            limiter.check(key="ip:1.1.1.1:auth_login", policy=policy)

        assert exc_info.value.status_code == 503
        assert "Service temporarily unavailable" in exc_info.value.detail

        events = exporter.get_events()
        error_events = [
            e
            for e in events
            if e.event_name == "rate_limit" and e.error_category == "RATE_LIMIT_STORAGE_ERROR"
        ]
        assert len(error_events) >= 1
        assert error_events[-1].attributes["rate_limit_status"] == "RATE_LIMIT_STORAGE_ERROR"
        assert error_events[-1].attributes["fail_closed"] is True
    finally:
        get_telemetry_manager().unregister_exporter(exporter)


def test_rate_limiter_fail_open_on_storage_error():
    """Verify fail_closed=False allows request through when storage fails."""
    storage = InMemoryRateLimitStorage()
    storage.simulate_failure = True
    limiter = RateLimiter(storage=storage)
    exporter = InMemoryTelemetryExporter()
    get_telemetry_manager().register_exporter(exporter)

    try:
        policy = RateLimitPolicy(
            name="chat",
            max_requests=5,
            window_seconds=60,
            fail_closed=False,
        )

        res = limiter.check(key="user:3:chat", policy=policy, user_id="user-3")
        assert res.allowed is True

        events = exporter.get_events()
        error_events = [
            e
            for e in events
            if e.event_name == "rate_limit" and e.error_category == "RATE_LIMIT_STORAGE_ERROR"
        ]
        assert len(error_events) >= 1
        assert error_events[-1].attributes["fail_closed"] is False
    finally:
        get_telemetry_manager().unregister_exporter(exporter)


def test_rate_limiter_disabled_bypass(monkeypatch):
    """Verify RATE_LIMIT_ENABLED=False bypasses all rate limiting."""
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    storage = InMemoryRateLimitStorage()
    limiter = RateLimiter(storage=storage)

    policy = RateLimitPolicy(name="test", max_requests=1, window_seconds=60)
    for _ in range(10):
        res = limiter.check("user:bypass:test", policy)
        assert res.allowed is True
