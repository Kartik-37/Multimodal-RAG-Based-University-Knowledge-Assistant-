"""
Unit Tests for Embedding Provider and Vector Validation.

Verifies:
1. 1024-dimensional valid embeddings accepted.
2. 1023-dimensional embeddings rejected with EmbeddingDimensionError.
3. 1025-dimensional embeddings rejected with EmbeddingDimensionError.
4. Non-numeric / NaN / Inf values rejected with EmbeddingError.
5. Count mismatches (Correction 3) explicitly fail with EmbeddingCountMismatchError.
6. Empty text input handling.
7. Provider failure handling and error propagation.
8. Batch embedding generation with custom batch sizes.
"""

import math

import pytest

from backend.app.services.embedding.base import BaseEmbeddingProvider
from backend.app.services.embedding.exceptions import (
    EmbeddingCountMismatchError,
    EmbeddingDimensionError,
    EmbeddingError,
    EmbeddingProviderError,
)
from backend.app.services.embedding.validator import validate_embedding, validate_embeddings_batch


class MockTestEmbeddingProvider(BaseEmbeddingProvider):
    """Deterministic in-memory embedding provider for unit testing."""

    def __init__(
        self,
        dimension: int = 1024,
        model_name: str = "test-embed-1024",
        fail: bool = False,
        dimension_override: int | None = None,
        count_mismatch_offset: int = 0,
    ) -> None:
        self._dim = dimension
        self._model = model_name
        self.fail = fail
        self.dimension_override = dimension_override
        self.count_mismatch_offset = count_mismatch_offset

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return self._model

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if self.fail:
            raise EmbeddingProviderError("Simulated embedding service unreachable.")
        if not texts:
            return []

        target_dim = self.dimension_override if self.dimension_override is not None else self._dim
        count = max(0, len(texts) + self.count_mismatch_offset)

        results: list[list[float]] = []
        for i in range(count):
            # Deterministic reproducible vector
            vec = [(float(i * 0.01 + j * 0.001)) for j in range(target_dim)]
            results.append(vec)

        # Enforce validation in provider contract
        return validate_embeddings_batch(
            vectors=results,
            expected_count=len(texts),
            expected_dim=self._dim,
        )

    async def embed_query(self, query: str) -> list[float]:
        res = await self.embed_texts([query])
        return res[0]


# ------------------------------------------------------------------------------
# Validator Tests
# ------------------------------------------------------------------------------


def test_valid_1024_dimension_embedding_accepted() -> None:
    """Verify that a valid 1024-dimensional float vector is accepted."""
    vec = [0.05] * 1024
    validated = validate_embedding(vec, expected_dim=1024)
    assert len(validated) == 1024
    assert validated[0] == pytest.approx(0.05)


def test_1023_dimension_embedding_rejected() -> None:
    """Verify that an undersized vector (1023) is rejected without padding."""
    vec = [0.1] * 1023
    with pytest.raises(
        EmbeddingDimensionError, match="Embedding dimension mismatch: expected 1024, got 1023"
    ):
        validate_embedding(vec, expected_dim=1024)


def test_1025_dimension_embedding_rejected() -> None:
    """Verify that an oversized vector (1025) is rejected without truncation."""
    vec = [0.1] * 1025
    with pytest.raises(
        EmbeddingDimensionError, match="Embedding dimension mismatch: expected 1024, got 1025"
    ):
        validate_embedding(vec, expected_dim=1024)


def test_none_or_non_sequence_vector_rejected() -> None:
    """Verify None or invalid types raise EmbeddingError."""
    with pytest.raises(EmbeddingError, match="Embedding vector is None"):
        validate_embedding(None, expected_dim=1024)

    with pytest.raises(EmbeddingError, match="Embedding vector must be a sequence"):
        validate_embedding("not-a-vector", expected_dim=1024)  # type: ignore


def test_non_numeric_elements_rejected() -> None:
    """Verify vectors containing non-numeric values are rejected."""
    vec = [0.1] * 1023 + ["invalid_string"]  # type: ignore
    with pytest.raises(EmbeddingError, match="Embedding vector contains non-numeric value"):
        validate_embedding(vec, expected_dim=1024)


def test_nan_and_inf_elements_rejected() -> None:
    """Verify vectors containing NaN or Inf are rejected."""
    vec_nan = [0.1] * 1023 + [float("nan")]
    with pytest.raises(EmbeddingError, match="Embedding vector contains invalid non-finite value"):
        validate_embedding(vec_nan, expected_dim=1024)

    vec_inf = [0.1] * 1023 + [float("inf")]
    with pytest.raises(EmbeddingError, match="Embedding vector contains invalid non-finite value"):
        validate_embedding(vec_inf, expected_dim=1024)


def test_batch_count_mismatch_rejected() -> None:
    """Verify Correction 3: Mismatched returned vector count raises EmbeddingCountMismatchError."""
    texts = ["chunk 1", "chunk 2", "chunk 3"]
    vectors = [[0.1] * 1024, [0.2] * 1024]  # 2 vectors for 3 texts

    with pytest.raises(
        EmbeddingCountMismatchError,
        match="Embedding count mismatch: requested 3 texts, but received 2 embeddings",
    ):
        validate_embeddings_batch(vectors, expected_count=len(texts), expected_dim=1024)


# ------------------------------------------------------------------------------
# Provider Contract Tests
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_provider_successful_batch_embedding() -> None:
    """Verify mock provider embeds multiple chunks and returns exact 1024-d vectors."""
    provider = MockTestEmbeddingProvider(dimension=1024)
    chunks = ["Operating Systems Unit 1", "Memory Management Unit 2", "File Systems Unit 3"]

    embeddings = await provider.embed_texts(chunks)
    assert len(embeddings) == 3
    for emb in embeddings:
        assert len(emb) == 1024
        assert all(isinstance(x, float) and not math.isnan(x) for x in emb)


@pytest.mark.asyncio
async def test_provider_query_embedding() -> None:
    """Verify mock provider embeds a single query."""
    provider = MockTestEmbeddingProvider(dimension=1024)
    query_vector = await provider.embed_query("What is virtual memory?")
    assert len(query_vector) == 1024
    assert isinstance(query_vector[0], float)


@pytest.mark.asyncio
async def test_provider_empty_texts_handling() -> None:
    """Verify empty input list returns empty result list without errors."""
    provider = MockTestEmbeddingProvider(dimension=1024)
    assert await provider.embed_texts([]) == []


@pytest.mark.asyncio
async def test_provider_dimension_mismatch_rejected() -> None:
    """Verify provider generating wrong dimension (e.g. 768) is caught and rejected."""
    provider = MockTestEmbeddingProvider(dimension=1024, dimension_override=768)
    with pytest.raises(EmbeddingDimensionError):
        await provider.embed_texts(["sample text"])


@pytest.mark.asyncio
async def test_provider_count_mismatch_rejected() -> None:
    """Verify provider returning fewer embeddings than requested chunks is rejected."""
    provider = MockTestEmbeddingProvider(dimension=1024, count_mismatch_offset=-1)
    with pytest.raises(EmbeddingCountMismatchError):
        await provider.embed_texts(["chunk 1", "chunk 2"])


@pytest.mark.asyncio
async def test_provider_failure_raises_embedding_provider_error() -> None:
    """Verify provider failure is cleanly wrapped in EmbeddingProviderError."""
    provider = MockTestEmbeddingProvider(dimension=1024, fail=True)
    with pytest.raises(EmbeddingProviderError, match="Simulated embedding service unreachable"):
        await provider.embed_texts(["sample text"])
