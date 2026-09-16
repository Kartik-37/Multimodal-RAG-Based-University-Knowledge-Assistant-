"""
Deterministic Query Processing Service.

Prepares user queries for downstream retrieval (vector, lexical, hybrid RRF)
and reranking (CrossEncoder) through safe, deterministic text normalization.
Preserves the raw user query, enforces security constraints, strips non-printable
control characters, applies Unicode NFKC normalization, and preserves domain-critical
technical tokens and punctuation without performing semantic rewriting or LLM inference.
"""

import re
import threading
import unicodedata

from backend.app.core.config import settings
from backend.app.schemas.query_processing import QueryProcessingResult
from backend.app.services.chunking import TokenEstimator


class QueryValidationError(Exception):
    """Raised when query input fails validation (empty, non-string, or exceeds max length)."""

    pass


# Non-printable ASCII/Unicode control characters (0x00-0x08, 0x0B-0x0C, 0x0E-0x1F, 0x7F)
# Tab (0x09) and Newline (0x0A) are handled during whitespace normalization.
_CONTROL_CHARS_REGEX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Quoted phrase regex (single or double quotes enclosing non-empty text)
_QUOTED_PHRASE_REGEX = re.compile(r"""(?:"[^"]+"|\'[^\']+\')""")

# Conservative technical token detection:
# - Programming symbols: C++, C#, .NET, F#
# - Database keywords & identifiers: SQL, SELECT, FROM, WHERE, INSERT, UPDATE, DELETE, JOIN, TABLE, PostgreSQL, pgvector
# - Protocol & status codes: HTTP, HTTPS, HTTP 401, etc.
# - Version patterns: Python 3.12, v1.0.0
# - Hyphenated / dotted / snake_case technical identifiers: BCA Sem-4, sys.argv, os_scheduling
_TECHNICAL_TOKEN_REGEX = re.compile(
    r"""(?:
        \bC\+\+           # C++
        |\bC\#            # C#
        |\.NET\b          # .NET
        |\bF\#            # F#
        |\b(?:SELECT|FROM|WHERE|INSERT|UPDATE|DELETE|JOIN|TABLE|POSTGRESQL|PGVECTOR)\b # SQL/DB keywords
        |\bHTTP(?:S)?(?:\s+\d{3})?\b  # HTTP / HTTP 401
        |\b[a-zA-Z]+[-_][a-zA-Z0-9_-]+\b  # Hyphenated/underscored identifiers (e.g. Sem-4, bca_sem4)
        |\b[a-zA-Z]+\s+\d+(?:\.\d+)+\b     # Language versions (e.g. Python 3.12)
        |\b\w+\.\w+\b                       # Dotted identifiers (e.g. file.pdf, os.path)
    )""",
    re.IGNORECASE | re.VERBOSE,
)


class QueryProcessor:
    """
    Deterministic Query Processor.

    Applies a clean, deterministic pipeline:
    1. Type validation (must be string).
    2. Non-printable control character stripping.
    3. Unicode NFKC normalization (compatibility decomposition + canonical composition).
    4. Internal whitespace standardization (collapses tabs, newlines, multiple spaces).
    5. Leading and trailing whitespace stripping.
    6. Non-empty validation.
    7. Maximum length validation against settings.RETRIEVAL_MAX_QUERY_LENGTH.
    8. Diagnostic metadata extraction (character count, token estimate, quote/technical flags).
    """

    def __init__(self, token_estimator: TokenEstimator | None = None) -> None:
        self._token_estimator = token_estimator or TokenEstimator()

    def process(self, query: str) -> QueryProcessingResult:
        """
        Deterministically process a raw search query.

        Args:
            query: Raw user query string.

        Returns:
            QueryProcessingResult with original_query, processed_query, and diagnostic metadata.

        Raises:
            QueryValidationError: If query is not a string, is empty/whitespace-only,
                                  or exceeds settings.RETRIEVAL_MAX_QUERY_LENGTH.
        """
        if not isinstance(query, str):
            raise QueryValidationError(f"Query must be a string, got {type(query).__name__}.")

        original_query = query

        # 1. Strip dangerous non-printable control characters
        has_control_chars = bool(_CONTROL_CHARS_REGEX.search(query))
        cleaned = _CONTROL_CHARS_REGEX.sub("", query)

        # 2. Unicode NFKC Normalization
        # Standardizes compatibility ligatures (e.g. 'ﬁ' -> 'fi') and full-width forms
        # while preserving natural accented characters (e.g. 'café' remains 'café').
        nfkc_normalized = unicodedata.normalize("NFKC", cleaned)
        was_unicode_normalized = nfkc_normalized != cleaned
        cleaned = nfkc_normalized

        # 3. Whitespace normalization: convert newlines/tabs to space, collapse repeated spaces
        cleaned = (
            cleaned.replace("\r\n", " ").replace("\r", " ").replace("\n", " ").replace("\t", " ")
        )
        cleaned = re.sub(r" +", " ", cleaned)
        cleaned = cleaned.strip()

        # 4. Empty / Whitespace-only validation
        if not cleaned:
            raise QueryValidationError("Query cannot be empty or whitespace only.")

        # 5. Length validation against authoritative limit
        if len(cleaned) > settings.RETRIEVAL_MAX_QUERY_LENGTH:
            raise QueryValidationError(
                f"Query length ({len(cleaned)} characters) exceeds maximum permitted limit "
                f"of {settings.RETRIEVAL_MAX_QUERY_LENGTH} characters."
            )

        # 6. Extract diagnostic metadata (never alters retrieval or ranking behavior)
        char_count = len(cleaned)
        token_count = self._token_estimator.estimate_tokens(cleaned)
        has_quotes = bool(_QUOTED_PHRASE_REGEX.search(cleaned))
        has_technical = bool(_TECHNICAL_TOKEN_REGEX.search(cleaned))

        metadata = {
            "unicode_normalized": was_unicode_normalized,
            "whitespace_collapsed": cleaned != original_query,
            "control_chars_stripped": has_control_chars,
        }

        return QueryProcessingResult(
            original_query=original_query,
            processed_query=cleaned,
            character_count=char_count,
            token_estimate=token_count,
            has_quotes=has_quotes,
            has_technical_tokens=has_technical,
            metadata=metadata,
        )


# Global singleton instance
_default_query_processor: QueryProcessor | None = None
_processor_init_lock = threading.Lock()


def get_query_processor() -> QueryProcessor:
    """
    Get or create the singleton QueryProcessor instance.
    """
    global _default_query_processor
    if _default_query_processor is None:
        with _processor_init_lock:
            if _default_query_processor is None:
                _default_query_processor = QueryProcessor()
    return _default_query_processor
