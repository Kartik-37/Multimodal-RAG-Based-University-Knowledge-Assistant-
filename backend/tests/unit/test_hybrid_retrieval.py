"""
Unit tests for Hybrid Retrieval Service and Reciprocal Rank Fusion (RRF).

Verifies:
- RRF mathematical formulation and smoothing constant (RRF_K).
- 1-based candidate rank indexing.
- Single-branch vs dual-branch contribution accumulation.
- Duplicate chunk prevention (fusion by chunk_id).
- Deterministic secondary tie-breaking.
- Candidate top_k bounding and slicing.
- Empty branch handling (empty vector, empty lexical, both empty).
- Metadata and structural provenance preservation.
- Safe default factory for chunk_metadata.
- Validation bounds and whitespace-only query rejection.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.core.config import settings
from backend.app.schemas.hybrid_retrieval import (
    HybridRetrievalRequest,
    HybridRetrievalResultItem,
)
from backend.app.schemas.lexical_retrieval import (
    LexicalRetrievalResponse,
    LexicalRetrievalResultItem,
)
from backend.app.schemas.retrieval import (
    RetrievalResponse,
    RetrievalResultItem,
)
from backend.app.services.hybrid_retrieval import (
    HybridRetrievalService,
)


def _create_mock_vector_item(
    chunk_id: uuid.UUID,
    chunk_index: int = 0,
    text: str = "Sample vector text",
    distance: float = 0.2,
    similarity: float = 0.8,
) -> RetrievalResultItem:
    return RetrievalResultItem(
        chunk_id=chunk_id,
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_title="vector_doc.pdf",
        chunk_index=chunk_index,
        text=text,
        page_number=1,
        section_title="Vector Section",
        chunk_metadata={"source": "vector"},
        cosine_distance=distance,
        similarity=similarity,
    )


def _create_mock_lexical_item(
    chunk_id: uuid.UUID,
    chunk_index: int = 0,
    text: str = "Sample lexical text",
    lexical_score: float = 0.75,
) -> LexicalRetrievalResultItem:
    return LexicalRetrievalResultItem(
        chunk_id=chunk_id,
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_title="lexical_doc.pdf",
        chunk_index=chunk_index,
        text=text,
        page_number=2,
        section_title="Lexical Section",
        chunk_metadata={"source": "lexical"},
        lexical_score=lexical_score,
    )


def test_rrf_formula_mathematical_calculation() -> None:
    """Verify exact mathematical RRF calculation for rank positions."""
    service = HybridRetrievalService(rrf_k=60)

    chunk_a = uuid.uuid4()
    chunk_b = uuid.uuid4()
    chunk_c = uuid.uuid4()

    # chunk_a: vector rank 1, lexical rank 2
    # chunk_b: vector rank 2, lexical None
    # chunk_c: vector None, lexical rank 1
    vector_items = [
        _create_mock_vector_item(chunk_a, chunk_index=0),
        _create_mock_vector_item(chunk_b, chunk_index=1),
    ]
    lexical_items = [
        _create_mock_lexical_item(chunk_c, chunk_index=2),
        _create_mock_lexical_item(chunk_a, chunk_index=0),
    ]

    fused = service.fuse_ranks(vector_items, lexical_items, top_k=10)

    # Expected contributions with RRF_K = 60:
    # chunk_a: 1/(60 + 1) + 1/(60 + 2) = 1/61 + 1/62 = 0.01639344 + 0.01612903 = 0.032522
    # chunk_c: 1/(60 + 1) = 0.016393
    # chunk_b: 1/(60 + 2) = 0.016129
    assert len(fused) == 3

    item_a = next(i for i in fused if i.chunk_id == chunk_a)
    assert item_a.vector_rank == 1
    assert item_a.lexical_rank == 2
    assert item_a.vector_contribution == round(1.0 / 61, 6)
    assert item_a.lexical_contribution == round(1.0 / 62, 6)
    assert item_a.rrf_score == round((1.0 / 61) + (1.0 / 62), 6)

    item_c = next(i for i in fused if i.chunk_id == chunk_c)
    assert item_c.vector_rank is None
    assert item_c.lexical_rank == 1
    assert item_c.vector_contribution == 0.0
    assert item_c.lexical_contribution == round(1.0 / 61, 6)
    assert item_c.rrf_score == round(1.0 / 61, 6)

    item_b = next(i for i in fused if i.chunk_id == chunk_b)
    assert item_b.vector_rank == 2
    assert item_b.lexical_rank is None
    assert item_b.vector_contribution == round(1.0 / 62, 6)
    assert item_b.lexical_contribution == 0.0
    assert item_b.rrf_score == round(1.0 / 62, 6)

    # Ordering check: a > c > b
    assert fused[0].chunk_id == chunk_a
    assert fused[1].chunk_id == chunk_c
    assert fused[2].chunk_id == chunk_b


def test_rrf_k_authoritative_config_and_behavior() -> None:
    """Verify that settings.RRF_K is used by default and affects scores properly."""
    # Default uses settings.RRF_K
    service_default = HybridRetrievalService()
    assert service_default.rrf_k == settings.RRF_K

    # Custom RRF_K sensitivity
    service_k20 = HybridRetrievalService(rrf_k=20)
    service_k100 = HybridRetrievalService(rrf_k=100)

    chunk_id = uuid.uuid4()
    v_items = [_create_mock_vector_item(chunk_id)]

    fused_k20 = service_k20.fuse_ranks(v_items, [], top_k=5)
    fused_k100 = service_k100.fuse_ranks(v_items, [], top_k=5)

    assert fused_k20[0].rrf_score == round(1.0 / (20 + 1), 6)
    assert fused_k100[0].rrf_score == round(1.0 / (100 + 1), 6)
    assert fused_k20[0].rrf_score > fused_k100[0].rrf_score


def test_rank_starts_at_one() -> None:
    """Verify candidate rank numbering strictly starts at 1, not 0."""
    service = HybridRetrievalService(rrf_k=60)
    chunk_1 = uuid.uuid4()
    chunk_2 = uuid.uuid4()

    v_items = [
        _create_mock_vector_item(chunk_1),
        _create_mock_vector_item(chunk_2),
    ]
    fused = service.fuse_ranks(v_items, [], top_k=5)

    assert fused[0].vector_rank == 1
    assert fused[1].vector_rank == 2


def test_duplicate_prevention_on_chunk_id() -> None:
    """Verify that chunks appearing in both branches fuse into a single candidate."""
    service = HybridRetrievalService(rrf_k=60)
    shared_chunk = uuid.uuid4()

    v_items = [_create_mock_vector_item(shared_chunk, text="Shared chunk text")]
    l_items = [_create_mock_lexical_item(shared_chunk, text="Shared chunk text")]

    fused = service.fuse_ranks(v_items, l_items, top_k=10)

    assert len(fused) == 1
    assert fused[0].chunk_id == shared_chunk
    assert fused[0].vector_rank == 1
    assert fused[0].lexical_rank == 1
    # Both contributions present
    assert fused[0].vector_contribution > 0.0
    assert fused[0].lexical_contribution > 0.0
    # Both diagnostic metrics preserved
    assert fused[0].similarity == 0.8
    assert fused[0].lexical_score == 0.75


def test_deterministic_tie_breaking() -> None:
    """Verify equal RRF scores are deterministically ordered by chunk_index, then chunk_id."""
    service = HybridRetrievalService(rrf_k=60)

    # Create two chunks that will have identical RRF scores (e.g. both vector-only at rank 1)
    # Give them different chunk_index
    id_1 = uuid.UUID("11111111-1111-1111-1111-111111111111")
    id_2 = uuid.UUID("22222222-2222-2222-2222-222222222222")

    # Both rank 1 in their respective single branches:
    # id_1 at vector rank 1 (chunk_index=5)
    # id_2 at lexical rank 1 (chunk_index=2)
    v_items = [_create_mock_vector_item(id_1, chunk_index=5)]
    l_items = [_create_mock_lexical_item(id_2, chunk_index=2)]

    fused = service.fuse_ranks(v_items, l_items, top_k=10)

    assert len(fused) == 2
    assert fused[0].rrf_score == fused[1].rrf_score
    # id_2 has lower chunk_index (2 vs 5), so it must break tie first
    assert fused[0].chunk_id == id_2
    assert fused[1].chunk_id == id_1


def test_top_k_bounds_limiting() -> None:
    """Verify top_k parameter strictly caps returned candidate count."""
    service = HybridRetrievalService(rrf_k=60)
    v_items = [_create_mock_vector_item(uuid.uuid4(), chunk_index=i) for i in range(10)]

    fused = service.fuse_ranks(v_items, [], top_k=3)
    assert len(fused) == 3


def test_empty_vector_result_set() -> None:
    """Verify hybrid fusion works smoothly when vector branch returns empty."""
    service = HybridRetrievalService(rrf_k=60)
    chunk_id = uuid.uuid4()
    l_items = [_create_mock_lexical_item(chunk_id)]

    fused = service.fuse_ranks([], l_items, top_k=5)
    assert len(fused) == 1
    assert fused[0].chunk_id == chunk_id
    assert fused[0].vector_rank is None
    assert fused[0].lexical_rank == 1
    assert fused[0].vector_contribution == 0.0
    assert fused[0].lexical_contribution == round(1.0 / 61, 6)


def test_empty_lexical_result_set() -> None:
    """Verify hybrid fusion works smoothly when lexical branch returns empty."""
    service = HybridRetrievalService(rrf_k=60)
    chunk_id = uuid.uuid4()
    v_items = [_create_mock_vector_item(chunk_id)]

    fused = service.fuse_ranks(v_items, [], top_k=5)
    assert len(fused) == 1
    assert fused[0].chunk_id == chunk_id
    assert fused[0].vector_rank == 1
    assert fused[0].lexical_rank is None
    assert fused[0].vector_contribution == round(1.0 / 61, 6)
    assert fused[0].lexical_contribution == 0.0


def test_both_branches_empty() -> None:
    """Verify hybrid fusion returns an empty list when both branches are empty."""
    service = HybridRetrievalService(rrf_k=60)
    fused = service.fuse_ranks([], [], top_k=5)
    assert fused == []


def test_safe_metadata_default_factory() -> None:
    """Verify HybridRetrievalResultItem uses a safe default factory for chunk_metadata."""
    item1 = HybridRetrievalResultItem(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_title="test.txt",
        chunk_index=0,
        text="Test chunk",
        rrf_score=0.016393,
    )
    item2 = HybridRetrievalResultItem(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_title="test.txt",
        chunk_index=1,
        text="Test chunk 2",
        rrf_score=0.016129,
    )
    item1.chunk_metadata["custom_key"] = "test_value"
    assert "custom_key" not in item2.chunk_metadata
    assert item2.chunk_metadata == {}


def test_hybrid_request_validation() -> None:
    """Verify HybridRetrievalRequest bounds and whitespace validation."""
    # Valid
    req = HybridRetrievalRequest(query="valid query", top_k=10)
    assert req.query == "valid query"
    assert req.top_k == 10

    # Whitespace only
    with pytest.raises(ValueError, match="empty or whitespace only"):
        HybridRetrievalRequest(query="   \t\n  ")

    # Out of bounds top_k
    with pytest.raises(ValueError):
        HybridRetrievalRequest(query="valid", top_k=0)
    with pytest.raises(ValueError):
        HybridRetrievalRequest(query="valid", top_k=51)

    # Oversized query
    oversized = "a" * (settings.RETRIEVAL_MAX_QUERY_LENGTH + 1)
    with pytest.raises(ValueError):
        HybridRetrievalRequest(query=oversized, top_k=10)


@pytest.mark.asyncio
async def test_hybrid_service_orchestration_async() -> None:
    """Verify HybridRetrievalService calls vector and lexical services and fuses output."""
    mock_vector = MagicMock()
    mock_lexical = MagicMock()

    kb_id = uuid.uuid4()
    query = "Operating System Scheduling"
    chunk_v = uuid.uuid4()
    chunk_l = uuid.uuid4()

    mock_vector.retrieve = AsyncMock(
        return_value=RetrievalResponse(
            query=query,
            knowledge_base_id=kb_id,
            total_results=1,
            results=[_create_mock_vector_item(chunk_v, chunk_index=0)],
        )
    )
    mock_lexical.retrieve = MagicMock(
        return_value=LexicalRetrievalResponse(
            query=query,
            knowledge_base_id=kb_id,
            total_results=1,
            results=[_create_mock_lexical_item(chunk_l, chunk_index=1)],
        )
    )

    service = HybridRetrievalService(
        vector_service=mock_vector,
        lexical_service=mock_lexical,
        rrf_k=60,
    )

    db = MagicMock()
    resp = await service.retrieve(db=db, kb_id=kb_id, query=query, top_k=5)

    assert resp.knowledge_base_id == kb_id
    assert resp.total_results == 2
    assert resp.rrf_k == 60
    assert len(resp.results) == 2
    mock_vector.retrieve.assert_called_once()
    mock_lexical.retrieve.assert_called_once()
