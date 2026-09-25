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
from typing import Any

from fastapi.testclient import TestClient

from backend.app.core.security import SESSION_COOKIE_NAME
from backend.app.main import app
from frontend.client.error_handler import normalize_error
from frontend.client.models import (
    ActivityEventDTO,
    AdminUserDTO,
    ChatMessageDTO,
    CitationDTO,
    ComponentHealthDTO,
    CourseDocumentPreviewDTO,
    CourseSummaryDTO,
    DocumentDTO,
    HybridRetrievalResultDTO,
    IndexingJobDTO,
    KnowledgeBaseDTO,
    LexicalRetrievalResultDTO,
    QueryProcessingResultDTO,
    RerankResultDTO,
    RetrievalResultDTO,
    SystemHealthDTO,
    UserDTO,
)


class FrontendAPIClient:
    """API Client mediating presentation requests to the backend service boundary."""

    def __init__(self, base_url: str = "http://testserver/api/v1") -> None:
        self.base_url = base_url
        self._current_user: UserDTO | None = None
        self._session_token: str | None = None
        # TestClient handles real FastAPI middleware, cookies, dependencies, and DB sessions
        self._http = TestClient(app, base_url=base_url)

        # In-memory document status storage for Step 4 presentation
        self._documents: dict[str, list[DocumentDTO]] = {}

    # --------------------------------------------------------------------------
    # Authentication & Session Boundary
    # --------------------------------------------------------------------------

    def set_session_token(self, token: str | None) -> None:
        """Explicitly set or clear session token on the internal HTTP client."""
        self._session_token = token
        if token:
            self._http.cookies.set(SESSION_COOKIE_NAME, token)
            self._http.headers["Authorization"] = f"Bearer {token}"
        else:
            self.clear_session()

    def get_session_token(self) -> str | None:
        """Retrieve active raw session token from cookies or explicit record."""
        return self._http.cookies.get(SESSION_COOKIE_NAME) or self._session_token

    def clear_session(self) -> None:
        """Clear all authenticated credentials and identity from this client instance."""
        self._current_user = None
        self._session_token = None
        self._http.cookies.clear()
        self._http.headers.pop("Authorization", None)

    def _handle_auth_failure(self, status_code: int) -> None:
        """If response is 401 Unauthorized or 403 Forbidden, automatically invalidate the local session."""
        if status_code in (401, 403):
            self.clear_session()
            _set_persistent_token(None)

    def login(self, email: str, password: str, required_role: str | None = None) -> UserDTO:
        """Authenticate user against Argon2id hash and establish PostgreSQL session."""
        if not email or not password:
            raise ValueError("Email and password must not be empty.")

        clean_role = (required_role or "").strip().upper()
        if clean_role == "STUDENT":
            endpoint = "/auth/login/student"
        elif clean_role == "ADMIN":
            endpoint = "/auth/login/admin"
        else:
            endpoint = "/auth/login"

        resp = self._http.post(
            endpoint,
            json={"email": email.strip(), "password": password},
        )
        if resp.status_code != 200:
            self._handle_auth_failure(resp.status_code)
            try:
                err_data = resp.json()
                detail = err_data.get("detail", err_data)
            except Exception:
                detail = resp.text
            raise ValueError(normalize_error(detail, context="auth"))

        data = resp.json()
        user_data = data["user"]
        self._current_user = UserDTO(
            id=str(user_data["id"]),
            email=user_data["email"],
            full_name=user_data["full_name"],
            role=user_data["role"],
            admin_role=user_data.get("admin_role"),
            permissions=user_data.get("permissions", []),
        )
        raw_token = self._http.cookies.get(SESSION_COOKIE_NAME)
        if raw_token:
            self._session_token = raw_token
            self._http.headers["Authorization"] = f"Bearer {raw_token}"
        return self._current_user

    def student_login(self, email: str, password: str) -> UserDTO:
        """Authenticate student credentials strictly against Student Portal."""
        return self.login(email=email, password=password, required_role="STUDENT")

    def admin_login(self, email: str, password: str) -> UserDTO:
        """Authenticate administrator credentials strictly against Administrator Portal."""
        return self.login(email=email, password=password, required_role="ADMIN")

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
            try:
                err_data = resp.json()
                detail = err_data.get("detail", err_data)
            except Exception:
                detail = resp.text
            raise ValueError(normalize_error(detail, context="auth"))

        # Automatically authenticate the new student strictly into the student portal
        try:
            return self.student_login(email=email, password=password)
        except Exception as exc:
            raise ValueError(
                f"Account created successfully, but automatic login failed: {exc}"
            ) from exc

    def logout(self) -> None:
        """Terminate active session in PostgreSQL and clear cookie."""
        try:
            self._http.post("/auth/logout")
        finally:
            self.clear_session()

    def get_current_user(self) -> UserDTO | None:
        """Retrieve currently authenticated user identity from backend session.

        The backend PostgreSQL session is authoritative: if the session is expired,
        invalidated, or absent, the client state is immediately cleared and None is returned.
        """
        token = self.get_session_token()
        if not token:
            self._current_user = None
            return None

        resp = self._http.get("/auth/me")
        if resp.status_code == 200:
            user_data = resp.json()
            self._current_user = UserDTO(
                id=str(user_data["id"]),
                email=user_data["email"],
                full_name=user_data["full_name"],
                role=user_data["role"],
                admin_role=user_data.get("admin_role"),
                permissions=user_data.get("permissions", []),
            )
            return self._current_user
        else:
            self.clear_session()
            return None

    # --------------------------------------------------------------------------
    # Knowledge Bases Boundary
    # --------------------------------------------------------------------------

    def get_knowledge_bases(self) -> list[KnowledgeBaseDTO]:
        """
        Fetch knowledge bases accessible to the current user.

        Non-success responses are surfaced to the UI instead of being converted
        into an empty list. An empty list has semantic meaning (the user truly
        has no authorized courses) and must never hide a 401/403/5xx failure.
        """
        resp = self._http.get("/knowledge-bases")
        if resp.status_code != 200:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise ValueError(normalize_error(detail, context="course"))

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

    def get_chat_scope_courses(self) -> list[KnowledgeBaseDTO]:
        """Fetch courses the current user may actually use in chat."""
        resp = self._http.get("/knowledge-bases/chat-scopes")
        if resp.status_code != 200:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise ValueError(normalize_error(detail, context="chat"))

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

    def get_document_scope_courses(self) -> list[KnowledgeBaseDTO]:
        """Fetch courses available to document management for this admin."""
        resp = self._http.get("/knowledge-bases/document-scopes")
        if resp.status_code != 200:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise ValueError(normalize_error(detail, context="document"))

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
            raise ValueError(normalize_error(403, context="admin"))
        if resp.status_code != 201:
            try:
                err_data = resp.json()
                detail = err_data.get("detail", err_data)
            except Exception:
                detail = resp.text
            raise ValueError(normalize_error(detail, context="admin"))

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

    def get_course_summaries(self) -> list[CourseSummaryDTO]:
        """
        Fetch aggregated course summaries with document metrics and previews.
        Single backend request to avoid N+1 queries.
        """
        resp = self._http.get("/knowledge-bases/summaries")
        if resp.status_code != 200:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise ValueError(normalize_error(detail, context="course"))
        items = resp.json()
        return [
            CourseSummaryDTO(
                id=str(item["id"]),
                name=item["name"],
                description=item.get("description", ""),
                created_at=item["created_at"][:10],
                total_documents=item.get("total_documents", 0),
                active_documents=item.get("active_documents", 0),
                inactive_documents=item.get("inactive_documents", 0),
                indexed_documents=item.get("indexed_documents", 0),
                indexing_documents=item.get("indexing_documents", 0),
                failed_documents=item.get("failed_documents", 0),
                document_previews=[
                    CourseDocumentPreviewDTO(
                        id=str(p["id"]),
                        filename=p["filename"],
                        file_type=p["file_type"],
                        status=p["status"],
                        indexing_status=p.get("indexing_status", "PENDING"),
                        is_active=p["is_active"],
                    )
                    for p in item.get("document_previews", [])
                ],
            )
            for item in items
        ]

    # --------------------------------------------------------------------------
    # Documents Boundary
    # --------------------------------------------------------------------------

    def get_documents(self, kb_id: str) -> list[DocumentDTO]:
        """Fetch real documents for an authorized knowledge base from FastAPI."""
        resp = self._http.get(f"/knowledge-bases/{kb_id}/documents")
        if resp.status_code != 200:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise ValueError(normalize_error(detail, context="document"))

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
                is_active=item.get("is_active", True),
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
            raise ValueError(normalize_error(403, context="admin"))
        if resp.status_code not in (200, 201):
            try:
                err_data = resp.json()
                detail = err_data.get("detail", err_data)
            except Exception:
                detail = resp.text
            raise ValueError(normalize_error(detail, context="document"))

        item = resp.json()
        return DocumentDTO(
            id=str(item["id"]),
            kb_id=str(item["knowledge_base_id"]),
            filename=item["original_filename"],
            file_type=item["file_type"],
            file_size_bytes=item.get("file_size_bytes", size),
            status=item.get("status", "COMPLETED"),
            indexing_status=item.get("indexing_status", "PENDING"),
            is_active=item.get("is_active", True),
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
            is_active=item.get("is_active", True),
            error_message=item.get("error_message"),
            indexing_error=item.get("indexing_error"),
            chunk_count=item.get("chunk_count", 0),
            created_at=item.get("created_at", "")[:16].replace("T", " "),
            indexed_at=item.get("indexed_at")[:16].replace("T", " ")
            if item.get("indexed_at")
            else None,
        )

    def get_document_index_status(self, kb_id: str, document_id: str) -> IndexingJobDTO:
        """
        Fetch persistent vector indexing job status and chunk progress.
        """
        resp = self._http.get(f"/knowledge-bases/{kb_id}/documents/{document_id}/index-status")
        if resp.status_code != 200:
            raise ValueError(normalize_error(resp.json(), context="document"))

        item = resp.json()
        return IndexingJobDTO(
            job_id=str(item["job_id"]) if item.get("job_id") else None,
            document_id=str(item["document_id"]),
            knowledge_base_id=str(item["knowledge_base_id"]),
            status=item["status"],
            stage=item["stage"],
            total_chunks=item.get("total_chunks", 0),
            processed_chunks=item.get("processed_chunks", 0),
            embedded_chunks=item.get("embedded_chunks", 0),
            indexed_chunks=item.get("indexed_chunks", 0),
            progress_percent=item.get("progress_percent", 0.0),
            document_name=item.get("document_name"),
            course_name=item.get("course_name"),
            error_message=item.get("error_message"),
            attempt_number=item.get("attempt_number", 1),
            started_at=str(item["started_at"]) if item.get("started_at") else None,
            completed_at=str(item["completed_at"]) if item.get("completed_at") else None,
        )

    def retry_indexing(self, kb_id: str, document_id: str) -> IndexingJobDTO:
        """
        Retry indexing for a failed or stuck document.
        """
        resp = self._http.post(f"/knowledge-bases/{kb_id}/documents/{document_id}/retry-indexing")
        if resp.status_code == 403:
            raise ValueError("You do not have permission to retry indexing.")
        if resp.status_code not in (200, 202):
            detail = resp.json().get("detail", "Failed to retry indexing.")
            raise ValueError(detail)

        item = resp.json()
        doc_id = str(item.get("document_id") or item.get("id"))
        return IndexingJobDTO(
            job_id=str(item["job_id"]) if item.get("job_id") else None,
            document_id=doc_id,
            knowledge_base_id=str(item.get("knowledge_base_id", kb_id)),
            status=item.get("indexing_status") or item.get("status", "PROCESSING"),
            stage=item.get("stage", "PREPARING"),
            total_chunks=item.get("chunk_count") or item.get("total_chunks", 0),
            processed_chunks=item.get("processed_chunks", 0),
            embedded_chunks=item.get("embedded_chunks", 0),
            indexed_chunks=item.get("indexed_chunks", 0),
            progress_percent=item.get("progress_percent", 0.0),
            document_name=item.get("original_filename") or item.get("document_name"),
            course_name=item.get("course_name"),
            error_message=item.get("indexing_error") or item.get("error_message"),
            attempt_number=item.get("attempt_number", 1),
            started_at=str(item["started_at"]) if item.get("started_at") else None,
            completed_at=str(item["completed_at"]) if item.get("completed_at") else None,
        )

    def get_indexing_jobs(self) -> list[IndexingJobDTO]:
        """
        List all persistent indexing jobs across authorized courses.
        """
        resp = self._http.get("/knowledge-bases/indexing-jobs")
        if resp.status_code != 200:
            raise ValueError(normalize_error(resp.json(), context="document"))

        items = resp.json()
        return [
            IndexingJobDTO(
                job_id=str(item["job_id"]) if item.get("job_id") else None,
                document_id=str(item["document_id"]),
                knowledge_base_id=str(item["knowledge_base_id"]),
                status=item["status"],
                stage=item["stage"],
                total_chunks=item.get("total_chunks", 0),
                processed_chunks=item.get("processed_chunks", 0),
                embedded_chunks=item.get("embedded_chunks", 0),
                indexed_chunks=item.get("indexed_chunks", 0),
                progress_percent=item.get("progress_percent", 0.0),
                document_name=item.get("document_name"),
                course_name=item.get("course_name"),
                error_message=item.get("error_message"),
                attempt_number=item.get("attempt_number", 1),
                started_at=str(item["started_at"]) if item.get("started_at") else None,
                completed_at=str(item["completed_at"]) if item.get("completed_at") else None,
            )
            for item in items
        ]

    def get_system_health(self) -> SystemHealthDTO:
        """
        Fetch real system health for core backend components.
        """
        resp = self._http.get("/knowledge-bases/system/health")
        if resp.status_code != 200:
            raise ValueError(normalize_error(resp.json(), context="system"))

        data = resp.json()
        comps = [
            ComponentHealthDTO(
                name=c["name"],
                status=c["status"],
                message=c.get("message", ""),
            )
            for c in data.get("components", [])
        ]
        return SystemHealthDTO(
            status=data.get("status", "healthy"),
            components=comps,
            checked_at=str(data.get("checked_at", "")),
        )

    def get_activity_log(self) -> list[ActivityEventDTO]:
        """
        Fetch administrative activity audit timeline.
        """
        resp = self._http.get("/knowledge-bases/system/activity")
        if resp.status_code != 200:
            raise ValueError(normalize_error(resp.json(), context="system"))

        items = resp.json()
        return [
            ActivityEventDTO(
                id=item["id"],
                timestamp=str(item["timestamp"]),
                actor_name=item["actor_name"],
                actor_email=item["actor_email"],
                action=item["action"],
                resource_type=item["resource_type"],
                resource_name=item["resource_name"],
                status=item["status"],
                details=item.get("details", ""),
            )
            for item in items
        ]

    def activate_document(self, kb_id: str, document_id: str) -> DocumentDTO:
        """
        Activate an ingested and indexed document for retrieval.
        Restricted strictly to administering ADMIN.
        """
        resp = self._http.patch(f"/knowledge-bases/{kb_id}/documents/{document_id}/activate")
        if resp.status_code == 403:
            raise ValueError(normalize_error(403, context="admin"))
        if resp.status_code != 200:
            raise ValueError(normalize_error(resp.json(), context="document"))

        item = resp.json()
        return DocumentDTO(
            id=str(item["id"]),
            kb_id=str(item["knowledge_base_id"]),
            filename=item["original_filename"],
            file_type=item["file_type"],
            file_size_bytes=item.get("file_size_bytes", 0),
            status=item.get("status", "COMPLETED"),
            indexing_status=item.get("indexing_status", "PENDING"),
            is_active=item.get("is_active", True),
            error_message=item.get("error_message"),
            indexing_error=item.get("indexing_error"),
            chunk_count=item.get("chunk_count", 0),
            created_at=item.get("created_at", "")[:16].replace("T", " "),
            indexed_at=item.get("indexed_at")[:16].replace("T", " ")
            if item.get("indexed_at")
            else None,
        )

    def deactivate_document(self, kb_id: str, document_id: str) -> DocumentDTO:
        """
        Deactivate a document so it is excluded from retrieval while preserving data.
        Restricted strictly to administering ADMIN.
        """
        resp = self._http.patch(f"/knowledge-bases/{kb_id}/documents/{document_id}/deactivate")
        if resp.status_code == 403:
            raise ValueError(normalize_error(403, context="admin"))
        if resp.status_code != 200:
            raise ValueError(normalize_error(resp.json(), context="document"))

        item = resp.json()
        return DocumentDTO(
            id=str(item["id"]),
            kb_id=str(item["knowledge_base_id"]),
            filename=item["original_filename"],
            file_type=item["file_type"],
            file_size_bytes=item.get("file_size_bytes", 0),
            status=item.get("status", "COMPLETED"),
            indexing_status=item.get("indexing_status", "PENDING"),
            is_active=item.get("is_active", False),
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
            raise ValueError(normalize_error(detail, context="document"))

    # --------------------------------------------------------------------------
    # Conversational RAG Query Boundary
    # --------------------------------------------------------------------------

    def send_chat_message(
        self,
        kb_id: str | None,
        question: str,
        document_id: str | None = None,
        scope: str | None = None,
    ) -> ChatMessageDTO:
        """
        Submit question to conversational query endpoint.
        Supports scopes: ALL_COURSES, COURSE, DOCUMENT.
        """
        if not question.strip():
            raise ValueError("Question cannot be empty.")

        payload: dict[str, Any] = {"question": question.strip()}
        if scope:
            payload["scope"] = scope
        if kb_id:
            try:
                kb_uuid = uuid.UUID(kb_id)
                payload["knowledge_base_id"] = str(kb_uuid)
            except ValueError:
                raise ValueError("Invalid knowledge base ID format.") from None
        if document_id:
            try:
                doc_uuid = uuid.UUID(document_id)
                payload["document_id"] = str(doc_uuid)
            except ValueError:
                raise ValueError("Invalid document ID format.") from None

        resp = self._http.post(
            "/chat/query",
            json=payload,
        )
        if resp.status_code == 404:
            raise ValueError("Knowledge base not found or unauthorized.")
        if resp.status_code != 200:
            detail = resp.json().get("detail", "Query failed.")
            raise ValueError(normalize_error(detail, context="chat"))

        data = resp.json()
        citations = [
            CitationDTO(
                document_name=c["document_name"],
                page_number=c.get("page_number"),
                chunk_id=c["chunk_id"],
                relevance_score=c["relevance_score"],
                snippet=c["snippet"],
                source_id=c.get("source_id"),
                document_id=str(c["document_id"]) if c.get("document_id") else None,
                section_title=c.get("section_title"),
                knowledge_base_id=str(c["knowledge_base_id"])
                if c.get("knowledge_base_id")
                else None,
            )
            for c in data.get("citations", [])
        ]

        grounding_data = data.get("grounding") or {}
        latency_data = data.get("latency") or {}

        return ChatMessageDTO(
            id=f"msg-{uuid.uuid4().hex[:8]}",
            role="assistant",
            content=data["answer"],
            citations=citations,
            created_at=datetime.now().strftime("%H:%M"),
            is_grounded=grounding_data.get("is_grounded"),
            grounding_status=grounding_data.get("status"),
            total_pipeline_ms=latency_data.get("total_pipeline_ms"),
            model=data.get("model"),
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

    # --------------------------------------------------------------------------
    # Administrator Management Boundary
    # --------------------------------------------------------------------------

    def create_admin(
        self,
        email: str,
        password: str,
        full_name: str,
        admin_role: str = "FACULTY_ADMIN",
        permissions: list[str] | None = None,
        assigned_course_ids: list[str] | None = None,
    ) -> AdminUserDTO:
        """
        Create a new administrator account (MAIN_ADMIN or FACULTY_ADMIN).
        """
        if not email or not password or not full_name:
            raise ValueError("All fields are required.")

        payload: dict[str, Any] = {
            "email": email.strip(),
            "password": password,
            "full_name": full_name.strip(),
            "admin_role": admin_role,
            "permissions": permissions or [],
        }
        if assigned_course_ids is not None:
            payload["assigned_course_ids"] = assigned_course_ids

        resp = self._http.post(
            "/auth/admin",
            json=payload,
        )
        if resp.status_code != 201:
            raise ValueError(normalize_error(resp.json(), context="admin"))

        data = resp.json()
        return AdminUserDTO(
            id=str(data["id"]),
            email=data["email"],
            full_name=data["full_name"],
            role=data["role"],
            admin_role=data.get("admin_role", "FACULTY_ADMIN"),
            permissions=data.get("permissions", []),
            assigned_courses=data.get("assigned_courses", []),
            is_active=data.get("is_active", True),
            created_at=data.get("created_at", "")[:10],
        )

    def get_admins(self) -> list[AdminUserDTO]:
        """
        List all administrator accounts. Restricted strictly to authenticated ADMINs.
        """
        resp = self._http.get("/auth/admins")
        if resp.status_code != 200:
            raise ValueError(normalize_error(resp.json(), context="admin"))

        items = resp.json()
        return [
            AdminUserDTO(
                id=str(item["id"]),
                email=item["email"],
                full_name=item["full_name"],
                role=item["role"],
                admin_role=item.get("admin_role", "MAIN_ADMIN"),
                permissions=item.get("permissions", []),
                assigned_courses=item.get("assigned_courses", []),
                is_active=item.get("is_active", True),
                created_at=item.get("created_at", "")[:10],
            )
            for item in items
        ]

    def update_admin_permissions(
        self,
        admin_id: str,
        permissions: list[str],
        assigned_course_ids: list[str] | None = None,
    ) -> AdminUserDTO:
        """
        Update permissions and course assignments for a faculty administrator.
        """
        payload: dict[str, Any] = {"permissions": permissions}
        if assigned_course_ids is not None:
            payload["assigned_course_ids"] = assigned_course_ids

        resp = self._http.patch(
            f"/auth/admins/{admin_id}/permissions",
            json=payload,
        )
        if resp.status_code != 200:
            raise ValueError(normalize_error(resp.json(), context="admin"))

        data = resp.json()
        return AdminUserDTO(
            id=str(data["id"]),
            email=data["email"],
            full_name=data["full_name"],
            role=data["role"],
            admin_role=data.get("admin_role", "FACULTY_ADMIN"),
            permissions=data.get("permissions", []),
            assigned_courses=data.get("assigned_courses", []),
            is_active=data.get("is_active", True),
            created_at=data.get("created_at", "")[:10],
        )

    def deactivate_admin(self, admin_id: str) -> AdminUserDTO:
        """
        Deactivate an administrator account.
        """
        resp = self._http.patch(f"/auth/admins/{admin_id}/deactivate")
        if resp.status_code != 200:
            raise ValueError(normalize_error(resp.json(), context="admin"))

        data = resp.json()
        return AdminUserDTO(
            id=str(data["id"]),
            email=data["email"],
            full_name=data["full_name"],
            role=data["role"],
            admin_role=data.get("admin_role", "FACULTY_ADMIN"),
            permissions=data.get("permissions", []),
            is_active=data.get("is_active", False),
            created_at=data.get("created_at", "")[:10],
        )

    def activate_admin(self, admin_id: str) -> AdminUserDTO:
        """
        Reactivate an administrator account.
        """
        resp = self._http.patch(f"/auth/admins/{admin_id}/activate")
        if resp.status_code != 200:
            raise ValueError(normalize_error(resp.json(), context="admin"))

        data = resp.json()
        return AdminUserDTO(
            id=str(data["id"]),
            email=data["email"],
            full_name=data["full_name"],
            role=data["role"],
            admin_role=data.get("admin_role", "FACULTY_ADMIN"),
            permissions=data.get("permissions", []),
            is_active=data.get("is_active", True),
            created_at=data.get("created_at", "")[:10],
        )

    def delete_admin(self, admin_id: str) -> None:
        """
        Delete an administrator account.
        """
        resp = self._http.delete(f"/auth/admins/{admin_id}")
        if resp.status_code != 200:
            raise ValueError(normalize_error(resp.json(), context="admin"))


_session_clients: dict[str, FrontendAPIClient] = {}


def _get_browser_session_id() -> str | None:
    """Extract browser session identifier from active NiceGUI / Starlette request context."""
    # 1. From NiceGUI storage request contextvar
    try:
        from nicegui.storage import request_contextvar

        req = request_contextvar.get()
        if req and hasattr(req, "session") and "id" in req.session:
            return str(req.session["id"])
    except Exception:
        pass

    # 2. From NiceGUI context.client.request
    try:
        from nicegui import context

        client = context.client
        if client and hasattr(client, "request") and client.request:
            req = client.request
            if hasattr(req, "session") and "id" in req.session:
                return str(req.session["id"])
    except Exception:
        pass

    return None


def _get_persistent_token() -> str | None:
    """Retrieve session token from server-side app.storage.user if in UI context."""
    try:
        from nicegui import app

        if hasattr(app, "storage") and hasattr(app.storage, "user"):
            return app.storage.user.get("auth_session_token")
    except Exception:
        pass
    return None


def _set_persistent_token(token: str | None) -> None:
    """Save or remove session token in server-side app.storage.user if in UI context."""
    try:
        from nicegui import app

        if hasattr(app, "storage") and hasattr(app.storage, "user"):
            if token:
                app.storage.user["auth_session_token"] = token
            else:
                app.storage.user.pop("auth_session_token", None)
    except Exception:
        pass


class _SessionAPIClientProxy:
    """Resolve one FrontendAPIClient per browser session.

    The FastAPI session is stored in PostgreSQL and authenticated via an HttpOnly
    cookie or Authorization header. In NiceGUI, each browser user is identified by
    a persistent session ID (via Starlette SessionMiddleware).

    This proxy ensures:
    - Each browser client has an isolated FrontendAPIClient with its own cookie jar.
    - User A never shares or inherits User B's authentication or cookies.
    - Authentication survives page navigation (e.g. /login -> /dashboard).
    - When outside a NiceGUI client context (unit tests / CLI code), a private fallback client is used.
    """

    def __init__(self) -> None:
        self._fallback_client = FrontendAPIClient()

    def _get_client(self) -> FrontendAPIClient:
        session_id = _get_browser_session_id()
        if not session_id:
            # No active NiceGUI client context (e.g. direct unit tests).
            return self._fallback_client

        client = _session_clients.get(session_id)
        if client is None:
            client = FrontendAPIClient()
            saved_token = _get_persistent_token()
            if saved_token:
                client.set_session_token(saved_token)
            _session_clients[session_id] = client

        return client

    def login(self, email: str, password: str, required_role: str | None = None) -> UserDTO:
        client = self._get_client()
        user = client.login(email, password, required_role=required_role)
        token = client.get_session_token()
        if token:
            _set_persistent_token(token)
        return user

    def student_login(self, email: str, password: str) -> UserDTO:
        return self.login(email, password, required_role="STUDENT")

    def admin_login(self, email: str, password: str) -> UserDTO:
        return self.login(email, password, required_role="ADMIN")

    def register(self, email: str, password: str, full_name: str) -> UserDTO:
        client = self._get_client()
        user = client.register(email, password, full_name)
        token = client.get_session_token()
        if token:
            _set_persistent_token(token)
        return user

    def logout(self) -> None:
        session_id = _get_browser_session_id()
        client = self._get_client()
        try:
            client.logout()
        finally:
            _set_persistent_token(None)
            if session_id and session_id in _session_clients:
                _session_clients.pop(session_id, None)

    def get_current_user(self) -> UserDTO | None:
        client = self._get_client()
        user = client.get_current_user()
        if user is None:
            _set_persistent_token(None)
        return user

    def clear_session(self) -> None:
        session_id = _get_browser_session_id()
        client = self._get_client()
        client.clear_session()
        _set_persistent_token(None)
        if session_id and session_id in _session_clients:
            _session_clients.pop(session_id, None)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._get_client(), name)


# Presentation-layer API boundary. The proxy keeps authentication/session state
# isolated per NiceGUI browser client while retaining the existing call sites.
api_client = _SessionAPIClientProxy()
