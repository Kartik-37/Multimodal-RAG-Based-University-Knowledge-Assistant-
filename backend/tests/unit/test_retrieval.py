"""
Unit Tests for Vector Retrieval Layer (Step 7).

Tests query normalization, bounds validation, embedding provider integration,
dimension checking, provider failure handling, and result mapping.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from backend.app.core.config import settings
from backend.app.models.document import DocumentChunk
from backend.app.schemas.retrieval import RetrievalRequest, RetrievalResponse
from backend.app.services.embedding.base import BaseEmbeddingProvider
from backend.app.services.embedding.exceptions import (
    EmbeddingProviderError,
)
from backend.app.services.retrieval import (
    RetrievalProviderError,
    RetrievalValidationError,
    VectorRetrievalService,
)


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Test embedding provider with controllable responses."""

    def __init__(self, dimension: int = 1024, model_name: str = "test-embed:0.6b") -> None:
        self._dim = dimension
        self._model = model_name
        self.embed_query_mock = AsyncMock(return_value=[0.1] * dimension)
        self.embed_texts_mock = AsyncMock(return_value=[[0.1] * dimension])

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return self._model

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return await self.embed_texts_mock(texts)

    async def embed_query(self, query: str) -> list[float]:
        return await self.embed_query_mock(query)


def test_retrieval_request_valid() -> None:
    """Valid search query and default top_k accepted."""
    req = RetrievalRequest(query="What is database normalization?")
    assert req.query == "What is database normalization?"
    assert req.top_k == settings.RAG_TOP_K_RETRIEVAL


def test_retrieval_request_custom_top_k() -> None:
    """Valid custom top_k within bounds accepted."""
    req = RetrievalRequest(query="Binary search trees", top_k=10)
    assert req.top_k == 10


@pytest.mark.parametrize("bad_query", ["", "   ", "\t\n  \r\n"])
def test_retrieval_request_rejects_empty_or_whitespace_query(bad_query: str) -> None:
    """Empty or whitespace-only queries must fail validation."""
    with pytest.raises(ValidationError):
        RetrievalRequest(query=bad_query)


def test_retrieval_request_rejects_excessive_query_length() -> None:
    """Query exceeding maximum permitted character length must fail validation."""
    oversized = "a" * (settings.RETRIEVAL_MAX_QUERY_LENGTH + 1)
    with pytest.raises(ValidationError):
        RetrievalRequest(query=oversized)


@pytest.mark.parametrize("bad_k", [0, -1, -10, 51, 100])
def test_retrieval_request_rejects_out_of_bounds_top_k(bad_k: int) -> None:
    """top_k below minimum or above maximum must fail validation."""
    with pytest.raises(ValidationError):
        RetrievalRequest(query="valid query", top_k=bad_k)


def test_service_validate_query_normalizes_whitespace() -> None:
    """Surrounding whitespace must be stripped cleanly."""
    service = VectorRetrievalService(provider=MockEmbeddingProvider())
    assert service.validate_query("  What is SQL injection?  \n") == "What is SQL injection?"


def test_service_validate_query_unicode_preserved() -> None:
    """Unicode characters and mathematical symbols must be preserved."""
    service = VectorRetrievalService(provider=MockEmbeddingProvider())
    unicode_q = "Graph theory: λ(G) ≤ κ(G) ≤ δ(G) algorithm?"
    assert service.validate_query(unicode_q) == unicode_q


def test_service_validate_query_empty_raises_retrieval_validation_error() -> None:
    """Service method raises RetrievalValidationError on blank query."""
    service = VectorRetrievalService(provider=MockEmbeddingProvider())
    with pytest.raises(RetrievalValidationError):
        service.validate_query("   ")


def test_service_validate_query_length_exceeded_raises() -> None:
    """Service method raises RetrievalValidationError on oversized query."""
    service = VectorRetrievalService(provider=MockEmbeddingProvider())
    with pytest.raises(RetrievalValidationError):
        service.validate_query("x" * (settings.RETRIEVAL_MAX_QUERY_LENGTH + 5))


