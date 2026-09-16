"""
CrossEncoder Reranking Service.

Orchestrates candidate retrieval from Step 9 Hybrid Retrieval (Reciprocal Rank Fusion)
and scores each candidate against the search query using a local CrossEncoder provider.
Preserves full provenance from prior retrieval stages while establishing final semantic
ordering based strictly on raw CrossEncoder scores.
"""

import logging
import threading
import uuid
from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.schemas.reranking import RerankResponse, RerankResultItem
from backend.app.services.hybrid_retrieval import (
    HybridRetrievalError,
    HybridRetrievalProviderError,
    HybridRetrievalService,
    HybridRetrievalValidationError,
    get_hybrid_retrieval_service,
)
from backend.app.services.reranking.base import BaseRerankerProvider
from backend.app.services.reranking.cross_encoder_provider import (
    HuggingFaceCrossEncoderProvider,
)
from backend.app.services.reranking.exceptions import (
    RerankerError,
    RerankerProviderError,
    RerankerValidationError,
)
from backend.app.services.reranking.validator import RerankValidator

logger = logging.getLogger(__name__)

# Global singleton provider instance
_default_cross_encoder_provider: BaseRerankerProvider | None = None
_provider_init_lock = threading.Lock()


def get_default_reranker_provider() -> BaseRerankerProvider:
    """
    Thread-safe getter for the global default CrossEncoder provider.
    Ensures a single model instance is shared across service executions.
    """
    global _default_cross_encoder_provider
    if _default_cross_encoder_provider is None:
        with _provider_init_lock:
            if _default_cross_encoder_provider is None:
                _default_cross_encoder_provider = HuggingFaceCrossEncoderProvider()
    return _default_cross_encoder_provider


