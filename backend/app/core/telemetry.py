"""
Core Telemetry, Structured Logging, and Observability Framework.

Provides:
- Async-safe context variables for request correlation and tenant isolation tracing.
- Security-conscious data and string sanitization preventing secret, credential,
  and complete prompt/document/answer logging.
- Deterministic error categorization reusing Steps 7–16 domain exceptions.
- Pluggable telemetry exporter abstraction (Logging and In-Memory collectors).
- Production-grade structured JSON log formatter.
- FastAPI CorrelationIdMiddleware for HTTP request correlation and header propagation.
"""

import collections
import contextvars
import json
import logging
import re
import threading
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from backend.app.schemas.telemetry import (
    RAGPipelineTelemetry,
    TelemetryEvent,
)

# -------------------------------------------------------------------------
# 1. Async-Safe Context Variables
# -------------------------------------------------------------------------

request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id_ctx", default=None
)
user_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "user_id_ctx", default=None
)
kb_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("kb_id_ctx", default=None)


def get_request_id() -> str:
    """Return the active correlation/request ID or fallback if not in a request context."""
    val = request_id_ctx.get()
    return val if val is not None else "no-request-id"


def set_request_id(req_id: str | None) -> contextvars.Token:
    """Set the active correlation/request ID for the current async context."""
    return request_id_ctx.set(req_id)


def get_current_user_id() -> str | None:
    """Return the authenticated user ID active in the current request context."""
    return user_id_ctx.get()


def set_current_user_id(uid: str | None) -> contextvars.Token:
    """Set the authenticated user ID for the current async context."""
    return user_id_ctx.set(uid)


def get_current_kb_id() -> str | None:
    """Return the knowledge base ID active in the current request context."""
    return kb_id_ctx.get()


def set_current_kb_id(kbid: str | None) -> contextvars.Token:
    """Set the knowledge base ID for the current async context."""
    return kb_id_ctx.set(kbid)


# -------------------------------------------------------------------------
# 2. Security Redaction & Data Sanitization
# -------------------------------------------------------------------------

REDACTED_VALUE = "[REDACTED]"
REDACTED_PASSWORD_HASH = "[REDACTED_PASSWORD_HASH]"

# Compiled regex scrubbers for free-form strings, error messages, and exception tracebacks
_DATABASE_URL_PATTERN = re.compile(
    r"(?i)(postgresql(?:\+[a-z0-9]+)?://[^:\s/@]+:)(.*)(@[a-zA-Z0-9.\-_]+(?::[0-9]+)?/[^\s]*)",
)

_BEARER_TOKEN_PATTERN = re.compile(
    r"(?i)(bearer\s+)[a-zA-Z0-9\-_.~+/]+=*",
)
_BASIC_AUTH_PATTERN = re.compile(
    r"(?i)(basic\s+)[a-zA-Z0-9+/=]+",
)
_PASSWORD_KEY_VALUE_PATTERN = re.compile(
    r"(?i)(password|token|secret|api_key|apikey)\s*[:=]\s*(?:'[^']*'|\"[^\"]*\"|[^\s,;&]+)",
)
_ARGON2_HASH_PATTERN = re.compile(
    r"\$argon2id\$v=\d+\$m=\d+,t=\d+,p=\d+\$[A-Za-z0-9+/]+\$[A-Za-z0-9+/]+",
)


# HTTP header keys that must always be redacted
SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "proxy-authorization",
}

# Substrings in dictionary keys indicating sensitive credential/auth data
SENSITIVE_KEY_SUBSTRINGS = {
    "password",
    "password_hash",
    "hashed_password",
    "token",
    "secret",
    "cookie",
    "api_key",
    "apikey",
    "credential",
    "database_url",
    "dsn",
    "private_key",
    "auth_header",
}

# Dictionary keys representing raw document content, prompts, or model completions
# that must NEVER be logged in full text
RAW_TEXT_KEYS = {
    "document_content",
    "raw_content",
    "chunk_text",
    "content",
    "prompt",
    "raw_prompt",
    "system_prompt",
    "user_prompt",
    "answer",
    "model_response",
    "response_text",
    "completion",
}


