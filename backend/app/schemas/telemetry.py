"""
Telemetry and Observability Pydantic Schemas.

Defines standardized data transfer models for structured events, RAG stage metrics,
and pipeline telemetry, adhering to strict security and privacy standards.
"""

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class TelemetryEvent(BaseModel):
    """
    Generic structured telemetry event envelope.
    """

    event_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique event identifier.",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO-8601 UTC timestamp of event generation.",
    )
    event_name: str = Field(..., description="Canonical name of the telemetry event.")
    request_id: str = Field(..., description="Correlation request ID.")
    user_id: str | None = Field(default=None, description="Authenticated user ID if available.")
    knowledge_base_id: str | None = Field(
        default=None, description="Knowledge base ID if applicable."
    )
    status: Literal["SUCCESS", "FAILURE"] = Field(..., description="Execution status.")
    duration_ms: float = Field(default=0.0, ge=0.0, description="Duration in milliseconds.")
    error_category: str | None = Field(
        default=None, description="Standardized error category if failed."
    )
    attributes: dict[str, Any] = Field(
        default_factory=dict,
        description="Sanitized event attributes (no credentials/PII/raw text).",
    )


class RAGStageTelemetry(BaseModel):
    """
    Telemetry for an individual RAG pipeline stage.
    """

    stage_name: str = Field(..., description="Name of the RAG pipeline stage.")
    status: Literal["SUCCESS", "FAILURE"] = Field(..., description="Stage execution status.")
    duration_ms: float = Field(default=0.0, ge=0.0, description="Stage latency in milliseconds.")
    candidate_count: int | None = Field(
        default=None, description="Number of items produced or processed by stage."
    )
    error_category: str | None = Field(
        default=None, description="Categorized error reason if failed."
    )
    attributes: dict[str, Any] = Field(default_factory=dict, description="Safe stage attributes.")


class RAGPipelineTelemetry(BaseModel):
    """
    Comprehensive end-to-end RAG pipeline telemetry event.
    """

    event_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique event identifier.",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO-8601 UTC timestamp.",
    )
    event_name: str = Field(default="rag_pipeline_execution", description="Canonical event name.")
    request_id: str = Field(..., description="Correlation request ID.")
    user_id: str | None = Field(default=None, description="Authenticated user ID if available.")
    knowledge_base_id: str = Field(..., description="Target knowledge base ID.")
    status: Literal["SUCCESS", "FAILURE"] = Field(..., description="Overall pipeline status.")
    total_duration_ms: float = Field(
        default=0.0, ge=0.0, description="Total pipeline latency in milliseconds."
    )
    stages: dict[str, RAGStageTelemetry] = Field(
        default_factory=dict,
        description="Telemetry records for each executed RAG stage.",
    )
    retrieval_candidate_count: int = Field(
        default=0, ge=0, description="Candidates retrieved by hybrid search."
    )
    reranked_candidate_count: int = Field(
        default=0, ge=0, description="Candidates preserved after reranking."
    )
    assembled_context_count: int = Field(
        default=0, ge=0, description="Chunks assembled into context."
    )
    is_empty_context: bool = Field(
        default=False, description="Whether retrieval yielded an empty context."
    )
    is_refusal: bool = Field(
        default=False, description="Whether pipeline generated a safe refusal."
    )
    grounding_status: str = Field(default="UNKNOWN", description="Deterministic grounding outcome.")
    citation_count: int = Field(
        default=0, ge=0, description="Number of valid citations referenced."
    )
    model: str | None = Field(default=None, description="LLM model identifier used for generation.")
    error_category: str | None = Field(
        default=None, description="Failure category if pipeline failed."
    )
    attributes: dict[str, Any] = Field(default_factory=dict, description="Safe summary attributes.")
