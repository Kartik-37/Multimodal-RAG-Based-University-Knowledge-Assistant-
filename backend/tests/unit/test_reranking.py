"""
Unit Tests for CrossEncoder Reranking Layer.

Validates input/output score validators, mock provider abstraction,
candidate sorting strictly by raw CrossEncoder score DESC, provenance preservation,
tie-breaking behavior, and error handling without external network dependencies.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.core.config import settings
from backend.app.schemas.hybrid_retrieval import HybridRetrievalResponse, HybridRetrievalResultItem
from backend.app.schemas.reranking import RerankRequest, RerankResultItem
from backend.app.services.hybrid_retrieval import (
    HybridRetrievalError,
    HybridRetrievalProviderError,
    HybridRetrievalService,
    HybridRetrievalValidationError,
)
from backend.app.services.reranking.base import BaseRerankerProvider
from backend.app.services.reranking.exceptions import (
    RerankerError,
    RerankerProviderError,
    RerankerValidationError,
)
from backend.app.services.reranking.service import RerankingService
from backend.app.services.reranking.validator import RerankValidator


class DummyMockRerankerProvider(BaseRerankerProvider):
    """Predictable mock provider returning controlled scores for unit testing."""

    def __init__(self, scores: list[float] | None = None) -> None:
        self._scores = scores or []
        self._calls: list[tuple[str, list[str]]] = []

    @property
    def model_name(self) -> str:
        return "mock-reranker-model"

    async def compute_scores(self, query: str, texts: list[str]) -> list[float]:
        self._calls.append((query, texts))
        if not texts:
            return []
        if self._scores:
            return self._scores[: len(texts)]
        # Default: descending float scores based on text length
        return [float(len(t)) for t in texts]


def make_sample_hybrid_candidate(
    chunk_index: int,
    text: str,
    rrf_score: float = 0.015,
    vector_rank: int | None = 1,
    lexical_rank: int | None = 2,
    cosine_distance: float | None = 0.15,
    similarity: float | None = 0.85,
    lexical_score: float | None = 0.42,
    chunk_id: uuid.UUID | None = None,
    doc_id: uuid.UUID | None = None,
    kb_id: uuid.UUID | None = None,
) -> HybridRetrievalResultItem:
    """Helper to construct a fully-populated Step 9 hybrid candidate."""
    return HybridRetrievalResultItem(
        chunk_id=chunk_id or uuid.uuid4(),
        document_id=doc_id or uuid.uuid4(),
        knowledge_base_id=kb_id or uuid.uuid4(),
        document_title="operating_systems.pdf",
        chunk_index=chunk_index,
        text=text,
        page_number=1,
        section_title="Process Synchronization",
        chunk_metadata={"source": "test", "token_estimate": 45},
        rrf_score=rrf_score,
        vector_rank=vector_rank,
        lexical_rank=lexical_rank,
        vector_contribution=1.0 / (60 + (vector_rank or 60)),
        lexical_contribution=1.0 / (60 + (lexical_rank or 60)),
        cosine_distance=cosine_distance,
        similarity=similarity,
        lexical_score=lexical_score,
    )


# ---------------------------------------------------------------------------
# Validator Tests
# ---------------------------------------------------------------------------


class TestRerankValidator:
    """Test suite for RerankValidator input and output validations."""

    def test_validate_query_success(self) -> None:
        assert RerankValidator.validate_query("  operating systems concepts  ") == (
            "operating systems concepts"
        )

    def test_validate_query_empty_or_whitespace(self) -> None:
        with pytest.raises(RerankerValidationError, match="cannot be empty or whitespace"):
            RerankValidator.validate_query("")

        with pytest.raises(RerankerValidationError, match="cannot be empty or whitespace"):
            RerankValidator.validate_query("   \t\n  ")

    def test_validate_query_non_string(self) -> None:
        with pytest.raises(RerankerValidationError, match="Query must be a string"):
            RerankValidator.validate_query(123)  # type: ignore

    def test_validate_rerank_scores_success(self) -> None:
        scores = [0.952341, -2.414123, 15.0, 0.0]
        RerankValidator.validate_rerank_scores(scores, expected_count=4)

    def test_validate_rerank_scores_count_mismatch(self) -> None:
        with pytest.raises(RerankerValidationError, match="returned 2 scores for 3 input texts"):
            RerankValidator.validate_rerank_scores([1.0, 2.0], expected_count=3)

    def test_validate_rerank_scores_nan(self) -> None:
        with pytest.raises(RerankerValidationError, match="non-finite"):
            RerankValidator.validate_rerank_scores([1.0, float("nan"), 3.0], expected_count=3)

    def test_validate_rerank_scores_infinity(self) -> None:
        with pytest.raises(RerankerValidationError, match="non-finite"):
            RerankValidator.validate_rerank_scores([1.0, float("inf"), 3.0], expected_count=3)

    def test_validate_rerank_scores_boolean_rejected(self) -> None:
        with pytest.raises(RerankerValidationError, match="not numeric"):
            RerankValidator.validate_rerank_scores([True, 1.0], expected_count=2)

    def test_validate_rerank_scores_non_numeric(self) -> None:
        with pytest.raises(RerankerValidationError, match="not numeric"):
            RerankValidator.validate_rerank_scores(["high", 1.0], expected_count=2)  # type: ignore

    def test_validate_rerank_scores_non_list(self) -> None:
        with pytest.raises(RerankerValidationError, match="Expected scores to be a list"):
            RerankValidator.validate_rerank_scores("not-a-list", expected_count=1)  # type: ignore


# ---------------------------------------------------------------------------
# Schema Tests
# ---------------------------------------------------------------------------


class TestRerankSchemas:
    """Test suite for RerankRequest and RerankResultItem schemas."""

    def test_request_whitespace_rejected(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty or whitespace"):
            RerankRequest(query="   ")

    def test_request_defaults(self) -> None:
        req = RerankRequest(query="what is virtual memory?")
        assert req.candidate_limit == settings.RAG_TOP_K_RETRIEVAL
        assert req.top_k == settings.RAG_TOP_K_RERANK

    def test_result_item_unrounded_score(self) -> None:
        raw_float = 0.123456789012345
        item = RerankResultItem(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            knowledge_base_id=uuid.uuid4(),
            document_title="test.pdf",
            chunk_index=0,
            text="sample text",
            rrf_score=0.016,
            reranker_score=raw_float,
            reranker_rank=1,
        )
        # Score must remain the exact raw finite float (NO internal rounding)
        assert item.reranker_score == raw_float


# ---------------------------------------------------------------------------
# Reranking Service Unit Tests
# ---------------------------------------------------------------------------


class TestRerankingService:
    """Test suite for RerankingService orchestration logic."""

    @pytest.mark.asyncio
    async def test_empty_candidates_returns_empty_response(self) -> None:
        mock_hybrid = MagicMock(spec=HybridRetrievalService)
        mock_hybrid.retrieve = AsyncMock(
            return_value=HybridRetrievalResponse(
                query="test query",
                knowledge_base_id=uuid.uuid4(),
                total_results=0,
                results=[],
            )
        )
        mock_provider = DummyMockRerankerProvider()
        service = RerankingService(hybrid_service=mock_hybrid, reranker_provider=mock_provider)

        resp = await service.rerank(
            db=MagicMock(),
            kb_id=uuid.uuid4(),
            query="test query",
        )
        assert resp.total_candidates_reranked == 0
        assert resp.total_results == 0
        assert resp.results == []
        assert len(mock_provider._calls) == 0

    @pytest.mark.asyncio
    async def test_rerank_orders_strictly_by_raw_score_desc(self) -> None:
        """Verify candidate chunks are ordered strictly by CrossEncoder score DESC."""
        kb_id = uuid.uuid4()
        c1 = make_sample_hybrid_candidate(chunk_index=0, text="First candidate (low relevance)")
        c2 = make_sample_hybrid_candidate(chunk_index=1, text="Second candidate (high relevance)")
        c3 = make_sample_hybrid_candidate(chunk_index=2, text="Third candidate (medium relevance)")

        mock_hybrid = MagicMock(spec=HybridRetrievalService)
        mock_hybrid.retrieve = AsyncMock(
            return_value=HybridRetrievalResponse(
                query="cpu scheduling",
                knowledge_base_id=kb_id,
                total_results=3,
                results=[c1, c2, c3],
            )
        )

        # CrossEncoder scores: c1 -> -1.5, c2 -> 4.87654321, c3 -> 1.25
        # Expected rerank order: c2 (4.87654321), c3 (1.25), c1 (-1.5)
        raw_c2_score = 4.87654321098765
        mock_provider = DummyMockRerankerProvider(scores=[-1.5, raw_c2_score, 1.25])
        service = RerankingService(hybrid_service=mock_hybrid, reranker_provider=mock_provider)

        resp = await service.rerank(
            db=MagicMock(),
            kb_id=kb_id,
            query="cpu scheduling",
            candidate_limit=20,
            top_k=5,
        )

        assert resp.total_candidates_reranked == 3
        assert resp.total_results == 3

        # Rank 1: c2
        assert resp.results[0].chunk_id == c2.chunk_id
        assert resp.results[0].reranker_rank == 1
        assert resp.results[0].reranker_score == raw_c2_score  # Exact raw float!

        # Rank 2: c3
        assert resp.results[1].chunk_id == c3.chunk_id
        assert resp.results[1].reranker_rank == 2
        assert resp.results[1].reranker_score == 1.25

        # Rank 3: c1
        assert resp.results[2].chunk_id == c1.chunk_id
        assert resp.results[2].reranker_rank == 3
        assert resp.results[2].reranker_score == -1.5

    @pytest.mark.asyncio
    async def test_rerank_preserves_full_step9_provenance(self) -> None:
        """Verify all Step 9 metadata, RRF score, branch ranks, and distances are preserved."""
        kb_id = uuid.uuid4()
        c = make_sample_hybrid_candidate(
            chunk_index=3,
            text="Semaphores and mutexes",
            rrf_score=0.0325,
            vector_rank=2,
            lexical_rank=1,
            cosine_distance=0.12,
            similarity=0.88,
            lexical_score=0.67,
        )

        mock_hybrid = MagicMock(spec=HybridRetrievalService)
        mock_hybrid.retrieve = AsyncMock(
            return_value=HybridRetrievalResponse(
                query="mutex",
                knowledge_base_id=kb_id,
                total_results=1,
                results=[c],
            )
        )

        raw_score = 2.718281828459045
        mock_provider = DummyMockRerankerProvider(scores=[raw_score])
        service = RerankingService(hybrid_service=mock_hybrid, reranker_provider=mock_provider)

        resp = await service.rerank(db=MagicMock(), kb_id=kb_id, query="mutex")
        assert len(resp.results) == 1
        item = resp.results[0]

        assert item.chunk_id == c.chunk_id
        assert item.document_id == c.document_id
        assert item.document_title == "operating_systems.pdf"
        assert item.chunk_index == 3
        assert item.text == "Semaphores and mutexes"
        assert item.page_number == 1
        assert item.section_title == "Process Synchronization"
        assert item.chunk_metadata == {"source": "test", "token_estimate": 45}
        assert item.rrf_score == 0.0325
        assert item.vector_rank == 2
        assert item.lexical_rank == 1
        assert item.cosine_distance == 0.12
        assert item.similarity == 0.88
        assert item.lexical_score == 0.67
        assert item.reranker_score == raw_score
        assert item.reranker_rank == 1

    @pytest.mark.asyncio
    async def test_rerank_deterministic_tie_breaking(self) -> None:
        """When CrossEncoder scores are identical, tie-breaker must use chunk_index ASC then chunk_id ASC."""
        kb_id = uuid.uuid4()
        id_a = uuid.UUID("00000000-0000-0000-0000-000000000001")
        id_b = uuid.UUID("00000000-0000-0000-0000-000000000002")

        # Two chunks with identical score, different chunk_index
        c_later = make_sample_hybrid_candidate(chunk_index=5, text="Later chunk", chunk_id=id_a)
        c_earlier = make_sample_hybrid_candidate(chunk_index=2, text="Earlier chunk", chunk_id=id_b)

        mock_hybrid = MagicMock(spec=HybridRetrievalService)
        # Hybrid branch returned c_later first
        mock_hybrid.retrieve = AsyncMock(
            return_value=HybridRetrievalResponse(
                query="test",
                knowledge_base_id=kb_id,
                total_results=2,
                results=[c_later, c_earlier],
            )
        )

        # Both get identical CrossEncoder score
        mock_provider = DummyMockRerankerProvider(scores=[3.0, 3.0])
        service = RerankingService(hybrid_service=mock_hybrid, reranker_provider=mock_provider)

        resp = await service.rerank(db=MagicMock(), kb_id=kb_id, query="test")
        assert len(resp.results) == 2
        # Earlier chunk (chunk_index=2) should break the tie and be ranked #1
        assert resp.results[0].chunk_id == id_b
        assert resp.results[0].chunk_index == 2
        assert resp.results[0].reranker_rank == 1

        assert resp.results[1].chunk_id == id_a
        assert resp.results[1].chunk_index == 5
        assert resp.results[1].reranker_rank == 2

    @pytest.mark.asyncio
    async def test_top_k_limiting(self) -> None:
        """Verify top_k bounds candidate output count."""
        kb_id = uuid.uuid4()
        candidates = [
            make_sample_hybrid_candidate(chunk_index=i, text=f"Chunk {i}") for i in range(10)
        ]
        mock_hybrid = MagicMock(spec=HybridRetrievalService)
        mock_hybrid.retrieve = AsyncMock(
            return_value=HybridRetrievalResponse(
                query="test",
                knowledge_base_id=kb_id,
                total_results=10,
                results=candidates,
            )
        )

        mock_provider = DummyMockRerankerProvider(scores=[float(i) for i in range(10)])
        service = RerankingService(hybrid_service=mock_hybrid, reranker_provider=mock_provider)

        resp = await service.rerank(
            db=MagicMock(),
            kb_id=kb_id,
            query="test",
            candidate_limit=10,
            top_k=3,
        )
        assert resp.total_candidates_reranked == 10
        assert resp.total_results == 3
        assert len(resp.results) == 3

    @pytest.mark.asyncio
    async def test_hybrid_validation_error_mapped(self) -> None:
        mock_hybrid = MagicMock(spec=HybridRetrievalService)
        mock_hybrid.retrieve = AsyncMock(
            side_effect=HybridRetrievalValidationError("Invalid query terms")
        )
        service = RerankingService(
            hybrid_service=mock_hybrid, reranker_provider=DummyMockRerankerProvider()
        )

        with pytest.raises(RerankerValidationError, match="Invalid query terms"):
            await service.rerank(db=MagicMock(), kb_id=uuid.uuid4(), query="bad query")

    @pytest.mark.asyncio
    async def test_hybrid_provider_error_mapped(self) -> None:
        mock_hybrid = MagicMock(spec=HybridRetrievalService)
        mock_hybrid.retrieve = AsyncMock(
            side_effect=HybridRetrievalProviderError("Ollama connection failed")
        )
        service = RerankingService(
            hybrid_service=mock_hybrid, reranker_provider=DummyMockRerankerProvider()
        )

        with pytest.raises(RerankerProviderError, match="Ollama connection failed"):
            await service.rerank(db=MagicMock(), kb_id=uuid.uuid4(), query="valid query")

    @pytest.mark.asyncio
    async def test_hybrid_general_error_mapped(self) -> None:
        mock_hybrid = MagicMock(spec=HybridRetrievalService)
        mock_hybrid.retrieve = AsyncMock(side_effect=HybridRetrievalError("Database deadlock"))
        service = RerankingService(
            hybrid_service=mock_hybrid, reranker_provider=DummyMockRerankerProvider()
        )

        with pytest.raises(RerankerError, match="Database deadlock"):
            await service.rerank(db=MagicMock(), kb_id=uuid.uuid4(), query="valid query")
