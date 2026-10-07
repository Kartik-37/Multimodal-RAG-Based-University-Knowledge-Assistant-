"""
Document File Streaming and Lookup Endpoints.

Provides direct access to original uploaded course documents (PDFs, text files):
- Stream by document UUID (/documents/{document_id}/file)
- Stream by original filename and course (/documents/by-name?name=...&kb_id=...)
- Enforces strict server-side authorization and multi-user isolation.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from backend.app.api.deps import (
    AuthenticatedUser,
    DatabaseSession,
    get_authorized_document,
    get_authorized_knowledge_base,
)
from backend.app.models.document import Document
from backend.app.models.user import UserRole
from backend.app.services.storage import storage_service

router = APIRouter(prefix="/documents", tags=["documents"])


def _stream_document(doc: Document) -> FileResponse:
    """Validate storage path and construct inline FileResponse."""
    try:
        abs_path = storage_service.get_absolute_path(doc.storage_key)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid storage path.",
        ) from exc

    if not abs_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found on disk.",
        )

    media_type = doc.mime_type or "application/octet-stream"
    disposition = "inline"
    if doc.file_type == "pdf":
        media_type = "application/pdf"
    elif doc.file_type in ("docx", "doc"):
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        disposition = "attachment"
    elif doc.file_type in ("txt", "text"):
        media_type = "text/plain; charset=utf-8"
    elif doc.file_type in ("md", "markdown"):
        media_type = "text/markdown; charset=utf-8"
    elif doc.file_type == "csv":
        media_type = "text/csv; charset=utf-8"

    return FileResponse(
        path=str(abs_path),
        media_type=media_type,
        filename=doc.original_filename,
        content_disposition_type=disposition,
        headers={"Accept-Ranges": "bytes"},
    )


@router.get(
    "/{document_id}/file",
    status_code=status.HTTP_200_OK,
    summary="Stream document file by document ID",
)
def get_document_file_by_id(
    document_id: uuid.UUID,
    db: DatabaseSession,
    current_user: AuthenticatedUser,
) -> FileResponse:
    """
    Stream document file by document UUID.
    Verifies user has access to parent course and document is published if student.
    """
    doc = get_authorized_document(
        document_id=document_id,
        current_user=current_user,
        db=db,
    )
    return _stream_document(doc)


@router.get(
    "/by-name",
    status_code=status.HTTP_200_OK,
    summary="Stream document file by original filename and optional course ID",
)
def get_document_file_by_name(
    name: Annotated[str, Query(description="Original filename to locate")],
    db: DatabaseSession,
    current_user: AuthenticatedUser,
    kb_id: Annotated[uuid.UUID | None, Query(description="Optional parent course ID")] = None,
) -> FileResponse:
    """
    Locate and stream document file by filename and optional course.
    Useful when citation or client only has the filename.
    """
    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename query parameter 'name' cannot be empty.",
        )

    stmt = select(Document).where(Document.original_filename == clean_name)
    if kb_id:
        stmt = stmt.where(Document.knowledge_base_id == kb_id)
    if current_user.role == UserRole.STUDENT:
        stmt = stmt.where(Document.is_active.is_(True))

    stmt = stmt.order_by(Document.created_at.desc())
    docs = db.execute(stmt).scalars().all()

    if not docs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    # Find the first document the user is authorized to view
    for doc in docs:
        try:
            get_authorized_knowledge_base(
                kb_id=doc.knowledge_base_id,
                current_user=current_user,
                db=db,
            )
            return _stream_document(doc)
        except HTTPException:
            continue

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Document not found.",
    )
