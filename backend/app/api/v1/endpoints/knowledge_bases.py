"""
Knowledge Base Management and Access Endpoints.

Enforces role-based access control and multi-user isolation:
- Only ADMIN users can create, manage, or add members to knowledge bases.
- STUDENT users can only access knowledge bases for which they possess explicit membership.
- Unauthorized access returns HTTP 404 to avoid leaking private resource existence.
"""

import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import and_, func, select

from backend.app.api.deps import (
    AuthenticatedAdmin,
    AuthenticatedUser,
    DatabaseSession,
    RateLimitIndexing,
    RateLimitUpload,
    get_authorized_knowledge_base,
    require_knowledge_base_admin,
)
from backend.app.models.document import Document, DocumentChunk, DocumentStatus, IndexingStatus
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseMember
from backend.app.models.user import User, UserRole
from backend.app.schemas.document import DocumentChunkResponse, DocumentResponse
from backend.app.schemas.knowledge_base import (
    AddMemberRequest,
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    MemberResponse,
)
from backend.app.services.indexing import index_document_task
from backend.app.services.ingestion import process_document_task
from backend.app.services.storage import storage_service

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])

AuthorizedKB = Annotated[KnowledgeBase, Depends(get_authorized_knowledge_base)]
AdminKB = Annotated[KnowledgeBase, Depends(require_knowledge_base_admin)]


