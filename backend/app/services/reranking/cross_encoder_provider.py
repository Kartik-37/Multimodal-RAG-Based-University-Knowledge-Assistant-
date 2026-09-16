"""
Hugging Face CrossEncoder Reranker Provider.

Implements the BaseRerankerProvider contract using a local sentence-transformers
CrossEncoder model. Model loading is thread-safe and lazy; inference is executed
in a worker thread via asyncio.to_thread to maintain an unblocked FastAPI event loop.
"""

import asyncio
import logging
import threading
from typing import Any

from backend.app.core.config import settings
from backend.app.services.reranking.base import BaseRerankerProvider
from backend.app.services.reranking.exceptions import (
    RerankerProviderError,
    RerankerValidationError,
)
from backend.app.services.reranking.validator import RerankValidator

logger = logging.getLogger(__name__)


class HuggingFaceCrossEncoderProvider(BaseRerankerProvider):
    """
    Local CrossEncoder reranking provider utilizing Hugging Face models via sentence-transformers.
    """

    def __init__(
        self,
        model_name: str | None = None,
        batch_size: int | None = None,
        device: str | None = None,
    ) -> None:
        """
        Initialize the CrossEncoder provider configuration.

        Args:
            model_name: Hugging Face model repository name or local directory.
                        Defaults to settings.RERANKER_MODEL.
            batch_size: Batch size for model inference evaluation.
                        Defaults to settings.RERANK_BATCH_SIZE.
            device: Computing device ('cpu', 'cuda', etc.). Defaults to None (auto-detect).
        """
        self._model_name = model_name or settings.RERANKER_MODEL
        self._batch_size = batch_size or settings.RERANK_BATCH_SIZE
        self._device = device
        self._model: Any = None
        self._lock = threading.Lock()

    @property
    def model_name(self) -> str:
        """Return the configured model repository name."""
        return self._model_name

    def _get_or_load_model(self) -> Any:
        """
        Thread-safe lazy initialization of the local CrossEncoder model.

        Returns:
            Instantiated CrossEncoder instance.

        Raises:
            RerankerProviderError: If the model fails to load.
        """
        if self._model is None:
            with self._lock:
                if self._model is None:
                    try:
                        logger.info(
                            "Loading local CrossEncoder model: %s (device=%s)",
                            self._model_name,
                            self._device,
                        )
                        from sentence_transformers import CrossEncoder

                        self._model = CrossEncoder(
                            self._model_name,
                            device=self._device,
                        )
                        logger.info("Successfully loaded CrossEncoder model: %s", self._model_name)
                    except Exception as exc:
                        logger.exception(
                            "Failed to load CrossEncoder model '%s': %s",
                            self._model_name,
                            exc,
                        )
                        raise RerankerProviderError(
                            f"Failed to load CrossEncoder model '{self._model_name}': {exc}"
                        ) from exc
        return self._model

    async def compute_scores(self, query: str, texts: list[str]) -> list[float]:
        """
        Compute joint relevance scores for the query against candidate texts using
        the local CrossEncoder.

        Args:
            query: User query string.
            texts: Candidate chunk text strings.

        Returns:
            list[float]: Raw finite scores in 1-to-1 input candidate order.
                         Scores are NOT rounded.

        Raises:
            RerankerValidationError: If query or outputs fail validation.
            RerankerProviderError: If model execution fails.
        """
        clean_query = RerankValidator.validate_query(query)

        if not texts:
            return []

        # Ensure model is initialized
        try:
            model = self._get_or_load_model()
        except RerankerProviderError:
            raise
        except Exception as exc:
            raise RerankerProviderError(f"Model initialization error: {exc}") from exc

        # Construct query-text pairs for cross-encoding
        pairs = [[clean_query, text] for text in texts]

        # Execute inference in non-blocking worker thread
        def _predict() -> Any:
            return model.predict(
                pairs,
                batch_size=self._batch_size,
                show_progress_bar=False,
            )

        try:
            raw_scores = await asyncio.to_thread(_predict)
        except Exception as exc:
            logger.exception("Inference failed during CrossEncoder prediction: %s", exc)
            raise RerankerProviderError(f"CrossEncoder inference failed: {exc}") from exc

        # Convert numpy array or iterable output to python floats
        if hasattr(raw_scores, "tolist"):
            raw_list = raw_scores.tolist()
        else:
            raw_list = list(raw_scores)

        if isinstance(raw_list, (int, float)):
            scores = [float(raw_list)]
        else:
            scores = [float(s) for s in raw_list]

        # Validate score length, numeric type, and finite constraints
        try:
            RerankValidator.validate_rerank_scores(scores, len(texts))
        except RerankerValidationError as val_err:
            logger.error("Reranker score validation error: %s", val_err)
            raise

        return scores
