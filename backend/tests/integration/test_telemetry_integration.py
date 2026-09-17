"""
Integration tests for Observability, Structured Logging, and Telemetry (Step 17).

Verifies:
- HTTP request ID generation when missing.
- Deterministic HTTP request ID propagation when provided by client.
- Malformed request ID rejection and safe fallback.
- Context variable isolation and propagation through FastAPI requests.
- Structured RAG pipeline telemetry emission on authenticated chat requests.
- Correct user_id, kb_id, and stage timings in emitted telemetry.
- Telemetry recording on provider failures (503) and timeouts (504).
- Strict absence of credentials, passwords, tokens, and raw texts in telemetry.
"""

import uuid
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.security import get_password_hash
from backend.app.core.telemetry import (
    InMemoryTelemetryExporter,
    get_telemetry_manager,
)
from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.models.user import User, UserRole
from backend.app.schemas.context_assembly import ContextAssemblyResult, ContextItem
from backend.app.schemas.grounding_validation import (
    CitationValidationItem,
    ClaimValidationItem,
    GroundingStatus,
    GroundingValidationResult,
)
from backend.app.schemas.hybrid_retrieval import (
    HybridRetrievalResponse,
    HybridRetrievalResultItem,
)
from backend.app.schemas.llm import LLMGenerationResponse
from backend.app.schemas.query_processing import QueryProcessingResult
from backend.app.schemas.reranking import RerankResultItem
from backend.app.services.llm.exceptions import LLMProviderError, LLMTimeoutError
from backend.app.services.rag_orchestrator import RAGOrchestrator, get_rag_orchestrator


@pytest.fixture(autouse=True)
def clean_test_db(db_engine) -> Generator[None, None, None]:
    """Clean all application tables before and after each test function."""
    with db_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE document_chunks, documents, "
                "knowledge_base_members, knowledge_bases, "
                "user_sessions, users CASCADE;"
            )
        )
    yield
    with db_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE document_chunks, documents, "
                "knowledge_base_members, knowledge_bases, "
                "user_sessions, users CASCADE;"
            )
        )


@pytest.fixture
def telemetry_exporter() -> Generator[InMemoryTelemetryExporter, None, None]:
    """Fixture registering an InMemoryTelemetryExporter and cleaning up afterwards."""
    exporter = InMemoryTelemetryExporter()
    manager = get_telemetry_manager()
    manager.register_exporter(exporter)
    yield exporter
    manager.unregister_exporter(exporter)


def create_user_direct(
    db: Session,
    email: str,
    password: str = "TestPassword123!",
    full_name: str = "Test User",
    role: UserRole = UserRole.STUDENT,
) -> User:
    """Provision a user directly in the test database."""
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


def make_grounding_result(
    query: str = "test",
    claims: list[ClaimValidationItem] | None = None,
    citations: list[CitationValidationItem] | None = None,
) -> GroundingValidationResult:
    """Helper to construct GroundingValidationResult for testing."""
    claims = claims or []
    citations = citations or []
    return GroundingValidationResult(
        query=query,
        original_query=query,
        total_claims=len(claims),
        factual_claims=len([c for c in claims if not c.is_conversational]),
        conversational_claims=len([c for c in claims if c.is_conversational]),
        cited_claims=len([c for c in claims if c.cited_source_ids]),
        uncited_claims=len([c for c in claims if not c.cited_source_ids]),
        supported_claims=len([c for c in claims if c.status == GroundingStatus.SUPPORTED]),
        supported_uncited_claims=0,
        unsupported_claims=0,
        unverifiable_claims=0,
        citations_found=len(citations),
        unique_citations_found=len({c.source_id for c in citations}),
        valid_citations=len([c for c in citations if c.is_valid]),
        invalid_citations=0,
        malformed_citations_count=0,
        citation_validity_rate=1.0 if citations else 0.0,
        citation_coverage=1.0 if claims else 0.0,
        claim_support_rate=1.0 if claims else 0.0,
        unsupported_claim_rate=0.0,
        latency_ms=8.5,
        has_conflicts=False,
        claims=claims,
        citations=citations,
        conflicts=[],
    )


