"""
PostgreSQL Full-Text Lexical Retrieval Service.

Implements native lexical/text matching over document chunks using PostgreSQL's
full-text search facilities (tsvector, websearch_to_tsquery, ts_rank_cd, and GIN index).

Important Architectural Decisions:
- Independent from Ollama: Requires ZERO embeddings or model calls; operates normally
  even if Ollama is offline.
- Eligible Content: Chunks from documents with DocumentStatus == COMPLETED are searchable
  regardless of vector indexing status (does not require embedding IS NOT NULL).
- Exact KB Isolation: SQL query is strictly constrained to the authorized knowledge_base_id.
- Safe Query Processing: Uses PostgreSQL's websearch_to_tsquery for natural-language
  robustness, operator tolerance, and injection protection.
- Native Scoring: Exposes PostgreSQL's cover density ranking score as lexical_score
  (not falsely labeled as BM25).
- Deterministic Ordering: Secondary tie-breaking by chunk_index ASC, id ASC.
"""

import logging
import uuid

from sqlalchemy import and_, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.document import Document, DocumentChunk, DocumentStatus
from backend.app.schemas.lexical_retrieval import (
    LexicalRetrievalResponse,
    LexicalRetrievalResultItem,
)

logger = logging.getLogger(__name__)


class LexicalRetrievalError(Exception):
    """Base exception for lexical retrieval errors."""

    pass


class LexicalRetrievalValidationError(LexicalRetrievalError):
    """Raised when query or lexical retrieval parameters fail validation."""

    pass


class LexicalRetrievalService:
    """
    Service executing PostgreSQL-native full-text lexical retrieval over document chunks.
    """

    def __init__(self, language: str | None = None) -> None:
        self._language = language or settings.LEXICAL_LANGUAGE

    @property
    def language(self) -> str:
        """The PostgreSQL text-search dictionary configuration name (e.g. 'english')."""
        return self._language

    def validate_query(self, query: str) -> str:
        """
        Validate and normalize query input string.

        Raises:
            LexicalRetrievalValidationError: If query is empty, whitespace-only, or exceeds max length.
        """
        if not query or not query.strip():
            raise LexicalRetrievalValidationError(
                "Query string cannot be empty or whitespace only."
            )

        normalized_query = query.strip()
        if len(normalized_query) > settings.LEXICAL_MAX_QUERY_LENGTH:
            raise LexicalRetrievalValidationError(
                f"Query length ({len(normalized_query)} chars) exceeds maximum permitted limit "
                f"of {settings.LEXICAL_MAX_QUERY_LENGTH} characters."
            )

        return normalized_query

    def validate_top_k(self, top_k: int) -> int:
        """
        Validate requested top_k bound.

        Raises:
            LexicalRetrievalValidationError: If top_k is outside permitted bounds.
        """
        if top_k < settings.RETRIEVAL_MIN_TOP_K:
            raise LexicalRetrievalValidationError(
                f"top_k must be at least {settings.RETRIEVAL_MIN_TOP_K}, got {top_k}."
            )
        if top_k > settings.RETRIEVAL_MAX_TOP_K:
            raise LexicalRetrievalValidationError(
                f"top_k cannot exceed {settings.RETRIEVAL_MAX_TOP_K}, got {top_k}."
            )
        return top_k

    def retrieve(
        self,
        db: Session,
        kb_id: uuid.UUID | list[uuid.UUID],
        query: str,
        top_k: int = settings.LEXICAL_TOP_K,
        document_id: uuid.UUID | None = None,
    ) -> LexicalRetrievalResponse:
        """
        Execute PostgreSQL full-text lexical search against an authorized knowledge base or collection.

        Args:
            db: Active SQLAlchemy database session.
            kb_id: Authorized knowledge base UUID or list of authorized UUIDs.
            query: Natural-language search query string.
            top_k: Maximum number of top candidates to retrieve.
            document_id: Optional UUID of a specific document to scope retrieval.

        Returns:
            LexicalRetrievalResponse with ranked chunks and cover density ranking scores.

        Raises:
            LexicalRetrievalValidationError: On invalid input.
            LexicalRetrievalError: On database query failure.
        """
        clean_query = self.validate_query(query)
        bounded_top_k = self.validate_top_k(top_k)

        # Scoping resolution: Empty collection MUST return zero results immediately (never an unscoped query)
        if isinstance(kb_id, (list, tuple, set)):
            kb_ids_list = list(kb_id)
            if len(kb_ids_list) == 0:
                return LexicalRetrievalResponse(
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

        # Build PostgreSQL websearch tsquery
        query_tsquery = func.websearch_to_tsquery(self._language, clean_query)

        # Cover density ranking function (ts_rank_cd)
        score_expr = func.ts_rank_cd(DocumentChunk.searchable_text, query_tsquery).label(
            "lexical_score"
        )

        # Invariant: Only successfully ingested (COMPLETED) documents participate
        conditions = [
            kb_filter,
            Document.status == DocumentStatus.COMPLETED,
            DocumentChunk.searchable_text.is_not(None),
            DocumentChunk.searchable_text.op("@@")(query_tsquery),
        ]
        if document_id is not None:
            conditions.append(Document.id == document_id)
        else:
            conditions.append(Document.is_active.is_(True))

        stmt = (
            select(
                DocumentChunk,
                Document.original_filename,
                score_expr,
            )
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(and_(*conditions))
            .order_by(
                score_expr.desc(),
                DocumentChunk.chunk_index.asc(),
                DocumentChunk.id.asc(),
            )
            .limit(bounded_top_k)
        )

        try:
            rows = db.execute(stmt).all()
        except SQLAlchemyError as exc:
            logger.exception("Database error occurred during lexical retrieval for KB %s", kb_id)
            raise LexicalRetrievalError(
                "Database query failed during lexical full-text search."
            ) from exc

        results: list[LexicalRetrievalResultItem] = []
        for chunk, original_filename, score_val in rows:
            score = float(score_val)
            item = LexicalRetrievalResultItem(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                knowledge_base_id=chunk.knowledge_base_id,
                document_title=original_filename,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                chunk_metadata=chunk.chunk_metadata or {},
                lexical_score=round(score, 6),
            )
            results.append(item)

        return LexicalRetrievalResponse(
            query=clean_query,
            knowledge_base_id=response_kb_id,
            total_results=len(results),
            results=results,
        )


# Singleton default lexical retrieval service instance
_default_lexical_service: LexicalRetrievalService | None = None


def get_lexical_retrieval_service() -> LexicalRetrievalService:
    """Singleton getter for the default application lexical retrieval service."""
    global _default_lexical_service
    if _default_lexical_service is None:
        _default_lexical_service = LexicalRetrievalService()
    return _default_lexical_service
