"""
Integration Tests for Document Ingestion, Parsing, Chunking & RBAC.

Verifies:
1. Upload security: 401 unauthenticated, 403 student, 404 cross-tenant isolation.
2. Content validation: Magic byte checks for PDF/DOCX, reject invalid/fake renamed files.
3. Path traversal protection: Malicious filenames are sanitized; stored strictly within STORAGE_DIR.
4. Real end-to-end ingestion (Correction #7): Real 2-page PDF uploaded by ADMIN -> PENDING
   -> processed to COMPLETED -> chunks in PostgreSQL with correct page numbers and text.
5. Ingestion failure handling (Correction #2): Failed ingestion marks document as FAILED with
   safe error message and zero orphaned chunks in database.
6. Admin document management: List documents, inspect chunks, delete document with file cleanup (Correction #5).
7. Multi-user isolation: Cross-user and non-member access returns 404.
"""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.app.core.security import get_password_hash
from backend.app.models.document import Document, DocumentChunk, DocumentStatus
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseMember
from backend.app.models.user import User, UserRole
from backend.app.services.ingestion import ingestion_pipeline
from backend.app.services.storage import storage_service
from backend.tests.fixtures_documents import (
    create_sample_csv_bytes,
    create_sample_docx_bytes,
    create_sample_md_bytes,
    create_sample_pdf_bytes,
    create_sample_txt_bytes,
)


@pytest.fixture(autouse=True)
def clean_ingestion_db(db_engine) -> Generator[None, None, None]:
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


def provision_user(
    db: Session,
    email: str,
    password: str = "SecurePassword123!",
    role: UserRole = UserRole.ADMIN,
) -> User:
    """Helper to provision a user directly in database."""
    user = User(
        email=email.strip().lower(),
        password_hash=get_password_hash(password),
        full_name="Test Ingestion User",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def provision_kb(db: Session, owner: User, name: str = "Test Knowledge Base") -> KnowledgeBase:
    """Helper to create a knowledge base."""
    kb = KnowledgeBase(name=name, description="Test description", created_by_id=owner.id)
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


# ==============================================================================
# 1. UPLOAD SECURITY & AUTHORIZATION TESTS
# ==============================================================================


def test_unauthenticated_upload_rejected(api_client: TestClient) -> None:
    """Unauthenticated requests to upload endpoint return 401 Unauthorized."""
    api_client.cookies.clear()
    fake_kb_id = uuid.uuid4()
    resp = api_client.post(f"/api/v1/knowledge-bases/{fake_kb_id}/documents")
    assert resp.status_code == 401


def test_student_upload_rejected(api_client: TestClient, db_session: Session) -> None:
    """Students attempting to upload receive 403 Forbidden."""
    student = provision_user(db_session, "student_uploader@univ.edu", role=UserRole.STUDENT)
    admin = provision_user(db_session, "admin_owner@univ.edu", role=UserRole.ADMIN)
    kb = provision_kb(db_session, admin)

    # Login as student
    api_client.post(
        "/api/v1/auth/login",
        json={"email": student.email, "password": "SecurePassword123!"},
    )

    files = {"file": ("test.txt", b"Student test content", "text/plain")}
    resp = api_client.post(f"/api/v1/knowledge-bases/{kb.id}/documents", files=files)
    assert resp.status_code == 403
    assert "Administrator privileges required" in resp.json()["detail"]


def test_cross_tenant_upload_isolated(api_client: TestClient, db_session: Session) -> None:
    """Admin B cannot upload documents into Admin A's private knowledge base (returns 404)."""
    admin_a = provision_user(db_session, "admin_a@univ.edu", role=UserRole.ADMIN)
    admin_b = provision_user(db_session, "admin_b@univ.edu", role=UserRole.ADMIN)
    kb_a = provision_kb(db_session, admin_a, "Admin A KB")

    # Login as Admin B
    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin_b.email, "password": "SecurePassword123!"},
    )

    files = {"file": ("test.txt", b"Admin B malicious content", "text/plain")}
    resp = api_client.post(f"/api/v1/knowledge-bases/{kb_a.id}/documents", files=files)
    assert resp.status_code == 404
    assert "Knowledge base not found" in resp.json()["detail"]


