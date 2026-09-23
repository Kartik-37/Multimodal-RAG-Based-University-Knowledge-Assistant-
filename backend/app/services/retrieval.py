"""
Vector Retrieval Service.

Implements exact pgvector cosine similarity search over vector-indexed document chunks
within an authorized knowledge base.

Key Design Decisions:
- Exact Cosine Search: Uses pgvector's `<=>` operator ordered in PostgreSQL.
- Server-side Filtering: Constrained strictly by `knowledge_base_id` and `embedding IS NOT NULL`.
- Deterministic Ties: Secondary order by `chunk_index ASC, id ASC`.
- Score Transparency: Exposes both raw `cosine_distance` and direct `similarity = 1.0 - cosine_distance`.
- Provider Independence: Reuses BaseEmbeddingProvider (OllamaEmbeddingProvider by default).
"""

import asyncio
import logging
import uuid

from sqlalchemy import and_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.document import Document, DocumentChunk, DocumentStatus, IndexingStatus
from backend.app.schemas.retrieval import RetrievalResponse, RetrievalResultItem
from backend.app.services.embedding.base import BaseEmbeddingProvider
from backend.app.services.embedding.exceptions import (
    EmbeddingDimensionError,
    EmbeddingError,
    EmbeddingProviderError,
)
from backend.app.services.embedding.service import get_embedding_service

logger = logging.getLogger(__name__)


class RetrievalError(Exception):
    """Base exception for retrieval errors."""

    pass


class RetrievalValidationError(RetrievalError):
    """Raised when query or retrieval parameters fail validation."""

    pass


class RetrievalProviderError(RetrievalError):
    """Raised when the embedding provider fails during query embedding."""

    pass


