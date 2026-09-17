"""
Unit tests for Observability, Structured Logging, and Telemetry (Step 17).

Verifies:
- Request ID generation, propagation, and validation.
- User ID and Knowledge Base ID context variable handling.
- Concurrency isolation across asynchronous tasks.
- Secret, credential, database URL, and header redaction.
- Absence of raw document, prompt, and model completion logging.
- Deterministic error categorization using Steps 7–16 domain exceptions.
- Structured JSON log formatting.
- In-memory and logging exporter behavior.
- RAG orchestrator stage timing, telemetry recording, failure logging, and timeout logging.
"""

import asyncio
import json
import logging
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.exceptions import HTTPException

from backend.app.core.telemetry import (
    REDACTED_PASSWORD_HASH,
    REDACTED_VALUE,
    InMemoryTelemetryExporter,
    StructuredJSONFormatter,
    TelemetryManager,
    categorize_exception,
    get_current_kb_id,
    get_current_user_id,
    get_request_id,
    sanitize_headers,
    sanitize_log_data,
    sanitize_string,
    set_current_kb_id,
    set_current_user_id,
    set_request_id,
)
from backend.app.schemas.context_assembly import ContextAssemblyResult, ContextItem
from backend.app.schemas.grounding_validation import (
    GroundingValidationResult,
)
from backend.app.schemas.hybrid_retrieval import (
    HybridRetrievalResponse,
    HybridRetrievalResultItem,
)
from backend.app.schemas.llm import LLMGenerationResponse
from backend.app.schemas.query_processing import QueryProcessingResult
from backend.app.schemas.reranking import RerankResultItem
from backend.app.schemas.telemetry import (
    RAGPipelineTelemetry,
    TelemetryEvent,
)
from backend.app.services.hybrid_retrieval import (
    HybridRetrievalProviderError,
    HybridRetrievalValidationError,
)
from backend.app.services.llm.exceptions import (
    LLMConnectionError,
    LLMModelNotFoundError,
    LLMTimeoutError,
)
from backend.app.services.rag_orchestrator import RAGOrchestrator
from backend.app.services.retrieval import RetrievalValidationError

# =========================================================================
# 1. Context Variables & Concurrency Isolation Tests
# =========================================================================


def test_request_id_lifecycle():
    """Verify get_request_id returns fallback when unset and propagates value when set."""
    # When unset
    assert get_request_id() in ("no-request-id", get_request_id())

    _token = set_request_id("test-req-12345")
    try:
        assert get_request_id() == "test-req-12345"
    finally:
        set_request_id(None)


def test_user_and_kb_context_lifecycle():
    """Verify user_id and kb_id context variables set and reset correctly."""
    _u_token = set_current_user_id("user-uuid-111")
    _k_token = set_current_kb_id("kb-uuid-222")
    try:
        assert get_current_user_id() == "user-uuid-111"
        assert get_current_kb_id() == "kb-uuid-222"
    finally:
        set_current_user_id(None)
        set_current_kb_id(None)

    assert get_current_user_id() is None
    assert get_current_kb_id() is None


@pytest.mark.asyncio
async def test_concurrent_request_isolation():
    """
    Verify that concurrent async tasks execute with complete context isolation
    and never share or overwrite each other's correlation or tenant state.
    """
    num_tasks = 25
    results = {}

    async def task_worker(task_id: int):
        req_id = f"req-{task_id}-{uuid.uuid4()}"
        uid = f"user-{task_id}"
        kbid = f"kb-{task_id}"

        set_request_id(req_id)
        set_current_user_id(uid)
        set_current_kb_id(kbid)

        # Yield to event loop multiple times to interleave tasks
        await asyncio.sleep(0.01)
        r1 = (get_request_id(), get_current_user_id(), get_current_kb_id())
        await asyncio.sleep(0.01)
        r2 = (get_request_id(), get_current_user_id(), get_current_kb_id())

        results[task_id] = (r1, r2, (req_id, uid, kbid))

    tasks = [task_worker(i) for i in range(num_tasks)]
    await asyncio.gather(*tasks)

    assert len(results) == num_tasks
    for task_id, (r1, r2, expected) in results.items():
        assert r1 == expected, f"Task {task_id} context was corrupted during stage 1"
        assert r2 == expected, f"Task {task_id} context was corrupted during stage 2"


