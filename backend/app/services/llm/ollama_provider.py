"""
Ollama LLM Provider.

Communicates with a local Ollama HTTP instance (/api/chat) to perform
grounded completions using the configured local model (default: qwen3:4b).
"""

import logging

import httpx

from backend.app.core.config import settings
from backend.app.schemas.llm import LLMProviderResponse
from backend.app.services.llm.base import BaseLLMProvider
from backend.app.services.llm.exceptions import (
    LLMConnectionError,
    LLMModelNotFoundError,
    LLMProviderError,
    LLMResponseError,
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)


class OllamaLLMProvider(BaseLLMProvider):
    """
    Ollama implementation of BaseLLMProvider.

    Interfaces with the local Ollama chat API (/api/chat), supporting system
    prompts, sampling temperature, max output tokens, timeouts, and safe
    metadata extraction.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model_name: str | None = None,
        default_temperature: float | None = None,
        default_max_tokens: int | None = None,
        default_timeout: float | None = None,
    ) -> None:
        self._base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self._model_name = model_name or settings.OLLAMA_LLM_MODEL
        self._default_temperature = (
            default_temperature if default_temperature is not None else settings.LLM_TEMPERATURE
        )
        self._default_max_tokens = (
            default_max_tokens if default_max_tokens is not None else settings.LLM_MAX_OUTPUT_TOKENS
        )
        self._default_timeout = (
            default_timeout if default_timeout is not None else settings.LLM_REQUEST_TIMEOUT_SECONDS
        )

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def base_url(self) -> str:
        return self._base_url

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
        Generate completion using Ollama /api/chat.
        """
        timeout = timeout_seconds if timeout_seconds is not None else self._default_timeout
        temp = temperature if temperature is not None else self._default_temperature
        num_predict = (
            max_output_tokens if max_output_tokens is not None else self._default_max_tokens
        )

        url = f"{self._base_url}/api/chat"
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_prompt},
        ]
        payload = {
            "model": self._model_name,
            "messages": messages,
            "stream": False,
            # qwen3 can expose a separate reasoning channel. The application
            # contract is answer-only, so explicitly disable model thinking
            # output rather than risking internal reasoning reaching the UI.
            "think": False,
            "options": {
                "temperature": temp,
                "num_predict": num_predict,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload)
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            msg = (
                f"Failed to connect to Ollama at {self._base_url}. "
                "Ensure the Ollama service is running locally ('ollama serve')."
            )
            logger.error(msg)
            raise LLMConnectionError(msg) from exc
        except httpx.TimeoutException as exc:
            msg = f"Ollama generation timed out after {timeout} seconds at {self._base_url}."
            logger.error(msg)
            raise LLMTimeoutError(msg) from exc
        except httpx.HTTPError as exc:
            msg = f"HTTP error communicating with Ollama: {exc}"
            logger.error(msg)
            raise LLMProviderError(msg) from exc

        if response.status_code == 404:
            msg = (
                f"Ollama reported model '{self._model_name}' not found. "
                f"Ensure the model is pulled ('ollama pull {self._model_name}')."
            )
            logger.error(msg)
            raise LLMModelNotFoundError(msg)

        if response.status_code != 200:
            msg = (
                f"Ollama API returned unexpected HTTP {response.status_code}: {response.text[:200]}"
            )
            logger.error(msg)
            raise LLMProviderError(msg)

        try:
            data = response.json()
        except Exception as exc:
            msg = f"Failed to parse JSON response from Ollama: {exc}"
            logger.error(msg)
            raise LLMResponseError(msg) from exc

        if not isinstance(data, dict):
            raise LLMResponseError("Ollama response body is not a JSON object.")

        msg_obj = data.get("message")
        if not isinstance(msg_obj, dict):
            raise LLMResponseError("Ollama response missing message object.")

        if "content" not in msg_obj and "thinking" not in msg_obj:
            raise LLMResponseError("Ollama response missing message content.")

        # The UI contract is answer-only. If a provider ignores the explicit
        # think=False request and returns only a private reasoning channel,
        # fail closed instead of exposing chain-of-thought text.
        raw_content = (msg_obj.get("content") or "").strip()
        if not raw_content:
            if msg_obj.get("thinking"):
                raise LLMResponseError(
                    "Ollama returned reasoning without a final answer. Please try again."
                )
            raise LLMResponseError("Ollama returned an empty generation response.")

        if "</think>" in raw_content:
            content = raw_content.split("</think>")[-1].strip()
        else:
            content = raw_content

        if not content:
            raise LLMResponseError("Ollama returned an empty final answer.")

        # Safe diagnostic metadata only: exclude internals, credentials, or raw traces
        prompt_tokens = data.get("prompt_eval_count")
        output_tokens = data.get("eval_count")
        total_duration_ns = data.get("total_duration")
        total_duration_ms = (
            round(total_duration_ns / 1_000_000.0, 2) if total_duration_ns is not None else None
        )

        safe_metadata: dict[str, float] = {}
        if "eval_duration" in data and data["eval_duration"]:
            safe_metadata["eval_duration_ms"] = round(data["eval_duration"] / 1_000_000.0, 2)
        if "prompt_eval_duration" in data and data["prompt_eval_duration"]:
            safe_metadata["prompt_eval_duration_ms"] = round(
                data["prompt_eval_duration"] / 1_000_000.0, 2
            )

        return LLMProviderResponse(
            content=content,
            model=data.get("model", self._model_name),
            prompt_tokens=prompt_tokens,
            output_tokens=output_tokens,
            total_duration_ms=total_duration_ms,
            safe_metadata=safe_metadata,
        )
