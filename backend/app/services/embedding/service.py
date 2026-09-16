"""
Embedding Service.

Provides a unified high-level interface for embedding generation across the application,
abstracting provider lifecycle and validation details.
"""

import asyncio

from backend.app.services.embedding.base import BaseEmbeddingProvider
from backend.app.services.embedding.ollama_provider import OllamaEmbeddingProvider


class EmbeddingService:
    """
    Application-level service for generating validated dense vector embeddings.
    """

    def __init__(self, provider: BaseEmbeddingProvider | None = None) -> None:
        self._provider = provider or OllamaEmbeddingProvider()

    @property
    def provider(self) -> BaseEmbeddingProvider:
        return self._provider

    @property
    def dimension(self) -> int:
        return self._provider.dimension

    @property
    def model_name(self) -> str:
        return self._provider.model_name

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate and validate embeddings for a list of texts."""
        return await self._provider.embed_texts(texts)

    async def embed_query(self, query: str) -> list[float]:
        """Generate and validate an embedding for a search query."""
        return await self._provider.embed_query(query)

    def embed_texts_sync(self, texts: list[str]) -> list[list[float]]:
        """Synchronous wrapper for embedding texts when invoked from non-async contexts."""
        return asyncio.run(self.embed_texts(texts))


_default_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Singleton getter for the default application embedding service."""
    global _default_embedding_service
    if _default_embedding_service is None:
        _default_embedding_service = EmbeddingService()
    return _default_embedding_service