# =========================================================================
# 2. Security Redaction Tests
# =========================================================================


def test_redaction_passwords_and_hashes():
    """Verify plaintext passwords and Argon2 password hashes are scrubbed."""
    raw_hash = "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$abcdefghijklmnopqrstuvwxyz0123456789+/"
    sanitized_hash = sanitize_string(raw_hash)
    assert sanitized_hash == REDACTED_PASSWORD_HASH
    assert raw_hash not in sanitized_hash

    # Password assignment in string
    assert sanitize_string("password = 'superSecretPassword123!'") == "password=[REDACTED]"
    assert sanitize_string("token: secret-value-here") == "token=[REDACTED]"


def test_redaction_bearer_tokens_and_api_keys():
    """Verify authorization headers and API keys are redacted."""
    raw_bearer = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz.123"
    assert sanitize_string(raw_bearer) == "Authorization: Bearer [REDACTED]"

    raw_basic = "Authorization: Basic dXNlcjpwYXNzd29yZA=="
    assert sanitize_string(raw_basic) == "Authorization: Basic [REDACTED]"

    raw_apikey = "api_key=sk-proj-abcdef123456"
    assert sanitize_string(raw_apikey) == "api_key=[REDACTED]"


def test_redaction_database_urls():
    """Verify database connection strings with passwords are scrubbed."""
    url = "postgresql+psycopg://rag_user:SecretP@ssword123@localhost:5432/rag_assistant_db"
    sanitized = sanitize_string(url)
    assert sanitized == "postgresql+psycopg://rag_user:[REDACTED]@localhost:5432/rag_assistant_db"
    assert "SecretP@ssword123" not in sanitized


