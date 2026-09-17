"""
Base LLM Provider Interface.

Defines the abstract interface for LLM providers (Ollama, local mock,
cloud providers, etc.) ensuring that the core RAG application remains
strictly decoupled from specific provider implementations.
"""

from abc import ABC, abstractmethod

from backend.app.schemas.llm import LLMProviderResponse


class BaseLLMProvider(ABC):
    """
    Abstract contract for grounded LLM answer generation.

    All LLM providers must implement this contract to ensure consistent
    parameter validation, timeout handling, error reporting, and token accounting.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """The canonical name of this provider (e.g. 'ollama', 'openai')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """The identifier of the active LLM model (e.g. 'qwen3:4b')."""
        pass

    @abstractmethod
    async def generate(
        self,
        system_instruction: str,
        user_prompt: str,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        timeout_seconds: float | None = None,
        **kwargs,
    ) -> LLMProviderResponse:
        """
        Generate a text completion given system directives and user prompt.

        Args:
            system_instruction: System grounding directives and constraints.
            user_prompt: User question with untrusted evidence payload.
            temperature: Sampling temperature override.
            max_output_tokens: Maximum token generation budget override.
            timeout_seconds: Timeout in seconds for the request.
            **kwargs: Optional provider-specific arguments.

        Returns:
            LLMProviderResponse containing generated text and safe metrics.

        Raises:
            LLMConnectionError: If the provider is unreachable.
            LLMTimeoutError: If the request times out.
            LLMModelNotFoundError: If the model is not found/installed.
            LLMResponseError: If the response is empty or invalid.
            LLMProviderError: On any other provider failure.
        """
        pass
