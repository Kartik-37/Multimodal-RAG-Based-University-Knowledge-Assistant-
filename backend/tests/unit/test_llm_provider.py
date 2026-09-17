"""
Unit Tests for OllamaLLMProvider and BaseLLMProvider.

Verifies:
1. Successful request payload construction and response parsing.
2. Token accounting (prompt_tokens, output_tokens, latency).
3. Connection failure handling (LLMConnectionError).
4. Timeout error handling (LLMTimeoutError).
5. Model not found handling (LLMModelNotFoundError on 404).
6. Provider server error handling (LLMProviderError on 500).
7. Malformed JSON handling (LLMResponseError).
8. Empty response handling (LLMResponseError).
9. Safe metadata isolation.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from backend.app.schemas.llm import LLMProviderResponse
from backend.app.services.llm.base import BaseLLMProvider
from backend.app.services.llm.exceptions import (
    LLMConnectionError,
    LLMModelNotFoundError,
    LLMProviderError,
    LLMResponseError,
    LLMTimeoutError,
)
from backend.app.services.llm.ollama_provider import OllamaLLMProvider


class MockCustomLLMProvider(BaseLLMProvider):
    """Verifies that custom providers can implement BaseLLMProvider cleanly."""

    @property
    def provider_name(self) -> str:
        return "custom_test_provider"

    @property
    def model_name(self) -> str:
        return "custom-model-v1"

    async def generate(
        self,
        system_instruction: str,
        user_prompt: str,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        timeout_seconds: float | None = None,
        **kwargs,
    ) -> LLMProviderResponse:
        return LLMProviderResponse(
            content="Custom provider response [source_1].",
            model=self.model_name,
            prompt_tokens=15,
            output_tokens=5,
            total_duration_ms=120.0,
            safe_metadata={"test": 1.0},
        )


class TestLLMProviderUnit:
    """Unit tests for LLM providers."""

    @pytest.mark.asyncio
    async def test_custom_provider_abstraction(self) -> None:
        """Verify provider abstraction functions independently of Ollama."""
        provider = MockCustomLLMProvider()
        assert provider.provider_name == "custom_test_provider"
        assert provider.model_name == "custom-model-v1"

        res = await provider.generate("system", "prompt")
        assert isinstance(res, LLMProviderResponse)
        assert res.content == "Custom provider response [source_1]."
        assert res.prompt_tokens == 15
        assert res.output_tokens == 5

    @pytest.mark.asyncio
    async def test_ollama_provider_successful_generation(self) -> None:
        """Verify Ollama provider generates completion and parses token metrics."""
        mock_response_data = {
            "model": "qwen3:4b",
            "created_at": "2026-09-17T05:00:00Z",
            "message": {
                "role": "assistant",
                "content": "Operating systems manage CPU and memory resources [source_1].",
            },
            "done": True,
            "total_duration": 2500000000,  # 2.5s -> 2500ms
            "load_duration": 500000000,
            "prompt_eval_count": 42,
            "prompt_eval_duration": 300000000,
            "eval_count": 18,
            "eval_duration": 1700000000,
        }

        mock_resp = httpx.Response(
            status_code=200,
            json=mock_response_data,
            request=httpx.Request("POST", "http://localhost:11434/api/chat"),
        )

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            provider = OllamaLLMProvider(
                base_url="http://localhost:11434",
                model_name="qwen3:4b",
                default_temperature=0.2,
                default_max_tokens=512,
                default_timeout=30.0,
            )

            result = await provider.generate(
                system_instruction="System grounding prompt",
                user_prompt="What does an OS manage?",
                temperature=0.1,
                max_output_tokens=256,
            )

            assert isinstance(result, LLMProviderResponse)
            assert result.content == "Operating systems manage CPU and memory resources [source_1]."
            assert result.model == "qwen3:4b"
            assert result.prompt_tokens == 42
            assert result.output_tokens == 18
            assert result.total_duration_ms == 2500.0
            assert result.safe_metadata["eval_duration_ms"] == 1700.0

            # Verify outgoing HTTP payload structure
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args.kwargs
            json_payload = call_kwargs["json"]
            assert json_payload["model"] == "qwen3:4b"
            assert json_payload["stream"] is False
            assert json_payload["messages"] == [
                {"role": "system", "content": "System grounding prompt"},
                {"role": "user", "content": "What does an OS manage?"},
            ]
            assert json_payload["options"]["temperature"] == 0.1
            assert json_payload["options"]["num_predict"] == 256

    @pytest.mark.asyncio
    async def test_ollama_provider_connection_failure(self) -> None:
        """Verify connection failure raises LLMConnectionError."""
        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection refused")

            provider = OllamaLLMProvider(base_url="http://localhost:9999")
            with pytest.raises(LLMConnectionError, match="Failed to connect to Ollama"):
                await provider.generate("sys", "user")

    @pytest.mark.asyncio
    async def test_ollama_provider_timeout_error(self) -> None:
        """Verify timeout raises LLMTimeoutError."""
        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Read timed out")

            provider = OllamaLLMProvider(base_url="http://localhost:11434")
            with pytest.raises(LLMTimeoutError, match="Ollama generation timed out"):
                await provider.generate("sys", "user")

    @pytest.mark.asyncio
    async def test_ollama_provider_model_not_found_404(self) -> None:
        """Verify HTTP 404 raises LLMModelNotFoundError."""
        mock_resp = httpx.Response(
            status_code=404,
            text="model 'nonexistent_model' not found",
            request=httpx.Request("POST", "http://localhost:11434/api/chat"),
        )
        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            provider = OllamaLLMProvider(model_name="nonexistent_model")
            with pytest.raises(LLMModelNotFoundError, match="reported model.*not found"):
                await provider.generate("sys", "user")

    @pytest.mark.asyncio
    async def test_ollama_provider_server_error_500(self) -> None:
        """Verify HTTP 500 raises LLMProviderError."""
        mock_resp = httpx.Response(
            status_code=500,
            text="Internal server error",
            request=httpx.Request("POST", "http://localhost:11434/api/chat"),
        )
        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            provider = OllamaLLMProvider()
            with pytest.raises(LLMProviderError, match="returned unexpected HTTP 500"):
                await provider.generate("sys", "user")

    @pytest.mark.asyncio
    async def test_ollama_provider_malformed_json_response(self) -> None:
        """Verify non-JSON response raises LLMResponseError."""
        mock_resp = httpx.Response(
            status_code=200,
            content=b"not-json-content",
            request=httpx.Request("POST", "http://localhost:11434/api/chat"),
        )
        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            provider = OllamaLLMProvider()
            with pytest.raises(LLMResponseError, match="Failed to parse JSON response"):
                await provider.generate("sys", "user")

    @pytest.mark.asyncio
    async def test_ollama_provider_missing_content(self) -> None:
        """Verify missing message.content raises LLMResponseError."""
        mock_resp = httpx.Response(
            status_code=200,
            json={"done": True, "message": {}},
            request=httpx.Request("POST", "http://localhost:11434/api/chat"),
        )
        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            provider = OllamaLLMProvider()
            with pytest.raises(LLMResponseError, match="missing message content"):
                await provider.generate("sys", "user")

    @pytest.mark.asyncio
    async def test_ollama_provider_empty_string_response(self) -> None:
        """Verify empty string response raises LLMResponseError."""
        mock_resp = httpx.Response(
            status_code=200,
            json={"done": True, "message": {"content": "   \n\t "}},
            request=httpx.Request("POST", "http://localhost:11434/api/chat"),
        )
        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            provider = OllamaLLMProvider()
            with pytest.raises(LLMResponseError, match="returned an empty generation response"):
                await provider.generate("sys", "user")