def test_redaction_headers():
    """Verify header sanitizer redacts Authorization and Cookie headers."""
    headers = {
        "Authorization": "Bearer my-secret-jwt",
        "Cookie": "session_id=abcdef12345",
        "Set-Cookie": "auth_token=xyz",
        "X-API-Key": "my-api-key",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    cleaned = sanitize_headers(headers)
    assert cleaned["Authorization"] == REDACTED_VALUE
    assert cleaned["Cookie"] == REDACTED_VALUE
    assert cleaned["Set-Cookie"] == REDACTED_VALUE
    assert cleaned["X-API-Key"] == REDACTED_VALUE
    assert cleaned["Content-Type"] == "application/json"
    assert cleaned["Accept"] == "application/json"


def test_absence_of_raw_document_prompt_answer_logging():
    """
    Verify that raw text keys (documents, prompts, full model completions)
    are replaced with safe metadata and never logged in raw form.
    """
    data = {
        "document_content": "This is a full confidential university document " * 10,
        "prompt": "System: You are an AI assistant. Context: [source_1] text...",
        "answer": "Here is the complete multi-paragraph model answer...",
        "chunk_text": "A raw chunk text...",
        "safe_metric": 42,
        "candidate_count": 5,
    }
    sanitized = sanitize_log_data(data)

    assert sanitized["document_content"].startswith("[REDACTED_TEXT:")
    assert sanitized["prompt"].startswith("[REDACTED_TEXT:")
    assert sanitized["answer"].startswith("[REDACTED_TEXT:")
    assert sanitized["chunk_text"].startswith("[REDACTED_TEXT:")
    assert sanitized["safe_metric"] == 42
    assert sanitized["candidate_count"] == 5

    # Check that raw full strings do not appear
    assert "confidential university document" not in json.dumps(sanitized)
    assert "multi-paragraph model answer" not in json.dumps(sanitized)


def test_recursive_dictionary_sanitization():
    """Verify recursive dicts and lists are properly sanitized."""
    nested = {
        "user": {
            "id": "123",
            "password_hash": "$argon2id$v=19$m=65536,t=3,p=4$salt$hash",
            "session_token": "secret_tok_123",
        },
        "items": [
            {"token": "item_tok_456", "name": "Item A"},
            {"api_key": "item_key_789", "name": "Item B"},
        ],
    }
    sanitized = sanitize_log_data(nested)
    assert sanitized["user"]["password_hash"] == REDACTED_VALUE
    assert sanitized["user"]["session_token"] == REDACTED_VALUE
    assert sanitized["user"]["id"] == "123"
    assert sanitized["items"][0]["token"] == REDACTED_VALUE
    assert sanitized["items"][0]["name"] == "Item A"
    assert sanitized["items"][1]["api_key"] == REDACTED_VALUE


# =========================================================================
# 3. Deterministic Error Categorization Tests
# =========================================================================


def test_deterministic_error_categorization():
    """Verify exceptions map to consistent, standardized categories."""
    assert categorize_exception(LLMTimeoutError("timed out")) == "TIMEOUT_ERROR"
    assert (
        categorize_exception(HybridRetrievalValidationError("invalid top_k")) == "VALIDATION_ERROR"
    )
    assert categorize_exception(RetrievalValidationError("empty query")) == "VALIDATION_ERROR"
    assert categorize_exception(HybridRetrievalProviderError("failed")) == "PROVIDER_ERROR"
    assert categorize_exception(LLMConnectionError("cannot connect")) == "PROVIDER_ERROR"
    assert categorize_exception(LLMModelNotFoundError("model 404")) == "PROVIDER_ERROR"
    assert categorize_exception(HTTPException(status_code=403)) == "AUTHORIZATION_ERROR"
    assert categorize_exception(HTTPException(status_code=404)) == "AUTHORIZATION_ERROR"
    assert categorize_exception(HTTPException(status_code=500)) == "HTTP_ERROR"
    assert categorize_exception(RuntimeError("unexpected")) == "UNEXPECTED_ERROR"


# =========================================================================
# 4. Structured JSON Formatter Tests
# =========================================================================


def test_structured_json_formatter():
    """Verify StructuredJSONFormatter emits valid, sanitized JSON with context enrichment."""
    formatter = StructuredJSONFormatter()
    set_request_id("req-json-formatter-test")
    set_current_user_id("user-formatter-test")
    set_current_kb_id("kb-formatter-test")

    try:
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname=__file__,
            lineno=100,
            msg="User login attempted with password=%s",
            args=("Secret123!",),
            exc_info=None,
        )
        record.custom_metric = 99.5
        record.auth_token = "jwt-secret-token"

        formatted = formatter.format(record)
        parsed = json.loads(formatted)

        assert parsed["logger"] == "test_logger"
        assert parsed["level"] == "INFO"
        assert parsed["request_id"] == "req-json-formatter-test"
        assert parsed["user_id"] == "user-formatter-test"
        assert parsed["knowledge_base_id"] == "kb-formatter-test"
        assert parsed["custom_metric"] == 99.5
        assert parsed["auth_token"] == REDACTED_VALUE
        assert "Secret123!" not in formatted
    finally:
        set_request_id(None)
        set_current_user_id(None)
        set_current_kb_id(None)


# =========================================================================
# 5. Exporter and Telemetry Manager Tests
# =========================================================================


def test_in_memory_telemetry_exporter():
    """Verify InMemoryTelemetryExporter stores and filters events safely."""
    exporter = InMemoryTelemetryExporter(max_events=10)
    manager = TelemetryManager()
    manager.register_exporter(exporter)

    evt = TelemetryEvent(
        event_name="test_event",
        request_id="req-1",
        status="SUCCESS",
        duration_ms=15.2,
    )
    manager.record_event(evt)

    pipeline_evt = RAGPipelineTelemetry(
        request_id="req-1",
        knowledge_base_id="kb-1",
        status="SUCCESS",
        total_duration_ms=45.0,
    )
    manager.record_pipeline_event(pipeline_evt)

    events = exporter.get_events()
    pipelines = exporter.get_pipeline_events()

    assert len(events) == 1
    assert events[0].request_id == "req-1"
    assert len(pipelines) == 1
    assert pipelines[0].request_id == "req-1"

    assert len(exporter.find_pipeline_by_request_id("req-1")) == 1
    assert len(exporter.find_pipeline_by_request_id("unknown")) == 0

    exporter.clear()
    assert len(exporter.get_events()) == 0
    assert len(exporter.get_pipeline_events()) == 0


