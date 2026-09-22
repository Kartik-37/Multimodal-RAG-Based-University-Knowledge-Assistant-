"""
Integration Tests for Global Multi-KB Retrieval, Isolation, and Document Activation.

Step 21B Verification:
1. Inactive documents are strictly excluded from vector and lexical retrieval.
2. Direct retrieval-service calls with empty KB list [] return [] without unscoped queries.
3. Multi-KB global retrieval retains non-null knowledge_base_id and full provenance.
4. Unauthorized knowledge base materials never leak into student global queries.
5. Preserves existing /api/v1/chat/query scoped behavior when knowledge_base_id is supplied.
6. Document activation and deactivation endpoints enforce RBAC and idempotency (409 on repeat).
7. Admin provisioning is restricted to ADMIN and strictly privacy-preserving.
"""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.security import get_password_hash
from backend.app.models.document import Document, DocumentChunk, DocumentStatus, IndexingStatus
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseMember
from backend.app.models.user import User, UserRole
from backend.app.services.embedding.base import BaseEmbeddingProvider
from backend.app.services.lexical_retrieval import LexicalRetrievalService
from backend.app.services.retrieval import VectorRetrievalService


class MockTestEmbeddingProvider(BaseEmbeddingProvider):
    """Deterministic 1024-dimensional embedding provider for integration tests."""

    @property
    def dimension(self) -> int:
        return 1024

    @property
    def model_name(self) -> str:
        return "mock-test-embedding"

    def _make_vector(self, text_val: str) -> list[float]:
        vec = [0.0] * 1024
        for i, ch in enumerate(text_val[:12]):
            idx = (ord(ch) * 19 + i * 37) % 1024
            vec[idx] = 1.0
        vec[0] += 0.5
        return vec

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._make_vector(t) for t in texts]

    async def embed_query(self, query: str) -> list[float]:
        return self._make_vector(query)


@pytest.fixture(autouse=True)
def clean_db(db_engine) -> Generator[None, None, None]:
    """Clean all tables before and after each test."""
    with db_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE document_chunks, documents, knowledge_base_members, "
                "knowledge_bases, user_sessions, users CASCADE;"
            )
        )
    yield
    with db_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE document_chunks, documents, knowledge_base_members, "
                "knowledge_bases, user_sessions, users CASCADE;"
            )
        )


@pytest.fixture
def mock_embedding_provider() -> MockTestEmbeddingProvider:
    return MockTestEmbeddingProvider()


# ------------------------------------------------------------------------------
# 1. Direct Retrieval-Service Tests for Empty KB List []
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_kb_list_retrieval(
    db_session: Session, mock_embedding_provider: MockTestEmbeddingProvider
) -> None:
    """
    Direct retrieval-service tests for an empty KB ID list [].
    Both vector and lexical retrieval must return [] and must never produce an unscoped query.
    """
    # Create an active, indexed document in a random KB
    admin = User(
        id=uuid.uuid4(),
        email="prof@univ.edu",
        password_hash=get_password_hash("AdminPass123!"),
        full_name="Professor Smith",
        role=UserRole.ADMIN,
    )
    db_session.add(admin)
    db_session.commit()

    kb = KnowledgeBase(id=uuid.uuid4(), name="Sample KB", created_by_id=admin.id)
    db_session.add(kb)
    db_session.commit()

    doc = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb.id,
        original_filename="notes.txt",
        storage_key=f"uploads/{kb.id}/notes.txt",
        file_type="txt",
        mime_type="text/plain",
        file_size_bytes=100,
        content_hash="abc123hash",
        status=DocumentStatus.COMPLETED,
        indexing_status=IndexingStatus.COMPLETED,
        is_active=True,
    )
    db_session.add(doc)
    db_session.commit()

    chunk = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        knowledge_base_id=kb.id,
        chunk_index=0,
        text="Essential quantum computing notes and algorithms.",
        embedding=mock_embedding_provider._make_vector(
            "Essential quantum computing notes and algorithms."
        ),
        token_count=10,
    )
    db_session.add(chunk)
    db_session.commit()

    vector_service = VectorRetrievalService(provider=mock_embedding_provider)
    lexical_service = LexicalRetrievalService()

    # 1. Vector retrieval with empty list []
    vector_results = await vector_service.retrieve(
        db=db_session,
        kb_id=[],
        query="quantum computing",
        top_k=5,
    )
    assert vector_results.results == [], (
        "Vector retrieval with kb_id=[] must return empty list immediately."
    )
    assert vector_results.total_results == 0

    # 2. Lexical retrieval with empty list []
    lexical_results = lexical_service.retrieve(
        db=db_session,
        kb_id=[],
        query="quantum computing",
        top_k=5,
    )
    assert lexical_results.results == [], (
        "Lexical retrieval with kb_id=[] must return empty list immediately."
    )
    assert lexical_results.total_results == 0