def test_unsupported_file_extension_rejected(api_client: TestClient, db_session: Session) -> None:
    """Unsupported file types (e.g. .exe, .py) are rejected with 400 Bad Request."""
    admin = provision_user(db_session, "admin_ext@univ.edu", role=UserRole.ADMIN)
    kb = provision_kb(db_session, admin)

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    files = {"file": ("malicious.exe", b"MZ\x90\x00executable", "application/octet-stream")}
    resp = api_client.post(f"/api/v1/knowledge-bases/{kb.id}/documents", files=files)
    assert resp.status_code == 400
    assert "Unsupported file extension" in resp.json()["detail"]


def test_fake_renamed_pdf_rejected(api_client: TestClient, db_session: Session) -> None:
    """Files renamed to .pdf without valid %PDF- magic bytes are rejected (Correction #4)."""
    admin = provision_user(db_session, "admin_magic@univ.edu", role=UserRole.ADMIN)
    kb = provision_kb(db_session, admin)

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    # Fake PDF containing plain text without %PDF- magic signature
    files = {"file": ("fake.pdf", b"This is just plain text, not a real PDF.", "application/pdf")}
    resp = api_client.post(f"/api/v1/knowledge-bases/{kb.id}/documents", files=files)
    assert resp.status_code == 400
    assert "Missing '%PDF-' file signature" in resp.json()["detail"]


def test_path_traversal_filename_sanitized(api_client: TestClient, db_session: Session) -> None:
    """Path traversal filename (../../etc/passwd.txt) is sanitized and stays in storage dir."""
    admin = provision_user(db_session, "admin_traversal@univ.edu", role=UserRole.ADMIN)
    kb = provision_kb(db_session, admin)

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    traversal_name = "../../../../etc/passwd.txt"
    files = {"file": (traversal_name, b"Safe text content inside.", "text/plain")}
    resp = api_client.post(f"/api/v1/knowledge-bases/{kb.id}/documents", files=files)
    assert resp.status_code == 201

    data = resp.json()
    assert data["original_filename"] == "passwd.txt"
    assert ".." not in data["original_filename"]

    # Verify physical file is safely inside storage directory
    db_doc = db_session.execute(select(Document).where(Document.id == data["id"])).scalar_one()
    abs_path = storage_service.get_absolute_path(db_doc.storage_key)
    assert abs_path.is_relative_to(storage_service.storage_dir)


# ==============================================================================
# 2. REAL END-TO-END INGESTION TESTS (Correction #7)
# ==============================================================================


def test_real_pdf_end_to_end_ingestion(api_client: TestClient, db_session: Session) -> None:
    """
    Complete end-to-end integration test:
    ADMIN login -> KB create -> multipart upload real 2-page PDF -> ingestion -> COMPLETED
    -> verify chunks in PostgreSQL with correct page numbers and text.
    """
    admin = provision_user(db_session, "admin_e2e@univ.edu", role=UserRole.ADMIN)
    kb = provision_kb(db_session, admin, "Distributed Systems")

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    pdf_bytes = create_sample_pdf_bytes()
    files = {"file": ("distributed_systems.pdf", pdf_bytes, "application/pdf")}

    upload_resp = api_client.post(f"/api/v1/knowledge-bases/{kb.id}/documents", files=files)
    assert upload_resp.status_code == 201

    doc_data = upload_resp.json()
    doc_id = uuid.UUID(doc_data["id"])
    assert doc_data["file_type"] == "pdf"
    assert doc_data["original_filename"] == "distributed_systems.pdf"

    # In FastAPI TestClient, BackgroundTasks run synchronously before response returns
    # Verify in database that status is COMPLETED
    db_doc = db_session.execute(select(Document).where(Document.id == doc_id)).scalar_one()
    assert db_doc.status == DocumentStatus.COMPLETED
    assert db_doc.error_message is None

    # Query chunks directly from PostgreSQL
    chunks = (
        db_session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == doc_id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
        .scalars()
        .all()
    )

    assert len(chunks) == 2, f"Expected 2 chunks from 2 pages, got {len(chunks)}"

    # Check Chunk 0 (Page 1)
    c0 = chunks[0]
    assert c0.chunk_index == 0
    assert c0.page_number == 1
    assert "Page 1: Introduction to BCA RAG System" in c0.text
    assert c0.token_count > 0

    # Check Chunk 1 (Page 2)
    c1 = chunks[1]
    assert c1.chunk_index == 1
    assert c1.page_number == 2
    assert "Page 2: Advanced Vector Database Architecture" in c1.text
    assert c1.token_count > 0


