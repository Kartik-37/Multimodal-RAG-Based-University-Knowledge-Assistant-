"""
Embedding Exceptions.

Defines structured domain exceptions for embedding generation, vector validation,
provider connectivity, and batch dimension/count mismatches.
"""


class EmbeddingError(Exception):
    """Base exception for all embedding generation and validation errors."""

    pass


class EmbeddingDimensionError(EmbeddingError):
    """Raised when an embedding vector's dimensionality does not match the configured dimension."""

    pass


class EmbeddingCountMismatchError(EmbeddingError):
    """Raised when the number of returned embeddings does not match the requested text count."""

    pass


class EmbeddingProviderError(EmbeddingError):
    """Raised when an external embedding provider (e.g. Ollama) is unreachable or fails."""

    pass