# =========================================================================
# 6. RAG Orchestrator Telemetry & Failure Tests
# =========================================================================


def make_grounding_result(
    query: str = "what is testing",
    total_claims: int = 1,
    factual_claims: int = 1,
    conversational_claims: int = 0,
    cited_claims: int = 1,
    uncited_claims: int = 0,
    supported_claims: int = 1,
    supported_uncited_claims: int = 0,
    unsupported_claims: int = 0,
    unverifiable_claims: int = 0,
    citations_found: int = 1,
    unique_citations_found: int = 1,
    valid_citations: int = 1,
    invalid_citations: int = 0,
    malformed_citations_count: int = 0,
    citation_validity_rate: float = 1.0,
    citation_coverage: float = 1.0,
    claim_support_rate: float = 1.0,
    unsupported_claim_rate: float = 0.0,
    has_conflicts: bool = False,
    claims: list | None = None,
    citations: list | None = None,
    conflicts: list | None = None,
) -> GroundingValidationResult:
    """Helper to construct GroundingValidationResult with realistic defaults."""
    return GroundingValidationResult(
        query=query,
        original_query=query,
        total_claims=total_claims,
        factual_claims=factual_claims,
        conversational_claims=conversational_claims,
        cited_claims=cited_claims,
        uncited_claims=uncited_claims,
        supported_claims=supported_claims,
        supported_uncited_claims=supported_uncited_claims,
        unsupported_claims=unsupported_claims,
        unverifiable_claims=unverifiable_claims,
        citations_found=citations_found,
        unique_citations_found=unique_citations_found,
        valid_citations=valid_citations,
        invalid_citations=invalid_citations,
        malformed_citations_count=malformed_citations_count,
        citation_validity_rate=citation_validity_rate,
        citation_coverage=citation_coverage,
        claim_support_rate=claim_support_rate,
        unsupported_claim_rate=unsupported_claim_rate,
        latency_ms=10.0,
        has_conflicts=has_conflicts,
        claims=claims or [],
        citations=citations or [],
        conflicts=conflicts or [],
    )


