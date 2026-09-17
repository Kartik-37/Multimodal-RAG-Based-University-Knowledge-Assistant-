"""Core utilities, configuration, and security foundations."""

from backend.app.core.config import settings
from backend.app.core.telemetry import (
    CorrelationIdMiddleware,
    StructuredJSONFormatter,
    TelemetryManager,
    get_current_kb_id,
    get_current_user_id,
    get_request_id,
    get_telemetry_manager,
    sanitize_headers,
    sanitize_log_data,
    sanitize_string,
    setup_logging,
)

__all__ = [
    "settings",
    "CorrelationIdMiddleware",
    "StructuredJSONFormatter",
    "TelemetryManager",
    "get_request_id",
    "get_current_user_id",
    "get_current_kb_id",
    "get_telemetry_manager",
    "sanitize_headers",
    "sanitize_log_data",
    "sanitize_string",
    "setup_logging",
]
