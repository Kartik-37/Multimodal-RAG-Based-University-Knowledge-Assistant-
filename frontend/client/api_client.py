"""
Centralized Frontend API Client.

Encapsulates all communication between the NiceGUI presentation layer and the
FastAPI backend API.

In Step 3, before the full authentication and RAG backend is implemented in Step 4,
this client maintains an in-memory session and deterministic responses for UI validation.
It isolates this temporary behavior completely from the UI widgets, allowing smooth
transition to real HTTP calls in Step 4 without changing UI code.
"""

import uuid
from datetime import datetime

from frontend.client.models import (
    ChatMessageDTO,
    CitationDTO,
    DocumentDTO,
    KnowledgeBaseDTO,
    UserDTO,
)


class FrontendAPIClient:
    """API Client mediating presentation requests to the backend service boundary."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000/api/v1") -> None:
        self.base_url = base_url
        self._current_user: UserDTO | None = None

        # In-memory presentation store for Step 3 UI testing
        self._knowledge_bases: list[KnowledgeBaseDTO] = [
            KnowledgeBaseDTO(
                id="kb-default-university",
                name="University Regulations & Policies",
                description="Official BCA curriculum, exam regulations, and library rules.",
                document_count=2,
                created_at="2026-09-01",
            ),
            KnowledgeBaseDTO(
                id="kb-admissions",
                name="Admissions & Eligibility",
                description="BCA admission guidelines and reservation quotas.",
                document_count=1,
                created_at="2026-09-05",
            ),
        ]

        self._documents: dict[str, list[DocumentDTO]] = {
            "kb-default-university": [
                DocumentDTO(
                    id="doc-1",
                    kb_id="kb-default-university",
                    filename="KSU-Act-English.pdf",
                    file_type="pdf",
                    file_size_bytes=351416,
                    status="INDEXED",
                    chunk_count=32,
                    created_at="2026-09-01 10:30",
                ),
                DocumentDTO(
                    id="doc-2",
                    kb_id="kb-default-university",
                    filename="examination_ordinance.docx",
                    file_type="docx",
                    file_size_bytes=48120,
                    status="INDEXED",
                    chunk_count=15,
                    created_at="2026-09-02 11:15",
                ),
            ],
            "kb-admissions": [
                DocumentDTO(
                    id="doc-3",
                    kb_id="kb-admissions",
                    filename="bca_eligibility_criteria.txt",
                    file_type="txt",
                    file_size_bytes=12400,
                    status="INDEXED",
                    chunk_count=6,
                    created_at="2026-09-05 14:00",
                ),
            ],
        }

    # --------------------------------------------------------------------------
    # Authentication Boundary
    # --------------------------------------------------------------------------

    def login(self, email: str, password: str) -> UserDTO:
        """
        Authenticate user with email and password.
        Validates non-empty credentials and sets current session user.
        """
        if not email or not password:
            raise ValueError("Email and password must not be empty.")

        user_name = email.split("@")[0].capitalize()
        self._current_user = UserDTO(
            id=f"usr-{abs(hash(email)) % 10000}",
            email=email,
            full_name=user_name,
        )
        return self._current_user

    def register(self, email: str, password: str, full_name: str) -> UserDTO:
        """Register a new user account."""
        if not email or not password or not full_name:
            raise ValueError("All registration fields are required.")

        self._current_user = UserDTO(
            id=f"usr-{abs(hash(email)) % 10000}",
            email=email,
            full_name=full_name,
        )
        return self._current_user

    def logout(self) -> None:
        """Clear active user session."""
        self._current_user = None

    def get_current_user(self) -> UserDTO | None:
        """Retrieve currently authenticated user, or None if unauthenticated."""
        return self._current_user

    # --------------------------------------------------------------------------
    # Knowledge Bases Boundary
    # --------------------------------------------------------------------------

    def get_knowledge_bases(self) -> list[KnowledgeBaseDTO]:
        """Fetch all knowledge bases accessible to the current user."""
        return list(self._knowledge_bases)

    def create_knowledge_base(self, name: str, description: str = "") -> KnowledgeBaseDTO:
        """Create a new user knowledge base."""
        if not name.strip():
            raise ValueError("Knowledge base name cannot be empty.")

        kb = KnowledgeBaseDTO(
            id=f"kb-{uuid.uuid4().hex[:8]}",
            name=name.strip(),
            description=description.strip(),
            document_count=0,
            created_at=datetime.now().strftime("%Y-%m-%d"),
        )
        self._knowledge_bases.append(kb)
        self._documents[kb.id] = []
        return kb

    # --------------------------------------------------------------------------
    # Documents Boundary
    # --------------------------------------------------------------------------

    def get_documents(self, kb_id: str) -> list[DocumentDTO]:
        """Fetch documents belonging to a knowledge base."""
        return list(self._documents.get(kb_id, []))

    def upload_document(
        self, kb_id: str, filename: str, content_size_bytes: int = 0
    ) -> DocumentDTO:
        """Register an uploaded document into a knowledge base."""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
        doc = DocumentDTO(
            id=f"doc-{uuid.uuid4().hex[:8]}",
            kb_id=kb_id,
            filename=filename,
            file_type=ext,
            file_size_bytes=content_size_bytes,
            status="INDEXED",
            chunk_count=5,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
        if kb_id not in self._documents:
            self._documents[kb_id] = []
        self._documents[kb_id].append(doc)

        # Update KB document count
        for kb in self._knowledge_bases:
            if kb.id == kb_id:
                kb.document_count = len(self._documents[kb_id])
                break

        return doc

    # --------------------------------------------------------------------------
    # Conversational RAG Query Boundary
    # --------------------------------------------------------------------------

    def send_chat_message(self, kb_id: str, question: str) -> ChatMessageDTO:
        """
        Submit a question to the conversational RAG pipeline.
        Returns a response containing citations and evidence metadata.
        """
        if not question.strip():
            raise ValueError("Question cannot be empty.")

        # Representative evidence citation demonstrating citation/evidence inspection panel
        citations = [
            CitationDTO(
                document_name="KSU-Act-English.pdf",
                page_number=3,
                chunk_id="KSU-Act-English.pdf_p3_c1",
                relevance_score=0.892,
                snippet=(
                    "The University shall maintain standards for Bachelor in Computer "
                    "Applications (BCA) and relevant academic programmes as prescribed by the "
                    "Academic Council."
                ),
            ),
            CitationDTO(
                document_name="examination_ordinance.docx",
                page_number=1,
                chunk_id="examination_ordinance.docx_p1_c0",
                relevance_score=0.781,
                snippet=(
                    "Students must maintain a minimum of 75% attendance in both lecture and "
                    "laboratory sessions to be eligible for university semester examinations."
                ),
            ),
        ]

        answer = (
            f"Based on the knowledge base documents, here is the answer regarding your query "
            f"'{question.strip()}':\n\n"
            f"1. As stated in [KSU-Act-English.pdf, Page 3], the university oversees academic standards "
            f"and curriculum approval.\n"
            f"2. Under [examination_ordinance.docx, Page 1], candidates are required to fulfill attendance "
            f"and examination criteria."
        )

        return ChatMessageDTO(
            id=f"msg-{uuid.uuid4().hex[:8]}",
            role="assistant",
            content=answer,
            citations=citations,
            created_at=datetime.now().strftime("%H:%M"),
        )


# Global default client instance for the frontend presentation layer
api_client = FrontendAPIClient()