def test_docx_ingestion_end_to_end(api_client: TestClient, db_session: Session) -> None:
    """Verify real DOCX ingestion generates chunks with heading and table metadata."""
    admin = provision_user(db_session, "admin_docx@univ.edu", role=UserRole.ADMIN)
    kb = provision_kb(db_session, admin, "DOCX Knowledge Base")

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    docx_bytes = create_sample_docx_bytes()
    files = {
        "file": (
            "architecture.docx",
            docx_bytes,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }

    upload_resp = api_client.post(f"/api/v1/knowledge-bases/{kb.id}/documents", files=files)
    assert upload_resp.status_code == 201

    doc_id = uuid.UUID(upload_resp.json()["id"])
    db_doc = db_session.execute(select(Document).where(Document.id == doc_id)).scalar_one()
    assert db_doc.status == DocumentStatus.COMPLETED

    # Check chunks via API endpoint
    chunk_resp = api_client.get(f"/api/v1/knowledge-bases/{kb.id}/documents/{doc_id}/chunks")
    assert chunk_resp.status_code == 200
    chunk_data = chunk_resp.json()
    assert len(chunk_data) >= 2

    # Verify structural titles
    titles = [c["section_title"] for c in chunk_data]
    assert "BCA System Specification" in titles or "Database Architecture" in titles


def test_markdown_and_csv_ingestion(api_client: TestClient, db_session: Session) -> None:
    """Verify Markdown and CSV documents ingest and extract cleanly."""
    admin = provision_user(db_session, "admin_md_csv@univ.edu", role=UserRole.ADMIN)
    kb = provision_kb(db_session, admin)

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    # 1. Markdown
    md_bytes = create_sample_md_bytes()
    resp_md = api_client.post(
        f"/api/v1/knowledge-bases/{kb.id}/documents",
        files={"file": ("syllabus.md", md_bytes, "text/markdown")},
    )
    assert resp_md.status_code == 201
    doc_md_id = uuid.UUID(resp_md.json()["id"])
    doc_md = db_session.execute(select(Document).where(Document.id == doc_md_id)).scalar_one()
    assert doc_md.status == DocumentStatus.COMPLETED

    # 2. CSV
    csv_bytes = create_sample_csv_bytes()
    resp_csv = api_client.post(
        f"/api/v1/knowledge-bases/{kb.id}/documents",
        files={"file": ("grades.csv", csv_bytes, "text/csv")},
    )
    assert resp_csv.status_code == 201
    doc_csv_id = uuid.UUID(resp_csv.json()["id"])
    doc_csv = db_session.execute(select(Document).where(Document.id == doc_csv_id)).scalar_one()
    assert doc_csv.status == DocumentStatus.COMPLETED


def test_ingestion_failure_handling(db_session: Session) -> None:
    """
    Verify failure handling (Correction #2):
    When an unparseable or corrupted document causes ingestion error,
    document.status is updated to FAILED and NO partial chunks remain in DB.
    """
    admin = provision_user(db_session, "admin_fail@univ.edu", role=UserRole.ADMIN)
    kb = provision_kb(db_session, admin)

    # Save a file with a non-existent path or bad format directly
    doc = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb.id,
        original_filename="corrupted.pdf",
        storage_key=f"storage/{kb.id}/non_existent.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size_bytes=100,
        content_hash="abc123hash",
        status=DocumentStatus.PENDING,
    )
    db_session.add(doc)
    db_session.commit()

    # Run ingestion pipeline directly
    result = ingestion_pipeline.process_document(doc.id)
    assert result is False

    # Check database status
    db_session.refresh(doc)
    assert doc.status == DocumentStatus.FAILED
    assert doc.error_message is not None
    assert "not found" in doc.error_message.lower()

    # Verify ZERO chunks exist for this document
    chunks = (
        db_session.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc.id))
        .scalars()
        .all()
    )
    assert len(chunks) == 0


# ==============================================================================
# 3. DOCUMENT MANAGEMENT & DELETION TESTS (Correction #5)
# ==============================================================================


