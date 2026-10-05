"""
Core Application Configuration.

Uses Pydantic Settings to validate environment variables with sensible defaults
for development while enforcing strict validation in production.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
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
    APP_NAME: str = "RAG Assistant"
    APP_ENV: Literal["development", "testing", "production"] = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # CORS Settings (Explicit origins for NiceGUI/API client communication)
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ],
        description="Allowed CORS origins for web clients. Wildcard is never combined with credentials.",
    )

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
    OLLAMA_EMBED_BATCH_SIZE: int = Field(
        default=4,
        ge=1,
        description="Maximum chunk count per Ollama embedding batch to prevent local inference timeouts.",
    )
    OLLAMA_EMBED_TIMEOUT: float = Field(
        default=120.0,
        ge=5.0,
        description="HTTP timeout in seconds for Ollama embedding batch calls.",
    )

    # LLM Generation Defaults
    LLM_TEMPERATURE: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for grounded generation (low values favor evidence-bounded responses).",
    )
    LLM_MAX_OUTPUT_TOKENS: int = Field(
        default=384,
        ge=1,
        le=4096,
        description="Maximum generation token budget for the model response.",
    )
    LLM_REQUEST_TIMEOUT_SECONDS: float = Field(
        default=180.0,
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

    # Step 14 Grounding & Citation Validation Configuration
    GROUNDING_MIN_OVERLAP_THRESHOLD: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum content-word recall threshold required to consider a claim supported by cited evidence.",
    )
    GROUNDING_MAX_ANSWER_LENGTH: int = Field(
        default=10000,
        ge=100,
        le=100000,
        description="Maximum character length of generated answer processed by the validator.",
    )
    GROUNDING_MAX_CLAIMS_PER_ANSWER: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Maximum number of sentence claims parsed and validated per answer.",
    )
    GROUNDING_MAX_CITATIONS_PER_ANSWER: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of citation occurrences parsed and validated per answer.",
    )
    GROUNDING_MAX_EVIDENCE_ITEMS: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of context evidence items processed for cross-verification.",
    )

    # Step 18 Rate Limiting & Abuse Protection Configuration
    RATE_LIMIT_ENABLED: bool = Field(
        default=True,
        description="Master switch to enable or disable server-side rate limiting.",
    )
    TRUSTED_PROXIES: set[str] = Field(
        default_factory=set,
        description="Explicit allowlist of trusted upstream reverse proxy IP addresses.",
    )
    RATE_LIMIT_STORAGE_TYPE: Literal["postgres", "memory"] = Field(
        default="postgres",
        description="Backend storage for rate-limit state ('postgres' or 'memory').",
    )

    # Authentication Endpoints (Unauthenticated, IP-based, Fail-Closed)
    RATE_LIMIT_LOGIN_MAX_REQUESTS: int = Field(
        default=20,
        ge=1,
        description="Maximum allowed login attempts per IP within the window.",
    )
    RATE_LIMIT_LOGIN_WINDOW_SECONDS: int = Field(
        default=60,
        ge=1,
        description="Window duration in seconds for login rate limiting.",
    )
    RATE_LIMIT_REGISTER_MAX_REQUESTS: int = Field(
        default=20,
        ge=1,
        description="Maximum allowed registration attempts per IP within the window.",
    )
    RATE_LIMIT_REGISTER_WINDOW_SECONDS: int = Field(
        default=60,
        ge=1,
        description="Window duration in seconds for registration rate limiting.",
    )

    # Chat & Full RAG Pipeline (Authenticated User-based)
    RATE_LIMIT_CHAT_MAX_REQUESTS: int = Field(
        default=30,
        ge=1,
        description="Maximum allowed chat RAG pipeline queries per authenticated user within the window.",
    )
    RATE_LIMIT_CHAT_WINDOW_SECONDS: int = Field(
        default=60,
        ge=1,
        description="Window duration in seconds for chat rate limiting.",
    )

    # Retrieval Operations (Vector, Lexical, Hybrid, Reranking - Authenticated User-based)
    RATE_LIMIT_RETRIEVAL_MAX_REQUESTS: int = Field(
        default=60,
        ge=1,
        description="Maximum allowed retrieval inspection requests per user within the window.",
    )
    RATE_LIMIT_RETRIEVAL_WINDOW_SECONDS: int = Field(
        default=60,
        ge=1,
        description="Window duration in seconds for retrieval rate limiting.",
    )

    # Document Upload (ADMIN Authenticated)
    RATE_LIMIT_UPLOAD_MAX_REQUESTS: int = Field(
        default=20,
        ge=1,
        description="Maximum allowed document uploads per admin within the window.",
    )
    RATE_LIMIT_UPLOAD_WINDOW_SECONDS: int = Field(
        default=60,
        ge=1,
        description="Window duration in seconds for document upload rate limiting.",
    )

    # Document Indexing (ADMIN Authenticated)
    RATE_LIMIT_INDEXING_MAX_REQUESTS: int = Field(
        default=20,
        ge=1,
        description="Maximum allowed indexing triggers per admin within the window.",
    )
    RATE_LIMIT_INDEXING_WINDOW_SECONDS: int = Field(
        default=60,
        ge=1,
        description="Window duration in seconds for document indexing rate limiting.",
    )

    # Security Failure Modes (Fail-Closed vs Fail-Open)
    RATE_LIMIT_AUTH_FAIL_CLOSED: bool = Field(
        default=True,
        description="Whether authentication endpoints fail closed (HTTP 503) if rate-limit storage fails.",
    )
    RATE_LIMIT_EXPENSIVE_FAIL_CLOSED: bool = Field(
        default=False,
        description="Whether expensive RAG endpoints fail closed (HTTP 503) or fail open with telemetry error.",
    )

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """
        Enforce strict production configuration invariants:
        1. In production, DEBUG must be False.
        2. In production, SECRET_KEY must not be the default insecure development placeholder.
        3. In production, SECRET_KEY must be at least 32 characters long.
        """
        if self.APP_ENV == "production":
            if self.DEBUG:
                raise ValueError("DEBUG must be False in production environment.")
            if self.SECRET_KEY == "dev-insecure-secret-key-change-in-production":
                raise ValueError(
                    "SECRET_KEY cannot be the default insecure placeholder in production."
                )
            if len(self.SECRET_KEY) < 32:
                raise ValueError("SECRET_KEY must be at least 32 characters in production.")
        return self


# Singleton settings instance
settings = Settings()
