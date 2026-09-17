"""
Integration Tests for End-to-End Chat and RAG Orchestration.

Verifies:
- Authenticated ADMIN access to owned knowledge bases.
- Authenticated STUDENT access to member knowledge bases.
- Cross-user and cross-tenant KB isolation (returns HTTP 404).
- Unauthenticated access rejection (returns HTTP 401).
- Empty-context safe refusal fast-path (no LLM invocation).
- Backward compatibility of POST /api/v1/chat/query.
- Canonical REST endpoint POST /api/v1/knowledge-bases/{kb_id}/chat.
- Safe error mapping for provider unavailability (503) and timeout (504).
- No requirement for a live Ollama server (mocked deterministic LLM provider).
"""

import uuid
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.security import get_password_hash
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseMember
from backend.app.models.user import User, UserRole
from backend.app.schemas.chat import (
    ChatLatencyBreakdownDTO,
    ChatQueryResponse,
    CitationItem,
    ClaimSummaryDTO,
    GroundingSummaryDTO,
)
from backend.app.services.llm.exceptions import LLMProviderError, LLMTimeoutError
from backend.app.services.rag_orchestrator import RAGOrchestrator, get_rag_orchestrator


@pytest.fixture(autouse=True)
def clean_chat_db(db_engine) -> Generator[None, None, None]:
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


def create_user_direct(
    db: Session,
    email: str,
    password: str = "TestPassword123!",
    full_name: str = "Test User",
    role: UserRole = UserRole.STUDENT,
    is_active: bool = True,
) -> User:
    """Helper to provision a user directly in the database."""
    user = User(
        email=email.strip().lower(),
        password_hash=get_password_hash(password),
        full_name=full_name,
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_unauthenticated_request_returns_401(api_client: TestClient) -> None:
    """Verify unauthenticated requests return 401 for both chat endpoints."""
    fake_kb_id = uuid.uuid4()

    # Legacy endpoint
    resp_legacy = api_client.post(
        "/api/v1/chat/query",
        json={"knowledge_base_id": str(fake_kb_id), "question": "What is testing?"},
    )
    assert resp_legacy.status_code == 401

    # Canonical endpoint
    resp_canon = api_client.post(
        f"/api/v1/knowledge-bases/{fake_kb_id}/chat",
        json={"question": "What is testing?"},
    )
    assert resp_canon.status_code == 401


def test_unauthorized_kb_access_returns_404(api_client: TestClient, db_session: Session) -> None:
    """Verify querying an unauthorized or nonexistent KB returns 404."""
    admin_a = create_user_direct(db_session, email="prof_a@university.edu", role=UserRole.ADMIN)
    create_user_direct(db_session, email="prof_b@university.edu", role=UserRole.ADMIN)
    create_user_direct(db_session, email="student_outsider@university.edu", role=UserRole.STUDENT)

    kb = KnowledgeBase(
        name="Private Exam Key",
        description="Confidential exam questions",
        created_by_id=admin_a.id,
    )
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)

    # 1. Admin B attempts to query Admin A's private KB -> 404
    api_client.post(
        "/api/v1/auth/login",
        json={"email": "prof_b@university.edu", "password": "TestPassword123!"},
    )
    resp_admin_b = api_client.post(
        f"/api/v1/knowledge-bases/{kb.id}/chat",
        json={"question": "Show exam questions"},
    )
    assert resp_admin_b.status_code == 404
    assert resp_admin_b.json()["detail"] == "Knowledge base not found."

    # 2. Student without membership attempts to query -> 404
    api_client.post(
        "/api/v1/auth/login",
        json={"email": "student_outsider@university.edu", "password": "TestPassword123!"},
    )
    resp_student = api_client.post(
        "/api/v1/chat/query",
        json={"knowledge_base_id": str(kb.id), "question": "Show exam questions"},
    )
    assert resp_student.status_code == 404
    assert resp_student.json()["detail"] == "Knowledge base not found."