# ------------------------------------------------------------------------------
# 2. Inactive Document Leakage Prevention (SSDL 2025 vs 2026)
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inactive_document_leakage_prevention(
    db_session: Session, mock_embedding_provider: MockTestEmbeddingProvider
) -> None:
    """
    Historical documents with is_active=False must be strictly excluded from both
    vector and lexical retrieval, even when chunks are indexed and text matches.
    """
    admin = User(
        id=uuid.uuid4(),
        email="dept@univ.edu",
        password_hash=get_password_hash("AdminPass123!"),
        full_name="Department Head",
        role=UserRole.ADMIN,
    )
    db_session.add(admin)
    db_session.commit()

    kb = KnowledgeBase(id=uuid.uuid4(), name="Software Engineering", created_by_id=admin.id)
    db_session.add(kb)
    db_session.commit()

    # Document 1: 2025 Syllabus (DEACTIVATED / is_active=False)
    doc_2025 = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb.id,
        original_filename="SSDL_Syllabus_2025.pdf",
        storage_key=f"uploads/{kb.id}/ssdl_2025.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size_bytes=5000,
        content_hash="hash2025",
        status=DocumentStatus.COMPLETED,
        indexing_status=IndexingStatus.COMPLETED,
        is_active=False,  # Deactivated
    )
    db_session.add(doc_2025)

    # Document 2: 2026 Syllabus (ACTIVE / is_active=True)
    doc_2026 = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb.id,
        original_filename="SSDL_Syllabus_2026.pdf",
        storage_key=f"uploads/{kb.id}/ssdl_2026.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size_bytes=5200,
        content_hash="hash2026",
        status=DocumentStatus.COMPLETED,
        indexing_status=IndexingStatus.COMPLETED,
        is_active=True,  # Active
    )
    db_session.add(doc_2026)
    db_session.commit()

    chunk_2025 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_2025.id,
        knowledge_base_id=kb.id,
        chunk_index=0,
        text="Grading criteria for 2025: Midterm 40%, Final Exam 60%.",
        embedding=mock_embedding_provider._make_vector(
            "Grading criteria for 2025: Midterm 40%, Final Exam 60%."
        ),
        token_count=12,
    )
    chunk_2026 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_2026.id,
        knowledge_base_id=kb.id,
        chunk_index=0,
        text="Grading criteria for 2026: Assignments 30%, Project 30%, Final 40%.",
        embedding=mock_embedding_provider._make_vector(
            "Grading criteria for 2026: Assignments 30%, Project 30%, Final 40%."
        ),
        token_count=14,
    )
    db_session.add_all([chunk_2025, chunk_2026])
    db_session.commit()

    # Test Vector Retrieval
    vector_service = VectorRetrievalService(provider=mock_embedding_provider)
    v_results = await vector_service.retrieve(
        db=db_session,
        kb_id=kb.id,
        query="Grading criteria for exams",
        top_k=5,
    )
    assert len(v_results.results) == 1, "Vector retrieval must exclude inactive documents."
    assert v_results.results[0].document_id == doc_2026.id
    assert "2026" in v_results.results[0].text

    # Test Lexical Retrieval
    lexical_service = LexicalRetrievalService()
    l_results = lexical_service.retrieve(
        db=db_session,
        kb_id=kb.id,
        query="Grading criteria",
        top_k=5,
    )
    assert len(l_results.results) == 1, "Lexical retrieval must exclude inactive documents."
    assert l_results.results[0].document_id == doc_2026.id
    assert "2026" in l_results.results[0].text