def sanitize_string(text: str) -> str:
    """
    Sanitize sensitive information from a string, such as embedded database passwords,
    bearer tokens, basic auth credentials, and Argon2 password hashes.
    """
    if not text:
        return text

    # 1. Database URLs with user:password@host
    text = _DATABASE_URL_PATTERN.sub(r"\1[REDACTED]\3", text)
    # 2. Bearer tokens
    text = _BEARER_TOKEN_PATTERN.sub(r"\1[REDACTED]", text)
    # 3. Basic auth
    text = _BASIC_AUTH_PATTERN.sub(r"\1[REDACTED]", text)
    # 4. Key=value credential pairs
    text = _PASSWORD_KEY_VALUE_PATTERN.sub(r"\1=[REDACTED]", text)
    # 5. Argon2 password hashes
    text = _ARGON2_HASH_PATTERN.sub(REDACTED_PASSWORD_HASH, text)

    return text


def sanitize_headers(headers: Any) -> dict[str, str]:
    """
    Sanitize HTTP request/response headers, redacting Authorization, Cookie, and sensitive headers.
    """
    result: dict[str, str] = {}
    items = headers.items() if hasattr(headers, "items") else headers
    for k, v in items:
        k_str = str(k)
        if k_str.lower() in SENSITIVE_HEADERS:
            result[k_str] = REDACTED_VALUE
        else:
            result[k_str] = sanitize_string(str(v))
    return result


def sanitize_log_data(data: Any, max_string_preview: int = 150) -> Any:
    """
    Recursively sanitize dictionaries, lists, and primitives for safe logging.
    - Redacts sensitive credential keys with '[REDACTED]'.
    - Prevents raw document, prompt, and full model output leakage by replacing with safe metadata.
    - Sanitizes string values with regex scrubbers.
    - Clamps excessively long string values.
    """
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            k_str = str(k).lower()

            # 1. Check for sensitive credential fields
            if any(sub in k_str for sub in SENSITIVE_KEY_SUBSTRINGS):
                sanitized[k] = REDACTED_VALUE
                continue

            # 2. Check for raw content / prompt / model response fields
            if k_str in RAW_TEXT_KEYS:
                if isinstance(v, str):
                    sanitized[k] = f"[REDACTED_TEXT: {len(v)} chars]"
                else:
                    sanitized[k] = "[REDACTED_TEXT]"
                continue

            sanitized[k] = sanitize_log_data(v, max_string_preview=max_string_preview)
        return sanitized

    elif isinstance(data, (list, tuple, set)):
        return [sanitize_log_data(item, max_string_preview=max_string_preview) for item in data]

    elif isinstance(data, str):
        cleaned = sanitize_string(data)
        if len(cleaned) > max_string_preview:
            return cleaned[:max_string_preview] + f"... [truncated, total {len(cleaned)} chars]"
        return cleaned

    elif isinstance(data, (int, float, bool)) or data is None:
        return data

    else:
        cleaned = sanitize_string(str(data))
        if len(cleaned) > max_string_preview:
            return cleaned[:max_string_preview] + f"... [truncated, total {len(cleaned)} chars]"
        return cleaned


# -------------------------------------------------------------------------
# 3. Deterministic Error Categorization
# -------------------------------------------------------------------------


def categorize_exception(exc: Exception) -> str:
    """
    Map domain and system exceptions to standardized telemetry error categories.
    Reuses existing exception classes from Steps 7–16 without inventing new error types.
    """
    exc_name = exc.__class__.__name__

    # 1. Timeout errors
    if "timeout" in exc_name.lower():
        return "TIMEOUT_ERROR"

    # 2. Validation errors
    if "validation" in exc_name.lower() or "valueerror" in exc_name.lower():
        return "VALIDATION_ERROR"

    # 3. Provider errors (LLM, Embedding, CrossEncoder, Retrieval)
    if (
        "provider" in exc_name.lower()
        or "connection" in exc_name.lower()
        or "notfound" in exc_name.lower()
    ):
        return "PROVIDER_ERROR"

    # 4. Database errors
    if (
        "sqlalchemy" in exc.__class__.__module__.lower()
        or "database" in exc_name.lower()
        or "psycopg" in exc.__class__.__module__.lower()
    ):
        return "DATABASE_ERROR"

    # 5. HTTP errors / Authorization / Rate Limiting
    if "http" in exc_name.lower():
        status_code = getattr(exc, "status_code", None)
        if status_code in (401, 403, 404):
            return "AUTHORIZATION_ERROR"
        if status_code == 429:
            return "RATE_LIMIT_EXCEEDED"
        return "HTTP_ERROR"

    return "UNEXPECTED_ERROR"