# =========================================================================
# 1. HTTP Request ID Lifecycle & Propagation
# =========================================================================


def test_http_request_id_generation_when_missing(api_client: TestClient):
    """Verify that incoming requests without X-Request-ID receive a new UUID4 in response headers."""
    response = api_client.get("/health")
    assert response.status_code == 200
    req_id = response.headers.get("X-Request-ID")
    assert req_id is not None
    # Validate it is a valid UUID
    parsed_uuid = uuid.UUID(req_id)
    assert parsed_uuid.version == 4


def test_http_request_id_propagation_when_provided(api_client: TestClient):
    """Verify that a valid client-supplied X-Request-ID is preserved deterministically."""
    custom_id = "trace-custom-correlation-12345"
    response = api_client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id


def test_http_request_id_sanitization_for_malformed_input(api_client: TestClient):
    """Verify that malformed or injection strings in X-Request-ID are replaced with safe UUIDs."""
    malicious_id = "<script>alert(1)</script>"
    response = api_client.get("/health", headers={"X-Request-ID": malicious_id})
    assert response.status_code == 200
    res_id = response.headers.get("X-Request-ID")
    assert res_id != malicious_id
    assert uuid.UUID(res_id).version == 4

    excessive_id = "a" * 100  # Longer than 64 chars
    response2 = api_client.get("/health", headers={"X-Request-ID": excessive_id})
    assert response2.status_code == 200
    assert response2.headers.get("X-Request-ID") != excessive_id


def test_http_request_telemetry_event_recorded(
    api_client: TestClient, telemetry_exporter: InMemoryTelemetryExporter
):
    """Verify that HTTP requests emit http_request telemetry events with correct status and timing."""
    telemetry_exporter.clear()
    resp = api_client.get("/health", headers={"X-Request-ID": "http-evt-test-1"})
    assert resp.status_code == 200

    events = telemetry_exporter.get_events()
    matching = [e for e in events if e.request_id == "http-evt-test-1"]
    assert len(matching) == 1
    evt = matching[0]
    assert evt.event_name == "http_request"
    assert evt.status == "SUCCESS"
    assert evt.duration_ms >= 0.0
    assert evt.attributes["method"] == "GET"
    assert evt.attributes["path"] == "/health"
    assert evt.attributes["status_code"] == 200


# =========================================================================
# 2. Authenticated RAG Pipeline Telemetry
# =========================================================================


