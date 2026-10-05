"""
Unit tests for application configuration and environment settings.
"""

from backend.app.core.config import Settings


def test_default_settings() -> None:
    """Verify default settings values match expected project specification."""
    cfg = Settings()
    assert cfg.APP_NAME == "RAG Assistant"
    assert cfg.API_V1_STR == "/api/v1"
    assert cfg.OLLAMA_LLM_MODEL == "qwen3:4b"
    assert cfg.OLLAMA_EMBED_MODEL == "qwen3-embedding:0.6b"
    assert cfg.EMBEDDING_DIM == 1024
    assert cfg.RRF_K == 60
    assert cfg.RAG_TOP_K_RETRIEVAL == 20
    assert cfg.RAG_TOP_K_RERANK == 5


def test_custom_settings_override() -> None:
    """Verify settings can be overridden programmatically or via env."""
    cfg = Settings(APP_NAME="Custom Assistant", EMBEDDING_DIM=768)
    assert cfg.APP_NAME == "Custom Assistant"
    assert cfg.EMBEDDING_DIM == 768