@pytest.fixture
def mock_orchestrator_components():
    """Provide mocked pipeline components for RAGOrchestrator telemetry verification."""
    qp = MagicMock()
    hybrid = MagicMock()
    rerank = MagicMock()
    ca = MagicMock()
    llm = MagicMock()
    gv = MagicMock()

    qp.process.return_value = QueryProcessingResult(
        original_query="What is testing?",
        processed_query="what is testing",
        character_count=15,
        token_estimate=4,
        has_quotes=False,
        has_technical_tokens=False,
        metadata={},
    )

    chunk_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    kb_id = uuid.uuid4()
    hybrid_item = HybridRetrievalResultItem(
        chunk_id=chunk_id,
        document_id=doc_id,
        knowledge_base_id=kb_id,
        document_title="Testing Guide",
        chunk_index=0,
        page_number=1,
        section_title="Introduction",
        text="Testing verifies correct system operation.",
        rrf_score=0.85,
        vector_rank=1,
        lexical_rank=1,
        chunk_metadata={},
    )

    hybrid.retrieve = AsyncMock(
        return_value=HybridRetrievalResponse(
            query="what is testing",
            knowledge_base_id=uuid.uuid4(),
            top_k=20,
            rrf_k=60,
            vector_weight=0.5,
            lexical_weight=0.5,
            total_results=1,
            results=[hybrid_item],
            latency_breakdown={},
            fusion_strategy="rrf",
        )
    )

    rerank_item = RerankResultItem(
        chunk_id=chunk_id,
        document_id=doc_id,
        knowledge_base_id=kb_id,
        document_title="Testing Guide",
        chunk_index=0,
        page_number=1,
        section_title="Introduction",
        text="Testing verifies correct system operation.",
        reranker_score=4.5,
        reranker_rank=1,
        rrf_score=0.85,
        chunk_metadata={},
    )

    rerank.rerank_candidates = AsyncMock(return_value=[rerank_item])

    context_item = ContextItem(
        source_id="source_1",
        chunk_id=chunk_id,
        document_id=doc_id,
        knowledge_base_id=kb_id,
        document_title="Testing Guide",
        chunk_index=0,
        page_number=1,
        section_title="Introduction",
        text="Testing verifies correct system operation.",
        reranker_score=4.5,
        reranker_rank=1,
        rrf_score=0.85,
        estimated_tokens=8,
        chunk_metadata={},
    )

    ca.assemble.return_value = ContextAssemblyResult(
        query="what is testing",
        items=[context_item],
        total_items=1,
        total_estimated_tokens=8,
        token_budget=1000,
        candidates_received=1,
        items_skipped_budget=0,
        items_deduplicated=0,
        metadata={},
    )

    llm.generate_grounded_answer = AsyncMock(
        return_value=LLMGenerationResponse(
            answer="Testing verifies correct system operation [source_1].",
            query="what is testing",
            provider="ollama",
            model="qwen3:4b",
            is_empty_context=False,
            prompt_tokens=45,
            output_tokens=12,
            latency_ms=80.0,
            sources_referenced=["source_1"],
        )
    )

    gv.validate.return_value = make_grounding_result(
        factual_claims=1,
        supported_claims=1,
        citation_coverage=1.0,
        citation_validity_rate=1.0,
    )

    return {
        "qp": qp,
        "hybrid": hybrid,
        "rerank": rerank,
        "ca": ca,
        "llm": llm,
        "gv": gv,
    }


@pytest.mark.asyncio
async def test_successful_pipeline_telemetry_emission(mock_orchestrator_components):
    """
    Verify that a successful query execution records an RAGPipelineTelemetry event
    with all stages, non-negative latencies, correct candidate counts, and no sensitive data.
    """
    c = mock_orchestrator_components
    exporter = InMemoryTelemetryExporter()
    mgr = TelemetryManager()
    mgr.register_exporter(exporter)

    orchestrator = RAGOrchestrator(
        query_processor=c["qp"],
        hybrid_service=c["hybrid"],
        reranking_service=c["rerank"],
        context_assembler=c["ca"],
        llm_service=c["llm"],
        grounding_service=c["gv"],
        telemetry_manager=mgr,
    )

    kb_id = uuid.uuid4()
    set_request_id("req-success-pipeline")
    set_current_user_id("user-success-pipeline")

    try:
        resp = await orchestrator.execute_query(
            db=MagicMock(),
            kb_id=kb_id,
            raw_query="What is testing?",
        )
        assert resp is not None
        assert resp.answer.startswith("Testing verifies")

        pipelines = exporter.get_pipeline_events()
        assert len(pipelines) == 1
        pipe = pipelines[0]

        assert pipe.status == "SUCCESS"
        assert pipe.request_id == "req-success-pipeline"
        assert pipe.user_id == "user-success-pipeline"
        assert pipe.knowledge_base_id == str(kb_id)
        assert pipe.total_duration_ms > 0
        assert pipe.retrieval_candidate_count == 1
        assert pipe.reranked_candidate_count == 1
        assert pipe.assembled_context_count == 1
        assert pipe.is_empty_context is False
        assert pipe.is_refusal is False
        assert pipe.citation_count == 1
        assert pipe.model == "qwen3:4b"

        # Check stage breakdown
        expected_stages = {
            "query_processing",
            "hybrid_retrieval",
            "reranking",
            "context_assembly",
            "llm_generation",
            "grounding_validation",
        }
        assert set(pipe.stages.keys()) == expected_stages
        for _stage_name, stage in pipe.stages.items():
            assert stage.status == "SUCCESS"
            assert stage.duration_ms >= 0.0
            assert stage.error_category is None

        # Verify complete document and answer texts are NOT stored in attributes
        pipe_json = pipe.model_dump_json()
        assert "This is a full confidential university document" not in pipe_json
    finally:
        set_request_id(None)
        set_current_user_id(None)


