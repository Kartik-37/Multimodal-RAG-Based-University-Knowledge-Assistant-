"""
Hybrid Retrieval Service.

Combines exact dense vector retrieval (Step 7) and PostgreSQL-native full-text
lexical retrieval (Step 8) into a unified hybrid retrieval layer using
Reciprocal Rank Fusion (RRF).

Key Architectural Decisions:
- Service Reuse: Reuses VectorRetrievalService and LexicalRetrievalService directly,
  avoiding duplication of SQL, database access, or authorization logic.
- Pure Rank Fusion: Fuses 1-based candidate rank positions. Never averages, normalizes,
  or combines raw cosine distance/similarity and PostgreSQL ts_rank_cd scores.
- RRF Formulation:
    RRF_score(chunk) = sum(1 / (RRF_K + rank))
  Uses project configuration settings.RRF_K as authoritative constant.
- Stable Identity & Deduplication: Uses chunk_id as the unique key to fuse candidates
  appearing in both retrieval branches without duplicating results.
- Deterministic Tie-Breaking: Sorts primarily by rrf_score DESC, with deterministic
  secondary tie-breaking on chunk_index ASC, chunk_id ASC.
- Provenance Preservation: Retains all chunk structural metadata (document, page,
  section, metadata dictionary) and diagnostic metrics from both branches.
"""

import asyncio
import logging
import uuid

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.schemas.hybrid_retrieval import (
    HybridRetrievalResponse,
    HybridRetrievalResultItem,
)
from backend.app.schemas.lexical_retrieval import LexicalRetrievalResultItem
from backend.app.schemas.retrieval import RetrievalResultItem
from backend.app.services.lexical_retrieval import (
    LexicalRetrievalError,
    LexicalRetrievalService,
    LexicalRetrievalValidationError,
    get_lexical_retrieval_service,
)
from backend.app.services.retrieval import (
    RetrievalError,
    RetrievalProviderError,
    RetrievalValidationError,
    VectorRetrievalService,
    get_retrieval_service,
)

logger = logging.getLogger(__name__)


class HybridRetrievalError(Exception):
    """Base exception for hybrid retrieval errors."""

    pass


class HybridRetrievalValidationError(HybridRetrievalError):
    """Raised when query or hybrid retrieval parameters fail validation."""

    pass


class HybridRetrievalProviderError(HybridRetrievalError):
    """Raised when an underlying provider (e.g. embedding service) fails."""

    pass


