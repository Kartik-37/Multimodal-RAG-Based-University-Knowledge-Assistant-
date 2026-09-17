"""
Real Local Ollama LLM Generation Integration Test.

Connects to the real local Ollama service at http://127.0.0.1:11434, invokes the
configured qwen3:4b model with an assembled context package, and verifies
grounded completion, response schema conformity, and error handling.

Per Step 13 requirements:
- Verifies Ollama is reachable and qwen3:4b generation succeeds.
- Response is non-empty and conforms to LLMGenerationResponse.
- Model and provider information are correct.
- Assembled context is supplied to the provider.
- Citation marker [source_X] presence is inspected, but absence alone does NOT fail Step 13.
"""

import uuid

import httpx
import pytest

from backend.app.core.config import settings
from backend.app.schemas.context_assembly import (
    ContextAssemblyResult,
    ContextItem,
)
from backend.app.schemas.llm import (
    LLMGenerationRequest,
    LLMGenerationResponse,
)
from backend.app.services.llm.exceptions import (
    LLMConnectionError,
    LLMTimeoutError,
)
from backend.app.services.llm.ollama_provider import OllamaLLMProvider
from backend.app.services.llm.service import LLMGenerationService


def is_ollama_with_model_online(model_name: str = "qwen3:4b") -> bool:
    """Check whether local Ollama service is reachable and has the required model."""
    try:
        resp = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=3.0)
        if resp.status_code != 200:
            return False
        data = resp.json()
        models = [m.get("name", "") for m in data.get("models", [])]
        return any(model_name in m for m in models)
    except Exception:
        return False


@pytest.mark.asyncio
async def test_real_ollama_grounded_generation() -> None:
    """
    Connect to real local Ollama instance and generate a grounded answer using qwen3:4b.
    """
    if not is_ollama_with_model_online(settings.OLLAMA_LLM_MODEL):
        pytest.skip(
            f"Ollama daemon or model '{settings.OLLAMA_LLM_MODEL}' not available at "
            f"{settings.OLLAMA_BASE_URL}. Skipping real integration test."
        )

    # 1. Construct assembled context package (Step 12 output representation)
    item1 = ContextItem(
        source_id="source_1",
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_title="operating_systems_notes.pdf",
        chunk_index=0,
        text=(
            "First-Come, First-Served (FCFS) scheduling is a non-preemptive algorithm "
            "where the process that requests the CPU first is allocated the CPU first."
        ),
        page_number=12,
        section_title="CPU Scheduling",
        chunk_metadata={"unit": 1},
        reranker_rank=1,
        reranker_score=0.92,
        rrf_score=0.032,
        estimated_tokens=25,
    )

    context = ContextAssemblyResult(
        query="What is FCFS scheduling?",
        original_query="tell me about FCFS scheduling algorithm",
        items=[item1],
        total_items=1,
        total_estimated_tokens=25,
        token_budget=1000,
        candidates_received=1,
        items_skipped_budget=0,
        items_deduplicated=0,
    )

    request = LLMGenerationRequest(
        query="What is FCFS scheduling?",
        original_query="tell me about FCFS scheduling algorithm",
        context=context,
        temperature=0.1,
        max_output_tokens=512,
        timeout_seconds=120.0,
    )

    # 2. Invoke real LLM Generation Service
    provider = OllamaLLMProvider(
        base_url=settings.OLLAMA_BASE_URL,
        model_name=settings.OLLAMA_LLM_MODEL,
        default_timeout=120.0,
    )
    service = LLMGenerationService(provider=provider)

    response = await service.generate_grounded_answer(request)

    # 3. Strict verification of requirements
    assert isinstance(response, LLMGenerationResponse)
    assert response.provider == "ollama"
    assert settings.OLLAMA_LLM_MODEL in response.model
    assert response.is_empty_context is False
    assert response.sources_available == ["source_1"]
    assert isinstance(response.sources_referenced, list)

    # Generated answer must be non-empty and substantive
    assert response.answer is not None
    assert len(response.answer.strip()) > 0
    assert response.latency_ms > 0.0

    # Queries preserved
    assert response.query == "What is FCFS scheduling?"
    assert response.original_query == "tell me about FCFS scheduling algorithm"

    # Inspect source citation presence (informational for Step 13, not a hard failure)
    has_citation = "source_1" in response.sources_referenced or "[source_1]" in response.answer
    print(f"\n[Real Ollama Test] Answer generated in {response.latency_ms}ms.")
    print(f"[Real Ollama Test] Citation marker [source_1] detected: {has_citation}")


@pytest.mark.asyncio
async def test_real_ollama_unreachable_connection_error() -> None:
    """Verify that pointing to an unreachable port raises LLMConnectionError cleanly."""
    provider = OllamaLLMProvider(
        base_url="http://127.0.0.1:59999",  # Unused port
        default_timeout=2.0,
    )
    service = LLMGenerationService(provider=provider)

    item1 = ContextItem(
        source_id="source_1",
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_title="doc.pdf",
        chunk_index=0,
        text="Sample text",
        page_number=1,
        section_title=None,
        chunk_metadata={},
        reranker_rank=1,
        reranker_score=0.9,
        rrf_score=0.03,
        estimated_tokens=5,
    )

    context = ContextAssemblyResult(
        query="test query",
        original_query=None,
        items=[item1],
        total_items=1,
        total_estimated_tokens=5,
        token_budget=500,
        candidates_received=1,
        items_skipped_budget=0,
        items_deduplicated=0,
    )

    request = LLMGenerationRequest(
        query="test query",
        context=context,
        timeout_seconds=2.0,
    )

    with pytest.raises((LLMConnectionError, LLMTimeoutError)):
        await service.generate_grounded_answer(request)