class VectorRetrievalService:
    """
    Service executing dense vector retrieval using PostgreSQL + pgvector.
    """

    def __init__(self, provider: BaseEmbeddingProvider | None = None) -> None:
        self._provider = provider or get_embedding_service().provider

    @property
    def provider(self) -> BaseEmbeddingProvider:
        return self._provider

    def validate_query(self, query: str) -> str:
        """
        Validate and normalize query input string.

        Raises:
            RetrievalValidationError: If query is empty, whitespace-only, or exceeds max length.
        """
        if not query or not query.strip():
            raise RetrievalValidationError("Query string cannot be empty or whitespace only.")

        normalized_query = query.strip()
        if len(normalized_query) > settings.RETRIEVAL_MAX_QUERY_LENGTH:
            raise RetrievalValidationError(
                f"Query length ({len(normalized_query)} chars) exceeds maximum permitted limit "
                f"of {settings.RETRIEVAL_MAX_QUERY_LENGTH} characters."
            )

        return normalized_query

    def validate_top_k(self, top_k: int) -> int:
        """
        Validate requested top_k bound.

        Raises:
            RetrievalValidationError: If top_k is outside permitted bounds.
        """
        if top_k < settings.RETRIEVAL_MIN_TOP_K:
            raise RetrievalValidationError(
                f"top_k must be at least {settings.RETRIEVAL_MIN_TOP_K}, got {top_k}."
            )
        if top_k > settings.RETRIEVAL_MAX_TOP_K:
            raise RetrievalValidationError(
                f"top_k cannot exceed {settings.RETRIEVAL_MAX_TOP_K}, got {top_k}."
            )
        return top_k

    async def retrieve(
        self,
        db: Session,
        kb_id: uuid.UUID | list[uuid.UUID],
        query: str,
        top_k: int = settings.RAG_TOP_K_RETRIEVAL,
        document_id: uuid.UUID | None = None,
    ) -> RetrievalResponse:
        """
        Execute vector retrieval for an authorized knowledge base or collection of knowledge bases.

        Args:
            db: Active SQLAlchemy database session.
            kb_id: Authorized knowledge base UUID or list of authorized UUIDs.
            query: Natural-language query string.
            top_k: Maximum number of top candidates to retrieve.
            document_id: Optional UUID of a specific document to scope retrieval.

        Returns:
            RetrievalResponse with ranked chunks and similarity scores.

        Raises:
            RetrievalValidationError: On invalid input.
            RetrievalProviderError: On embedding provider failure.
            RetrievalError: On database query failure.
        """
        clean_query = self.validate_query(query)
        bounded_top_k = self.validate_top_k(top_k)

        # Scoping resolution: Empty collection MUST return zero results immediately (never an unscoped query)
        if isinstance(kb_id, (list, tuple, set)):
            kb_ids_list = list(kb_id)
            if len(kb_ids_list) == 0:
                return RetrievalResponse(
                    query=clean_query,
                    knowledge_base_id=None,
                    total_results=0,
                    results=[],
                )
            kb_filter = DocumentChunk.knowledge_base_id.in_(kb_ids_list)
            response_kb_id = kb_ids_list[0] if len(kb_ids_list) == 1 else None
        else:
            kb_filter = DocumentChunk.knowledge_base_id == kb_id
            response_kb_id = kb_id

        # 1. Generate query embedding through the configured embedding provider
        try:
            query_vector = await self._provider.embed_query(clean_query)
        except (EmbeddingProviderError, EmbeddingDimensionError, EmbeddingError) as exc:
            logger.error("Embedding provider failed during query embedding: %s", exc)
            raise RetrievalProviderError(
                "Embedding generation failed. Verify that the embedding service is operational."
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error occurred while generating query embedding.")
            raise RetrievalProviderError(
                "Internal error during query embedding generation."
            ) from exc

        # 2. Strict dimension verification
        if len(query_vector) != self._provider.dimension:
            msg = (
                f"Generated query vector dimension ({len(query_vector)}) does not match "
                f"expected dimension ({self._provider.dimension})."
            )
            logger.error(msg)
            raise RetrievalProviderError(msg)

        # 3. Execute exact pgvector cosine distance search in PostgreSQL
        # The `<=>` operator calculates cosine distance: 1 - cosine_similarity
        distance_expr = DocumentChunk.embedding.cosine_distance(query_vector).label("distance")

        # Invariant: Only successfully ingested (COMPLETED) and indexed documents participate
        conditions = [
            kb_filter,
            Document.status == DocumentStatus.COMPLETED,
            Document.indexing_status == IndexingStatus.COMPLETED,
            DocumentChunk.embedding.is_not(None),
        ]
        if document_id is not None:
            conditions.append(Document.id == document_id)
        else:
            conditions.append(Document.is_active.is_(True))

        stmt = (
            select(
                DocumentChunk,
                Document.original_filename,
                distance_expr,
            )
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(and_(*conditions))
            .order_by(
                distance_expr.asc(),
                DocumentChunk.chunk_index.asc(),
                DocumentChunk.id.asc(),
            )
            .limit(bounded_top_k)
        )

        try:
            rows = db.execute(stmt).all()
        except SQLAlchemyError as exc:
            logger.exception("Database error occurred during vector retrieval for KB %s", kb_id)
            raise RetrievalError("Database query failed during vector similarity search.") from exc

        # 4. Map rows to RetrievalResultItem schemas (preserving individual chunk knowledge_base_id)
        results: list[RetrievalResultItem] = []
        for chunk, original_filename, distance_val in rows:
            dist = float(distance_val)
            similarity = 1.0 - dist

            item = RetrievalResultItem(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                knowledge_base_id=chunk.knowledge_base_id,
                document_title=original_filename,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                chunk_metadata=chunk.chunk_metadata or {},
                cosine_distance=round(dist, 6),
                similarity=round(similarity, 6),
            )
            results.append(item)

        return RetrievalResponse(
            query=clean_query,
            knowledge_base_id=response_kb_id,
            total_results=len(results),
            results=results,
        )

    def retrieve_sync(
        self,
        db: Session,
        kb_id: uuid.UUID | list[uuid.UUID],
        query: str,
        top_k: int = settings.RAG_TOP_K_RETRIEVAL,
        document_id: uuid.UUID | None = None,
    ) -> RetrievalResponse:
        """Synchronous wrapper for vector retrieval when called from non-async contexts."""
        return asyncio.run(self.retrieve(db=db, kb_id=kb_id, query=query, top_k=top_k, document_id=document_id))


# Singleton default retrieval service instance
_default_retrieval_service: VectorRetrievalService | None = None


def get_retrieval_service() -> VectorRetrievalService:
    """Singleton getter for the default application vector retrieval service."""
    global _default_retrieval_service
    if _default_retrieval_service is None:
        _default_retrieval_service = VectorRetrievalService()
    return _default_retrieval_service
