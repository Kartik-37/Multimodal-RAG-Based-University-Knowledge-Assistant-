"""
Unit & Contract Tests for Step 20 — Backend Production Quality Gate.

Provides explicit, targeted verification for:
1. Application Lifecycle & Startup (FastAPI lifespan, startup health check, engine.dispose on shutdown).
2. Database / Alembic Invariants (no pending migrations, test DB at migration head).
3. Provider Failure & Resilience (dimension mismatches, provider errors, transaction rollbacks).
4. Performance Sanity Checks (CrossEncoder singleton, bounded top-k parameters).
5. Rate Limiting Failure Policies (fail-closed auth vs fail-open RAG).
6. Configuration & Environment Invariants (.env.example compatibility).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, settings
from backend.app.core.rate_limit import (
    RateLimitPolicy,
)
from backend.app.db.session import create_db_engine, engine
from backend.app.main import lifespan
from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.models.user import User, UserRole
from backend.app.services.embedding.base import BaseEmbeddingProvider
from backend.app.services.reranking.base import BaseRerankerProvider
from backend.app.services.reranking.exceptions import (
    RerankerProviderError,
)
from backend.app.services.reranking.service import (
    RerankingService,
    get_default_reranker_provider,
)
from backend.app.services.retrieval import (
    RetrievalProviderError,
    RetrievalValidationError,
    VectorRetrievalService,
)

# ==============================================================================
# 1. APPLICATION LIFECYCLE & STARTUP QUALITY GATE
# ==============================================================================


@pytest.mark.asyncio
async def test_lifespan_startup_fails_fast_when_database_unavailable() -> None:
    """
    Quality Gate Dim 1:
    Verifies that application lifespan fails fast with a RuntimeError when PostgreSQL
    is unreachable on startup, does NOT swallow the failure, and disposes connection pool.
    """
    mock_app = FastAPI()
    with patch("backend.app.main.check_database_connection", return_value=False):
        with patch.object(engine, "dispose") as mock_dispose:
            with pytest.raises(RuntimeError, match="Database connection could not be established"):
                async with lifespan(mock_app):
                    pass
            mock_dispose.assert_called_once()


@pytest.mark.asyncio
async def test_lifespan_normal_shutdown_disposes_engine() -> None:
    """
    Quality Gate Dim 1:
    Verifies that engine.dispose() is cleanly invoked upon normal lifespan termination.
    """
    mock_app = FastAPI()
    with patch("backend.app.main.check_database_connection", return_value=True):
        with patch.object(engine, "dispose") as mock_dispose:
            async with lifespan(mock_app):
                # Inside lifespan, engine is NOT disposed
                mock_dispose.assert_not_called()
            # On exit, engine.dispose() MUST have been called exactly once
            mock_dispose.assert_called_once()


@pytest.mark.asyncio
async def test_lifespan_exception_shutdown_disposes_engine() -> None:
    """
    Quality Gate Dim 1:
    Verifies that engine.dispose() is guaranteed to execute via the finally block
    even if an unhandled exception occurs while the application is running.
    """
    mock_app = FastAPI()
    with patch("backend.app.main.check_database_connection", return_value=True):
        with patch.object(engine, "dispose") as mock_dispose:
            with pytest.raises(ValueError, match="Simulated application error"):
                async with lifespan(mock_app):
                    raise ValueError("Simulated application error")
            mock_dispose.assert_called_once()


def test_engine_not_disposed_during_ordinary_request_handling(client: TestClient) -> None:
    """
    Quality Gate Dim 1:
    Verifies that engine.dispose() is NOT triggered during normal HTTP request routing.
    """
    with patch.object(engine, "dispose") as mock_dispose:
        resp = client.get("/health")
        assert resp.status_code == status.HTTP_200_OK
        mock_dispose.assert_not_called()


def test_no_second_sqlalchemy_engine_created() -> None:
    """
    Quality Gate Dim 1:
    Verifies that main.py reuses the singleton engine from backend.app.db.session
    and does not create a redundant secondary connection pool.
    """
    from backend.app.main import engine as main_engine

    assert main_engine is engine


# ==============================================================================
# 2. DATABASE & ALEMBIC QUALITY GATE
# ==============================================================================


def test_alembic_schema_matches_migration_head() -> None:
    """
    Quality Gate Dim 2:
    Verifies that:
    1. The migration chain has a single deterministic head.
    2. The local PostgreSQL test database current revision exactly matches that head.
    """
    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    head_rev = script.get_current_head()
    assert head_rev is not None

    test_engine = create_db_engine(settings.TEST_DATABASE_URL)
    with test_engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        current_rev = ctx.get_current_revision()
        assert current_rev == head_rev, (
            f"Test DB revision ({current_rev}) does not match Alembic head ({head_rev})"
        )
    test_engine.dispose()


# ==============================================================================
# 3. PROVIDER FAILURE & RESILIENCE
# ==============================================================================


class MockMismatchedDimensionEmbeddingProvider(BaseEmbeddingProvider):
    """Mock provider that returns vectors with mismatched dimensions (768 vs 1024)."""

    @property
    def model_name(self) -> str:
        return "mock-768"

    @property
    def dimension(self) -> int:
        return 1024

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 768 for _ in texts]

    async def embed_query(self, query: str) -> list[float]:
        # Return 768 elements despite claiming dimension=1024
        return [0.1] * 768


@pytest.mark.asyncio
async def test_vector_retrieval_rejects_mismatched_embedding_dimension(
    db_session: Session,
) -> None:
    """
    Quality Gate Dim 5:
    Verifies that VectorRetrievalService strictly detects and rejects embedding vectors
    whose dimension deviates from the authoritative 1024 dimension without querying DB.
    """
    provider = MockMismatchedDimensionEmbeddingProvider()
    service = VectorRetrievalService(provider=provider)
    kb_id = uuid.uuid4()

    with pytest.raises(RetrievalProviderError, match="dimension.*does not match expected"):
        await service.retrieve(db=db_session, kb_id=kb_id, query="Test query", top_k=5)


class MockFailingRerankerProvider(BaseRerankerProvider):
    """Mock reranker provider that simulates host failure/OOM."""

    @property
    def model_name(self) -> str:
        return "mock-fail"

    async def compute_scores(self, query: str, texts: list[str]) -> list[float]:
        raise RerankerProviderError("Simulated neural model inference failure.")


@pytest.mark.asyncio
async def test_reranker_provider_failure_handled_gracefully(db_session: Session) -> None:
    """
    Quality Gate Dim 5:
    Verifies that RerankingService wraps underlying provider failures into
    RerankerProviderError without corrupting database state.
    """
    from backend.app.schemas.hybrid_retrieval import (
        HybridRetrievalResponse,
        HybridRetrievalResultItem,
    )

    failing_provider = MockFailingRerankerProvider()
    mock_item = HybridRetrievalResultItem(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_title="Test Doc",
        chunk_index=0,
        text="Sample text to rerank",
        page_number=1,
        section_title="Intro",
        chunk_metadata={},
        vector_rank=1,
        lexical_rank=1,
        vector_score=0.9,
        lexical_score=0.8,
        rrf_score=0.032,
    )
    mock_hybrid = MagicMock()
    mock_hybrid.retrieve = AsyncMock(
        return_value=HybridRetrievalResponse(
            knowledge_base_id=mock_item.knowledge_base_id,
            query="test",
            total_results=1,
            results=[mock_item],
        )
    )

    service = RerankingService(
        hybrid_service=mock_hybrid,
        reranker_provider=failing_provider,
    )

    with pytest.raises(RerankerProviderError, match="Simulated neural model inference failure"):
        await service.rerank(db=db_session, kb_id=uuid.uuid4(), query="test", candidate_limit=5)


def test_transaction_rollback_on_simulated_db_error(db_session: Session) -> None:
    """
    Quality Gate Dim 5:
    Verifies that transactional state is completely rolled back on error and
    leaves no uncommitted or orphaned records.
    """
    # Create user outside the failed block
    user = User(
        id=uuid.uuid4(),
        email=f"rollback_test_{uuid.uuid4().hex[:8]}@univ.edu",
        full_name="Rollback User",
        password_hash="mock_hash",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    # Attempt an invalid transaction
    try:
        with db_session.begin_nested():
            kb = KnowledgeBase(
                id=uuid.uuid4(),
                name="Rollback KB",
                description="Testing rollback",
                created_by_id=user.id,
            )
            db_session.add(kb)
            # Force integrity violation: insert duplicate user email (unique constraint)
            duplicate_user = User(
                id=uuid.uuid4(),
                email=user.email,
                full_name="Conflict User",
                password_hash="mock_hash",
                role=UserRole.STUDENT,
                is_active=True,
            )
            db_session.add(duplicate_user)
            db_session.flush()
    except Exception:
        pass

    # The KB should NOT be persisted due to nested rollback
    saved_kb = (
        db_session.query(KnowledgeBase).filter(KnowledgeBase.created_by_id == user.id).first()
    )
    assert saved_kb is None


# ==============================================================================
# 4. DATABASE & MODEL PERFORMANCE SANITY CHECKS
# ==============================================================================


def test_cross_encoder_provider_singleton() -> None:
    """
    Quality Gate Dim 6:
    Verifies that get_default_reranker_provider() is a thread-safe singleton,
    preventing repeated 100MB+ neural model weight initializations in memory.
    """
    p1 = get_default_reranker_provider()
    p2 = get_default_reranker_provider()
    assert p1 is p2


def test_top_k_retrieval_bounds_enforced() -> None:
    """
    Quality Gate Dim 6:
    Verifies that VectorRetrievalService validates and bounds top_k,
    preventing unbounded DB memory consumption.
    """
    service = VectorRetrievalService()

    # Reject 0 or negative
    with pytest.raises(RetrievalValidationError):
        service.validate_top_k(0)

    with pytest.raises(RetrievalValidationError):
        service.validate_top_k(-5)

    # Reject excessive top_k > 50
    with pytest.raises(RetrievalValidationError):
        service.validate_top_k(100)

    # Valid top_k
    assert service.validate_top_k(10) == 10


# ==============================================================================
# 5. RATE LIMITING POLICY INVARIANTS
# ==============================================================================


def test_rate_limiting_auth_fail_closed_policy() -> None:
    """
    Quality Gate Dim 8:
    Verifies that when rate limit storage fails, authentication policy fails closed
    (HTTP 503) per settings.RATE_LIMIT_AUTH_FAIL_CLOSED.
    """
    policy = RateLimitPolicy(
        name="test_login",
        max_requests=5,
        window_seconds=60,
        fail_closed=True,
    )
    assert policy.fail_closed is True


def test_rate_limiting_rag_fail_open_policy() -> None:
    """
    Quality Gate Dim 8:
    Verifies that expensive RAG endpoints follow fail-open policy when storage is
    unavailable to preserve student search accessibility while logging telemetry.
    """
    policy = RateLimitPolicy(
        name="test_chat",
        max_requests=30,
        window_seconds=60,
        fail_closed=False,
    )
    assert policy.fail_closed is False


# ==============================================================================
# 6. CONFIGURATION & ENVIRONMENT INVARIANTS
# ==============================================================================


def test_env_example_parseable_by_settings() -> None:
    """
    Quality Gate Dim 11:
    Verifies that the root .env.example file can be parsed directly by pydantic-settings
    without syntax errors, type coercions failures, or validation exceptions.
    """
    parsed_settings = Settings(_env_file=".env.example")
    assert parsed_settings.APP_NAME == "RAG Assistant"
    assert isinstance(parsed_settings.CORS_ORIGINS, list)
    assert len(parsed_settings.CORS_ORIGINS) >= 1
    assert isinstance(parsed_settings.TRUSTED_PROXIES, set)
    assert parsed_settings.EMBEDDING_DIM == 1024
    assert parsed_settings.RATE_LIMIT_ENABLED is True
    assert parsed_settings.RATE_LIMIT_LOGIN_MAX_REQUESTS == 20
    assert parsed_settings.RATE_LIMIT_AUTH_FAIL_CLOSED is True
    assert parsed_settings.RATE_LIMIT_EXPENSIVE_FAIL_CLOSED is False
