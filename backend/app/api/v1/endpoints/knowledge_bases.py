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
from sqlalchemy import and_, func, or_, select

from backend.app.api.deps import (
    AuthenticatedAdmin,
    AuthenticatedUser,
    DatabaseSession,
    RateLimitIndexing,
    RateLimitUpload,
    check_user_permission,
    get_authorized_knowledge_base,
    is_main_admin,
    require_knowledge_base_admin,
)
from backend.app.core.permissions import Permission
from backend.app.models.document import Document, DocumentChunk, DocumentStatus, IndexingStatus
from backend.app.models.indexing_job import IndexingJob
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseMember
from backend.app.models.user import User, UserRole
from backend.app.schemas.document import DocumentChunkResponse, DocumentResponse
from backend.app.schemas.knowledge_base import (
    AddMemberRequest,
    CourseDocumentPreview,
    CourseSummaryResponse,
    IndexingJobResponse,
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    MemberResponse,
)
from backend.app.services.indexing import index_document_task, indexing_pipeline
from backend.app.services.indexing_worker import notify_indexing_worker
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
    Restricted strictly to users with COURSE_CREATE permission.
    """
    if not check_user_permission(current_user, Permission.COURSE_CREATE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Missing required permission 'COURSE_CREATE'.",
        )

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
    - MAIN_ADMIN: views all knowledge bases in system.
    - FACULTY_ADMIN: views knowledge bases they created or were granted access.
    - STUDENT: views only knowledge bases where they were granted membership.
    """
    if current_user.role == UserRole.ADMIN:
        if not check_user_permission(current_user, Permission.COURSE_VIEW):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Missing required permission 'COURSE_VIEW'.",
            )
        if is_main_admin(current_user):
            stmt = select(KnowledgeBase).order_by(KnowledgeBase.created_at.desc())
        else:
            stmt = (
                select(KnowledgeBase)
                .outerjoin(
                    KnowledgeBaseMember,
                    KnowledgeBase.id == KnowledgeBaseMember.knowledge_base_id,
                )
                .where(
                    or_(
                        KnowledgeBase.created_by_id == current_user.id,
                        KnowledgeBaseMember.user_id == current_user.id,
                    )
                )
                .distinct()
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
    "/summaries",
    response_model=list[CourseSummaryResponse],
    status_code=status.HTTP_200_OK,
    summary="Get aggregated course summaries with document metrics and previews",
)
def get_course_summaries(
    current_user: AuthenticatedUser,
    db: DatabaseSession,
) -> list[CourseSummaryResponse]:
    """
    Retrieve courses accessible to current user with aggregated document counts
    and compact file previews. Strictly avoids N+1 database queries.
    """
    if current_user.role == UserRole.ADMIN:
        if not check_user_permission(current_user, Permission.COURSE_VIEW):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Missing required permission 'COURSE_VIEW'.",
            )
        if is_main_admin(current_user):
            kb_stmt = select(KnowledgeBase).order_by(KnowledgeBase.created_at.desc())
        else:
            kb_stmt = (
                select(KnowledgeBase)
                .outerjoin(
                    KnowledgeBaseMember,
                    KnowledgeBase.id == KnowledgeBaseMember.knowledge_base_id,
                )
                .where(
                    or_(
                        KnowledgeBase.created_by_id == current_user.id,
                        KnowledgeBaseMember.user_id == current_user.id,
                    )
                )
                .distinct()
                .order_by(KnowledgeBase.created_at.desc())
            )
    else:
        kb_stmt = (
            select(KnowledgeBase)
            .join(
                KnowledgeBaseMember,
                KnowledgeBase.id == KnowledgeBaseMember.knowledge_base_id,
            )
            .where(KnowledgeBaseMember.user_id == current_user.id)
            .order_by(KnowledgeBase.created_at.desc())
        )

    kbs = db.execute(kb_stmt).scalars().all()
    if not kbs:
        return []

    kb_ids = [kb.id for kb in kbs]
    doc_stmt = (
        select(Document)
        .where(Document.knowledge_base_id.in_(kb_ids))
        .order_by(Document.created_at.desc())
    )
    all_docs = db.execute(doc_stmt).scalars().all()

    docs_by_kb: dict[uuid.UUID, list[Document]] = {k.id: [] for k in kbs}
    for d in all_docs:
        docs_by_kb[d.knowledge_base_id].append(d)

    results: list[CourseSummaryResponse] = []
    for kb in kbs:
        kb_docs = docs_by_kb.get(kb.id, [])
        total = len(kb_docs)
        active = sum(1 for d in kb_docs if d.is_active)
        inactive = total - active
        indexed = sum(
            1
            for d in kb_docs
            if d.indexing_status == IndexingStatus.COMPLETED
            or str(getattr(d, "indexing_status", "")) == "COMPLETED"
        )
        indexing = sum(
            1
            for d in kb_docs
            if d.indexing_status == IndexingStatus.PROCESSING
            or str(getattr(d, "indexing_status", "")) in ("PROCESSING", "QUEUED")
        )
        failed = sum(
            1
            for d in kb_docs
            if d.indexing_status == IndexingStatus.FAILED
            or str(getattr(d, "indexing_status", "")) == "FAILED"
        )
        previews = [
            CourseDocumentPreview(
                id=d.id,
                filename=d.original_filename,
                file_type=d.file_type,
                status=d.status.value if hasattr(d.status, "value") else str(d.status),
                indexing_status=d.indexing_status.value
                if hasattr(d.indexing_status, "value")
                else str(d.indexing_status),
                is_active=d.is_active,
            )
            for d in kb_docs[:4]
        ]
        results.append(
            CourseSummaryResponse(
                id=kb.id,
                name=kb.name,
                description=kb.description,
                created_at=kb.created_at,
                total_documents=total,
                active_documents=active,
                inactive_documents=inactive,
                indexed_documents=indexed,
                indexing_documents=indexing,
                failed_documents=failed,
                document_previews=previews,
            )
        )
    return results


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
    current_user: AuthenticatedAdmin,
    _rate_limit: RateLimitUpload,
    file: Annotated[UploadFile | None, File()] = None,
) -> DocumentResponse | dict[str, str]:
    """
    Upload and ingest a document into an authorized knowledge base.
    Restricted strictly to administrators with DOCUMENT_UPLOAD permission.
    """
    if not check_user_permission(current_user, Permission.DOCUMENT_UPLOAD):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Missing required permission 'DOCUMENT_UPLOAD'.",
        )

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
        is_active=doc.is_active,
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
    current_user: AuthenticatedUser,
) -> list[DocumentResponse]:
    """
    Retrieve all documents belonging to an authorized knowledge base.
    Accessible to administrators with DOCUMENT_VIEW permission and authorized students.
    """
    if current_user.role == UserRole.ADMIN and not check_user_permission(current_user, Permission.DOCUMENT_VIEW):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Missing required permission 'DOCUMENT_VIEW'.",
        )

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
                is_active=doc.is_active,
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
    current_user: AuthenticatedUser,
) -> DocumentResponse:
    """
    Retrieve metadata and processing status for an individual document.
    """
    if current_user.role == UserRole.ADMIN and not check_user_permission(current_user, Permission.DOCUMENT_VIEW):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Missing required permission 'DOCUMENT_VIEW'.",
        )

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
        is_active=doc.is_active,
        error_message=doc.error_message,
        indexing_error=doc.indexing_error,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        indexed_at=doc.indexed_at,
        chunk_count=chunk_count,
    )