@router.post(
    "",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new knowledge base (ADMIN only)",
)
def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    current_user: AuthenticatedAdmin,
    db: DatabaseSession,
) -> KnowledgeBaseResponse:
    """
    Create a new knowledge base.
    Restricted strictly to users with the ADMIN role.
    """
    kb = KnowledgeBase(
        name=payload.name.strip(),
        description=payload.description.strip(),
        created_by_id=current_user.id,
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return KnowledgeBaseResponse.model_validate(kb)


@router.get(
    "",
    response_model=list[KnowledgeBaseResponse],
    status_code=status.HTTP_200_OK,
    summary="List all knowledge bases authorized for current user",
)
def list_knowledge_bases(
    current_user: AuthenticatedUser,
    db: DatabaseSession,
) -> list[KnowledgeBaseResponse]:
    """
    List knowledge bases using authorization-aware filtering at the SQL layer:
    - ADMIN: views knowledge bases they created.
    - STUDENT: views only knowledge bases where they were granted membership.
    """
    if current_user.role == UserRole.ADMIN:
        stmt = (
            select(KnowledgeBase)
            .where(KnowledgeBase.created_by_id == current_user.id)
            .order_by(KnowledgeBase.created_at.desc())
        )
    else:
        stmt = (
            select(KnowledgeBase)
            .join(
                KnowledgeBaseMember,
                KnowledgeBase.id == KnowledgeBaseMember.knowledge_base_id,
            )
            .where(KnowledgeBaseMember.user_id == current_user.id)
            .order_by(KnowledgeBase.created_at.desc())
        )

    kbs = db.execute(stmt).scalars().all()
    return [KnowledgeBaseResponse.model_validate(k) for k in kbs]


@router.get(
    "/{kb_id}",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Get details of an authorized knowledge base",
)
def get_knowledge_base(
    kb: AuthorizedKB,
) -> KnowledgeBaseResponse:
    """
    Retrieve knowledge base details.
    Returns HTTP 404 if the user is not authorized to access this knowledge base.
    """
    return KnowledgeBaseResponse.model_validate(kb)


@router.post(
    "/{kb_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Grant student access to a knowledge base (ADMIN only)",
)
def add_member(
    payload: AddMemberRequest,
    kb: AdminKB,
    db: DatabaseSession,
) -> MemberResponse:
    """
    Grant access to a student user. Restricted to the administering ADMIN.
    """
    # Verify target user exists
    target_user_stmt = select(User).where(User.id == payload.user_id)
    target_user = db.execute(target_user_stmt).scalar_one_or_none()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    # Check for existing membership
    existing_stmt = select(KnowledgeBaseMember).where(
        and_(
            KnowledgeBaseMember.knowledge_base_id == kb.id,
            KnowledgeBaseMember.user_id == payload.user_id,
        )
    )
    existing_member = db.execute(existing_stmt).scalar_one_or_none()
    if existing_member:
        return MemberResponse.model_validate(existing_member)

    member = KnowledgeBaseMember(
        knowledge_base_id=kb.id,
        user_id=payload.user_id,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return MemberResponse.model_validate(member)


@router.post(
    "/{kb_id}/documents",
    response_model=DocumentResponse | dict[str, str],
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest document (ADMIN only)",
)
async def upload_document(
    kb: AdminKB,
    background_tasks: BackgroundTasks,
    response: Response,
    db: DatabaseSession,
    _rate_limit: RateLimitUpload,
    file: Annotated[UploadFile | None, File()] = None,
) -> DocumentResponse | dict[str, str]:
    """
    Upload and ingest a document into an authorized knowledge base.
    Restricted strictly to the ADMIN who owns the target knowledge base.

    If invoked without a file, returns authorization status confirmation
    for backward compatibility with Step 4 authorization probes.
    """
    if file is None:
        response.status_code = status.HTTP_200_OK
        return {
            "status": "authorized",
            "knowledge_base_id": str(kb.id),
            "message": "User is authorized to upload documents.",
        }

    # Validate file extension, size, and content signature/magic bytes
    validated = await storage_service.validate_and_read_upload(file)

    # Generate unpredictable UUID for internal storage
    document_id = uuid.uuid4()
    storage_key = storage_service.save_file(
        knowledge_base_id=kb.id,
        document_id=document_id,
        extension=validated.extension,
        content=validated.content,
    )

    # Create document record in PENDING state
    doc = Document(
        id=document_id,
        knowledge_base_id=kb.id,
        original_filename=validated.original_filename,
        storage_key=storage_key,
        file_type=validated.file_type,
        mime_type=validated.mime_type,
        file_size_bytes=validated.file_size_bytes,
        content_hash=validated.content_hash,
        status=DocumentStatus.PENDING,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Dispatch ingestion background task
    background_tasks.add_task(process_document_task, doc.id)

    response.status_code = status.HTTP_201_CREATED
    return DocumentResponse(
        id=doc.id,
        knowledge_base_id=doc.knowledge_base_id,
        original_filename=doc.original_filename,
        file_type=doc.file_type,
        mime_type=doc.mime_type,
        file_size_bytes=doc.file_size_bytes,
        status=doc.status,
        indexing_status=doc.indexing_status,
        error_message=doc.error_message,
        indexing_error=doc.indexing_error,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        indexed_at=doc.indexed_at,
        chunk_count=0,
    )


@router.get(
    "/{kb_id}/documents",
    response_model=list[DocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="List all documents in an authorized knowledge base",
)
def list_documents(
    kb: AuthorizedKB,
    db: DatabaseSession,
) -> list[DocumentResponse]:
    """
    Retrieve all documents belonging to an authorized knowledge base.
    Accessible to the ADMIN creator and authorized STUDENT members.
    """
    docs = (
        db.execute(
            select(Document)
            .where(Document.knowledge_base_id == kb.id)
            .order_by(Document.created_at.desc())
        )
        .scalars()
        .all()
    )

    results: list[DocumentResponse] = []
    for doc in docs:
        chunk_count = db.execute(
            select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == doc.id)
        ).scalar_one()

        results.append(
            DocumentResponse(
                id=doc.id,
                knowledge_base_id=doc.knowledge_base_id,
                original_filename=doc.original_filename,
                file_type=doc.file_type,
                mime_type=doc.mime_type,
                file_size_bytes=doc.file_size_bytes,
                status=doc.status,
                indexing_status=doc.indexing_status,
                error_message=doc.error_message,
                indexing_error=doc.indexing_error,
                created_at=doc.created_at,
                updated_at=doc.updated_at,
                indexed_at=doc.indexed_at,
                chunk_count=chunk_count,
            )
        )
    return results


@router.get(
    "/{kb_id}/documents/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get document details and processing status",
)
def get_document(
    kb: AuthorizedKB,
    document_id: uuid.UUID,
    db: DatabaseSession,
) -> DocumentResponse:
    """
    Retrieve metadata and processing status for an individual document.
    """
    doc = db.execute(
        select(Document).where(
            and_(
                Document.id == document_id,
                Document.knowledge_base_id == kb.id,
            )
        )
    ).scalar_one_or_none()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    chunk_count = db.execute(
        select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == doc.id)
    ).scalar_one()

    return DocumentResponse(
        id=doc.id,
        knowledge_base_id=doc.knowledge_base_id,
        original_filename=doc.original_filename,
        file_type=doc.file_type,
        mime_type=doc.mime_type,
        file_size_bytes=doc.file_size_bytes,
        status=doc.status,
        indexing_status=doc.indexing_status,
        error_message=doc.error_message,
        indexing_error=doc.indexing_error,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        indexed_at=doc.indexed_at,
        chunk_count=chunk_count,
    )


@router.post(
    "/{kb_id}/documents/{document_id}/index",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger vector indexing for an ingested document (ADMIN only)",
)
def index_document_endpoint(
    kb: AdminKB,
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: DatabaseSession,
    _rate_limit: RateLimitIndexing,
) -> DocumentResponse:
    """
    Trigger 1024-dimensional dense vector indexing for an ingested document.
    Restricted strictly to the ADMIN who manages the target knowledge base.

    Invariants (Addressing Step 6 Rules & Corrections):
    1. Document must exist within the target knowledge base (returns 404 otherwise).
    2. Document ingestion must be COMPLETED (returns 400 if still pending/processing/failed).
    3. Transition status to PROCESSING immediately and queue index_document_task
       via BackgroundTasks without blocking the API caller.
    """
    doc = db.execute(
        select(Document).where(
            and_(
                Document.id == document_id,
                Document.knowledge_base_id == kb.id,
            )
        )
    ).scalar_one_or_none()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    if doc.status != DocumentStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Document is not eligible for vector indexing. "
                f"Ingestion status is '{doc.status}' (must be COMPLETED)."
            ),
        )

    doc.indexing_status = IndexingStatus.PROCESSING
    doc.indexing_error = None
    db.commit()

    background_tasks.add_task(index_document_task, doc.id)

    chunk_count = db.execute(
        select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == doc.id)
    ).scalar_one()

    return DocumentResponse(
        id=doc.id,
        knowledge_base_id=doc.knowledge_base_id,
        original_filename=doc.original_filename,
        file_type=doc.file_type,
        mime_type=doc.mime_type,
        file_size_bytes=doc.file_size_bytes,
        status=doc.status,
        indexing_status=doc.indexing_status,
        error_message=doc.error_message,
        indexing_error=doc.indexing_error,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        indexed_at=doc.indexed_at,
        chunk_count=chunk_count,
    )