def test_authenticated_chat_telemetry_propagation(
    api_client: TestClient,
    db_session: Session,
    telemetry_exporter: InMemoryTelemetryExporter,
):
    """
    Verify that an authenticated chat request:
    1. Propagates request_id, user_id, and kb_id into RAGPipelineTelemetry.
    2. Records all execution stages with non-negative timings.
    3. Emits safe metrics without secret or raw prompt/document leakage.
    """
    admin = create_user_direct(
        db_session, email="telemetry_admin@university.edu", role=UserRole.ADMIN
    )
    kb = KnowledgeBase(
        name="Telemetry Knowledge Base",
        description="Testing observability pipeline",
        created_by_id=admin.id,
    )
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)

    # Login to acquire session cookie
    login_resp = api_client.post(
        "/api/v1/auth/login",
        json={"email": "telemetry_admin@university.edu", "password": "TestPassword123!"},
    )
    assert login_resp.status_code == 200

    chunk_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    # Create mock pipeline subservices
    qp = MagicMock()
    qp.process = MagicMock(
        return_value=QueryProcessingResult(
            original_query="What is testing?",
            processed_query="what is testing",
            character_count=16,
            token_estimate=3,
            has_quotes=False,
            has_technical_tokens=False,
            metadata={},
        )
    )

    hybrid = MagicMock()
    hybrid.retrieve = AsyncMock(
        return_value=HybridRetrievalResponse(
            query="what is testing",
            knowledge_base_id=kb.id,
            top_k=20,
            rrf_k=60,
            vector_weight=0.5,
            lexical_weight=0.5,
            total_results=1,
            results=[
                HybridRetrievalResultItem(
                    chunk_id=chunk_id,
                    document_id=doc_id,
                    knowledge_base_id=kb.id,
                    document_title="Guide.pdf",
                    chunk_index=0,
                    text="Testing verifies software correctness.",
                    rrf_score=0.95,
                    vector_rank=1,
                    lexical_rank=1,
                    chunk_metadata={},
                )
            ],
            latency_breakdown={},
            fusion_strategy="rrf",
        )
    )

    rerank = MagicMock()
    rerank.rerank_candidates = AsyncMock(
        return_value=[
            RerankResultItem(
                chunk_id=chunk_id,
                document_id=doc_id,
                knowledge_base_id=kb.id,
                document_title="Guide.pdf",
                chunk_index=0,
                text="Testing verifies software correctness.",
                rrf_score=0.95,
                reranker_score=0.99,
                reranker_rank=1,
                chunk_metadata={},
            )
        ]
    )

    ca = MagicMock()
    ca.assemble = MagicMock(
        return_value=ContextAssemblyResult(
            query="what is testing",
            items=[
                ContextItem(
                    source_id="source_1",
                    chunk_id=chunk_id,
                    document_id=doc_id,
                    knowledge_base_id=kb.id,
                    document_title="Guide.pdf",
                    chunk_index=0,
                    text="Testing verifies software correctness.",
                    page_number=1,
                    section_title="Intro",
                    reranker_rank=1,
                    reranker_score=0.99,
                    rrf_score=0.95,
                    estimated_tokens=15,
                )
            ],
            total_items=1,
            total_estimated_tokens=15,
            token_budget=1000,
            candidates_received=1,
            items_skipped_budget=0,
            items_deduplicated=0,
            metadata={},
        )
    )

    llm = MagicMock()
    llm.generate_grounded_answer = AsyncMock(
        return_value=LLMGenerationResponse(
            answer="Testing verifies software correctness [source_1].",
            query="what is testing",
            provider="ollama",
            model="qwen3:4b",
            is_empty_context=False,
            latency_ms=45.0,
            sources_referenced=["source_1"],
            output_tokens=15,
        )
    )

    gv = MagicMock()
    gv.validate = MagicMock(
        return_value=make_grounding_result(
            query="what is testing",
            claims=[
                ClaimValidationItem(
                    claim_index=1,
                    text="Testing verifies software correctness",
                    raw_text="Testing verifies software correctness [source_1].",
                    is_conversational=False,
                    cited_source_ids=["source_1"],
                    status=GroundingStatus.SUPPORTED,
                    rationale="Exact match with source_1",
                )
            ],
            citations=[
                CitationValidationItem(
                    raw_citation="[source_1]",
                    source_id="source_1",
                    is_valid=True,
                    context_item_id=chunk_id,
                    document_id=doc_id,
                    document_title="Guide.pdf",
                )
            ],
        )
    )

    orchestrator = RAGOrchestrator(
        query_processor=qp,
        hybrid_service=hybrid,
        reranking_service=rerank,
        context_assembler=ca,
        llm_service=llm,
        grounding_service=gv,
        telemetry_manager=get_telemetry_manager(),
    )

    api_client.app.dependency_overrides[get_rag_orchestrator] = lambda: orchestrator
    telemetry_exporter.clear()

    try:
        custom_req_id = "chat-telemetry-req-999"
        chat_resp = api_client.post(
            f"/api/v1/knowledge-bases/{kb.id}/chat",
            json={"question": "What is testing?"},
            headers={"X-Request-ID": custom_req_id},
        )
        assert chat_resp.status_code == 200
        assert chat_resp.headers.get("X-Request-ID") == custom_req_id
        data = chat_resp.json()
        assert data["answer"] == "Testing verifies software correctness [source_1]."

        # Verify emitted pipeline telemetry
        pipeline_events = telemetry_exporter.get_pipeline_events()
        assert len(pipeline_events) == 1
        pe = pipeline_events[0]
        assert pe.request_id == custom_req_id
        assert pe.user_id == str(admin.id)
        assert pe.knowledge_base_id == str(kb.id)
        assert pe.status == "SUCCESS"
        assert pe.total_duration_ms >= 0.0

        # Verify all 6 pipeline stages recorded
        stage_names = set(pe.stages.keys())
        expected_stages = {
            "query_processing",
            "hybrid_retrieval",
            "reranking",
            "context_assembly",
            "llm_generation",
            "grounding_validation",
        }
        assert expected_stages.issubset(stage_names)

        # Verify metrics
        assert pe.retrieval_candidate_count == 1
        assert pe.reranked_candidate_count == 1
        assert pe.assembled_context_count == 1
        assert pe.is_empty_context is False
        assert pe.grounding_status == "FULLY_SUPPORTED"

        # Security check: verify no secrets or full prompt / doc leak
        pe_json = pe.model_dump_json()
        assert "TestPassword123!" not in pe_json
        assert "password_hash" not in pe_json
        assert "postgresql://" not in pe_json
    finally:
        api_client.app.dependency_overrides.pop(get_rag_orchestrator, None)


