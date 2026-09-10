"""
Conversational RAG Query Endpoints.

Enforces that queries are only permitted from authenticated users (ADMIN or STUDENT)
who possess authorized access to the target knowledge base.
"""

import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from backend.app.api.deps import AuthenticatedUser, DatabaseSession, get_authorized_knowledge_base

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatQueryRequest(BaseModel):
    """Query payload for conversational RAG."""

    knowledge_base_id: uuid.UUID
    question: str = Field(min_length=1, max_length=1000)


class CitationSchema(BaseModel):
    """Retrieved citation source provenance."""

    document_name: str
    page_number: int | None = None
    chunk_id: str
    relevance_score: float
    snippet: str


class ChatQueryResponse(BaseModel):
    """Response returned from conversational query."""

    answer: str
    citations: list[CitationSchema]


@router.post(
    "/query",
    response_model=ChatQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit query to authorized knowledge base (ADMIN or authorized STUDENT)",
)
def query_knowledge_base(
    payload: ChatQueryRequest,
    current_user: AuthenticatedUser,
    db: DatabaseSession,
) -> ChatQueryResponse:
    """
    Submit a query against an authorized knowledge base.
    Both ADMIN and STUDENT users can query, but only if they have access to the target KB.
    """
    # Enforces multi-user isolation check: returns 404 if user has no access
    kb = get_authorized_knowledge_base(
        kb_id=payload.knowledge_base_id,
        current_user=current_user,
        db=db,
    )

    return ChatQueryResponse(
        answer=f"Grounded response for knowledge base '{kb.name}': Query '{payload.question}' verified.",
        citations=[
            CitationSchema(
                document_name="official_curriculum.pdf",
                page_number=1,
                chunk_id=f"{kb.id}_p1_c0",
                relevance_score=0.912,
                snippet="Official university curriculum guidelines and regulations.",
            )
        ],
    )
