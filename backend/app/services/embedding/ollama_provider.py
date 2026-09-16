"""
Ollama Embedding Provider.

Communicates with local Ollama instance via HTTP (/api/embed) to generate dense
vector embeddings using the configured local model (default: qwen3-embedding:0.6b).
"""

import logging

import httpx

from backend.app.core.config import settings
from backend.app.services.embedding.base import BaseEmbeddingProvider
from backend.app.services.embedding.exceptions import (
    EmbeddingCountMismatchError,
    EmbeddingError,
    EmbeddingProviderError,
)
from backend.app.services.embedding.validator import validate_embeddings_batch

logger = logging.getLogger(__name__)


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    """
    Ollama implementation of BaseEmbeddingProvider.

    Interfaces with local Ollama HTTP REST API using the modern /api/embed endpoint,
    supporting batched requests, strict dimensionality enforcement, and timeouts.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model_name: str | None = None,
        dimension: int | None = None,
        timeout: float = 30.0,
        batch_size: int = 32,
    ) -> None:
        self._base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self._model_name = model_name or settings.OLLAMA_EMBED_MODEL
        self._dimension = dimension if dimension is not None else settings.EMBEDDING_DIM
        self._timeout = timeout
        self._batch_size = max(1, batch_size)

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def base_url(self) -> str:
        return self._base_url

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Generate dense vector embeddings for a list of textual chunks.

        Texts are processed in batches according to self._batch_size.
        Enforces Correction 3: Exact count verification and strict dimension validation.
        """
        if not texts:
            return []

        all_embeddings: list[list[float]] = []

        # Chunk into manageable batches to avoid HTTP timeout / memory pressure
        for i in range(0, len(texts), self._batch_size):
            batch_texts = texts[i : i + self._batch_size]
            batch_embeddings = await self._embed_batch(batch_texts)
            all_embeddings.extend(batch_embeddings)

        if len(all_embeddings) != len(texts):
            raise EmbeddingCountMismatchError(
                f"Expected {len(texts)} total embeddings, but received {len(all_embeddings)}."
            )

        return all_embeddings

    async def _embed_batch(self, batch_texts: list[str]) -> list[list[float]]:
        """Execute a single batch request to Ollama /api/embed."""
        url = f"{self._base_url}/api/embed"
        payload = {
            "model": self._model_name,
            "input": batch_texts,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload)
        except httpx.ConnectError as exc:
            msg = (
                f"Failed to connect to Ollama at {self._base_url}. "
                "Ensure the Ollama service is running locally ('ollama serve')."
            )
            logger.error(msg)
            raise EmbeddingProviderError(msg) from exc
        except httpx.TimeoutException as exc:
            msg = f"Timeout ({self._timeout}s) while calling Ollama embedding API at {self._base_url}."
            logger.error(msg)
            raise EmbeddingProviderError(msg) from exc
        except httpx.HTTPError as exc:
            msg = f"HTTP error communicating with Ollama: {exc}"
            logger.error(msg)
            raise EmbeddingProviderError(msg) from exc

        if response.status_code != 200:
            error_detail = response.text
            msg = (
                f"Ollama embedding API returned HTTP {response.status_code}: {error_detail}. "
                f"Verify that model '{self._model_name}' is installed ('ollama pull {self._model_name}')."
            )
            logger.error(msg)
            raise EmbeddingProviderError(msg)

        data = response.json()
        raw_embeddings = data.get("embeddings")

        # Validate count and dimensionality strictly
        return validate_embeddings_batch(
            vectors=raw_embeddings,
            expected_count=len(batch_texts),
            expected_dim=self._dimension,
        )

    async def embed_query(self, query: str) -> list[float]:
        """
        Generate dense vector embedding for a single query string.
        """
        results = await self.embed_texts([query])
        if not results:
            raise EmbeddingError("Failed to generate embedding for search query.")
        return results[0]
