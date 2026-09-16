"""
Centralized Frontend API Client.

Encapsulates all communication between the NiceGUI presentation layer and the
FastAPI backend API.

In Step 4, this client communicates directly with the real FastAPI service boundary
and PostgreSQL database:
- Authenticates users with Argon2id and manages real server sessions.
- Enforces role-based permissions (ADMIN vs STUDENT).
- Uses authorization-aware queries for knowledge bases.
- Validates that unauthorized student actions are rejected by the backend.
"""

import uuid
from datetime import datetime

from fastapi.testclient import TestClient

from backend.app.main import app
from frontend.client.models import (
    ChatMessageDTO,
    CitationDTO,
    DocumentDTO,
    HybridRetrievalResultDTO,
    KnowledgeBaseDTO,
    LexicalRetrievalResultDTO,
    QueryProcessingResultDTO,
    RerankResultDTO,
    RetrievalResultDTO,
    UserDTO,
)


class FrontendAPIClient:
    """API Client mediating presentation requests to the backend service boundary."""

    def __init__(self, base_url: str = "http://testserver/api/v1") -> None:
        self.base_url = base_url
        self._current_user: UserDTO | None = None
        # TestClient handles real FastAPI middleware, cookies, dependencies, and DB sessions
        self._http = TestClient(app, base_url=base_url)

        # In-memory document status storage for Step 4 presentation
        self._documents: dict[str, list[DocumentDTO]] = {}

    # --------------------------------------------------------------------------
    # Authentication Boundary
    # --------------------------------------------------------------------------

    def login(self, email: str, password: str) -> UserDTO:
        """
        Authenticate user with email and password via FastAPI backend.
        Establishes an authoritative server session with Argon2id verification.
        """
        if not email or not password:
            raise ValueError("Email and password must not be empty.")

        resp = self._http.post(
            "/auth/login",
            json={"email": email.strip(), "password": password},
        )
        if resp.status_code != 200:
            detail = resp.json().get("detail", "Authentication failed.")
            raise ValueError(detail)

        data = resp.json()
        user_data = data["user"]
        self._current_user = UserDTO(
            id=str(user_data["id"]),
            email=user_data["email"],
            full_name=user_data["full_name"],
            role=user_data["role"],
        )
        return self._current_user

    def register(self, email: str, password: str, full_name: str) -> UserDTO:
        """
        Register a new user account via FastAPI backend.
        CRITICAL SECURITY: Public registration always creates a STUDENT account.
        """
        if not email or not password or not full_name:
            raise ValueError("All registration fields are required.")

        resp = self._http.post(
            "/auth/register",
            json={
                "email": email.strip(),
                "password": password,
                "full_name": full_name.strip(),
            },
        )
        if resp.status_code != 201:
            detail = resp.json().get("detail", "Registration failed.")
            raise ValueError(detail)

        # Automatically authenticate the new user
        return self.login(email=email, password=password)

    def logout(self) -> None:
        """Terminate active session in PostgreSQL and clear cookie."""
        try:
            self._http.post("/auth/logout")
        finally:
            self._current_user = None

    def get_current_user(self) -> UserDTO | None:
        """Retrieve currently authenticated user identity from backend session."""
        if self._current_user is None:
            resp = self._http.get("/auth/me")
            if resp.status_code == 200:
                user_data = resp.json()
                self._current_user = UserDTO(
                    id=str(user_data["id"]),
                    email=user_data["email"],
                    full_name=user_data["full_name"],
                    role=user_data["role"],
                )
        return self._current_user

    # --------------------------------------------------------------------------
    # Knowledge Bases Boundary
    # --------------------------------------------------------------------------

    def get_knowledge_bases(self) -> list[KnowledgeBaseDTO]:
        """
        Fetch knowledge bases accessible to the current user.
        FastAPI performs authorization-aware filtering at the database layer.
        """
        resp = self._http.get("/knowledge-bases")
        if resp.status_code != 200:
            return []

        items = resp.json()
        return [
            KnowledgeBaseDTO(
                id=str(item["id"]),
                name=item["name"],
                description=item.get("description", ""),
                document_count=len(self._documents.get(str(item["id"]), [])),
                created_at=item["created_at"][:10],
            )
            for item in items
        ]

    def create_knowledge_base(self, name: str, description: str = "") -> KnowledgeBaseDTO:
        """
        Create a new knowledge base.
        Server-side RBAC enforces ADMIN privileges.
        """
        if not name.strip():
            raise ValueError("Knowledge base name cannot be empty.")

        resp = self._http.post(
            "/knowledge-bases",
            json={"name": name.strip(), "description": description.strip()},
        )
        if resp.status_code == 403:
            raise ValueError("Administrator privileges required to create knowledge bases.")
        if resp.status_code != 201:
            detail = resp.json().get("detail", "Failed to create knowledge base.")
            raise ValueError(detail)

        data = resp.json()
        kb = KnowledgeBaseDTO(
            id=str(data["id"]),
            name=data["name"],
            description=data.get("description", ""),
            document_count=0,
            created_at=data["created_at"][:10],
        )
        self._documents[kb.id] = []
        return kb

    # --------------------------------------------------------------------------
    # Documents Boundary
    # --------------------------------------------------------------------------

    def get_documents(self, kb_id: str) -> list[DocumentDTO]:
        """Fetch real documents for an authorized knowledge base from FastAPI."""
        resp = self._http.get(f"/knowledge-bases/{kb_id}/documents")
        if resp.status_code != 200:
            return []

        items = resp.json()
        return [
            DocumentDTO(
                id=str(item["id"]),
                kb_id=str(item["knowledge_base_id"]),
                filename=item["original_filename"],
                file_type=item["file_type"],
                file_size_bytes=item["file_size_bytes"],
                status=item["status"],
                indexing_status=item.get("indexing_status", "PENDING"),
                error_message=item.get("error_message"),
                indexing_error=item.get("indexing_error"),
                chunk_count=item.get("chunk_count", 0),
                created_at=item["created_at"][:16].replace("T", " "),
                indexed_at=item.get("indexed_at")[:16].replace("T", " ")
                if item.get("indexed_at")
                else None,
            )
            for item in items
        ]

    def upload_document(
        self,
        kb_id: str,
        filename: str,
        content: bytes,
        content_size_bytes: int | None = None,
    ) -> DocumentDTO:
        """
        Upload document to real FastAPI endpoint.
        Server-side RBAC enforces ADMIN privileges.
        """
        size = content_size_bytes if content_size_bytes is not None else len(content)
        files = {"file": (filename, content)}

        resp = self._http.post(f"/knowledge-bases/{kb_id}/documents", files=files)
        if resp.status_code == 403:
            raise ValueError("Students are not permitted to upload documents.")
        if resp.status_code not in (200, 201):
            detail = resp.json().get("detail", "Document upload rejected.")
            raise ValueError(detail)

        item = resp.json()
        return DocumentDTO(
            id=str(item["id"]),
            kb_id=str(item["knowledge_base_id"]),
            filename=item["original_filename"],
            file_type=item["file_type"],
            file_size_bytes=item.get("file_size_bytes", size),
            status=item.get("status", "COMPLETED"),
            indexing_status=item.get("indexing_status", "PENDING"),
            error_message=item.get("error_message"),
            indexing_error=item.get("indexing_error"),
            chunk_count=item.get("chunk_count", 0),
            created_at=item.get("created_at", "")[:16].replace("T", " "),
            indexed_at=item.get("indexed_at")[:16].replace("T", " ")
            if item.get("indexed_at")
            else None,
        )

    def index_document(self, kb_id: str, document_id: str) -> DocumentDTO:
        """
        Trigger dense vector indexing via FastAPI endpoint.
        Server-side RBAC enforces ADMIN privileges.
        """
        resp = self._http.post(f"/knowledge-bases/{kb_id}/documents/{document_id}/index")
        if resp.status_code == 403:
            raise ValueError("Students are not permitted to trigger vector indexing.")
        if resp.status_code not in (200, 202):
            detail = resp.json().get("detail", "Failed to trigger vector indexing.")
            raise ValueError(detail)

        item = resp.json()
        return DocumentDTO(
            id=str(item["id"]),
            kb_id=str(item["knowledge_base_id"]),
            filename=item["original_filename"],
            file_type=item["file_type"],
            file_size_bytes=item.get("file_size_bytes", 0),
            status=item.get("status", "COMPLETED"),
            indexing_status=item.get("indexing_status", "PROCESSING"),
            error_message=item.get("error_message"),
            indexing_error=item.get("indexing_error"),
            chunk_count=item.get("chunk_count", 0),
            created_at=item.get("created_at", "")[:16].replace("T", " "),
            indexed_at=item.get("indexed_at")[:16].replace("T", " ")
            if item.get("indexed_at")
            else None,
        )

    def delete_document(self, kb_id: str, document_id: str) -> None:
        """
        Delete a document via real FastAPI endpoint.
        Server-side RBAC enforces ADMIN privileges.
        """
        resp = self._http.delete(f"/knowledge-bases/{kb_id}/documents/{document_id}")
        if resp.status_code == 403:
            raise ValueError("Students are not permitted to delete documents.")
        if resp.status_code != 200:
            detail = resp.json().get("detail", "Failed to delete document.")
            raise ValueError(detail)

    # --------------------------------------------------------------------------
    # Conversational RAG Query Boundary
    # --------------------------------------------------------------------------

    def send_chat_message(self, kb_id: str, question: str) -> ChatMessageDTO:
        """
        Submit question to conversational query endpoint.
        Both ADMIN and authorized STUDENT users can query.
        """
        if not question.strip():
            raise ValueError("Question cannot be empty.")

        try:
            kb_uuid = uuid.UUID(kb_id)
        except ValueError:
            raise ValueError("Invalid knowledge base ID format.") from None

        resp = self._http.post(
            "/chat/query",
            json={"knowledge_base_id": str(kb_uuid), "question": question.strip()},
        )
        if resp.status_code == 404:
            raise ValueError("Knowledge base not found or unauthorized.")
        if resp.status_code != 200:
            detail = resp.json().get("detail", "Query failed.")
            raise ValueError(detail)

        data = resp.json()
        citations = [
            CitationDTO(
                document_name=c["document_name"],
                page_number=c.get("page_number"),
                chunk_id=c["chunk_id"],
                relevance_score=c["relevance_score"],
                snippet=c["snippet"],
            )
            for c in data.get("citations", [])
        ]

        return ChatMessageDTO(
            id=f"msg-{uuid.uuid4().hex[:8]}",
            role="assistant",
            content=data["answer"],
            citations=citations,
            created_at=datetime.now().strftime("%H:%M"),
        )

    # --------------------------------------------------------------------------
    # Vector Retrieval Inspection Boundary (Step 7)
    # --------------------------------------------------------------------------

    def retrieve_chunks(
        self,
        kb_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[RetrievalResultDTO]:
        """
        Execute vector retrieval search for an authorized knowledge base.
        Returns ranked evidence chunks strictly as retrieved search results.
        """
        if not query.strip():
            raise ValueError("Query string cannot be empty.")

        try:
            kb_uuid = uuid.UUID(kb_id)
        except ValueError:
            raise ValueError("Invalid knowledge base ID format.") from None

        resp = self._http.post(
            f"/knowledge-bases/{kb_uuid}/retrieve",
            json={"query": query.strip(), "top_k": top_k},
        )
        if resp.status_code == 404:
            raise ValueError("Knowledge base not found or unauthorized.")
        if resp.status_code == 422:
            detail = resp.json().get("detail", "Invalid query parameters.")
            raise ValueError(str(detail))
        if resp.status_code != 200:
            detail = resp.json().get("detail", "Vector retrieval failed.")
            raise ValueError(str(detail))

        data = resp.json()
        return [
            RetrievalResultDTO(
                chunk_id=str(item["chunk_id"]),
                document_id=str(item["document_id"]),
                knowledge_base_id=str(item["knowledge_base_id"]),
                document_title=item["document_title"],
                chunk_index=item["chunk_index"],
                text=item["text"],
                page_number=item.get("page_number"),
                section_title=item.get("section_title"),
                cosine_distance=item["cosine_distance"],
                similarity=item["similarity"],
            )
            for item in data.get("results", [])
        ]

    # --------------------------------------------------------------------------
    # Lexical Retrieval Inspection Boundary (Step 8)
    # --------------------------------------------------------------------------

    def retrieve_lexical_chunks(
        self,
        kb_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[LexicalRetrievalResultDTO]:
        """
        Execute PostgreSQL full-text lexical search for an authorized knowledge base.
        Returns ranked evidence chunks strictly as lexical search results.
        """
        if not query.strip():
            raise ValueError("Query string cannot be empty.")

        try:
            kb_uuid = uuid.UUID(kb_id)
        except ValueError:
            raise ValueError("Invalid knowledge base ID format.") from None

        resp = self._http.post(
            f"/knowledge-bases/{kb_uuid}/lexical-retrieve",
            json={"query": query.strip(), "top_k": top_k},
        )
        if resp.status_code == 404:
            raise ValueError("Knowledge base not found or unauthorized.")
        if resp.status_code == 422:
            detail = resp.json().get("detail", "Invalid query parameters.")
            raise ValueError(str(detail))
        if resp.status_code != 200:
            detail = resp.json().get("detail", "Lexical retrieval failed.")
            raise ValueError(str(detail))

        data = resp.json()
        return [
            LexicalRetrievalResultDTO(
                chunk_id=str(item["chunk_id"]),
                document_id=str(item["document_id"]),
                knowledge_base_id=str(item["knowledge_base_id"]),
                document_title=item["document_title"],
                chunk_index=item["chunk_index"],
                text=item["text"],
                page_number=item.get("page_number"),
                section_title=item.get("section_title"),
                lexical_score=item["lexical_score"],
            )
            for item in data.get("results", [])
        ]

    # --------------------------------------------------------------------------
    # Hybrid Retrieval Inspection Boundary (Step 9)
    # --------------------------------------------------------------------------

    def retrieve_hybrid_chunks(
        self,
        kb_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[HybridRetrievalResultDTO]:
        """
        Execute hybrid retrieval (vector + lexical fused with RRF) for an authorized knowledge base.
        Returns ranked candidate chunks strictly as hybrid retrieval inspection results.
        """
        if not query.strip():
            raise ValueError("Query string cannot be empty.")

        try:
            kb_uuid = uuid.UUID(kb_id)
        except ValueError:
            raise ValueError("Invalid knowledge base ID format.") from None

        resp = self._http.post(
            f"/knowledge-bases/{kb_uuid}/hybrid-retrieve",
            json={"query": query.strip(), "top_k": top_k},
        )
        if resp.status_code == 404:
            raise ValueError("Knowledge base not found or unauthorized.")
        if resp.status_code == 422:
            detail = resp.json().get("detail", "Invalid query parameters.")
            raise ValueError(str(detail))
        if resp.status_code == 503:
            detail = resp.json().get("detail", "Embedding provider unavailable.")
            raise ValueError(str(detail))
        if resp.status_code != 200:
            detail = resp.json().get("detail", "Hybrid retrieval failed.")
            raise ValueError(str(detail))

        data = resp.json()
        return [
            HybridRetrievalResultDTO(
                chunk_id=str(item["chunk_id"]),
                document_id=str(item["document_id"]),
                knowledge_base_id=str(item["knowledge_base_id"]),
                document_title=item["document_title"],
                chunk_index=item["chunk_index"],
                text=item["text"],
                page_number=item.get("page_number"),
                section_title=item.get("section_title"),
                rrf_score=item["rrf_score"],
                vector_rank=item.get("vector_rank"),
                lexical_rank=item.get("lexical_rank"),
                vector_contribution=item.get("vector_contribution", 0.0),
                lexical_contribution=item.get("lexical_contribution", 0.0),
                cosine_distance=item.get("cosine_distance"),
                similarity=item.get("similarity"),
                lexical_score=item.get("lexical_score"),
            )
            for item in data.get("results", [])
        ]

    def rerank_chunks(
        self,
        kb_id: str,
        query: str,
        candidate_limit: int = 20,
        top_k: int = 5,
    ) -> list[RerankResultDTO]:
        """
        Execute CrossEncoder reranking on hybrid candidate chunks for an authorized knowledge base.
        Returns reranked candidate chunks strictly for inspection/verification.
        """
        if not query.strip():
            raise ValueError("Query string cannot be empty.")

        try:
            kb_uuid = uuid.UUID(kb_id)
        except ValueError:
            raise ValueError("Invalid knowledge base ID format.") from None

        resp = self._http.post(
            f"/knowledge-bases/{kb_uuid}/rerank",
            json={
                "query": query.strip(),
                "candidate_limit": candidate_limit,
                "top_k": top_k,
            },
        )
        if resp.status_code == 404:
            raise ValueError("Knowledge base not found or unauthorized.")
        if resp.status_code == 422:
            detail = resp.json().get("detail", "Invalid query parameters.")
            raise ValueError(str(detail))
        if resp.status_code == 503:
            detail = resp.json().get("detail", "Inference provider unavailable.")
            raise ValueError(str(detail))
        if resp.status_code != 200:
            detail = resp.json().get("detail", "Reranking operation failed.")
            raise ValueError(str(detail))

        data = resp.json()
        return [
            RerankResultDTO(
                chunk_id=str(item["chunk_id"]),
                document_id=str(item["document_id"]),
                knowledge_base_id=str(item["knowledge_base_id"]),
                document_title=item["document_title"],
                chunk_index=item["chunk_index"],
                text=item["text"],
                page_number=item.get("page_number"),
                section_title=item.get("section_title"),
                rrf_score=item["rrf_score"],
                vector_rank=item.get("vector_rank"),
                lexical_rank=item.get("lexical_rank"),
                vector_contribution=item.get("vector_contribution", 0.0),
                lexical_contribution=item.get("lexical_contribution", 0.0),
                cosine_distance=item.get("cosine_distance"),
                similarity=item.get("similarity"),
                lexical_score=item.get("lexical_score"),
                reranker_score=item["reranker_score"],
                reranker_rank=item["reranker_rank"],
            )
            for item in data.get("results", [])
        ]

    def process_query(self, query: str) -> QueryProcessingResultDTO:
        """
        Send raw query to /query/process for deterministic normalization.
        """
        resp = self._http.post("/query/process", json={"query": query})
        if resp.status_code == 401:
            raise ValueError("Authentication required to process queries.")
        if resp.status_code == 422:
            detail = resp.json().get("detail", "Invalid query.")
            raise ValueError(str(detail))
        if resp.status_code != 200:
            raise ValueError("Query processing failed.")

        item = resp.json()
        return QueryProcessingResultDTO(
            original_query=item["original_query"],
            processed_query=item["processed_query"],
            character_count=item["character_count"],
            token_estimate=item["token_estimate"],
            has_quotes=item.get("has_quotes", False),
            has_technical_tokens=item.get("has_technical_tokens", False),
            metadata=item.get("metadata", {}),
        )


# Global default client instance for the frontend presentation layer
api_client = FrontendAPIClient()
