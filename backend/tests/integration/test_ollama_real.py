"""
Real Local Ollama Integration Test.

Connects to the real local Ollama service at http://127.0.0.1:11434, invokes the
configured qwen3-embedding:0.6b model, and verifies that real 1024-dimensional
vector embeddings are generated.

Skips gracefully if the local Ollama daemon is not active.
"""

import httpx
import pytest

from backend.app.core.config import settings
from backend.app.services.embedding.ollama_provider import OllamaEmbeddingProvider


def is_ollama_online() -> bool:
    """Check whether local Ollama service is reachable."""
    try:
        resp = httpx.get(f"{settings.OLLAMA_BASE_URL}/", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


@pytest.mark.asyncio
async def test_real_ollama_embedding_generation() -> None:
    """
    Connect to real local Ollama instance and generate a 1024-dimensional embedding.
    Validates that the local qwen3-embedding:0.6b model behaves as specified.
    """
    if not is_ollama_online():
        pytest.skip(
            f"Ollama daemon not reachable at {settings.OLLAMA_BASE_URL}. Skipping real integration test."
        )

    provider = OllamaEmbeddingProvider(
        base_url=settings.OLLAMA_BASE_URL,
        model_name=settings.OLLAMA_EMBED_MODEL,
        dimension=settings.EMBEDDING_DIM,
    )

    test_chunks = [
        "Operating Systems Unit 1 covers Process Management and CPU scheduling.",
        "Database Management Systems covers relational normalization and ACID transactions.",
    ]

    embeddings = await provider.embed_texts(test_chunks)

    assert len(embeddings) == 2, f"Expected 2 embeddings, received {len(embeddings)}"
    for emb in embeddings:
        assert len(emb) == 1024, f"Expected 1024 dimensions, got {len(emb)}"
        assert all(isinstance(x, float) for x in emb)

    # Test single query embedding
    query_vector = await provider.embed_query("What is virtual memory paging?")
    assert len(query_vector) == 1024
    assert isinstance(query_vector[0], float)
