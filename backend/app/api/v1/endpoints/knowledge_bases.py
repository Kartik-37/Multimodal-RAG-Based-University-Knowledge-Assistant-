"""
Knowledge Base Management and Access Endpoints.

Enforces role-based access control and multi-user isolation:
- Only ADMIN users can create, manage, or add members to knowledge bases.
- STUDENT users can only access knowledge bases for which they possess explicit membership.
- Unauthorized access returns HTTP 404 to avoid leaking private resource existence.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select

from backend.app.api.deps import (
    AuthenticatedAdmin,
    AuthenticatedUser,
    DatabaseSession,
    get_authorized_knowledge_base,
    require_knowledge_base_admin,
)
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseMember
from backend.app.models.user import User, UserRole
from backend.app.schemas.knowledge_base import (
    AddMemberRequest,
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    MemberResponse,
)

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
    status_code=status.HTTP_200_OK,
    summary="Document upload authorization boundary (ADMIN only)",
)
def upload_document_authorization_gate(
    kb: AdminKB,
) -> dict[str, str]:
    """
    Enforces that document upload is strictly restricted to ADMINs.
    Step 4 security gate: students attempting to invoke this receive HTTP 403 Forbidden.
    """
    return {
        "status": "authorized",
        "knowledge_base_id": str(kb.id),
        "message": "User is authorized to upload documents.",
    }


@router.delete(
    "/{kb_id}/documents/{document_id}",
    status_code=status.HTTP_200_OK,
    summary="Document deletion authorization boundary (ADMIN only)",
)
def delete_document_authorization_gate(
    kb: AdminKB,
    document_id: str,
) -> dict[str, str]:
    """
    Enforces that document deletion is strictly restricted to ADMINs.
    Step 4 security gate: students attempting to invoke this receive HTTP 403 Forbidden.
    """
    return {
        "status": "authorized",
        "knowledge_base_id": str(kb.id),
        "document_id": document_id,
        "message": "User is authorized to delete documents.",
    }