def test_admin_list_and_inspect_documents(api_client: TestClient, db_session: Session) -> None:
    """Verify document list returns chunk counts and metadata."""
    admin = provision_user(db_session, "admin_list@univ.edu", role=UserRole.ADMIN)
    kb = provision_kb(db_session, admin)

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    txt_bytes = create_sample_txt_bytes()
    api_client.post(
        f"/api/v1/knowledge-bases/{kb.id}/documents",
        files={"file": ("notes.txt", txt_bytes, "text/plain")},
    )

    list_resp = api_client.get(f"/api/v1/knowledge-bases/{kb.id}/documents")
    assert list_resp.status_code == 200
    docs = list_resp.json()
    assert len(docs) == 1
    assert docs[0]["original_filename"] == "notes.txt"
    assert docs[0]["status"] == "COMPLETED"
    assert docs[0]["chunk_count"] > 0


def test_admin_deletion_with_file_cleanup(api_client: TestClient, db_session: Session) -> None:
    """
    Verify document deletion (Correction #5):
    Deletes document record, cascades chunks, and unlinks file from disk.
    """
    admin = provision_user(db_session, "admin_del@univ.edu", role=UserRole.ADMIN)
    kb = provision_kb(db_session, admin)

    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )

    txt_bytes = create_sample_txt_bytes()
    upload_resp = api_client.post(
        f"/api/v1/knowledge-bases/{kb.id}/documents",
        files={"file": ("to_delete.txt", txt_bytes, "text/plain")},
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["id"]

    db_doc = db_session.execute(select(Document).where(Document.id == doc_id)).scalar_one()
    disk_path = storage_service.get_absolute_path(db_doc.storage_key)
    assert disk_path.exists()

    # Call DELETE endpoint
    del_resp = api_client.delete(f"/api/v1/knowledge-bases/{kb.id}/documents/{doc_id}")
    assert del_resp.status_code == 200

    # Verify document and chunks removed from database
    doc_check = db_session.execute(
        select(Document).where(Document.id == doc_id)
    ).scalar_one_or_none()
    assert doc_check is None

    chunk_check = (
        db_session.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc_id))
        .scalars()
        .all()
    )
    assert len(chunk_check) == 0

    # Verify file unlinked from disk
    assert not disk_path.exists()


def test_student_read_only_access_rules(api_client: TestClient, db_session: Session) -> None:
    """
    Verify student permissions:
    - Student with membership can list/inspect documents (200).
    - Student cannot delete documents (403).
    - Student without membership gets 404.
    """
    admin = provision_user(db_session, "admin_perm@univ.edu", role=UserRole.ADMIN)
    student_enrolled = provision_user(
        db_session, "student_enrolled@univ.edu", role=UserRole.STUDENT
    )
    student_outsider = provision_user(
        db_session, "student_outsider@univ.edu", role=UserRole.STUDENT
    )

    kb = provision_kb(db_session, admin)

    # Grant membership to enrolled student
    membership = KnowledgeBaseMember(knowledge_base_id=kb.id, user_id=student_enrolled.id)
    db_session.add(membership)
    db_session.commit()

    # Upload a document as admin
    api_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "SecurePassword123!"},
    )
    up_resp = api_client.post(
        f"/api/v1/knowledge-bases/{kb.id}/documents",
        files={"file": ("course_info.txt", create_sample_txt_bytes(), "text/plain")},
    )
    doc_id = up_resp.json()["id"]

    # 1. Outsider student -> 404
    api_client.post(
        "/api/v1/auth/login",
        json={"email": student_outsider.email, "password": "SecurePassword123!"},
    )
    assert api_client.get(f"/api/v1/knowledge-bases/{kb.id}/documents").status_code == 404

    # 2. Enrolled student -> 200 on list and inspect
    api_client.post(
        "/api/v1/auth/login",
        json={"email": student_enrolled.email, "password": "SecurePassword123!"},
    )
    list_resp = api_client.get(f"/api/v1/knowledge-bases/{kb.id}/documents")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # 3. Enrolled student attempting DELETE -> 403 Forbidden
    del_resp = api_client.delete(f"/api/v1/knowledge-bases/{kb.id}/documents/{doc_id}")
    assert del_resp.status_code == 403
