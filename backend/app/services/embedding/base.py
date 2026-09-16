"""
Embedding Provider Abstraction.

Defines the abstract interface for embedding providers (Ollama, local mock, etc.)
ensuring the application core remains decoupled from specific provider implementations.
"""

from abc import ABC, abstractmethod


class BaseEmbeddingProvider(ABC):
    """
    Abstract interface for embedding generation.

    All embedding providers must implement this contract to ensure consistent
    dimension validation, batching, and error handling across the application.
    """

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Generate dense vector embeddings for a list of textual chunks.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors, where each vector is a list of floats matching
            the configured dimension.

        Raises:
            EmbeddingCountMismatchError: If returned vectors count != len(texts).
            EmbeddingDimensionError: If any vector dimension != self.dimension.
            EmbeddingProviderError: If the provider is unreachable or returns an error.
        """
        pass

    @abstractmethod
    async def embed_query(self, query: str) -> list[float]:
        """
        Generate dense vector embedding for a single search query.

        Args:
            query: The search query string to embed.

        Returns:
            A single embedding vector matching the configured dimension.

        Raises:
            EmbeddingDimensionError: If vector dimension != self.dimension.
            EmbeddingProviderError: If the provider is unreachable or returns an error.
        """
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """The expected vector dimensionality (e.g. 1024 for qwen3-embedding:0.6b)."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """The identifier of the underlying embedding model."""
        pass