@pytest.mark.parametrize("bad_k", [0, -5, 55])
def test_service_validate_top_k_bounds(bad_k: int) -> None:
    """Service method raises RetrievalValidationError on invalid top_k."""
    service = VectorRetrievalService(provider=MockEmbeddingProvider())
    with pytest.raises(RetrievalValidationError):
        service.validate_top_k(bad_k)


@pytest.mark.asyncio
async def test_service_embed_query_delegation() -> None:
    """Retrieval service generates embedding via BaseEmbeddingProvider."""
    provider = MockEmbeddingProvider()
    service = VectorRetrievalService(provider=provider)

    mock_db = MagicMock()
    mock_db.execute.return_value.all.return_value = []

    kb_id = uuid.uuid4()
    await service.retrieve(
        db=mock_db,
        kb_id=kb_id,
        query="Explain relational algebra",
        top_k=5,
    )

    provider.embed_query_mock.assert_awaited_once_with("Explain relational algebra")


@pytest.mark.asyncio
async def test_service_dimension_mismatch_raises_retrieval_provider_error() -> None:
    """If provider returns an invalid vector dimension, error is raised."""
    provider = MockEmbeddingProvider(dimension=1024)
    # Return 512 dimensions instead of configured 1024
    provider.embed_query_mock.return_value = [0.1] * 512

    service = VectorRetrievalService(provider=provider)
    mock_db = MagicMock()

    with pytest.raises(RetrievalProviderError) as exc_info:
        await service.retrieve(
            db=mock_db,
            kb_id=uuid.uuid4(),
            query="Valid query",
        )
    assert "does not match expected dimension" in str(exc_info.value)


@pytest.mark.asyncio
async def test_service_provider_failure_raises_controlled_error() -> None:
    """Embedding provider network or status failures raise controlled RetrievalProviderError."""
    provider = MockEmbeddingProvider()
    provider.embed_query_mock.side_effect = EmbeddingProviderError(
        "Connection refused to Ollama at http://localhost:11434"
    )

    service = VectorRetrievalService(provider=provider)
    mock_db = MagicMock()

    with pytest.raises(RetrievalProviderError) as exc_info:
        await service.retrieve(
            db=mock_db,
            kb_id=uuid.uuid4(),
            query="Valid query",
        )
    assert "Embedding generation failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_service_result_mapping_and_exact_similarity_conversion() -> None:
    """
    Verifies direct mathematical conversion:
    similarity = 1.0 - cosine_distance
    without silent clamping or modification.
    """
    provider = MockEmbeddingProvider()
    service = VectorRetrievalService(provider=provider)

    chunk_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    kb_id = uuid.uuid4()

    mock_chunk = MagicMock(spec=DocumentChunk)
    mock_chunk.id = chunk_id
    mock_chunk.document_id = doc_id
    mock_chunk.knowledge_base_id = kb_id
    mock_chunk.chunk_index = 2
    mock_chunk.text = "Relational database normalization is the process of structuring data."
    mock_chunk.page_number = 3
    mock_chunk.section_title = "3.2 Normal Forms"
    mock_chunk.chunk_metadata = {"source": "database_systems.pdf"}

    cosine_distance_val = 0.154321
    expected_similarity = round(1.0 - cosine_distance_val, 6)

    mock_db = MagicMock()
    mock_db.execute.return_value.all.return_value = [
        (mock_chunk, "database_systems.pdf", cosine_distance_val)
    ]

    response = await service.retrieve(
        db=mock_db,
        kb_id=kb_id,
        query="What is normalization?",
        top_k=5,
    )

    assert isinstance(response, RetrievalResponse)
    assert response.total_results == 1
    item = response.results[0]
    assert item.chunk_id == chunk_id
    assert item.document_id == doc_id
    assert item.knowledge_base_id == kb_id
    assert item.document_title == "database_systems.pdf"
    assert item.chunk_index == 2
    assert item.page_number == 3
    assert item.section_title == "3.2 Normal Forms"
    assert item.cosine_distance == round(cosine_distance_val, 6)
    assert item.similarity == expected_similarity