# ------------------------------------------------------------------------------
# 3. Multi-KB Global Retrieval and Provenance Retention
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multi_kb_global_retrieval_and_provenance(
    db_session: Session, mock_embedding_provider: MockTestEmbeddingProvider
) -> None:
    """
    When searching across multiple KBs, results must combine correctly
    and each result must retain its original non-null knowledge_base_id and document_id.
    """
    admin = User(
        id=uuid.uuid4(),
        email="prof2@univ.edu",
        password_hash=get_password_hash("AdminPass123!"),
        full_name="Professor Two",
        role=UserRole.ADMIN,
    )
    db_session.add(admin)
    db_session.commit()

    # Setup 3 KBs: DBMS, ML, SSDL
    kb_dbms = KnowledgeBase(id=uuid.uuid4(), name="Database Management", created_by_id=admin.id)
    kb_ml = KnowledgeBase(id=uuid.uuid4(), name="Machine Learning", created_by_id=admin.id)
    kb_ssdl = KnowledgeBase(id=uuid.uuid4(), name="Software Design Lab", created_by_id=admin.id)
    db_session.add_all([kb_dbms, kb_ml, kb_ssdl])
    db_session.commit()

    # Documents in each KB
    doc_dbms = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb_dbms.id,
        original_filename="dbms.txt",
        storage_key="s1",
        file_type="txt",
        mime_type="text/plain",
        file_size_bytes=100,
        content_hash="h1",
        status=DocumentStatus.COMPLETED,
        indexing_status=IndexingStatus.COMPLETED,
        is_active=True,
    )
    doc_ml = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb_ml.id,
        original_filename="ml.txt",
        storage_key="s2",
        file_type="txt",
        mime_type="text/plain",
        file_size_bytes=100,
        content_hash="h2",
        status=DocumentStatus.COMPLETED,
        indexing_status=IndexingStatus.COMPLETED,
        is_active=True,
    )
    doc_ssdl = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb_ssdl.id,
        original_filename="ssdl.txt",
        storage_key="s3",
        file_type="txt",
        mime_type="text/plain",
        file_size_bytes=100,
        content_hash="h3",
        status=DocumentStatus.COMPLETED,
        indexing_status=IndexingStatus.COMPLETED,
        is_active=True,
    )
    db_session.add_all([doc_dbms, doc_ml, doc_ssdl])
    db_session.commit()

    chunk_dbms = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_dbms.id,
        knowledge_base_id=kb_dbms.id,
        chunk_index=0,
        text="Relational algebra and relational database normal forms.",
        embedding=mock_embedding_provider._make_vector("Relational algebra and normal forms."),
        token_count=10,
    )
    chunk_ml = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_ml.id,
        knowledge_base_id=kb_ml.id,
        chunk_index=0,
        text="Supervised learning with neural networks and database features.",
        embedding=mock_embedding_provider._make_vector(
            "Supervised learning neural networks database."
        ),
        token_count=10,
    )
    chunk_ssdl = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_ssdl.id,
        knowledge_base_id=kb_ssdl.id,
        chunk_index=0,
        text="Architectural design patterns including repository and relational data mappers.",
        embedding=mock_embedding_provider._make_vector("Architectural design patterns repository."),
        token_count=10,
    )
    db_session.add_all([chunk_dbms, chunk_ml, chunk_ssdl])
    db_session.commit()

    vector_service = VectorRetrievalService(provider=mock_embedding_provider)
    results = await vector_service.retrieve(
        db=db_session,
        kb_id=[kb_dbms.id, kb_ml.id, kb_ssdl.id],
        query="relational database architecture",
        top_k=10,
    )

    assert len(results.results) >= 2, "Should retrieve chunks across multiple KBs."
    retrieved_kbs = {r.knowledge_base_id for r in results.results}
    assert len(retrieved_kbs) > 1, "Must span multiple knowledge bases."
    for r in results.results:
        assert r.knowledge_base_id is not None
        assert r.document_id is not None
        assert r.chunk_id is not None