class HybridRetrievalService:
    """
    Service orchestrating dense vector and lexical full-text retrieval
    and fusing their ranked candidates using Reciprocal Rank Fusion (RRF).
    """

    def __init__(
        self,
        vector_service: VectorRetrievalService | None = None,
        lexical_service: LexicalRetrievalService | None = None,
        rrf_k: int | None = None,
    ) -> None:
        self._vector_service = vector_service or get_retrieval_service()
        self._lexical_service = lexical_service or get_lexical_retrieval_service()
        # Authoritative project configuration from settings, not hardcoded
        self._rrf_k = rrf_k if rrf_k is not None else settings.RRF_K

    @property
    def rrf_k(self) -> int:
        """The smoothing constant used for Reciprocal Rank Fusion."""
        return self._rrf_k

    @property
    def vector_service(self) -> VectorRetrievalService:
        return self._vector_service

    @property
    def lexical_service(self) -> LexicalRetrievalService:
        return self._lexical_service

    def validate_query(self, query: str) -> str:
        """
        Validate and normalize query input string.

        Raises:
            HybridRetrievalValidationError: If query is empty, whitespace-only, or exceeds max length.
        """
        if not query or not query.strip():
            raise HybridRetrievalValidationError("Query string cannot be empty or whitespace only.")

        normalized_query = query.strip()
        if len(normalized_query) > settings.RETRIEVAL_MAX_QUERY_LENGTH:
            raise HybridRetrievalValidationError(
                f"Query length ({len(normalized_query)} chars) exceeds maximum permitted limit "
                f"of {settings.RETRIEVAL_MAX_QUERY_LENGTH} characters."
            )

        return normalized_query

    def validate_top_k(self, top_k: int) -> int:
        """
        Validate requested top_k bound.

        Raises:
            HybridRetrievalValidationError: If top_k is outside permitted bounds.
        """
        if top_k < settings.RETRIEVAL_MIN_TOP_K:
            raise HybridRetrievalValidationError(
                f"top_k must be at least {settings.RETRIEVAL_MIN_TOP_K}, got {top_k}."
            )
        if top_k > settings.RETRIEVAL_MAX_TOP_K:
            raise HybridRetrievalValidationError(
                f"top_k cannot exceed {settings.RETRIEVAL_MAX_TOP_K}, got {top_k}."
            )
        return top_k

    def fuse_ranks(
        self,
        vector_results: list[RetrievalResultItem],
        lexical_results: list[LexicalRetrievalResultItem],
        top_k: int,
    ) -> list[HybridRetrievalResultItem]:
        """
        Fuse ranked candidates from vector and lexical retrieval branches using RRF.

        Args:
            vector_results: 1-indexed ranked candidates from vector search.
            lexical_results: 1-indexed ranked candidates from lexical full-text search.
            top_k: Maximum number of fused results to return.

        Returns:
            List of HybridRetrievalResultItem sorted by rrf_score DESC with
            deterministic tie-breaking on (chunk_index ASC, chunk_id ASC).
        """
        fused_candidates: dict[uuid.UUID, HybridRetrievalResultItem] = {}

        # 1. Process vector retrieval branch (1-based rank indexing)
        for rank, item in enumerate(vector_results, start=1):
            contrib = 1.0 / (self._rrf_k + rank)
            fused_candidates[item.chunk_id] = HybridRetrievalResultItem(
                chunk_id=item.chunk_id,
                document_id=item.document_id,
                knowledge_base_id=item.knowledge_base_id,
                document_title=item.document_title,
                chunk_index=item.chunk_index,
                text=item.text,
                page_number=item.page_number,
                section_title=item.section_title,
                chunk_metadata=dict(item.chunk_metadata) if item.chunk_metadata else {},
                rrf_score=contrib,
                vector_rank=rank,
                lexical_rank=None,
                vector_contribution=contrib,
                lexical_contribution=0.0,
                cosine_distance=item.cosine_distance,
                similarity=item.similarity,
                lexical_score=None,
            )

        # 2. Process lexical retrieval branch (1-based rank indexing)
        for rank, item in enumerate(lexical_results, start=1):
            contrib = 1.0 / (self._rrf_k + rank)
            if item.chunk_id in fused_candidates:
                existing = fused_candidates[item.chunk_id]
                # Accumulate RRF score and branch contributions
                existing.rrf_score += contrib
                existing.lexical_rank = rank
                existing.lexical_contribution = contrib
                existing.lexical_score = item.lexical_score
                # Preserve provenance if not already set
                if existing.page_number is None and item.page_number is not None:
                    existing.page_number = item.page_number
                if not existing.section_title and item.section_title:
                    existing.section_title = item.section_title
            else:
                fused_candidates[item.chunk_id] = HybridRetrievalResultItem(
                    chunk_id=item.chunk_id,
                    document_id=item.document_id,
                    knowledge_base_id=item.knowledge_base_id,
                    document_title=item.document_title,
                    chunk_index=item.chunk_index,
                    text=item.text,
                    page_number=item.page_number,
                    section_title=item.section_title,
                    chunk_metadata=dict(item.chunk_metadata) if item.chunk_metadata else {},
                    rrf_score=contrib,
                    vector_rank=None,
                    lexical_rank=rank,
                    vector_contribution=0.0,
                    lexical_contribution=contrib,
                    cosine_distance=None,
                    similarity=None,
                    lexical_score=item.lexical_score,
                )

        # 3. Round scores for precision and consistent display
        for item in fused_candidates.values():
            item.rrf_score = round(item.rrf_score, 6)
            item.vector_contribution = round(item.vector_contribution, 6)
            item.lexical_contribution = round(item.lexical_contribution, 6)

        # 4. Sort primarily by rrf_score DESC, with deterministic secondary tie-breaking
        sorted_results = sorted(
            fused_candidates.values(),
            key=lambda x: (-x.rrf_score, x.chunk_index, str(x.chunk_id)),
        )

        return sorted_results[:top_k]

    async def retrieve(
        self,
        db: Session,
        kb_id: uuid.UUID | list[uuid.UUID],
        query: str,
        top_k: int = settings.RAG_TOP_K_RETRIEVAL,
        document_id: uuid.UUID | None = None,
    ) -> HybridRetrievalResponse:
        """
        Execute hybrid retrieval combining dense vector search and PostgreSQL lexical search
        fused via Reciprocal Rank Fusion (RRF).

        Args:
            db: Active SQLAlchemy database session.
            kb_id: Authorized knowledge base UUID or list of authorized UUIDs.
            query: Natural-language query string.
            top_k: Maximum number of top fused chunks to return.
            document_id: Optional UUID of a specific document to scope retrieval.

        Returns:
            HybridRetrievalResponse with fused chunks ordered by descending RRF score.

        Raises:
            HybridRetrievalValidationError: On invalid query or parameter bounds.
            HybridRetrievalProviderError: On embedding provider failure.
            HybridRetrievalError: On database or retrieval failure.
        """
        clean_query = self.validate_query(query)
        bounded_top_k = self.validate_top_k(top_k)

        if isinstance(kb_id, (list, tuple, set)):
            kb_ids_list = list(kb_id)
            response_kb_id = kb_ids_list[0] if len(kb_ids_list) == 1 else None
        else:
            response_kb_id = kb_id

        # Candidate pool limit requested from each retrieval branch
        candidate_limit = max(bounded_top_k, settings.RAG_TOP_K_RETRIEVAL)

        # 1. Execute vector retrieval branch
        try:
            vector_response = await self._vector_service.retrieve(
                db=db,
                kb_id=kb_id,
                query=clean_query,
                top_k=candidate_limit,
                document_id=document_id,
            )
            vector_results = vector_response.results
        except RetrievalValidationError as exc:
            raise HybridRetrievalValidationError(str(exc)) from exc
        except RetrievalProviderError as exc:
            logger.error("Embedding provider failure during hybrid retrieval: %s", exc)
            raise HybridRetrievalProviderError(
                f"Embedding provider unavailable during hybrid retrieval: {exc}"
            ) from exc
        except RetrievalError as exc:
            logger.exception("Database failure during vector branch in hybrid retrieval: %s", exc)
            raise HybridRetrievalError(f"Vector retrieval branch failed: {exc}") from exc

        # 2. Execute lexical retrieval branch
        try:
            lexical_response = self._lexical_service.retrieve(
                db=db,
                kb_id=kb_id,
                query=clean_query,
                top_k=candidate_limit,
                document_id=document_id,
            )
            lexical_results = lexical_response.results
        except LexicalRetrievalValidationError as exc:
            raise HybridRetrievalValidationError(str(exc)) from exc
        except LexicalRetrievalError as exc:
            logger.exception("Database failure during lexical branch in hybrid retrieval: %s", exc)
            raise HybridRetrievalError(f"Lexical retrieval branch failed: {exc}") from exc

        # 3. Fuse candidates using Reciprocal Rank Fusion
        fused_items = self.fuse_ranks(
            vector_results=vector_results,
            lexical_results=lexical_results,
            top_k=bounded_top_k,
        )

        return HybridRetrievalResponse(
            query=clean_query,
            knowledge_base_id=response_kb_id,
            total_results=len(fused_items),
            results=fused_items,
            rrf_k=self._rrf_k,
        )

    def retrieve_sync(
        self,
        db: Session,
        kb_id: uuid.UUID | list[uuid.UUID],
        query: str,
        top_k: int = settings.RAG_TOP_K_RETRIEVAL,
        document_id: uuid.UUID | None = None,
    ) -> HybridRetrievalResponse:
        """Synchronous wrapper for hybrid retrieval when called from non-async contexts."""
        return asyncio.run(self.retrieve(db=db, kb_id=kb_id, query=query, top_k=top_k, document_id=document_id))


# Singleton default hybrid retrieval service instance
_default_hybrid_retrieval_service: HybridRetrievalService | None = None


def get_hybrid_retrieval_service() -> HybridRetrievalService:
    """Singleton getter for the default application hybrid retrieval service."""
    global _default_hybrid_retrieval_service
    if _default_hybrid_retrieval_service is None:
        _default_hybrid_retrieval_service = HybridRetrievalService()
    return _default_hybrid_retrieval_service