# -------------------------------------------------------------------------
# 4. Telemetry Exporters & Management
# -------------------------------------------------------------------------


class BaseTelemetryExporter(ABC):
    """Abstract base class for telemetry exporters."""

    @abstractmethod
    def export_event(self, event: TelemetryEvent) -> None:
        """Export a generic telemetry event."""
        pass

    @abstractmethod
    def export_pipeline(self, event: RAGPipelineTelemetry) -> None:
        """Export an end-to-end RAG pipeline telemetry event."""
        pass


class LoggingTelemetryExporter(BaseTelemetryExporter):
    """
    Default exporter that logs telemetry events as structured JSON via standard logging.
    """

    def __init__(self, logger_name: str = "rag.telemetry") -> None:
        self.logger = logging.getLogger(logger_name)

    def export_event(self, event: TelemetryEvent) -> None:
        try:
            event_dict = event.model_dump()
            sanitized_dict = sanitize_log_data(event_dict)
            self.logger.info(
                f"Telemetry event: {event.event_name}",
                extra={"telemetry_event": sanitized_dict, "structured": True},
            )
        except Exception:
            # Observability must never crash the application
            pass

    def export_pipeline(self, event: RAGPipelineTelemetry) -> None:
        try:
            event_dict = event.model_dump()
            sanitized_dict = sanitize_log_data(event_dict)
            self.logger.info(
                f"RAG pipeline telemetry: {event.status}",
                extra={"rag_pipeline_telemetry": sanitized_dict, "structured": True},
            )
        except Exception:
            pass


class InMemoryTelemetryExporter(BaseTelemetryExporter):
    """
    Thread-safe in-memory exporter for testing, benchmarking, and internal inspection.
    """

    def __init__(self, max_events: int = 1000) -> None:
        self.events: collections.deque = collections.deque(maxlen=max_events)
        self.pipeline_events: collections.deque = collections.deque(maxlen=max_events)
        self._lock = threading.Lock()

    def export_event(self, event: TelemetryEvent) -> None:
        with self._lock:
            self.events.append(event)

    def export_pipeline(self, event: RAGPipelineTelemetry) -> None:
        with self._lock:
            self.pipeline_events.append(event)

    def get_events(self) -> list[TelemetryEvent]:
        with self._lock:
            return list(self.events)

    def get_pipeline_events(self) -> list[RAGPipelineTelemetry]:
        with self._lock:
            return list(self.pipeline_events)

    def clear(self) -> None:
        with self._lock:
            self.events.clear()
            self.pipeline_events.clear()

    def find_pipeline_by_request_id(self, request_id: str) -> list[RAGPipelineTelemetry]:
        with self._lock:
            return [e for e in self.pipeline_events if e.request_id == request_id]


class TelemetryManager:
    """
    Central dispatcher routing structured telemetry events to registered exporters.
    """

    def __init__(self) -> None:
        self._exporters: list[BaseTelemetryExporter] = [LoggingTelemetryExporter()]
        self._lock = threading.Lock()

    def register_exporter(self, exporter: BaseTelemetryExporter) -> None:
        with self._lock:
            if exporter not in self._exporters:
                self._exporters.append(exporter)

    def unregister_exporter(self, exporter: BaseTelemetryExporter) -> None:
        with self._lock:
            if exporter in self._exporters:
                self._exporters.remove(exporter)

    def record_event(self, event: TelemetryEvent) -> None:
        with self._lock:
            exporters = list(self._exporters)
        for exp in exporters:
            try:
                exp.export_event(event)
            except Exception:
                pass

    def record_pipeline_event(self, event: RAGPipelineTelemetry) -> None:
        with self._lock:
            exporters = list(self._exporters)
        for exp in exporters:
            try:
                exp.export_pipeline(event)
            except Exception:
                pass


_telemetry_manager_instance: TelemetryManager | None = None
_telemetry_manager_lock = threading.Lock()


def get_telemetry_manager() -> TelemetryManager:
    """FastAPI/Application singleton dependency returning the TelemetryManager."""
    global _telemetry_manager_instance
    if _telemetry_manager_instance is None:
        with _telemetry_manager_lock:
            if _telemetry_manager_instance is None:
                _telemetry_manager_instance = TelemetryManager()
    return _telemetry_manager_instance