@router.get(
    "/{kb_id}/documents/{document_id}/index-status",
    response_model=IndexingJobResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current or latest vector indexing job status for a document",
)
def get_document_index_status(
    kb: AuthorizedKB,
    document_id: uuid.UUID,
    db: DatabaseSession,
    current_user: AuthenticatedUser,
) -> IndexingJobResponse:
    """
    Return truthful, persistent vector indexing job status, stage, and chunk progress.
    """
    if current_user.role == UserRole.ADMIN and not check_user_permission(current_user, Permission.DOCUMENT_VIEW):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Missing required permission 'DOCUMENT_VIEW'.",
        )

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

    job = db.execute(
        select(IndexingJob)
        .where(IndexingJob.document_id == document_id)
        .order_by(IndexingJob.created_at.desc())
    ).scalars().first()

    if not job:
        chunk_count = db.execute(
            select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == doc.id)
        ).scalar_one()
        indexed_count = chunk_count if doc.indexing_status == IndexingStatus.COMPLETED else 0
        pct = 100.0 if doc.indexing_status == IndexingStatus.COMPLETED else 0.0

        return IndexingJobResponse(
            id=None,
            job_id=None,
            document_id=doc.id,
            knowledge_base_id=doc.knowledge_base_id,
            status=doc.indexing_status.value if hasattr(doc.indexing_status, "value") else str(doc.indexing_status),
            stage="COMPLETED" if doc.indexing_status == IndexingStatus.COMPLETED else ("FAILED" if doc.indexing_status == IndexingStatus.FAILED else "PREPARING"),
            total_chunks=chunk_count,
            processed_chunks=indexed_count,
            embedded_chunks=indexed_count,
            indexed_chunks=indexed_count,
            progress_percent=pct,
            error_message=doc.indexing_error,
            attempt_number=1 if doc.indexing_status != IndexingStatus.PENDING else 0,
            started_at=doc.created_at,
            completed_at=doc.indexed_at,
        )

    return IndexingJobResponse(
        id=job.id,
        job_id=job.id,
        document_id=job.document_id,
        knowledge_base_id=job.knowledge_base_id,
        status=job.status,
        stage=job.stage,
        total_chunks=job.total_chunks,
        processed_chunks=job.processed_chunks,
        embedded_chunks=job.embedded_chunks,
        indexed_chunks=job.indexed_chunks,
        progress_percent=job.progress_percent,
        error_message=job.error_message,
        attempt_number=job.attempt_number,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


@router.patch(
    "/{kb_id}/documents/{document_id}/activate",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Activate a document for retrieval (ADMIN only)",
)
def activate_document(
    kb: AdminKB,
    document_id: uuid.UUID,
    db: DatabaseSession,
    current_user: AuthenticatedAdmin,
) -> DocumentResponse:
    """
    Activate an ingested and indexed document so it becomes eligible for vector
    and lexical retrieval. Restricted strictly to admins with DOCUMENT_PUBLISH permission.
    Returns 400 Bad Request if vector indexing has not completed successfully.
    Returns 409 Conflict if the document is already active.
    """
    if not check_user_permission(current_user, Permission.DOCUMENT_PUBLISH):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Missing required permission 'DOCUMENT_PUBLISH'.",
        )

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

    if doc.indexing_status != IndexingStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot activate a document that has not completed vector indexing.",
        )

    if doc.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="DOCUMENT_ALREADY_ACTIVE",
        )

    doc.is_active = True
    db.commit()
    db.refresh(doc)

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
        is_active=doc.is_active,
        error_message=doc.error_message,
        indexing_error=doc.indexing_error,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        indexed_at=doc.indexed_at,
        chunk_count=chunk_count,
    )