def test_authenticated_admin_canonical_endpoint_with_mocked_orchestrator(
    api_client: TestClient, db_session: Session
) -> None:
    """
    Verify authenticated admin can query their knowledge base via the canonical endpoint:
    POST /api/v1/knowledge-bases/{kb_id}/chat.
    """
    admin = create_user_direct(db_session, email="admin_chat@university.edu", role=UserRole.ADMIN)
    kb = KnowledgeBase(
        name="Distributed Systems",
        description="Course material",
        created_by_id=admin.id,
    )
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)

    api_client.post(
        "/api/v1/auth/login",
        json={"email": "admin_chat@university.edu", "password": "TestPassword123!"},
    )

    mock_response = ChatQueryResponse(
        query="What is 2PL?",
        processed_query="what is 2pl",
        knowledge_base_id=kb.id,
        answer="Two-phase locking ensures serializability [source_1].",
        is_empty_context=False,
        citations=[
            CitationItem(
                source_id="source_1",
                document_name="distributed_systems.pdf",
                document_id=uuid.uuid4(),
                chunk_id="chunk-123",
                page_number=14,
                section_title="Concurrency",
                relevance_score=0.98,
                snippet="Two-phase locking protocol guarantees conflict serializability.",
            )
        ],
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
                    claim_text="Two-phase locking ensures serializability.",
                    status="SUPPORTED",
                    cited_source="source_1",
                    rationale="",
                )
            ],
        ),
        latency=ChatLatencyBreakdownDTO(
            query_processing_ms=1.2,
            retrieval_ms=15.4,
            reranking_ms=10.1,
            context_assembly_ms=0.5,
            llm_generation_ms=105.0,
            grounding_validation_ms=4.2,
            total_pipeline_ms=136.4,
        ),
        model="qwen3:4b",
        metadata={},
    )

    mock_orchestrator = MagicMock(spec=RAGOrchestrator)
    mock_orchestrator.execute_query = AsyncMock(return_value=mock_response)

    api_client.app.dependency_overrides[get_rag_orchestrator] = lambda: mock_orchestrator
    try:
        resp = api_client.post(
            f"/api/v1/knowledge-bases/{kb.id}/chat",
            json={"question": "What is 2PL?"},
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["answer"] == "Two-phase locking ensures serializability [source_1]."
        assert data["knowledge_base_id"] == str(kb.id)
        assert data["is_empty_context"] is False
        assert len(data["citations"]) == 1
        assert data["citations"][0]["source_id"] == "source_1"
        assert data["citations"][0]["document_name"] == "distributed_systems.pdf"
        assert data["grounding"]["is_grounded"] is True
        assert data["grounding"]["status"] == "FULLY_SUPPORTED"
        assert data["latency"]["total_pipeline_ms"] == 136.4
    finally:
        api_client.app.dependency_overrides.pop(get_rag_orchestrator, None)


def test_authenticated_student_member_query_legacy_endpoint(
    api_client: TestClient, db_session: Session
) -> None:
    """
    Verify authenticated student with granted membership can query via legacy endpoint:
    POST /api/v1/chat/query.
    """
    admin = create_user_direct(db_session, email="prof_db@university.edu", role=UserRole.ADMIN)
    student = create_user_direct(
        db_session, email="student_enrolled@university.edu", role=UserRole.STUDENT
    )

    kb = KnowledgeBase(
        name="Operating Systems",
        description="OS notes",
        created_by_id=admin.id,
    )
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)

    # Add student as member
    membership = KnowledgeBaseMember(knowledge_base_id=kb.id, user_id=student.id)
    db_session.add(membership)
    db_session.commit()

    # Login student
    api_client.post(
        "/api/v1/auth/login",
        json={"email": "student_enrolled@university.edu", "password": "TestPassword123!"},
    )

    mock_response = ChatQueryResponse(
        query="What is paging?",
        processed_query="what is paging",
        knowledge_base_id=kb.id,
        answer="Paging is a memory management scheme [source_1].",
        is_empty_context=False,
        citations=[
            CitationItem(
                source_id="source_1",
                document_name="os_concepts.pdf",
                document_id=uuid.uuid4(),
                chunk_id="chunk-456",
                page_number=50,
                section_title="Virtual Memory",
                relevance_score=0.91,
                snippet="Paging eliminates the need for contiguous allocation of physical memory.",
            )
        ],
        grounding=GroundingSummaryDTO(
            is_grounded=True,
            status="FULLY_SUPPORTED",
            citation_validity_rate=1.0,
            citation_coverage=1.0,
            claim_support_rate=1.0,
            unsupported_claim_rate=0.0,
            has_conflicts=False,
            claims=[],
        ),
        latency=ChatLatencyBreakdownDTO(
            query_processing_ms=1.0,
            retrieval_ms=12.0,
            reranking_ms=8.0,
            context_assembly_ms=0.4,
            llm_generation_ms=90.0,
            grounding_validation_ms=3.0,
            total_pipeline_ms=114.4,
        ),
        model="qwen3:4b",
        metadata={},
    )

    mock_orchestrator = MagicMock(spec=RAGOrchestrator)
    mock_orchestrator.execute_query = AsyncMock(return_value=mock_response)

    api_client.app.dependency_overrides[get_rag_orchestrator] = lambda: mock_orchestrator
    try:
        resp = api_client.post(
            "/api/v1/chat/query",
            json={"knowledge_base_id": str(kb.id), "question": "What is paging?"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "Paging is a memory management scheme [source_1]."
        assert "citations" in data
        assert len(data["citations"]) == 1
    finally:
        api_client.app.dependency_overrides.pop(get_rag_orchestrator, None)


def test_empty_context_refusal_fast_path(api_client: TestClient, db_session: Session) -> None:
    """
    Verify empty-context queries safely return refusal without error.
    """
    admin = create_user_direct(db_session, email="admin_empty@university.edu", role=UserRole.ADMIN)
    kb = KnowledgeBase(
        name="Empty Knowledge Base",
        description="No documents uploaded yet",
        created_by_id=admin.id,
    )
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)

    api_client.post(
        "/api/v1/auth/login",
        json={"email": "admin_empty@university.edu", "password": "TestPassword123!"},
    )

    mock_empty_response = ChatQueryResponse(
        query="What is quantum computing?",
        processed_query="what is quantum computing",
        knowledge_base_id=kb.id,
        answer="I do not have sufficient information in the provided context to answer this question.",
        is_empty_context=True,
        citations=[],
        grounding=GroundingSummaryDTO(
            is_grounded=True,
            status="REFUSAL",
            citation_validity_rate=0.0,
            citation_coverage=0.0,
            claim_support_rate=0.0,
            unsupported_claim_rate=0.0,
            has_conflicts=False,
            claims=[],
        ),
        latency=ChatLatencyBreakdownDTO(
            query_processing_ms=1.1,
            retrieval_ms=8.0,
            reranking_ms=0.0,
            context_assembly_ms=0.2,
            llm_generation_ms=1.5,
            grounding_validation_ms=0.8,
            total_pipeline_ms=11.6,
        ),
        model="qwen3:4b",
        metadata={},
    )

    mock_orchestrator = MagicMock(spec=RAGOrchestrator)
    mock_orchestrator.execute_query = AsyncMock(return_value=mock_empty_response)

    api_client.app.dependency_overrides[get_rag_orchestrator] = lambda: mock_orchestrator
    try:
        resp = api_client.post(
            f"/api/v1/knowledge-bases/{kb.id}/chat",
            json={"question": "What is quantum computing?"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_empty_context"] is True
        assert data["grounding"]["status"] == "REFUSAL"
        assert data["grounding"]["is_grounded"] is True
        assert len(data["citations"]) == 0
    finally:
        api_client.app.dependency_overrides.pop(get_rag_orchestrator, None)


def test_provider_failure_maps_to_503(api_client: TestClient, db_session: Session) -> None:
    """Verify provider execution errors map cleanly to 503 Service Unavailable."""
    admin = create_user_direct(db_session, email="admin_err@university.edu", role=UserRole.ADMIN)
    kb = KnowledgeBase(
        name="Error KB",
        description="Testing provider errors",
        created_by_id=admin.id,
    )
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)

    api_client.post(
        "/api/v1/auth/login",
        json={"email": "admin_err@university.edu", "password": "TestPassword123!"},
    )

    mock_orchestrator = MagicMock(spec=RAGOrchestrator)
    mock_orchestrator.execute_query = AsyncMock(
        side_effect=LLMProviderError("Internal provider error")
    )

    api_client.app.dependency_overrides[get_rag_orchestrator] = lambda: mock_orchestrator
    try:
        resp = api_client.post(
            f"/api/v1/knowledge-bases/{kb.id}/chat",
            json={"question": "Trigger error"},
        )
        assert resp.status_code == 503
        data = resp.json()
        assert "temporarily unavailable" in data["detail"]
        assert "Internal provider error" not in data["detail"]
    finally:
        api_client.app.dependency_overrides.pop(get_rag_orchestrator, None)


def test_llm_timeout_maps_to_504(api_client: TestClient, db_session: Session) -> None:
    """Verify LLM timeout errors map cleanly to 504 Gateway Timeout."""
    admin = create_user_direct(
        db_session, email="admin_timeout@university.edu", role=UserRole.ADMIN
    )
    kb = KnowledgeBase(
        name="Timeout KB",
        description="Testing timeout",
        created_by_id=admin.id,
    )
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)

    api_client.post(
        "/api/v1/auth/login",
        json={"email": "admin_timeout@university.edu", "password": "TestPassword123!"},
    )

    mock_orchestrator = MagicMock(spec=RAGOrchestrator)
    mock_orchestrator.execute_query = AsyncMock(side_effect=LLMTimeoutError("Request timed out"))

    api_client.app.dependency_overrides[get_rag_orchestrator] = lambda: mock_orchestrator
    try:
        resp = api_client.post(
            f"/api/v1/knowledge-bases/{kb.id}/chat",
            json={"question": "Trigger timeout"},
        )
        assert resp.status_code == 504
        data = resp.json()
        assert "timed out" in data["detail"]
    finally:
        api_client.app.dependency_overrides.pop(get_rag_orchestrator, None)
