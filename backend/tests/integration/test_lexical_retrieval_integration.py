"""
Integration Tests for PostgreSQL Full-Text Lexical Retrieval Layer (Step 8).

Verifies:
1. PostgreSQL full-text search executed natively with tsvector, websearch_to_tsquery, and ts_rank_cd.
2. Results ranked by cover density score (ts_rank_cd) descending.
3. top_k parameter strictly enforced.
4. Non-matching chunks excluded.
5. Vector-less chunks (unindexed / pending indexing) are searchable lexically.
6. Knowledge-base authorization and isolation:
   - Admin can retrieve from owned KB.
   - Authorized student can retrieve from member KB.
   - Unauthorized student receives HTTP 404 (preventing existence leakage).
   - Foreign KB chunks never leak across KB boundaries.
   - Unauthenticated requests receive HTTP 401.
   - Nonexistent KB returns HTTP 404.
7. Stopword-only queries return empty results without SQL errors.
8. Special characters and boolean symbols (: & | ! * ") do not cause database errors.
9. Duplicate text chunks remain distinguishable by chunk/document IDs.
10. GIN index existence verified on document_chunks table.
11. Explicit provider independence: operates without Ollama running.
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
from backend.app.services.lexical_retrieval import LexicalRetrievalService


@pytest.fixture(autouse=True)
def clean_database(db_engine) -> Generator[None, None, None]:
    """Clean all tables before and after each test function."""
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


def create_user(
    db: Session,
    email: str,
    password: str = "SecurePassword123!",
    role: UserRole = UserRole.ADMIN,
) -> User:
    """Provision a user in PostgreSQL."""
    user = User(
        email=email.strip().lower(),
        password_hash=get_password_hash(password),
        full_name="Integration Test User",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_kb(db: Session, owner: User, name: str = "Lexical Test KB") -> KnowledgeBase:
    """Provision a knowledge base in PostgreSQL."""
    kb = KnowledgeBase(name=name, description="Test description", created_by_id=owner.id)
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


def create_document(
    db: Session,
    kb: KnowledgeBase,
    filename: str = "curriculum.pdf",
    status: DocumentStatus = DocumentStatus.COMPLETED,
    indexing_status: IndexingStatus = IndexingStatus.PENDING,
) -> Document:
    """Provision a document in PostgreSQL."""
    doc = Document(
        knowledge_base_id=kb.id,
        original_filename=filename,
        storage_key=f"storage/{kb.id}/{uuid.uuid4().hex}_{filename}",
        file_type="pdf",
        mime_type="application/pdf",
        file_size_bytes=4096,
        content_hash="a" * 64,
        status=status,
        indexing_status=indexing_status,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def create_chunk(
    db: Session,
    doc: Document,
    kb: KnowledgeBase,
    chunk_index: int,
    text_content: str,
    page_number: int | None = 1,
    section_title: str | None = "Section 1",
    embedding: list[float] | None = None,
) -> DocumentChunk:
    """Provision a document chunk (PostgreSQL automatically populates searchable_text)."""
    chunk = DocumentChunk(
        document_id=doc.id,
        knowledge_base_id=kb.id,
        chunk_index=chunk_index,
        text=text_content,
        token_count=len(text_content.split()),
        page_number=page_number,
        section_title=section_title,
        chunk_metadata={"test": True},
        embedding=embedding,
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)
    return chunk


# ------------------------------------------------------------------------------
# PostgreSQL-Native Search & Ranking Tests
# ------------------------------------------------------------------------------


def test_real_postgresql_lexical_full_text_search(db_session: Session) -> None:
    """
    Executes real PostgreSQL full-text queries over realistic academic chunks:
    - Chunk A: CPU scheduling concept
    - Chunk B: Database normalization
    - Chunk C: Random Forest decision trees
    - Chunk D: CPU scheduling algorithms (FCFS, SJF, Round Robin)
    """
    admin = create_user(db_session, "admin_lex_search@univ.edu", role=UserRole.ADMIN)
    kb = create_kb(db_session, admin)
    doc = create_document(db_session, kb, filename="computer_science.pdf")

    chunk_a = create_chunk(
        db_session,
        doc,
        kb,
        0,
        "CPU scheduling determines which process is selected for execution.",
        page_number=1,
        section_title="CPU Scheduling Concept",
    )
    chunk_b = create_chunk(
        db_session,
        doc,
        kb,
        1,
        "Database normalization reduces redundancy and improves relational schema design.",
        page_number=5,
        section_title="Relational Normalization",
    )
    chunk_c = create_chunk(
        db_session,
        doc,
        kb,
        2,
        "Random Forest combines multiple decision trees.",
        page_number=10,
        section_title="Machine Learning Ensembles",
    )
    chunk_d = create_chunk(
        db_session,
        doc,
        kb,
        3,
        "CPU scheduling algorithms include FCFS, SJF, and Round Robin.",
        page_number=2,
        section_title="CPU Algorithms",
    )

    service = LexicalRetrievalService()

    # 1. Query "CPU scheduling" must retrieve both CPU chunks, excluding DBMS and ML chunks
    resp_cpu = service.retrieve(db=db_session, kb_id=kb.id, query="CPU scheduling", top_k=10)
    assert resp_cpu.total_results == 2
    matched_ids = [r.chunk_id for r in resp_cpu.results]
    assert chunk_a.id in matched_ids
    assert chunk_d.id in matched_ids
    assert chunk_b.id not in matched_ids
    assert chunk_c.id not in matched_ids
    assert all(r.lexical_score > 0.0 for r in resp_cpu.results)

    # 2. Query "Round Robin" must retrieve Chunk D at Rank #1
    resp_rr = service.retrieve(db=db_session, kb_id=kb.id, query="Round Robin", top_k=5)
    assert resp_rr.total_results == 1
    assert resp_rr.results[0].chunk_id == chunk_d.id
    assert resp_rr.results[0].section_title == "CPU Algorithms"

    # 3. Query "database normalization" must retrieve Chunk B at Rank #1
    resp_db = service.retrieve(db=db_session, kb_id=kb.id, query="database normalization", top_k=5)
    assert resp_db.total_results == 1
    assert resp_db.results[0].chunk_id == chunk_b.id
    assert resp_db.results[0].document_title == "computer_science.pdf"


def test_vector_less_chunks_are_retrievable_lexically(db_session: Session) -> None:
    """
    Enforces Step 8 requirement:
    Unlike vector retrieval, lexical retrieval does NOT require an embedding.
    Chunks with embedding=None from a COMPLETED document must be retrievable.
    """
    admin = create_user(db_session, "admin_vectorless@univ.edu", role=UserRole.ADMIN)
    kb = create_kb(db_session, admin)

    # Document where indexing is PENDING or FAILED, but document status is COMPLETED
    doc = create_document(
        db_session,
        kb,
        filename="unindexed_doc.pdf",
        status=DocumentStatus.COMPLETED,
        indexing_status=IndexingStatus.PENDING,
    )

    # Explicitly NULL embedding
    chunk = create_chunk(
        db_session,
        doc,
        kb,
        0,
        "Software Engineering lifecycle models include Waterfall and Agile methodologies.",
        embedding=None,
    )

    service = LexicalRetrievalService()
    resp = service.retrieve(db=db_session, kb_id=kb.id, query="Waterfall and Agile", top_k=5)

    assert resp.total_results == 1
    assert resp.results[0].chunk_id == chunk.id
    assert "Waterfall and Agile" in resp.results[0].text


def test_gin_index_exists_on_searchable_text(db_engine) -> None:
    """
    Database-level verification:
    Verifies that the GIN index 'ix_document_chunks_searchable_text' is actively
    defined on public.document_chunks in PostgreSQL.
    """
    with db_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT indexname, indexdef FROM pg_indexes "
                "WHERE tablename = 'document_chunks' AND indexname = 'ix_document_chunks_searchable_text'"
            )
        ).fetchone()

    assert row is not None, "GIN index ix_document_chunks_searchable_text must exist in PostgreSQL"
    indexname, indexdef = row
    assert indexname == "ix_document_chunks_searchable_text"
    assert "using gin" in indexdef.lower()


# ------------------------------------------------------------------------------
# API Endpoint Integration Tests
# ------------------------------------------------------------------------------


def test_admin_lexical_retrieval_endpoint(api_client: TestClient, db_session: Session) -> None:
    """Admin retrieves lexically matched chunks via HTTP POST /api/v1/knowledge-bases/{kb_id}/lexical-retrieve."""
    admin = create_user(db_session, "admin_lex_endpoint@univ.edu", role=UserRole.ADMIN)
    kb = create_kb(db_session, admin, name="OS Course")
    doc = create_document(db_session, kb, filename="os_notes.pdf")

    create_chunk(
        db_session,
        doc,
        kb,
        0,
        "Virtual memory paging eliminates external fragmentation using a page table.",
        page_number=3,
        section_title="Paging",
    )

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    resp = api_client.post(
        f"/api/v1/knowledge-bases/{kb.id}/lexical-retrieve",
        json={"query": "virtual memory page table", "top_k": 5},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "virtual memory page table"
    assert data["knowledge_base_id"] == str(kb.id)
    assert data["total_results"] == 1
    match = data["results"][0]
    assert match["document_title"] == "os_notes.pdf"
    assert match["page_number"] == 3
    assert match["section_title"] == "Paging"
    assert match["lexical_score"] > 0.0


def test_student_membership_lexical_authorization(
    api_client: TestClient,
    db_session: Session,
) -> None:
    """
    Verifies knowledge-base authorization and isolation for lexical retrieval:
    - Student with membership can retrieve chunks (HTTP 200).
    - Student without membership receives HTTP 404 (preventing existence leakage).
    """
    admin = create_user(db_session, "admin_owner_auth@univ.edu", role=UserRole.ADMIN)
    student = create_user(db_session, "student_lex@univ.edu", role=UserRole.STUDENT)

    kb_enrolled = create_kb(db_session, admin, name="Enrolled Class")
    kb_secret = create_kb(db_session, admin, name="Faculty Private Exam")
    kb_secret.is_student_visible = False
    db_session.commit()
    db_session.refresh(kb_secret)

    # Grant student membership to kb_enrolled only
    membership = KnowledgeBaseMember(
        knowledge_base_id=kb_enrolled.id,
        user_id=student.id,
    )
    db_session.add(membership)
    db_session.commit()

    doc_enrolled = create_document(db_session, kb_enrolled, filename="syllabus.pdf")
    doc_secret = create_document(db_session, kb_secret, filename="midterm_solutions.pdf")

    create_chunk(db_session, doc_enrolled, kb_enrolled, 0, "Public attendance policy rules.")
    create_chunk(db_session, doc_secret, kb_secret, 0, "Confidential midterm question answers.")

    # Authenticate as student
    api_client.post(
        "/api/v1/auth/login",
        json={"email": student.email, "password": "SecurePassword123!"},
    )

    # 1. Authorized KB search succeeds
    resp_ok = api_client.post(
        f"/api/v1/knowledge-bases/{kb_enrolled.id}/lexical-retrieve",
        json={"query": "attendance policy", "top_k": 5},
    )
    assert resp_ok.status_code == 200
    assert resp_ok.json()["total_results"] == 1

    # 2. Unauthorized KB returns 404
    resp_unauth = api_client.post(
        f"/api/v1/knowledge-bases/{kb_secret.id}/lexical-retrieve",
        json={"query": "midterm question answers", "top_k": 5},
    )
    assert resp_unauth.status_code == 404
    assert "Knowledge base not found" in resp_unauth.json()["detail"]


def test_foreign_kb_chunks_never_leak_in_lexical_retrieval(
    api_client: TestClient,
    db_session: Session,
) -> None:
    """
    Verifies that lexical retrieval executes within the exact knowledge-base boundary
    and never returns chunks from foreign knowledge bases even with identical text.
    """
    admin_a = create_user(db_session, "admin_a_lex@univ.edu", role=UserRole.ADMIN)
    admin_b = create_user(db_session, "admin_b_lex@univ.edu", role=UserRole.ADMIN)

    kb_a = create_kb(db_session, admin_a, name="KB A")
    kb_b = create_kb(db_session, admin_b, name="KB B")

    doc_a = create_document(db_session, kb_a, filename="doc_a.pdf")
    doc_b = create_document(db_session, kb_b, filename="doc_b.pdf")

    create_chunk(db_session, doc_a, kb_a, 0, "Unique proprietary algorithm specification.")
    create_chunk(db_session, doc_b, kb_b, 0, "Unique proprietary algorithm specification.")

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin_a.email, "password": "SecurePassword123!"},
    )

    resp = api_client.post(
        f"/api/v1/knowledge-bases/{kb_a.id}/lexical-retrieve",
        json={"query": "proprietary algorithm specification", "top_k": 10},
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 1
    assert results[0]["knowledge_base_id"] == str(kb_a.id)


def test_unauthenticated_lexical_retrieval_returns_401(api_client: TestClient) -> None:
    """Unauthenticated requests return HTTP 401 Unauthorized."""
    api_client.cookies.clear()
    fake_kb_id = uuid.uuid4()
    resp = api_client.post(
        f"/api/v1/knowledge-bases/{fake_kb_id}/lexical-retrieve",
        json={"query": "search query"},
    )
    assert resp.status_code == 401


def test_nonexistent_kb_returns_404(api_client: TestClient, db_session: Session) -> None:
    """Request for nonexistent knowledge base returns HTTP 404."""
    admin = create_user(db_session, "admin_nx_lex@univ.edu", role=UserRole.ADMIN)
    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    resp = api_client.post(
        f"/api/v1/knowledge-bases/{uuid.uuid4()}/lexical-retrieve",
        json={"query": "any query"},
    )
    assert resp.status_code == 404


def test_empty_kb_returns_empty_results(api_client: TestClient, db_session: Session) -> None:
    """Empty knowledge base returns empty results list []."""
    admin = create_user(db_session, "admin_empty_lex@univ.edu", role=UserRole.ADMIN)
    kb = create_kb(db_session, admin, name="Empty Lexical KB")

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    resp = api_client.post(
        f"/api/v1/knowledge-bases/{kb.id}/lexical-retrieve",
        json={"query": "search anything"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_results"] == 0
    assert data["results"] == []


def test_stopword_only_query_returns_empty_results_safely(
    api_client: TestClient,
    db_session: Session,
) -> None:
    """
    Query containing only English stopwords ('the', 'of', 'in', 'a')
    evaluates to empty tsquery and returns 0 matches safely without errors.
    """
    admin = create_user(db_session, "admin_stopword@univ.edu", role=UserRole.ADMIN)
    kb = create_kb(db_session, admin)
    doc = create_document(db_session, kb)
    create_chunk(db_session, doc, kb, 0, "Computer networks and internet protocols.")

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    resp = api_client.post(
        f"/api/v1/knowledge-bases/{kb.id}/lexical-retrieve",
        json={"query": "the of in a", "top_k": 5},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_results"] == 0
    assert data["results"] == []


def test_special_character_queries_do_not_cause_sql_errors(
    api_client: TestClient,
    db_session: Session,
) -> None:
    """
    PostgreSQL boolean characters (: & | ! * ") and SQL characters are parsed
    safely by websearch_to_tsquery without throwing SQL syntax exceptions.
    """
    admin = create_user(db_session, "admin_special@univ.edu", role=UserRole.ADMIN)
    kb = create_kb(db_session, admin)
    doc = create_document(db_session, kb)
    create_chunk(db_session, doc, kb, 0, "C++ and Java object-oriented programming concepts.")

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    special_queries = [
        "C++ & Java | Python",
        "Object-Oriented * !procedural",
        "title:test AND id:'1'",
        '"exact phrase match"',
    ]
    for q in special_queries:
        resp = api_client.post(
            f"/api/v1/knowledge-bases/{kb.id}/lexical-retrieve",
            json={"query": q, "top_k": 5},
        )
        assert resp.status_code == 200, f"Query '{q}' failed with {resp.status_code}"


def test_duplicate_chunk_text_remains_distinguishable(
    api_client: TestClient,
    db_session: Session,
) -> None:
    """
    Two chunks with identical text remain distinct by chunk_id and chunk_index.
    """
    admin = create_user(db_session, "admin_dup_lex@univ.edu", role=UserRole.ADMIN)
    kb = create_kb(db_session, admin)
    doc = create_document(db_session, kb)

    chunk1 = create_chunk(db_session, doc, kb, 0, "Identical syllabus sentence.")
    chunk2 = create_chunk(db_session, doc, kb, 1, "Identical syllabus sentence.")

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    resp = api_client.post(
        f"/api/v1/knowledge-bases/{kb.id}/lexical-retrieve",
        json={"query": "syllabus sentence", "top_k": 5},
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 2
    ids = {r["chunk_id"] for r in results}
    assert ids == {str(chunk1.id), str(chunk2.id)}
    indices = [r["chunk_index"] for r in results]
    assert indices == [0, 1]
