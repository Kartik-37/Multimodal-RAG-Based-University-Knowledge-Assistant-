"""
LLM Generation Pydantic Schemas.

Defines data transfer models for grounded LLM generation requests,
provider responses, and finalized grounded generation responses.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.core.config import settings
from backend.app.schemas.context_assembly import ContextAssemblyResult


class LLMProviderResponse(BaseModel):
    """
    Standardized response emitted by any BaseLLMProvider implementation.
    """

    model_config = ConfigDict(from_attributes=True)

    content: str = Field(
        ...,
        description="Generated textual content from the model.",
    )
    model: str = Field(
        ...,
        description="Model identifier that produced the response.",
    )
    prompt_tokens: int | None = Field(
        default=None,
        description="Number of prompt tokens evaluated, if reported by provider.",
    )
    output_tokens: int | None = Field(
        default=None,
        description="Number of generated output tokens, if reported by provider.",
    )
    total_duration_ms: float | None = Field(
        default=None,
        description="Execution duration reported by provider in milliseconds.",
    )
    safe_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Safe diagnostic provider metrics (strictly excluding credentials, secrets, or internal paths).",
    )


class LLMGenerationRequest(BaseModel):
    """
    Request model for generating a grounded answer from assembled context.
    """

    model_config = ConfigDict(from_attributes=True)

    query: str = Field(
        ...,
        min_length=1,
        description="Active search or processed query.",
    )
    original_query: str | None = Field(
        default=None,
        description="Raw user query prior to query processing if available.",
    )
    context: ContextAssemblyResult = Field(
        ...,
        description="Assembled, token-budgeted, and deduplicated context package from Step 12.",
    )
    model: str | None = Field(
        default=None,
        description="Optional model identifier override (defaults to settings.OLLAMA_LLM_MODEL).",
    )
    temperature: float = Field(
        default_factory=lambda: settings.LLM_TEMPERATURE,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for grounded generation (low values favor evidence-bounded output).",
    )
    max_output_tokens: int = Field(
        default_factory=lambda: settings.LLM_MAX_OUTPUT_TOKENS,
        ge=1,
        le=4096,
        description="Maximum generation token budget.",
    )
    timeout_seconds: float = Field(
        default_factory=lambda: settings.LLM_REQUEST_TIMEOUT_SECONDS,
        ge=1.0,
        le=300.0,
        description="Timeout in seconds for provider generation requests.",
    )


class LLMGenerationResponse(BaseModel):
    """
    Grounded answer response containing generated text, attribution metadata,
    and safe execution metrics.
    """

    model_config = ConfigDict(from_attributes=True)

    answer: str = Field(
        ...,
        description="Generated grounded answer.",
    )
    query: str = Field(
        ...,
        description="Active search query.",
    )
    original_query: str | None = Field(
        default=None,
        description="Raw user query if available.",
    )
    provider: str = Field(
        ...,
        description="Name of the LLM provider (e.g. 'ollama').",
    )
    model: str = Field(
        ...,
        description="Name of the model utilized (e.g. 'qwen3:4b').",
    )
    sources_available: list[str] = Field(
        default_factory=list,
        description="List of source identifiers available in the supplied context (e.g. ['source_1', 'source_2']).",
    )
    sources_referenced: list[str] = Field(
        default_factory=list,
        description="Candidate source tags extracted from generated answer text for Step 14 citation validation.",
    )
    is_empty_context: bool = Field(
        default=False,
        description="True if generation occurred on empty/insufficient context.",
    )
    prompt_tokens: int | None = Field(
        default=None,
        description="Prompt token count if available.",
    )
    output_tokens: int | None = Field(
        default=None,
        description="Generated output token count if available.",
    )
    latency_ms: float = Field(
        ...,
        ge=0.0,
        description="Total round-trip latency in milliseconds.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Safe diagnostic metadata (excluding internal paths, credentials, and raw exception traces).",
    )