class RerankingService:
    """
    Coordinates hybrid candidate retrieval and CrossEncoder reranking.
    """

    def __init__(
        self,
        hybrid_service: HybridRetrievalService | None = None,
        reranker_provider: BaseRerankerProvider | None = None,
    ) -> None:
        """
        Initialize the RerankingService with hybrid retrieval and reranking providers.

        Args:
            hybrid_service: Step 9 HybridRetrievalService instance.
            reranker_provider: BaseRerankerProvider instance.
        """
        self._hybrid_service = hybrid_service or get_hybrid_retrieval_service()
        self._reranker_provider = reranker_provider or get_default_reranker_provider()

    @property
    def reranker_provider(self) -> BaseRerankerProvider:
        """Return the configured reranker provider instance."""
        return self._reranker_provider

    async def rerank(
        self,
        db: Session,
        kb_id: uuid.UUID,
        query: str,
        candidate_limit: int = settings.RAG_TOP_K_RETRIEVAL,
        top_k: int = settings.RAG_TOP_K_RERANK,
    ) -> RerankResponse:
        """
        Retrieve hybrid candidates and rerank them using the CrossEncoder provider.

        Args:
            db: Active database session for candidate retrieval.
            kb_id: Knowledge base identifier.
            query: User search query.
            candidate_limit: Number of hybrid candidates to retrieve from Step 9.
            top_k: Number of top reranked chunks to return.

        Returns:
            RerankResponse containing reranked items sorted by reranker_score DESC.

        Raises:
            RerankerValidationError: If query or parameter validation fails.
            RerankerProviderError: If CrossEncoder model inference fails.
            RerankerError: If hybrid retrieval or underlying pipeline fails.
        """
        clean_query = RerankValidator.validate_query(query)

        bounded_candidates = max(
            settings.RETRIEVAL_MIN_TOP_K,
            min(settings.RETRIEVAL_MAX_TOP_K, candidate_limit),
        )
        bounded_top_k = max(
            settings.RETRIEVAL_MIN_TOP_K,
            min(settings.RETRIEVAL_MAX_TOP_K, top_k),
        )

        # 1. Retrieve hybrid candidates via Step 9 RRF service
        try:
            hybrid_response = await self._hybrid_service.retrieve(
                db=db,
                kb_id=kb_id,
                query=clean_query,
                top_k=bounded_candidates,
            )
        except HybridRetrievalValidationError as exc:
            raise RerankerValidationError(str(exc)) from exc
        except HybridRetrievalProviderError as exc:
            raise RerankerProviderError(str(exc)) from exc
        except HybridRetrievalError as exc:
            raise RerankerError(str(exc)) from exc
        except Exception as exc:
            logger.exception("Unexpected error during hybrid candidate retrieval: %s", exc)
            raise RerankerError(f"Candidate retrieval failure: {exc}") from exc

        hybrid_candidates = hybrid_response.results

        # 2. If no candidate chunks found, return empty response
        if not hybrid_candidates:
            return RerankResponse(
                query=clean_query,
                knowledge_base_id=kb_id,
                model_name=self._reranker_provider.model_name,
                total_candidates_reranked=0,
                total_results=0,
                results=[],
                rrf_k=settings.RRF_K,
            )

        # 3. Compute joint relevance scores via CrossEncoder provider
        texts = [candidate.text for candidate in hybrid_candidates]
        try:
            scores = await self._reranker_provider.compute_scores(
                query=clean_query,
                texts=texts,
            )
        except (RerankerValidationError, RerankerProviderError):
            raise
        except Exception as exc:
            logger.exception("Unexpected error during CrossEncoder scoring: %s", exc)
            raise RerankerProviderError(f"CrossEncoder scoring failure: {exc}") from exc

        # 4. Pair candidate with raw score and sort strictly by score DESC
        # Tie-breakers: chunk_index ASC, str(chunk_id) ASC
        paired = list(zip(scores, hybrid_candidates, strict=True))
        paired.sort(key=lambda item: (-item[0], item[1].chunk_index, str(item[1].chunk_id)))

        # 5. Take top_k reranked candidates
        selected_paired = paired[:bounded_top_k]

        # 6. Build RerankResultItem preserving all Step 9 provenance
        reranked_items: list[RerankResultItem] = []
        for rank_idx, (raw_score, candidate) in enumerate(selected_paired, start=1):
            metadata_copy: dict[str, Any] = (
                dict(candidate.chunk_metadata) if candidate.chunk_metadata else {}
            )
            reranked_items.append(
                RerankResultItem(
                    chunk_id=candidate.chunk_id,
                    document_id=candidate.document_id,
                    knowledge_base_id=candidate.knowledge_base_id,
                    document_title=candidate.document_title,
                    chunk_index=candidate.chunk_index,
                    text=candidate.text,
                    page_number=candidate.page_number,
                    section_title=candidate.section_title,
                    chunk_metadata=metadata_copy,
                    rrf_score=candidate.rrf_score,
                    vector_rank=candidate.vector_rank,
                    lexical_rank=candidate.lexical_rank,
                    vector_contribution=candidate.vector_contribution,
                    lexical_contribution=candidate.lexical_contribution,
                    cosine_distance=candidate.cosine_distance,
                    similarity=candidate.similarity,
                    lexical_score=candidate.lexical_score,
                    reranker_score=float(raw_score),  # Raw float, unrounded
                    reranker_rank=rank_idx,
                )
            )

        return RerankResponse(
            query=clean_query,
            knowledge_base_id=kb_id,
            model_name=self._reranker_provider.model_name,
            total_candidates_reranked=len(hybrid_candidates),
            total_results=len(reranked_items),
            results=reranked_items,
            rrf_k=settings.RRF_K,
        )


# Global singleton service instance
_default_reranking_service: RerankingService | None = None
_service_init_lock = threading.Lock()


def get_reranking_service(
    hybrid_service: HybridRetrievalService | None = None,
    reranker_provider: BaseRerankerProvider | None = None,
) -> RerankingService:
    """
    Get or create the singleton RerankingService instance.
    If custom dependencies are supplied, returns a fresh instance.
    """
    global _default_reranking_service
    if hybrid_service is not None or reranker_provider is not None:
        return RerankingService(
            hybrid_service=hybrid_service,
            reranker_provider=reranker_provider,
        )

    if _default_reranking_service is None:
        with _service_init_lock:
            if _default_reranking_service is None:
                _default_reranking_service = RerankingService()
    return _default_reranking_service
