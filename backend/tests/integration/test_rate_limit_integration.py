"""
Integration Tests for Step 18 — Rate Limiting & Abuse Protection.

Verifies with real PostgreSQL database:
1. PostgresRateLimitStorage atomic upserts and thread-safe concurrency.
2. Authentication endpoints rate limiting (login, register).
3. Dependency Ordering: Unauthenticated requests return 401 WITHOUT consuming user quota.
4. Authenticated endpoints rate limiting (chat, retrieval, upload, indexing).
5. User quota isolation: One user consuming quota does not affect other users.
6. Anti-spoofing header resistance: Random X-Forwarded-For headers cannot bypass IP limits.
7. Storage failure behaviors: Fail-Closed (503) for auth vs Fail-Open (200 + warning) for chat.
8. Unthrottled endpoints: /query/process and GET metadata endpoints remain unthrottled.
9. Step 17 Telemetry integration and zero secret leakage.
"""

import threading
import uuid
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.rate_limit import (
    PostgresRateLimitStorage,
    RateLimitPolicy,
    RateLimitStorageError,
    get_rate_limiter,
)
from backend.app.core.security import get_password_hash
from backend.app.core.telemetry import (
    InMemoryTelemetryExporter,
    get_telemetry_manager,
)
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseMember
from backend.app.models.user import User, UserRole
from backend.app.schemas.chat import (
    ChatLatencyBreakdownDTO,
    ChatQueryResponse,
    ClaimSummaryDTO,
    GroundingSummaryDTO,
)
from backend.app.services.rag_orchestrator import RAGOrchestrator, get_rag_orchestrator

# =============================================================================
# Database cleanup fixture
# =============================================================================


@pytest.fixture(autouse=True)
def clean_rate_limit_db(db_engine) -> Generator[None, None, None]:
    """Clean all database tables including rate_limit_entries before and after each test."""
    with db_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE rate_limit_entries, document_chunks, documents, "
                "knowledge_base_members, knowledge_bases, "
                "user_sessions, users CASCADE;"
            )
        )
    yield
    with db_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE rate_limit_entries, document_chunks, documents, "
                "knowledge_base_members, knowledge_bases, "
                "user_sessions, users CASCADE;"
            )
        )