@router.patch(
    "/{kb_id}/documents/{document_id}/deactivate",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate a document from retrieval (ADMIN only)",
)
def deactivate_document(
    kb: AdminKB,
    document_id: uuid.UUID,
    db: DatabaseSession,
    current_user: AuthenticatedAdmin,
) -> DocumentResponse:
    """
    Deactivate a document so it is excluded from vector and lexical retrieval.
    Restricted strictly to admins with DOCUMENT_PUBLISH permission.
    """
    if not check_user_permission(current_user, Permission.DOCUMENT_PUBLISH):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Missing required permission 'DOCUMENT_PUBLISH'.",
        )

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

    if not doc.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="DOCUMENT_ALREADY_INACTIVE",
        )

    doc.is_active = False
    db.commit()
    db.refresh(doc)

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
        is_active=doc.is_active,
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
    current_user: AuthenticatedAdmin,
    _rate_limit: RateLimitIndexing,
) -> DocumentResponse:
    """
    Trigger 1024-dimensional dense vector indexing for an ingested document.
    Enforces DOCUMENT_INDEX or DOCUMENT_INDEX_RETRY permissions.
    Creates or reuses a persistent IndexingJob and notifies the worker.
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

    # Check permission (retry vs initial index)
    is_retry = (doc.indexing_status == IndexingStatus.FAILED)
    if is_retry:
        if not (check_user_permission(current_user, Permission.DOCUMENT_INDEX_RETRY) or check_user_permission(current_user, Permission.DOCUMENT_INDEX)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Missing required permission 'DOCUMENT_INDEX_RETRY'.",
            )
    else:
        if not check_user_permission(current_user, Permission.DOCUMENT_INDEX):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Missing required permission 'DOCUMENT_INDEX'.",
            )

    if doc.status != DocumentStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Document is not eligible for vector indexing. "
                f"Ingestion status is '{doc.status}' (must be COMPLETED)."
            ),
        )

    # Persistent job creation/reuse and notification
    job = indexing_pipeline.create_or_reuse_job(doc.id, kb.id)
    notify_indexing_worker()
    background_tasks.add_task(index_document_task, doc.id, job.id)

    db.refresh(doc)
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
        is_active=doc.is_active,
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
    current_user: AuthenticatedUser,
) -> list[DocumentChunkResponse]:
    """
    Inspect extracted text chunks, page numbers, and structural headings.
    """
    if current_user.role == UserRole.ADMIN and not check_user_permission(current_user, Permission.DOCUMENT_VIEW):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Missing required permission 'DOCUMENT_VIEW'.",
        )

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
    current_user: AuthenticatedAdmin,
) -> dict[str, str]:
    """
    Delete a document and all its derived chunks and physical files.
    Restricted strictly to administrators with DOCUMENT_DELETE permission.
    """
    if not check_user_permission(current_user, Permission.DOCUMENT_DELETE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Missing required permission 'DOCUMENT_DELETE'.",
        )

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
