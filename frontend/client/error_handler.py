"""
Frontend Error Normalization.

Transforms backend HTTP exceptions, Pydantic validation errors, and API error codes
into user-friendly, privacy-preserving messages. Ensures raw SQL, tracebacks,
and internal database UUIDs are never exposed in the presentation layer.
"""

from typing import Any


def normalize_error(err: Any, context: str | None = None) -> str:
    """
    Safely convert an API response, exception, or validation error into a clean message.

    :param err: The error object, status code, exception, dict, or string detail.
    :param context: Optional operational context ('auth', 'document', 'admin', 'chat').
    :return: Human-friendly error string.
    """
    if err is None:
        return "An unexpected error occurred. Please try again."

    # If err is an exception with an inner message or response
    if hasattr(err, "detail"):
        detail = err.detail
        status_code = getattr(err, "status_code", None)
        return _normalize_detail(detail, status_code=status_code, context=context)

    if isinstance(err, int):
        return _normalize_status_code(err, context=context)

    if isinstance(err, str):
        return _normalize_detail(err, context=context)

    if isinstance(err, dict):
        if "detail" in err:
            return _normalize_detail(err["detail"], context=context)
        if "message" in err:
            return _normalize_detail(err["message"], context=context)
        return "The request could not be completed. Please check your input."

    if isinstance(err, list):
        return _normalize_pydantic_errors(err, context=context)

    if hasattr(err, "args") and err.args:
        return _normalize_detail(str(err.args[0]), context=context)

    return "An unexpected error occurred. Please try again."


def _normalize_status_code(status_code: int, context: str | None = None) -> str:
    """Map HTTP status codes according to context."""
    if status_code == 400:
        return "The request was invalid. Please check your submission."
    if status_code == 401:
        if context == "auth":
            return "Invalid email or password."
        return "Authentication is required. Please sign in."
    if status_code == 403:
        if context == "admin":
            return "Administrator privileges are required for this action."
        return "You do not have permission to perform this action."
    if status_code == 404:
        if context == "document":
            return "The requested document was not found."
        return "The requested resource was not found."
    if status_code == 409:
        if context in ("auth", "admin"):
            return "An account with this email address already exists."
        if context == "document":
            return "Document state conflict occurred."
        return "A conflict occurred with the current state of the resource."
    if status_code == 413:
        return "The uploaded file exceeds the allowed size limit."
    if status_code == 415:
        return "The uploaded file format is not supported. Please upload a PDF or TXT document."
    if status_code == 422:
        return "Please verify that all fields are filled out correctly."
    if status_code == 429:
        return "Too many requests. Please wait a moment and try again."
    if status_code in (500, 502, 503, 504):
        return "A temporary server error occurred. Please try again later."
    return f"Request failed with status {status_code}."


def _normalize_pydantic_errors(errors: list[Any], context: str | None = None) -> str:
    """Format FastAPI / Pydantic validation error lists into friendly text."""
    messages: list[str] = []
    for item in errors:
        if not isinstance(item, dict):
            continue
        loc = item.get("loc", [])
        field_name = str(loc[-1]) if loc else ""
        err_type = str(item.get("type", "")).lower()
        msg = str(item.get("msg", "")).lower()

        # Password rules
        if "password" in field_name.lower():
            if "too_short" in err_type or "min_length" in err_type or "at least 8" in msg:
                messages.append("Password must be at least 8 characters.")
            else:
                messages.append("Password must be at least 8 characters.")
        elif "email" in field_name.lower():
            if (
                "already exists" in msg
                or "unique" in err_type
                or "duplicate" in err_type
                or "already registered" in msg
            ):
                messages.append("An account with this email already exists.")
            else:
                messages.append("Please enter a valid email address.")
        elif "full_name" in field_name.lower():
            messages.append("Full name is required.")
        elif "name" in field_name.lower():
            messages.append("Name is required.")
        elif "file" in field_name.lower():
            messages.append("A valid document file is required.")
        elif "too_short" in err_type or "min_length" in err_type:
            messages.append(f"The provided {field_name or 'input'} is too short.")
        elif "missing" in err_type:
            messages.append(f"Missing required field: {field_name or 'input'}.")
        elif item.get("msg"):
            messages.append(str(item.get("msg")))

    if messages:
        # Return deduplicated, clean messages
        unique_msgs = list(dict.fromkeys(messages))
        return " ".join(unique_msgs)
    return "Please verify that all fields are filled out correctly."


def _normalize_detail(
    detail: Any, status_code: int | None = None, context: str | None = None
) -> str:
    """Normalize string detail or structured detail."""
    if isinstance(detail, list):
        return _normalize_pydantic_errors(detail, context=context)

    if isinstance(detail, dict):
        if "detail" in detail:
            return _normalize_detail(detail["detail"], status_code=status_code, context=context)
        return _normalize_pydantic_errors([detail], context=context)

    if not isinstance(detail, str):
        detail_str = str(detail)
    else:
        detail_str = detail.strip()

    # Defensive parsing of stringified Pydantic or Python dicts/lists
    if ("'type':" in detail_str or '"type":' in detail_str) and (
        "loc" in detail_str or "msg" in detail_str
    ):
        import ast

        try:
            parsed = ast.literal_eval(detail_str)
            if isinstance(parsed, list):
                return _normalize_pydantic_errors(parsed, context=context)
            if isinstance(parsed, dict):
                return _normalize_pydantic_errors([parsed], context=context)
        except Exception:
            pass

    # Exact known backend error tokens
    if detail_str == "AUTH_EMAIL_EXISTS" or (status_code == 409 and context in ("auth", "admin")):
        return "An account with this email address already exists."
    if detail_str == "DOCUMENT_ALREADY_ACTIVE":
        return "This document is already active."
    if detail_str == "DOCUMENT_ALREADY_INACTIVE":
        return "This document is already inactive."
    if detail_str == "INVALID_CREDENTIALS":
        return "Invalid email or password."

    # Check common substrings
    lower = detail_str.lower()
    if "email already registered" in lower or "already exists" in lower:
        return "An account with this email address already exists."
    if "invalid email or password" in lower or "invalid credentials" in lower:
        return "Invalid email or password."
    if "password must be at least" in lower:
        return "Password must be at least 8 characters."
    if "file size exceeds" in lower or "too large" in lower:
        return "The uploaded file exceeds the allowed size limit."
    if "unsupported file" in lower or "not allowed" in lower:
        return "The uploaded file format is not supported. Please upload a PDF or TXT document."
    if "not found" in lower:
        if context == "document":
            return "The requested document was not found."
        return "The requested resource was not found."
    if "permission denied" in lower or "forbidden" in lower or "not permitted" in lower:
        if context == "admin":
            return "Administrator privileges are required for this action."
        return "You do not have permission to perform this action."

    # Suppress raw SQL or tracebacks
    if any(
        leak in lower
        for leak in ("select ", "insert ", "update ", "traceback", "uuid", "syntax error")
    ):
        return "A server processing error occurred. Please try again later."

    # If a status code is available, fallback to status code normalization
    if status_code and status_code >= 400:
        return _normalize_status_code(status_code, context=context)

    return detail_str