def _create_user(
    db: Session,
    email: str,
    password: str = "TestPassword123!",
    full_name: str = "Rate Limit User",
    role: UserRole = UserRole.STUDENT,
) -> User:
    """Helper to provision a user directly in PostgreSQL."""
    user = User(
        email=email.strip().lower(),
        password_hash=get_password_hash(password),
        full_name=full_name,
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_kb(db: Session, admin_user: User, name: str = "Test Knowledge Base") -> KnowledgeBase:
    """Helper to provision a KnowledgeBase in PostgreSQL."""
    kb = KnowledgeBase(
        name=name,
        description="Knowledge base for rate limit integration testing",
        created_by_id=admin_user.id,
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


def _grant_membership(db: Session, kb: KnowledgeBase, student: User) -> None:
    """Helper to grant a student membership to a knowledge base."""
    member = KnowledgeBaseMember(
        knowledge_base_id=kb.id,
        user_id=student.id,
    )
    db.add(member)
    db.commit()


# =============================================================================
# 1. Real PostgreSQL Storage & Concurrency
# =============================================================================


def test_postgres_rate_limit_storage_atomic_increments(db_engine):
    """Verify PostgresRateLimitStorage performs atomic upserts on real PostgreSQL."""
    storage = PostgresRateLimitStorage(db_engine=db_engine)
    policy = RateLimitPolicy(name="pg_test", max_requests=3, window_seconds=60)
    key = "user:pg-test-1:pg_test"

    res1 = storage.check_and_consume(key, policy)
    assert res1.allowed is True
    assert res1.current_count == 1
    assert res1.remaining == 2

    res2 = storage.check_and_consume(key, policy)
    assert res2.allowed is True
    assert res2.current_count == 2
    assert res2.remaining == 1

    res3 = storage.check_and_consume(key, policy)
    assert res3.allowed is True
    assert res3.current_count == 3
    assert res3.remaining == 0

    res4 = storage.check_and_consume(key, policy)
    assert res4.allowed is False
    assert res4.current_count == 4
    assert res4.remaining == 0
    assert res4.retry_after >= 1


def test_postgres_rate_limit_storage_concurrency_race_conditions(db_engine):
    """
    Verify PostgreSQL row-level locks on ON CONFLICT DO UPDATE prevent lost updates
    when multiple threads increment the exact same key concurrently.
    """
    storage = PostgresRateLimitStorage(db_engine=db_engine)
    policy = RateLimitPolicy(name="pg_concurrency", max_requests=100, window_seconds=60)
    key = "user:pg-concurrent:test"

    num_threads = 10
    counts: list[int] = []
    lock = threading.Lock()

    def worker():
        res = storage.check_and_consume(key, policy)
        with lock:
            counts.append(res.current_count)

    threads = [threading.Thread(target=worker) for _ in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(counts) == num_threads
    # All counts returned must be unique sequential integers from 1 to 10
    assert set(counts) == set(range(1, num_threads + 1))


# =============================================================================
# 2. Authentication Endpoints Rate Limiting
# =============================================================================


def test_login_rate_limiting(api_client: TestClient, db_session: Session, monkeypatch):
    """Verify login endpoint is rate-limited per client IP and returns 429 + Retry-After."""
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN_MAX_REQUESTS", 2)
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN_WINDOW_SECONDS", 60)

    _create_user(db_session, email="student_login@university.edu", password="Password123!")

    # Attempt 1: Success
    resp1 = api_client.post(
        "/api/v1/auth/login",
        json={"email": "student_login@university.edu", "password": "Password123!"},
    )
    assert resp1.status_code == 200

    # Attempt 2: Success
    resp2 = api_client.post(
        "/api/v1/auth/login",
        json={"email": "student_login@university.edu", "password": "Password123!"},
    )
    assert resp2.status_code == 200

    # Attempt 3: Exceeds limit -> 429
    resp3 = api_client.post(
        "/api/v1/auth/login",
        json={"email": "student_login@university.edu", "password": "Password123!"},
    )
    assert resp3.status_code == 429
    assert "Rate limit exceeded" in resp3.json()["detail"]
    assert "Retry-After" in resp3.headers
    assert int(resp3.headers["Retry-After"]) >= 1


def test_registration_rate_limiting(api_client: TestClient, monkeypatch):
    """Verify registration endpoint is rate-limited per client IP and returns 429."""
    monkeypatch.setattr(settings, "RATE_LIMIT_REGISTER_MAX_REQUESTS", 2)
    monkeypatch.setattr(settings, "RATE_LIMIT_REGISTER_WINDOW_SECONDS", 60)

    # Register 1: 201 Created
    resp1 = api_client.post(
        "/api/v1/auth/register",
        json={
            "email": "reg1@university.edu",
            "password": "Password123!",
            "full_name": "Reg One",
        },
    )
    assert resp1.status_code == 201

    # Register 2: 201 Created
    resp2 = api_client.post(
        "/api/v1/auth/register",
        json={
            "email": "reg2@university.edu",
            "password": "Password123!",
            "full_name": "Reg Two",
        },
    )
    assert resp2.status_code == 201

    # Register 3: Exceeds limit -> 429
    resp3 = api_client.post(
        "/api/v1/auth/register",
        json={
            "email": "reg3@university.edu",
            "password": "Password123!",
            "full_name": "Reg Three",
        },
    )
    assert resp3.status_code == 429
    assert "Retry-After" in resp3.headers


# =============================================================================
# 3. Dependency Ordering: Unauthenticated Requests Do Not Consume Quota
# =============================================================================


def test_unauthenticated_request_does_not_consume_user_quota(
    api_client: TestClient,
    db_session: Session,
    db_engine,
    monkeypatch,
):
    """
    CRITICAL SECURITY & DEPENDENCY ORDERING:
    Unauthenticated requests to protected endpoints return 401 without
    consuming any authenticated user quota.
    """
    monkeypatch.setattr(settings, "RATE_LIMIT_CHAT_MAX_REQUESTS", 2)
    fake_kb_id = uuid.uuid4()

    # Attempt unauthenticated requests
    for _ in range(5):
        resp = api_client.post(
            "/api/v1/chat/query",
            json={"knowledge_base_id": str(fake_kb_id), "question": "What is OS?"},
        )
        assert resp.status_code == 401

    # Verify zero user rate limit records were created in the database
    with db_engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM rate_limit_entries WHERE key LIKE 'user:%'")
        ).scalar_one()
        assert count == 0


# =============================================================================
# 4. Authenticated Chat & User Quota Isolation
# =============================================================================


def test_chat_rate_limiting_and_user_isolation(
    api_client: TestClient,
    db_session: Session,
    monkeypatch,
):
    """
    Verify:
    1. Authenticated chat endpoint throttles when user exceeds quota.
    2. User A exhausting quota does NOT block User B (strict tenant/user isolation).
    """
    monkeypatch.setattr(settings, "RATE_LIMIT_CHAT_MAX_REQUESTS", 2)
    monkeypatch.setattr(settings, "RATE_LIMIT_CHAT_WINDOW_SECONDS", 60)

    admin = _create_user(
        db_session,
        email="prof_os@university.edu",
        password="Password123!",
        role=UserRole.ADMIN,
    )
    student_a = _create_user(
        db_session,
        email="student_a@university.edu",
        password="Password123!",
        role=UserRole.STUDENT,
    )
    student_b = _create_user(
        db_session,
        email="student_b@university.edu",
        password="Password123!",
        role=UserRole.STUDENT,
    )

    kb = _create_kb(db_session, admin_user=admin, name="Operating Systems")
    _grant_membership(db_session, kb, student_a)
    _grant_membership(db_session, kb, student_b)

    # Mock orchestrator to avoid live model calls
    mock_orchestrator = MagicMock(spec=RAGOrchestrator)
    mock_orchestrator.execute_query = AsyncMock(
        return_value=ChatQueryResponse(
            query="What is scheduling?",
            processed_query="what is scheduling",
            knowledge_base_id=kb.id,
            answer="Operating systems manage hardware resources.",
            is_empty_context=False,
            citations=[],
            grounding=GroundingSummaryDTO(
                is_grounded=True,
                status="FULLY_SUPPORTED",
                citation_validity_rate=1.0,
                citation_coverage=1.0,
                claim_support_rate=1.0,
                unsupported_claim_rate=0.0,
                has_conflicts=False,
                claims=[
                    ClaimSummaryDTO(
                        claim_text="Operating systems manage hardware resources.",
                        status="SUPPORTED",
                        cited_source=None,
                        rationale="",
                    )
                ],
            ),
            latency=ChatLatencyBreakdownDTO(
                query_processing_ms=1.0,
                retrieval_ms=10.0,
                reranking_ms=5.0,
                context_assembly_ms=2.0,
                llm_generation_ms=50.0,
                grounding_validation_ms=5.0,
                total_pipeline_ms=73.0,
            ),
            model="mocked-llm",
        )
    )
    api_client.app.dependency_overrides[get_rag_orchestrator] = lambda: mock_orchestrator

    try:
        # 1. Login as Student A
        login_a = api_client.post(
            "/api/v1/auth/login",
            json={"email": "student_a@university.edu", "password": "Password123!"},
        )
        assert login_a.status_code == 200

        # Student A: Request 1 (OK)
        r1 = api_client.post(
            f"/api/v1/knowledge-bases/{kb.id}/chat",
            json={"question": "What is scheduling?"},
        )
        assert r1.status_code == 200

        # Student A: Request 2 (OK)
        r2 = api_client.post(
            f"/api/v1/knowledge-bases/{kb.id}/chat",
            json={"question": "What is paging?"},
        )
        assert r2.status_code == 200

        # Student A: Request 3 (Exceeds limit -> 429)
        r3 = api_client.post(
            f"/api/v1/knowledge-bases/{kb.id}/chat",
            json={"question": "What is deadlock?"},
        )
        assert r3.status_code == 429
        assert "Retry-After" in r3.headers

        # 2. Login as Student B (different user, same IP)
        login_b = api_client.post(
            "/api/v1/auth/login",
            json={"email": "student_b@university.edu", "password": "Password123!"},
        )
        assert login_b.status_code == 200

        # Student B must NOT be blocked by Student A's quota exhaustion!
        r_b1 = api_client.post(
            f"/api/v1/knowledge-bases/{kb.id}/chat",
            json={"question": "Explain virtual memory."},
        )
        assert r_b1.status_code == 200
        assert r_b1.json()["answer"] == "Operating systems manage hardware resources."
    finally:
        api_client.app.dependency_overrides.pop(get_rag_orchestrator, None)


# =============================================================================
# 5. Anti-Spoofing: Proxy Header Spoofing Resistance
# =============================================================================


def test_anti_spoofing_header_resistance(api_client: TestClient, monkeypatch):
    """
    CRITICAL SECURITY:
    An attacker cannot bypass IP rate limits by sending randomized X-Forwarded-For
    or Client-IP headers when connecting from an untrusted peer.
    """
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN_MAX_REQUESTS", 2)
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN_WINDOW_SECONDS", 60)
    # Ensure no proxies are trusted
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", set())

    # Request 1 with spoofed header
    r1 = api_client.post(
        "/api/v1/auth/login",
        json={"email": "hacker@evil.com", "password": "WrongPassword!"},
        headers={"X-Forwarded-For": "1.1.1.1", "Client-IP": "1.1.1.1"},
    )
    # Expected 401 Unauthorized for wrong credentials, but rate limiter consumed 1 attempt
    assert r1.status_code == 401

    # Request 2 with different spoofed header
    r2 = api_client.post(
        "/api/v1/auth/login",
        json={"email": "hacker@evil.com", "password": "WrongPassword!"},
        headers={"X-Forwarded-For": "2.2.2.2", "Client-IP": "2.2.2.2"},
    )
    assert r2.status_code == 401

    # Request 3 with yet another spoofed header -> MUST BE 429!
    r3 = api_client.post(
        "/api/v1/auth/login",
        json={"email": "hacker@evil.com", "password": "WrongPassword!"},
        headers={"X-Forwarded-For": "3.3.3.3", "Client-IP": "3.3.3.3"},
    )
    assert r3.status_code == 429
    assert "Rate limit exceeded" in r3.json()["detail"]


# =============================================================================
# 6. Storage Failure Behavior: Fail-Closed vs Fail-Open
# =============================================================================


def test_storage_failure_auth_fails_closed(api_client: TestClient, monkeypatch):
    """
    Verify authentication endpoints fail closed (HTTP 503) when rate limit storage fails.
    Prevents brute-force attacks during database degradation.
    """
    limiter = get_rate_limiter()
    mock_storage = MagicMock()
    mock_storage.check_and_consume.side_effect = RateLimitStorageError("DB connection lost")
    orig_storage = limiter.storage
    limiter.set_storage(mock_storage)

    try:
        resp = api_client.post(
            "/api/v1/auth/login",
            json={"email": "any@university.edu", "password": "Password123!"},
        )
        assert resp.status_code == 503
        assert "Service temporarily unavailable" in resp.json()["detail"]
    finally:
        limiter.set_storage(orig_storage)


def test_storage_failure_chat_fails_open(
    api_client: TestClient,
    db_session: Session,
    monkeypatch,
):
    """
    Verify expensive chat endpoints fail open (allows request) when rate limit storage fails
    and RATE_LIMIT_EXPENSIVE_FAIL_CLOSED=False.
    Maintains student availability with warning and telemetry error event.
    """
    monkeypatch.setattr(settings, "RATE_LIMIT_EXPENSIVE_FAIL_CLOSED", False)

    admin = _create_user(
        db_session,
        email="prof_db@university.edu",
        password="Password123!",
        role=UserRole.ADMIN,
    )
    student = _create_user(
        db_session,
        email="student_open@university.edu",
        password="Password123!",
        role=UserRole.STUDENT,
    )
    kb = _create_kb(db_session, admin_user=admin, name="Databases")
    _grant_membership(db_session, kb, student)

    # Mock orchestrator
    mock_orchestrator = MagicMock(spec=RAGOrchestrator)
    mock_orchestrator.execute_query = AsyncMock(
        return_value=ChatQueryResponse(
            query="What is atomicity?",
            processed_query="what is atomicity",
            knowledge_base_id=kb.id,
            answer="ACID guarantees database transaction integrity.",
            is_empty_context=False,
            citations=[],
            grounding=GroundingSummaryDTO(
                is_grounded=True,
                status="FULLY_SUPPORTED",
                citation_validity_rate=1.0,
                citation_coverage=1.0,
                claim_support_rate=1.0,
                unsupported_claim_rate=0.0,
                has_conflicts=False,
                claims=[
                    ClaimSummaryDTO(
                        claim_text="ACID guarantees database transaction integrity.",
                        status="SUPPORTED",
                        cited_source=None,
                        rationale="",
                    )
                ],
            ),
            latency=ChatLatencyBreakdownDTO(
                query_processing_ms=1.0,
                retrieval_ms=10.0,
                reranking_ms=5.0,
                context_assembly_ms=2.0,
                llm_generation_ms=50.0,
                grounding_validation_ms=5.0,
                total_pipeline_ms=73.0,
            ),
            model="mocked-llm",
        )
    )
    api_client.app.dependency_overrides[get_rag_orchestrator] = lambda: mock_orchestrator

    limiter = get_rate_limiter()
    mock_storage = MagicMock()
    mock_storage.check_and_consume.side_effect = RateLimitStorageError("Transient table lock")
    orig_storage = limiter.storage
    limiter.set_storage(mock_storage)

    exporter = InMemoryTelemetryExporter()
    get_telemetry_manager().register_exporter(exporter)

    try:
        # Login
        login_res = api_client.post(
            "/api/v1/auth/login",
            json={"email": "student_open@university.edu", "password": "Password123!"},
        )
        # Auth will fail closed while mock storage is in place, so temporarily restore for login
        limiter.set_storage(orig_storage)
        login_res = api_client.post(
            "/api/v1/auth/login",
            json={"email": "student_open@university.edu", "password": "Password123!"},
        )
        assert login_res.status_code == 200

        # Now enable storage failure for chat
        limiter.set_storage(mock_storage)

        chat_res = api_client.post(
            f"/api/v1/knowledge-bases/{kb.id}/chat",
            json={"question": "What is atomicity?"},
        )
        # Chat must FAIL OPEN (status 200) despite storage failure
        assert chat_res.status_code == 200
        assert "ACID guarantees" in chat_res.json()["answer"]

        # Telemetry must capture the storage error
        events = exporter.get_events()
        storage_errors = [
            e
            for e in events
            if e.event_name == "rate_limit" and e.error_category == "RATE_LIMIT_STORAGE_ERROR"
        ]
        assert len(storage_errors) >= 1
    finally:
        limiter.set_storage(orig_storage)
        api_client.app.dependency_overrides.pop(get_rag_orchestrator, None)
        get_telemetry_manager().unregister_exporter(exporter)


# =============================================================================
# 7. Pure Inspection Endpoints Remain Unthrottled
# =============================================================================


def test_query_process_is_not_rate_limited(api_client: TestClient, db_session: Session):
    """
    Verify /query/process (pure deterministic in-memory string normalizer)
    is NOT rate limited and handles rapid consecutive calls smoothly.
    """
    _user = _create_user(
        db_session,
        email="query_student@university.edu",
        password="Password123!",
    )
    login_res = api_client.post(
        "/api/v1/auth/login",
        json={"email": "query_student@university.edu", "password": "Password123!"},
    )
    assert login_res.status_code == 200

    for i in range(25):
        resp = api_client.post(
            "/api/v1/query/process",
            json={"query": f"deterministic query test number {i}"},
        )
        assert resp.status_code == 200
        assert resp.json()["processed_query"] == f"deterministic query test number {i}"


# =============================================================================
# 7.5 Retrieval, Upload, and Indexing Rate Limiting
# =============================================================================


def test_retrieval_rate_limiting(api_client: TestClient, db_session: Session, monkeypatch):
    """Verify retrieval endpoints are rate-limited per authenticated user."""
    monkeypatch.setattr(settings, "RATE_LIMIT_RETRIEVAL_MAX_REQUESTS", 2)
    monkeypatch.setattr(settings, "RATE_LIMIT_RETRIEVAL_WINDOW_SECONDS", 60)

    admin = _create_user(
        db_session,
        email="prof_retrieval@university.edu",
        password="Password123!",
        role=UserRole.ADMIN,
    )
    student = _create_user(
        db_session,
        email="student_retrieval@university.edu",
        password="Password123!",
        role=UserRole.STUDENT,
    )
    kb = _create_kb(db_session, admin_user=admin, name="Retrieval KB")
    _grant_membership(db_session, kb, student)

    # Mock retrieval service
    from backend.app.schemas.retrieval import RetrievalResponse
    from backend.app.services.retrieval import get_retrieval_service

    mock_service = MagicMock()
    mock_service.retrieve = AsyncMock(
        return_value=RetrievalResponse(
            query="test search",
            knowledge_base_id=kb.id,
            results=[],
            total_results=0,
        )
    )
    api_client.app.dependency_overrides[get_retrieval_service] = lambda: mock_service

    try:
        # Login
        login_res = api_client.post(
            "/api/v1/auth/login",
            json={"email": "student_retrieval@university.edu", "password": "Password123!"},
        )
        assert login_res.status_code == 200

        # Attempt 1 (OK)
        r1 = api_client.post(
            f"/api/v1/knowledge-bases/{kb.id}/retrieve",
            json={"query": "first search", "top_k": 5},
        )
        assert r1.status_code == 200

        # Attempt 2 (OK)
        r2 = api_client.post(
            f"/api/v1/knowledge-bases/{kb.id}/retrieve",
            json={"query": "second search", "top_k": 5},
        )
        assert r2.status_code == 200

        # Attempt 3 (Exceeds limit -> 429)
        r3 = api_client.post(
            f"/api/v1/knowledge-bases/{kb.id}/retrieve",
            json={"query": "third search", "top_k": 5},
        )
        assert r3.status_code == 429
        assert "Retry-After" in r3.headers
    finally:
        api_client.app.dependency_overrides.pop(get_retrieval_service, None)


def test_upload_and_indexing_rate_limiting(
    api_client: TestClient,
    db_session: Session,
    monkeypatch,
):
    """Verify document upload and indexing endpoints are rate-limited per admin user."""
    monkeypatch.setattr(settings, "RATE_LIMIT_UPLOAD_MAX_REQUESTS", 2)
    monkeypatch.setattr(settings, "RATE_LIMIT_UPLOAD_WINDOW_SECONDS", 60)
    monkeypatch.setattr(settings, "RATE_LIMIT_INDEXING_MAX_REQUESTS", 2)
    monkeypatch.setattr(settings, "RATE_LIMIT_INDEXING_WINDOW_SECONDS", 60)

    admin = _create_user(
        db_session,
        email="admin_upload@university.edu",
        password="Password123!",
        role=UserRole.ADMIN,
    )
    kb = _create_kb(db_session, admin_user=admin, name="Admin Upload KB")

    # Login as admin
    login_res = api_client.post(
        "/api/v1/auth/login",
        json={"email": "admin_upload@university.edu", "password": "Password123!"},
    )
    assert login_res.status_code == 200

    # Test Upload Limit (Invoking without file tests authorization probe while exercising rate limiter)
    u1 = api_client.post(f"/api/v1/knowledge-bases/{kb.id}/documents")
    assert u1.status_code == 200

    u2 = api_client.post(f"/api/v1/knowledge-bases/{kb.id}/documents")
    assert u2.status_code == 200

    u3 = api_client.post(f"/api/v1/knowledge-bases/{kb.id}/documents")
    assert u3.status_code == 429
    assert "Retry-After" in u3.headers

    # Test Indexing Limit (Using fake doc UUID: 404 from business logic, but rate limit consumes quota)
    fake_doc_id = uuid.uuid4()
    i1 = api_client.post(f"/api/v1/knowledge-bases/{kb.id}/documents/{fake_doc_id}/index")
    assert i1.status_code in (404, 202)

    i2 = api_client.post(f"/api/v1/knowledge-bases/{kb.id}/documents/{fake_doc_id}/index")
    assert i2.status_code in (404, 202)

    i3 = api_client.post(f"/api/v1/knowledge-bases/{kb.id}/documents/{fake_doc_id}/index")
    assert i3.status_code == 429
    assert "Retry-After" in i3.headers


# =============================================================================
# 8. Telemetry Integration & Secret Leakage Inspection
# =============================================================================


def test_rate_limit_telemetry_no_secrets_leaked(api_client: TestClient, monkeypatch):
    """
    Verify rate limiting telemetry events contain proper metadata and zero secrets.
    """
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN_MAX_REQUESTS", 1)
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN_WINDOW_SECONDS", 60)

    exporter = InMemoryTelemetryExporter()
    get_telemetry_manager().register_exporter(exporter)

    try:
        # Request 1 (Allowed)
        api_client.post(
            "/api/v1/auth/login",
            json={"email": "user@university.edu", "password": "SecretPassword123!"},
        )

        # Request 2 (Rejected)
        api_client.post(
            "/api/v1/auth/login",
            json={"email": "user@university.edu", "password": "SecretPassword123!"},
        )

        events = exporter.get_events()
        rate_events = [e for e in events if e.event_name == "rate_limit"]
        assert len(rate_events) >= 2

        for ev in rate_events:
            # Verify no credentials leaked in attributes
            attrs = ev.attributes
            for _k, v in attrs.items():
                v_str = str(v)
                assert "SecretPassword123!" not in v_str
                assert "postgresql://" not in v_str
                assert "secret_key" not in v_str
    finally:
        get_telemetry_manager().unregister_exporter(exporter)