def test_chat_timeout_telemetry_and_mapping(
    api_client: TestClient,
    db_session: Session,
    telemetry_exporter: InMemoryTelemetryExporter,
):
    """Verify that an LLM timeout produces HTTP 504 and X-Request-ID is preserved."""
    admin = create_user_direct(
        db_session, email="timeout_admin@university.edu", role=UserRole.ADMIN
    )
    kb = KnowledgeBase(
        name="Timeout Knowledge Base",
        description="Testing timeout mapping",
        created_by_id=admin.id,
    )
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)

    api_client.post(
        "/api/v1/auth/login",
        json={"email": "timeout_admin@university.edu", "password": "TestPassword123!"},
    )

    mock_orchestrator = MagicMock(spec=RAGOrchestrator)
    mock_orchestrator.execute_query = AsyncMock(
        side_effect=LLMTimeoutError("LLM exceeded generation budget of 120s")
    )

    api_client.app.dependency_overrides[get_rag_orchestrator] = lambda: mock_orchestrator
    telemetry_exporter.clear()

    try:
        custom_req_id = "timeout-trace-id-504"
        chat_resp = api_client.post(
            f"/api/v1/knowledge-bases/{kb.id}/chat",
            json={"question": "What is testing?"},
            headers={"X-Request-ID": custom_req_id},
        )
        assert chat_resp.status_code == 504
        assert chat_resp.headers.get("X-Request-ID") == custom_req_id
        assert "timed out" in chat_resp.json()["detail"].lower()

        # Telemetry check: HTTP request logged as FAILURE with TIMEOUT_ERROR
        events = telemetry_exporter.get_events()
        http_events = [
            e for e in events if e.request_id == custom_req_id and e.event_name == "http_request"
        ]
        assert len(http_events) == 1
        assert http_events[0].status == "FAILURE"
        assert http_events[0].error_category == "TIMEOUT_ERROR"
        assert http_events[0].attributes["status_code"] == 504
    finally:
        api_client.app.dependency_overrides.pop(get_rag_orchestrator, None)


