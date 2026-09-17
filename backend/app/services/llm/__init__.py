"""
LLM Generation Services Package.
"""

from backend.app.services.llm.base import BaseLLMProvider
from backend.app.services.llm.exceptions import (
    LLMConnectionError,
    LLMError,
    LLMModelNotFoundError,
    LLMProviderError,
    LLMResponseError,
    LLMTimeoutError,
)
from backend.app.services.llm.ollama_provider import OllamaLLMProvider
from backend.app.services.llm.prompt_builder import (
    SYSTEM_GROUNDING_INSTRUCTION,
    GroundedPromptBuilder,
)
from backend.app.services.llm.service import (
    LLMGenerationService,
    get_llm_generation_service,
)

__all__ = [
    "BaseLLMProvider",
    "OllamaLLMProvider",
    "GroundedPromptBuilder",
    "SYSTEM_GROUNDING_INSTRUCTION",
    "LLMGenerationService",
    "get_llm_generation_service",
    "LLMError",
    "LLMProviderError",
    "LLMConnectionError",
    "LLMTimeoutError",
    "LLMModelNotFoundError",
    "LLMResponseError",
]
