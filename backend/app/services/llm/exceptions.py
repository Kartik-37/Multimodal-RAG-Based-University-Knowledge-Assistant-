"""
LLM Generation Service Exceptions.

Domain exceptions for the provider-independent LLM generation layer.
Ensures internal error details are cleanly categorized and never leak
stack traces or secrets to users.
"""


class LLMError(Exception):
    """Base exception for all LLM generation errors."""

    pass


class LLMProviderError(LLMError):
    """Raised when an external or local LLM provider encounters an execution failure."""

    pass


class LLMConnectionError(LLMProviderError):
    """Raised when the LLM provider service is unreachable (connection refused/network error)."""

    pass


class LLMTimeoutError(LLMProviderError):
    """Raised when an LLM generation request exceeds its configured timeout window."""

    pass


class LLMModelNotFoundError(LLMProviderError):
    """Raised when the requested LLM model is not available or not installed."""

    pass


class LLMResponseError(LLMProviderError):
    """Raised when the LLM provider returns a malformed, invalid, or empty response."""

    pass
