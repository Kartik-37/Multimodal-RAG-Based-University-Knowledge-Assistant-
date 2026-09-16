"""
Reranking Service Exceptions.

Defines custom exception hierarchy for the CrossEncoder reranking layer.
"""


class RerankerError(Exception):
    """Base exception for all reranking pipeline errors."""

    pass


class RerankerValidationError(RerankerError):
    """Raised when query, input candidates, or returned inference scores fail validation."""

    pass


class RerankerProviderError(RerankerError):
    """Raised when the CrossEncoder inference provider encounters an execution failure."""

    pass