# ------------------------------------------------------------------------------
# 4. Unauthorized Cross-KB Isolation in Global Queries
# ------------------------------------------------------------------------------


def test_unauthorized_cross_kb_leakage_prevention(
    api_client: TestClient, db_session: Session
) -> None:
    """
    When a student queries globally without knowledge_base_id,
    only KBs where the student is an authorized member must be searched.
    Canary material in unassigned KBs must never leak.
    """
    # 1. Create Admin and two KBs
    admin = User(
        id=uuid.uuid4(),
        email="prof_admin@univ.edu",
        password_hash=get_password_hash("AdminPass123!"),
        full_name="Prof Administrator",
        role=UserRole.ADMIN,
    )
    student = User(
        id=uuid.uuid4(),
        email="student1@univ.edu",
        password_hash=get_password_hash("StudentPass123!"),
        full_name="Alice Student",
        role=UserRole.STUDENT,
    )
    db_session.add_all([admin, student])
    db_session.commit()

    kb_authorized = KnowledgeBase(id=uuid.uuid4(), name="Enrolled Course A", created_by_id=admin.id)
    kb_unauthorized = KnowledgeBase(
        id=uuid.uuid4(), name="Private Course B", created_by_id=admin.id
    )
    db_session.add_all([kb_authorized, kb_unauthorized])
    db_session.commit()

    # Enroll student in KB A only
    member = KnowledgeBaseMember(knowledge_base_id=kb_authorized.id, user_id=student.id)
    db_session.add(member)
    db_session.commit()

    # Add public doc in KB A and canary doc in KB B
    doc_a = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb_authorized.id,
        original_filename="course_a.txt",
        storage_key="sa",
        file_type="txt",
        mime_type="text/plain",
        file_size_bytes=100,
        content_hash="ha",
        status=DocumentStatus.COMPLETED,
        indexing_status=IndexingStatus.COMPLETED,
        is_active=True,
    )
    doc_b = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb_unauthorized.id,
        original_filename="secret_b.txt",
        storage_key="sb",
        file_type="txt",
        mime_type="text/plain",
        file_size_bytes=100,
        content_hash="hb",
        status=DocumentStatus.COMPLETED,
        indexing_status=IndexingStatus.COMPLETED,
        is_active=True,
    )
    db_session.add_all([doc_a, doc_b])
    db_session.commit()

    chunk_a = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_a.id,
        knowledge_base_id=kb_authorized.id,
        chunk_index=0,
        text="Regular course A material on standard data structures.",
        token_count=10,
    )
    chunk_b = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_b.id,
        knowledge_base_id=kb_unauthorized.id,
        chunk_index=0,
        text="TopSecretCanaryToken confidential faculty notes.",
        token_count=10,
    )
    db_session.add_all([chunk_a, chunk_b])
    db_session.commit()

    # Login as student
    login_resp = api_client.post(
        "/api/v1/auth/login", json={"email": "student1@univ.edu", "password": "StudentPass123!"}
    )
    assert login_resp.status_code == 200

    # Global chat query for secret canary
    chat_resp = api_client.post(
        "/api/v1/chat/query",
        json={"question": "What is the TopSecretCanaryToken?"},
    )
    assert chat_resp.status_code == 200
    data = chat_resp.json()

    # Canary must NOT appear anywhere in answer or citations
    assert "TopSecretCanaryToken" not in data.get("answer", "")
    citations = data.get("citations", [])
    for c in citations:
        assert c.get("knowledge_base_id") != str(kb_unauthorized.id)
        assert "TopSecretCanaryToken" not in c.get("snippet", "")


# ------------------------------------------------------------------------------
# 5. Scoped vs Global Chat Query Behavior
# ------------------------------------------------------------------------------