@router.get(
    "/{kb_id}/documents/{document_id}/chunks",
    response_model=list[DocumentChunkResponse],
    status_code=status.HTTP_200_OK,
    summary="Inspect extracted chunks for an authorized document",
)
def list_document_chunks(
    kb: AuthorizedKB,
    document_id: uuid.UUID,
    db: DatabaseSession,
) -> list[DocumentChunkResponse]:
    """
    Inspect extracted text chunks, page numbers, and structural headings.
    Useful for administrator auditing and citation verification.
    """
    doc = db.execute(
        select(Document).where(
            and_(
                Document.id == document_id,
                Document.knowledge_base_id == kb.id,
            )
        )
    ).scalar_one_or_none()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    chunks = (
        db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
        .scalars()
        .all()
    )

    return [
        DocumentChunkResponse(
            id=c.id,
            document_id=c.document_id,
            knowledge_base_id=c.knowledge_base_id,
            chunk_index=c.chunk_index,
            text=c.text,
            token_count=c.token_count,
            page_number=c.page_number,
            section_title=c.section_title,
            chunk_metadata=c.chunk_metadata,
            has_embedding=(c.embedding is not None),
            created_at=c.created_at,
        )
        for c in chunks
    ]


@router.delete(
    "/{kb_id}/documents/{document_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete document, chunks, and storage file (ADMIN only)",
)
def delete_document(
    kb: AdminKB,
    document_id: uuid.UUID,
    db: DatabaseSession,
) -> dict[str, str]:
    """
    Delete a document and all its derived chunks and physical files.
    Restricted strictly to the administering ADMIN.

    Consistency Strategy (Correction #5):
    1. The document record is removed in a database transaction, which cascades
       deletion to all associated DocumentChunk entities via PostgreSQL foreign keys.
    2. Only after database commit succeeds is the physical file unlinked from disk.
    3. If unlinking fails (e.g. temporary Windows file lock), a warning is logged
       for background orphan cleanup. No dangling database records are left pointing
       to missing files.
    """
    doc = db.execute(
        select(Document).where(
            and_(
                Document.id == document_id,
                Document.knowledge_base_id == kb.id,
            )
        )
    ).scalar_one_or_none()

    if doc:
        storage_key = doc.storage_key
        db.delete(doc)
        db.commit()
        # Post-commit physical file cleanup
        storage_service.delete_file(storage_key)

    return {
        "status": "authorized",
        "knowledge_base_id": str(kb.id),
        "document_id": str(document_id),
        "message": "Document deleted successfully.",
    }