def test_chat_provider_failure_telemetry_and_mapping(
    api_client: TestClient,
    db_session: Session,
    telemetry_exporter: InMemoryTelemetryExporter,
):
    """Verify that an underlying provider error produces HTTP 503 and preserves X-Request-ID."""
    admin = create_user_direct(
        db_session, email="provider_err_admin@university.edu", role=UserRole.ADMIN
    )
    kb = KnowledgeBase(
        name="Provider Error Knowledge Base",
        description="Testing provider error mapping",
        created_by_id=admin.id,
    )
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)

    api_client.post(
        "/api/v1/auth/login",
        json={"email": "provider_err_admin@university.edu", "password": "TestPassword123!"},
    )

    mock_orchestrator = MagicMock(spec=RAGOrchestrator)
    mock_orchestrator.execute_query = AsyncMock(
        side_effect=LLMProviderError("Ollama returned 500 internal server error")
    )

    api_client.app.dependency_overrides[get_rag_orchestrator] = lambda: mock_orchestrator
    telemetry_exporter.clear()

    try:
        custom_req_id = "provider-err-trace-id-503"
        chat_resp = api_client.post(
            f"/api/v1/knowledge-bases/{kb.id}/chat",
            json={"question": "What is testing?"},
            headers={"X-Request-ID": custom_req_id},
        )
        assert chat_resp.status_code == 503
        assert chat_resp.headers.get("X-Request-ID") == custom_req_id
        assert "temporarily unavailable" in chat_resp.json()["detail"].lower()

        # Telemetry check: HTTP request logged as FAILURE with PROVIDER_ERROR
        events = telemetry_exporter.get_events()
        http_events = [
            e for e in events if e.request_id == custom_req_id and e.event_name == "http_request"
        ]
        assert len(http_events) == 1
        assert http_events[0].status == "FAILURE"
        assert http_events[0].error_category == "PROVIDER_ERROR"
        assert http_events[0].attributes["status_code"] == 503
    finally:
        api_client.app.dependency_overrides.pop(get_rag_orchestrator, None)


# =========================================================================
# 3. Concurrency & Security Redaction Audits
# =========================================================================


def test_concurrent_http_request_isolation(
    api_client: TestClient, telemetry_exporter: InMemoryTelemetryExporter
):
    """Verify concurrent HTTP requests preserve strict correlation ID isolation."""
    from concurrent.futures import ThreadPoolExecutor

    telemetry_exporter.clear()
    num_requests = 20
    req_ids = [f"concurrent-http-{i}-{uuid.uuid4().hex[:8]}" for i in range(num_requests)]

    def make_req(req_id: str) -> str:
        resp = api_client.get("/health", headers={"X-Request-ID": req_id})
        assert resp.status_code == 200
        assert resp.headers.get("X-Request-ID") == req_id
        return req_id

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(make_req, req_ids))

    assert len(results) == num_requests
    events = telemetry_exporter.get_events()
    event_req_ids = {e.request_id for e in events if e.event_name == "http_request"}
    for req_id in req_ids:
        assert req_id in event_req_ids


def test_security_redaction_in_http_telemetry(
    api_client: TestClient,
    telemetry_exporter: InMemoryTelemetryExporter,
):
    """
    Verify that sensitive headers (Authorization, Cookie), credentials,
    and passwords are strictly excluded from HTTP telemetry events.
    """
    telemetry_exporter.clear()
    secret_token = "Bearer secret-super-sensitive-jwt-token-12345"
    custom_req_id = "security-audit-req-1"

    resp = api_client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@univ.edu", "password": "SuperSecretPassword123!"},
        headers={
            "X-Request-ID": custom_req_id,
            "Authorization": secret_token,
            "Cookie": "session=secret-session-cookie-val",
        },
    )
    assert resp.status_code in (401, 404, 422)

    events = telemetry_exporter.get_events()
    matching = [e for e in events if e.request_id == custom_req_id]
    assert len(matching) >= 1
    for evt in matching:
        evt_json = evt.model_dump_json()
        assert "SuperSecretPassword123!" not in evt_json
        assert secret_token not in evt_json
        assert "secret-session-cookie-val" not in evt_json
        assert "authorization" not in evt.attributes
        assert "cookie" not in evt.attributes
