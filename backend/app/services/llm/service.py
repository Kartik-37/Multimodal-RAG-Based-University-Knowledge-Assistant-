"""
Grounded LLM Generation Service.

Orchestrates the grounded generation stage:
1. Validates context availability with deterministic empty-context fast-path.
2. Formats system instructions and untrusted evidence via GroundedPromptBuilder.
3. Invokes the provider-independent BaseLLMProvider.
4. Extracts candidate source references for Step 14 citation validation.
5. Returns safe execution metadata without leaking internal secrets.
"""

import re
import threading
import time

from backend.app.schemas.llm import (
    LLMGenerationRequest,
    LLMGenerationResponse,
)
from backend.app.services.llm.base import BaseLLMProvider
from backend.app.services.llm.ollama_provider import OllamaLLMProvider
from backend.app.services.llm.prompt_builder import GroundedPromptBuilder

# Matches attribution markers formatted as [source_1], [source_2], etc.
_SOURCE_REF_REGEX = re.compile(r"\[(source_\d+)\]")

SAFE_INSUFFICIENT_EVIDENCE_ANSWER = (
    "I could not find any relevant information in the available documents to answer your question."
)


class LLMGenerationService:
    """
    Orchestration service for grounded LLM answer generation.
    """

    def __init__(
        self,
        provider: BaseLLMProvider | None = None,
        prompt_builder: GroundedPromptBuilder | None = None,
    ) -> None:
        self.provider = provider or OllamaLLMProvider()
        self.prompt_builder = prompt_builder or GroundedPromptBuilder()

    async def generate_grounded_answer(
        self, request: LLMGenerationRequest
    ) -> LLMGenerationResponse:
        """
        Generate a grounded answer for the provided query and assembled context.

        Args:
            request: Validated LLMGenerationRequest containing assembled context,
                     query, and generation options.

        Returns:
            LLMGenerationResponse with answer, source metadata, and token accounting.
        """
        # 1. Deterministic empty-context fast-path
        if request.context.total_items == 0 or not request.context.items:
            return LLMGenerationResponse(
                answer=SAFE_INSUFFICIENT_EVIDENCE_ANSWER,
                query=request.query,
                original_query=request.original_query,
                provider=self.provider.provider_name,
                model=request.model or self.provider.model_name,
                sources_available=[],
                sources_referenced=[],
                is_empty_context=True,
                prompt_tokens=0,
                output_tokens=0,
                latency_ms=0.0,
                metadata={
                    "fast_path": True,
                    "reason": "empty_context",
                },
            )

        # 2. Extract available source identifiers
        sources_available = [item.source_id for item in request.context.items]

        # 3. Build system instruction and untrusted evidence prompt
        system_instruction = self.prompt_builder.build_system_instruction()
        user_prompt = self.prompt_builder.build_user_prompt(
            query=request.query, context=request.context
        )

        # 4. Invoke the configured LLM provider
        start_time = time.perf_counter()
        provider_resp = await self.provider.generate(
            system_instruction=system_instruction,
            user_prompt=user_prompt,
            temperature=request.temperature,
            max_output_tokens=request.max_output_tokens,
            timeout_seconds=request.timeout_seconds,
        )
        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        # 5. Extract referenced candidate source identifiers for Step 14 citation validation
        raw_matches = _SOURCE_REF_REGEX.findall(provider_resp.content)
        seen_refs: set[str] = set()
        sources_referenced: list[str] = []
        for ref in raw_matches:
            if ref not in seen_refs:
                seen_refs.add(ref)
                sources_referenced.append(ref)

        # 6. Safe metadata assembly (excluding internals or raw traces)
        safe_metadata = dict(provider_resp.safe_metadata)
        safe_metadata["sources_available_count"] = len(sources_available)
        safe_metadata["sources_referenced_count"] = len(sources_referenced)

        return LLMGenerationResponse(
            answer=provider_resp.content,
            query=request.query,
            original_query=request.original_query,
            provider=self.provider.provider_name,
            model=provider_resp.model,
            sources_available=sources_available,
            sources_referenced=sources_referenced,
            is_empty_context=False,
            prompt_tokens=provider_resp.prompt_tokens,
            output_tokens=provider_resp.output_tokens,
            latency_ms=latency_ms,
            metadata=safe_metadata,
        )


# Thread-safe singleton
_service_instance: LLMGenerationService | None = None
_service_lock = threading.Lock()


def get_llm_generation_service() -> LLMGenerationService:
    """
    Return the singleton LLMGenerationService instance.
    """
    global _service_instance
    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = LLMGenerationService()
    return _service_instance