# -------------------------------------------------------------------------
# 5. Structured JSON Log Formatter
# -------------------------------------------------------------------------

STANDARD_LOG_RECORD_ATTRS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
}


class StructuredJSONFormatter(logging.Formatter):
    """
    Formats standard Python log records as secure, sanitized single-line JSON.
    Automatically enriches logs with request_id, user_id, and kb_id from contextvars.
    """

    def format(self, record: logging.LogRecord) -> str:
        record_dict: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": sanitize_string(record.getMessage()),
            "request_id": get_request_id(),
        }

        user_id = get_current_user_id()
        if user_id:
            record_dict["user_id"] = user_id

        kb_id = get_current_kb_id()
        if kb_id:
            record_dict["knowledge_base_id"] = kb_id

        # Collect custom extra fields passed to logger.info(..., extra={...})
        for key, val in record.__dict__.items():
            if key not in STANDARD_LOG_RECORD_ATTRS and not key.startswith("_"):
                k_str = str(key).lower()
                if any(sub in k_str for sub in SENSITIVE_KEY_SUBSTRINGS):
                    record_dict[key] = REDACTED_VALUE
                elif k_str in RAW_TEXT_KEYS:
                    record_dict[key] = f"[REDACTED_TEXT: {len(str(val))} chars]"
                else:
                    record_dict[key] = sanitize_log_data(val)

        if record.exc_info:
            record_dict["exception"] = sanitize_string(self.formatException(record.exc_info))

        return json.dumps(record_dict, default=str)


def setup_logging(level: str = "INFO", json_format: bool = True) -> None:
    """
    Configure root logging with the StructuredJSONFormatter.
    """
    root_logger = logging.getLogger()
    handler = logging.StreamHandler()
    if json_format:
        handler.setFormatter(StructuredJSONFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    # Avoid duplicate stream handlers
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        root_logger.addHandler(handler)


# -------------------------------------------------------------------------
# 6. CorrelationIdMiddleware (FastAPI/Starlette)
# -------------------------------------------------------------------------

_REQUEST_ID_REGEX = re.compile(r"^[a-zA-Z0-9\-_.:]{1,64}$")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    FastAPI / Starlette middleware for deterministic request correlation:
    - Extracts X-Request-ID from incoming headers (validating length and characters)
      or generates a cryptographically random UUID4.
    - Sets async-safe request_id context variable.
    - Attaches request_id to request.state.request_id.
    - Records request duration and emits an http_request telemetry event.
    - Injects X-Request-ID into HTTP response headers.
    - Resets context in a finally block to prevent context leakage across reused threads.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        header_req_id = request.headers.get("x-request-id") or request.headers.get("X-Request-ID")
        if header_req_id and _REQUEST_ID_REGEX.match(header_req_id):
            req_id = header_req_id
        else:
            req_id = str(uuid4())

        req_token = request_id_ctx.set(req_id)
        request.state.request_id = req_id

        t0 = time.perf_counter()
        status_code = 500
        error_cat = None

        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = req_id
            return response
        except Exception as exc:
            error_cat = categorize_exception(exc)
            raise exc
        finally:
            duration_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            if status_code >= 400 and error_cat is None:
                if status_code == 504:
                    error_cat = "TIMEOUT_ERROR"
                elif status_code == 503:
                    error_cat = "PROVIDER_ERROR"
                elif status_code in (401, 403):
                    error_cat = "AUTHORIZATION_ERROR"
                elif status_code == 429:
                    error_cat = "RATE_LIMIT_EXCEEDED"
                elif status_code == 422:
                    error_cat = "VALIDATION_ERROR"
                elif status_code >= 500:
                    error_cat = "INTERNAL_SERVER_ERROR"
                else:
                    error_cat = "HTTP_ERROR"

            try:
                http_event = TelemetryEvent(
                    event_name="http_request",
                    request_id=req_id,
                    user_id=get_current_user_id(),
                    knowledge_base_id=get_current_kb_id(),
                    status="SUCCESS" if status_code < 400 else "FAILURE",
                    duration_ms=duration_ms,
                    error_category=error_cat if status_code >= 400 else None,
                    attributes={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": status_code,
                        "client_ip": (request.client.host if request.client else "unknown"),
                    },
                )
                get_telemetry_manager().record_event(http_event)
            except Exception:
                pass

            request_id_ctx.reset(req_token)
