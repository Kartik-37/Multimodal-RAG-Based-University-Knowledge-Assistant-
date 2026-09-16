"""
Reranker Validation Utilities.

Validates input queries, candidate text sequences, and inference output scores
to prevent malformed values, shape mismatches, or non-finite numbers from entering
the ranking pipeline.
"""

import math
from typing import Any

from backend.app.services.reranking.exceptions import RerankerValidationError


class RerankValidator:
    """Validator for cross-encoder inference inputs and outputs."""

    @staticmethod
    def validate_query(query: str) -> str:
        """
        Validate that the query is a non-empty, non-whitespace string.

        Args:
            query: User search query.

        Returns:
            Normalized stripped query string.

        Raises:
            RerankerValidationError: If query is empty or purely whitespace.
        """
        if not isinstance(query, str):
            raise RerankerValidationError("Query must be a string.")
        stripped = query.strip()
        if not stripped:
            raise RerankerValidationError("Query cannot be empty or whitespace only.")
        return stripped

    @staticmethod
    def validate_rerank_scores(scores: list[Any], expected_count: int) -> None:
        """
        Verify that inference scores match the candidate count and contain only finite floats.

        Args:
            scores: Raw score list produced by the inference model.
            expected_count: Expected number of candidate texts.

        Raises:
            RerankerValidationError: If score count mismatches expected_count or if any score
                                    is NaN, infinite, or non-numeric.
        """
        if not isinstance(scores, list):
            raise RerankerValidationError(
                f"Expected scores to be a list, got {type(scores).__name__}."
            )

        if len(scores) != expected_count:
            raise RerankerValidationError(
                f"Reranker returned {len(scores)} scores for {expected_count} input texts."
            )

        for idx, score in enumerate(scores):
            # Exclude booleans which are technically a subclass of int in Python
            if isinstance(score, bool) or not isinstance(score, (int, float)):
                raise RerankerValidationError(
                    f"Score at index {idx} is not numeric: {score} ({type(score).__name__})."
                )
            if not math.isfinite(score):
                raise RerankerValidationError(
                    f"Score at index {idx} is non-finite (NaN or Inf): {score}."
                )
