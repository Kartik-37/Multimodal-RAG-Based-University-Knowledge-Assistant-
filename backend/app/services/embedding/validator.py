"""
Vector Validation Service.

Validates vector dimensionality, numeric validity, absence of NaN/Inf values,
and strict 1-to-1 cardinality between input texts and output embeddings.
"""

import math
from collections.abc import Sequence

from backend.app.services.embedding.exceptions import (
    EmbeddingCountMismatchError,
    EmbeddingDimensionError,
    EmbeddingError,
)


def validate_embedding(vector: Sequence[float] | None, expected_dim: int) -> list[float]:
    """
    Validate an individual embedding vector against strict dimensional and numeric criteria.

    Args:
        vector: The raw vector sequence returned by the provider.
        expected_dim: The expected vector dimensionality (e.g. 1024).

    Returns:
        The validated vector as a list of floats.

    Raises:
        EmbeddingError: If vector is None, not a sequence, or contains non-numeric/NaN/Inf values.
        EmbeddingDimensionError: If vector length != expected_dim.
    """
    if vector is None:
        raise EmbeddingError("Embedding vector is None.")

    if not isinstance(vector, Sequence) or isinstance(vector, (str, bytes)):
        raise EmbeddingError(
            f"Embedding vector must be a sequence of numbers, got {type(vector).__name__}."
        )

    actual_dim = len(vector)
    if actual_dim != expected_dim:
        raise EmbeddingDimensionError(
            f"Embedding dimension mismatch: expected {expected_dim}, got {actual_dim}. "
            "Vectors will neither be padded nor truncated."
        )

    validated: list[float] = []
    for idx, val in enumerate(vector):
        if not isinstance(val, (int, float)):
            raise EmbeddingError(
                f"Embedding vector contains non-numeric value at index {idx}: {type(val).__name__} ({val!r})."
            )
        float_val = float(val)
        if math.isnan(float_val) or math.isinf(float_val):
            raise EmbeddingError(
                f"Embedding vector contains invalid non-finite value ({float_val}) at index {idx}."
            )
        validated.append(float_val)

    return validated


def validate_embeddings_batch(
    vectors: list[Sequence[float]] | None,
    expected_count: int,
    expected_dim: int,
) -> list[list[float]]:
    """
    Validate a batch of embedding vectors against input count and dimensionality criteria.

    Enforces Correction 3: The number of returned embeddings must exactly match
    the number of requested texts. Never silently map mismatched vectors to chunks.

    Args:
        vectors: The list of raw vectors returned by the provider.
        expected_count: Number of input texts sent for embedding.
        expected_dim: Expected dimension of each vector.

    Returns:
        List of validated float vectors.

    Raises:
        EmbeddingCountMismatchError: If len(vectors) != expected_count.
        EmbeddingDimensionError: If any vector's length != expected_dim.
        EmbeddingError: If any vector contains invalid numeric values.
    """
    if vectors is None:
        raise EmbeddingError("Provider returned None instead of a list of embeddings.")

    if not isinstance(vectors, list):
        raise EmbeddingError(f"Embeddings batch must be a list, got {type(vectors).__name__}.")

    actual_count = len(vectors)
    if actual_count != expected_count:
        raise EmbeddingCountMismatchError(
            f"Embedding count mismatch: requested {expected_count} texts, but received {actual_count} embeddings. "
            "Batch cannot be mapped safely."
        )

    return [validate_embedding(vec, expected_dim) for vec in vectors]