def test_chat_query_scoped_vs_global(api_client: TestClient, db_session: Session) -> None:
    """
    Ensure POST /api/v1/chat/query preserves exact scoped behavior when knowledge_base_id
    is supplied, and uses global authorized resolution when omitted.
    """
    admin = User(
        id=uuid.uuid4(),
        email="prof_scope@univ.edu",
        password_hash=get_password_hash("AdminPass123!"),
        full_name="Prof Scoper",
        role=UserRole.ADMIN,
    )
    db_session.add(admin)
    db_session.commit()

    kb1 = KnowledgeBase(id=uuid.uuid4(), name="Scope KB 1", created_by_id=admin.id)
    kb2 = KnowledgeBase(id=uuid.uuid4(), name="Scope KB 2", created_by_id=admin.id)
    db_session.add_all([kb1, kb2])
    db_session.commit()

    api_client.post(
        "/api/v1/auth/login", json={"email": "prof_scope@univ.edu", "password": "AdminPass123!"}
    )

    # Query with explicit KB ID (Scoped)
    scoped_resp = api_client.post(
        "/api/v1/chat/query",
        json={"knowledge_base_id": str(kb1.id), "question": "What are the rules?"},
    )
    assert scoped_resp.status_code == 200
    assert scoped_resp.json().get("knowledge_base_id") == str(kb1.id)

    # Query without KB ID (Global)
    global_resp = api_client.post(
        "/api/v1/chat/query",
        json={"question": "What are the rules?"},
    )
    assert global_resp.status_code == 200
    assert global_resp.json().get("knowledge_base_id") is None


# ------------------------------------------------------------------------------
# 6. Document Activation and Deactivation Endpoints
# ------------------------------------------------------------------------------


def test_document_activate_deactivate_lifecycle(
    api_client: TestClient, db_session: Session
) -> None:
    """
    Test PATCH /knowledge-bases/{kb_id}/documents/{doc_id}/activate and deactivate.
    Enforces RBAC and 409 Conflict idempotency checks.
    """
    admin = User(
        id=uuid.uuid4(),
        email="admin_lifecycle@univ.edu",
        password_hash=get_password_hash("AdminPass123!"),
        full_name="Lifecycle Admin",
        role=UserRole.ADMIN,
    )
    student = User(
        id=uuid.uuid4(),
        email="student_lifecycle@univ.edu",
        password_hash=get_password_hash("StudentPass123!"),
        full_name="Student Lifecycle",
        role=UserRole.STUDENT,
    )
    db_session.add_all([admin, student])
    db_session.commit()

    kb = KnowledgeBase(id=uuid.uuid4(), name="Lifecycle KB", created_by_id=admin.id)
    db_session.add(kb)
    db_session.commit()

    doc = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb.id,
        original_filename="lifecycle.txt",
        storage_key="sl",
        file_type="txt",
        mime_type="text/plain",
        file_size_bytes=100,
        content_hash="hl",
        status=DocumentStatus.COMPLETED,
        indexing_status=IndexingStatus.COMPLETED,
        is_active=True,
    )
    db_session.add(doc)
    db_session.commit()

    # Student cannot deactivate (403)
    api_client.post(
        "/api/v1/auth/login",
        json={"email": "student_lifecycle@univ.edu", "password": "StudentPass123!"},
    )
    deact_resp = api_client.patch(f"/api/v1/knowledge-bases/{kb.id}/documents/{doc.id}/deactivate")
    assert deact_resp.status_code == 403

    # Admin deactivates document (200)
    api_client.post(
        "/api/v1/auth/login",
        json={"email": "admin_lifecycle@univ.edu", "password": "AdminPass123!"},
    )
    deact_resp = api_client.patch(f"/api/v1/knowledge-bases/{kb.id}/documents/{doc.id}/deactivate")
    assert deact_resp.status_code == 200
    assert deact_resp.json()["is_active"] is False

    # Repeat deactivate returns 409 Conflict
    deact_repeat = api_client.patch(
        f"/api/v1/knowledge-bases/{kb.id}/documents/{doc.id}/deactivate"
    )
    assert deact_repeat.status_code == 409
    assert deact_repeat.json()["detail"] == "DOCUMENT_ALREADY_INACTIVE"

    # Admin activates document (200)
    act_resp = api_client.patch(f"/api/v1/knowledge-bases/{kb.id}/documents/{doc.id}/activate")
    assert act_resp.status_code == 200
    assert act_resp.json()["is_active"] is True

    # Repeat activate returns 409 Conflict
    act_repeat = api_client.patch(f"/api/v1/knowledge-bases/{kb.id}/documents/{doc.id}/activate")
    assert act_repeat.status_code == 409
    assert act_repeat.json()["detail"] == "DOCUMENT_ALREADY_ACTIVE"