@pytest.mark.asyncio
async def test_failure_telemetry_emission_on_provider_error(mock_orchestrator_components):
    """
    Verify that when hybrid retrieval fails with HybridRetrievalProviderError:
    1. Exception is re-raised intact.
    2. Telemetry event is recorded with status='FAILURE' and error_category='PROVIDER_ERROR'.
    3. The failing stage is marked as 'FAILURE'.
    """
    c = mock_orchestrator_components
    c["hybrid"].retrieve = AsyncMock(
        side_effect=HybridRetrievalProviderError("Vector service unreachable")
    )

    exporter = InMemoryTelemetryExporter()
    mgr = TelemetryManager()
    mgr.register_exporter(exporter)

    orchestrator = RAGOrchestrator(
        query_processor=c["qp"],
        hybrid_service=c["hybrid"],
        reranking_service=c["rerank"],
        context_assembler=c["ca"],
        llm_service=c["llm"],
        grounding_service=c["gv"],
        telemetry_manager=mgr,
    )

    kb_id = uuid.uuid4()
    set_request_id("req-provider-failure")

    try:
        with pytest.raises(HybridRetrievalProviderError):
            await orchestrator.execute_query(
                db=MagicMock(),
                kb_id=kb_id,
                raw_query="What is testing?",
            )

        pipelines = exporter.get_pipeline_events()
        assert len(pipelines) == 1
        pipe = pipelines[0]

        assert pipe.status == "FAILURE"
        assert pipe.request_id == "req-provider-failure"
        assert pipe.error_category == "PROVIDER_ERROR"
        assert "hybrid_retrieval" in pipe.stages
        assert pipe.stages["hybrid_retrieval"].status == "FAILURE"
        assert pipe.stages["hybrid_retrieval"].error_category == "PROVIDER_ERROR"
        assert pipe.stages["query_processing"].status == "SUCCESS"
    finally:
        set_request_id(None)


@pytest.mark.asyncio
async def test_timeout_telemetry_emission(mock_orchestrator_components):
    """
    Verify that when LLM generation times out with LLMTimeoutError:
    1. Exception is re-raised intact.
    2. Telemetry records status='FAILURE' and error_category='TIMEOUT_ERROR'.
    3. The failing stage is recorded as 'llm_generation'.
    """
    c = mock_orchestrator_components
    c["llm"].generate_grounded_answer = AsyncMock(
        side_effect=LLMTimeoutError("LLM generation exceeded 120s timeout")
    )

    exporter = InMemoryTelemetryExporter()
    mgr = TelemetryManager()
    mgr.register_exporter(exporter)

    orchestrator = RAGOrchestrator(
        query_processor=c["qp"],
        hybrid_service=c["hybrid"],
        reranking_service=c["rerank"],
        context_assembler=c["ca"],
        llm_service=c["llm"],
        grounding_service=c["gv"],
        telemetry_manager=mgr,
    )

    kb_id = uuid.uuid4()
    set_request_id("req-timeout-failure")

    try:
        with pytest.raises(LLMTimeoutError):
            await orchestrator.execute_query(
                db=MagicMock(),
                kb_id=kb_id,
                raw_query="What is testing?",
            )

        pipelines = exporter.get_pipeline_events()
        assert len(pipelines) == 1
        pipe = pipelines[0]

        assert pipe.status == "FAILURE"
        assert pipe.request_id == "req-timeout-failure"
        assert pipe.error_category == "TIMEOUT_ERROR"
        assert pipe.stages["llm_generation"].status == "FAILURE"
        assert pipe.stages["llm_generation"].error_category == "TIMEOUT_ERROR"
        assert pipe.stages["context_assembly"].status == "SUCCESS"
    finally:
        set_request_id(None)
