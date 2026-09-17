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

    # Local Storage & Uploads
    STORAGE_DIR: Path = Field(
        default=Path("./storage"),
        description="Filesystem path for local uploaded documents.",
    )
    MAX_UPLOAD_SIZE_BYTES: int = Field(
        default=20 * 1024 * 1024,  # 20 MB default limit
        description="Maximum allowed uploaded file size in bytes.",
    )
    ALLOWED_EXTENSIONS: set[str] = Field(
        default={".pdf", ".docx", ".txt", ".md", ".csv"},
        description="Explicit allowlist of permitted file extensions.",
    )

    # Chunking & Token Estimator Parameters
    CHUNK_TARGET_TOKENS: int = Field(
        default=500,
        description="Target estimated token count per text chunk.",
    )
    CHUNK_OVERLAP_TOKENS: int = Field(
        default=100,
        description="Estimated token overlap between consecutive chunks.",
    )
    CHUNK_MIN_TOKENS: int = Field(
        default=50,
        description="Minimum token threshold to avoid creating tiny meaningless chunks.",
    )

    # Model Infrastructure (Ollama)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_LLM_MODEL: str = "qwen3:4b"
    OLLAMA_EMBED_MODEL: str = "qwen3-embedding:0.6b"

    # LLM Generation Defaults
    LLM_TEMPERATURE: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for grounded generation (low values favor evidence-bounded responses).",
    )
    LLM_MAX_OUTPUT_TOKENS: int = Field(
        default=1024,
        ge=1,
        le=4096,
        description="Maximum generation token budget for the model response.",
    )
    LLM_REQUEST_TIMEOUT_SECONDS: float = Field(
        default=120.0,
        ge=1.0,
        le=300.0,
        description="Timeout in seconds for LLM generation requests.",
    )

    # Verified Embedding Dimension for qwen3-embedding:0.6b
    EMBEDDING_DIM: int = 1024

    # Reranker Model
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RERANK_BATCH_SIZE: int = 32

    # RAG Pipeline Parameters
    RAG_TOP_K_RETRIEVAL: int = 20
    RAG_TOP_K_RERANK: int = 5
    RRF_K: int = 60
    MAX_CONTEXT_TOKENS: int = 2000

    # Vector Retrieval Bounds
    RETRIEVAL_MIN_TOP_K: int = 1
    RETRIEVAL_MAX_TOP_K: int = 50
    RETRIEVAL_MAX_QUERY_LENGTH: int = 1000

    # PostgreSQL Lexical Full-Text Search Configuration
    LEXICAL_LANGUAGE: str = Field(
        default="english",
        description="PostgreSQL full-text search text configuration dictionary (e.g. 'english').",
    )
    LEXICAL_TOP_K: int = Field(
        default=20,
        description="Default number of top lexical matches to return.",
    )
    LEXICAL_MAX_QUERY_LENGTH: int = Field(
        default=1000,
        description="Maximum character length permitted for search queries.",
    )


# Singleton settings instance
settings = Settings()
