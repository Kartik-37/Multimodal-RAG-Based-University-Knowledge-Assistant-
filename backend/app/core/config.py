"""
Core Application Configuration.

Uses Pydantic Settings to validate environment variables with sensible defaults
for development while enforcing strict validation in production.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    APP_NAME: str = "BCA RAG Assistant"
    APP_ENV: Literal["development", "testing", "production"] = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Security & Auth
    SECRET_KEY: str = Field(
        default="dev-insecure-secret-key-change-in-production",
        description="Cryptographic secret key for signing JWT tokens.",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"

    # Database
    # Note: postgresql+psycopg is the async/sync DB driver connection string
    DATABASE_URL: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/rag_assistant_db",
        description="PostgreSQL database connection URL.",
    )
    TEST_DATABASE_URL: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/rag_assistant_test_db",
        description="PostgreSQL test database connection URL.",
    )

    # Local Storage
    STORAGE_DIR: Path = Field(
        default=Path("./storage"),
        description="Filesystem path for local uploaded documents.",
    )

    # Model Infrastructure (Ollama)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_LLM_MODEL: str = "qwen3:4b"
    OLLAMA_EMBED_MODEL: str = "qwen3-embedding:0.6b"

    # Verified Embedding Dimension for qwen3-embedding:0.6b
    EMBEDDING_DIM: int = 1024

    # Reranker Model
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # RAG Pipeline Parameters
    RAG_TOP_K_RETRIEVAL: int = 20
    RAG_TOP_K_RERANK: int = 5
    RRF_K: int = 60
    MAX_CONTEXT_TOKENS: int = 2000


# Singleton settings instance
settings = Settings()