# ------------------------------------------------------------------------------
# 7. Administrator Management and Privacy
# ------------------------------------------------------------------------------


def test_admin_provisioning_and_privacy(api_client: TestClient, db_session: Session) -> None:
    """
    Test POST /api/v1/auth/admin and GET /api/v1/auth/admins.
    Enforces that:
    1. Students cannot create or list admins (403).
    2. Admin can create another Admin (201).
    3. Privacy is preserved: no UUID, no password hash, no session token.
    4. Duplicate email returns 409.
    """
    admin = User(
        id=uuid.uuid4(),
        email="root_admin@univ.edu",
        password_hash=get_password_hash("RootAdmin123!"),
        full_name="Root Administrator",
        role=UserRole.ADMIN,
    )
    student = User(
        id=uuid.uuid4(),
        email="regular_student@univ.edu",
        password_hash=get_password_hash("StudentPass123!"),
        full_name="Regular Student",
        role=UserRole.STUDENT,
    )
    db_session.add_all([admin, student])
    db_session.commit()

    # 1. Student attempts to create admin (403)
    api_client.post(
        "/api/v1/auth/login",
        json={"email": "regular_student@univ.edu", "password": "StudentPass123!"},
    )
    create_resp = api_client.post(
        "/api/v1/auth/admin",
        json={
            "email": "new_admin@univ.edu",
            "password": "NewAdminPass123!",
            "full_name": "Dr. New Admin",
        },
    )
    assert create_resp.status_code == 403

    # Student attempts to list admins (403)
    list_resp = api_client.get("/api/v1/auth/admins")
    assert list_resp.status_code == 403

    # 2. Admin creates another Admin (201)
    api_client.post(
        "/api/v1/auth/login", json={"email": "root_admin@univ.edu", "password": "RootAdmin123!"}
    )
    create_resp = api_client.post(
        "/api/v1/auth/admin",
        json={
            "email": "new_admin@univ.edu",
            "password": "NewAdminPass123!",
            "full_name": "Dr. New Admin",
        },
    )
    assert create_resp.status_code == 201
    created_data = create_resp.json()

    # Verify privacy preservation
    assert created_data["email"] == "new_admin@univ.edu"
    assert created_data["full_name"] == "Dr. New Admin"
    assert created_data["role"] == "ADMIN"
    assert "id" not in created_data
    assert "password" not in created_data
    assert "hashed_password" not in created_data
    assert "session_token" not in created_data

    # 3. Duplicate email returns 409
    dup_resp = api_client.post(
        "/api/v1/auth/admin",
        json={
            "email": "new_admin@univ.edu",
            "password": "AnotherPassword123!",
            "full_name": "Duplicate",
        },
    )
    assert dup_resp.status_code == 409
    assert (
        "already exists" in dup_resp.json()["detail"].lower()
        or dup_resp.json()["detail"] == "AUTH_EMAIL_EXISTS"
    )

    # 4. Admin lists admins (200)
    list_resp = api_client.get("/api/v1/auth/admins")
    assert list_resp.status_code == 200
    admin_list = list_resp.json()
    assert len(admin_list) >= 2
    for adm in admin_list:
        assert "email" in adm
        assert "full_name" in adm
        assert "role" in adm
        assert "id" not in adm
        assert "hashed_password" not in adm
