"""
Embedding Package.

Exports provider abstraction, Ollama implementation, vector validators,
exceptions, and high-level service coordinators.
"""

from backend.app.services.embedding.base import BaseEmbeddingProvider
from backend.app.services.embedding.exceptions import (
    EmbeddingCountMismatchError,
    EmbeddingDimensionError,
    EmbeddingError,
    EmbeddingProviderError,
)
from backend.app.services.embedding.ollama_provider import OllamaEmbeddingProvider
from backend.app.services.embedding.service import EmbeddingService, get_embedding_service
from backend.app.services.embedding.validator import validate_embedding, validate_embeddings_batch

__all__ = [
    "BaseEmbeddingProvider",
    "OllamaEmbeddingProvider",
    "EmbeddingService",
    "get_embedding_service",
    "validate_embedding",
    "validate_embeddings_batch",
    "EmbeddingError",
    "EmbeddingDimensionError",
    "EmbeddingCountMismatchError",
    "EmbeddingProviderError",
]
