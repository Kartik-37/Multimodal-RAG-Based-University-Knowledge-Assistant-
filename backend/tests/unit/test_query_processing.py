"""
Unit Tests for Deterministic Query Processing Layer (Step 11).

Validates:
1. Safe whitespace normalization (leading, trailing, and internal collapsing).
2. Control character stripping (null bytes, terminal escapes, etc.).
3. Unicode NFKC normalization (ligatures, full-width characters, accented characters).
4. Preservation of technical tokens, programming symbols, and punctuation.
5. Preservation of quoted phrases and casing.
6. SQL/malicious input treated strictly as inert data strings.
7. Original query preservation alongside processed query.
8. Length boundary constraints against settings.RETRIEVAL_MAX_QUERY_LENGTH.
9. Empty/whitespace-only rejection with QueryValidationError.
10. Strict idempotence: process(process(q).processed_query).processed_query == process(q).processed_query.
11. Diagnostic metadata accuracy.
"""

import pytest

from backend.app.core.config import settings
from backend.app.schemas.query_processing import QueryProcessingRequest, QueryProcessingResult
from backend.app.services.query_processing import (
    QueryProcessor,
    QueryValidationError,
    get_query_processor,
)


class TestQueryProcessor:
    """Test suite for QueryProcessor deterministic normalization and validation."""

    @pytest.fixture
    def processor(self) -> QueryProcessor:
        return QueryProcessor()

    # --------------------------------------------------------------------------
    # Basic & Whitespace Normalization
    # --------------------------------------------------------------------------

    def test_normal_query(self, processor: QueryProcessor) -> None:
        raw = "What are the core operating system scheduling algorithms?"
        result = processor.process(raw)
        assert result.original_query == raw
        assert result.processed_query == raw
        assert result.character_count == len(raw)
        assert result.token_estimate > 0
        assert result.has_quotes is False

    def test_leading_and_trailing_whitespace(self, processor: QueryProcessor) -> None:
        raw = "   process synchronization in operating systems   \t  \n"
        result = processor.process(raw)
        assert result.original_query == raw
        assert result.processed_query == "process synchronization in operating systems"
        assert result.metadata["whitespace_collapsed"] is True

    def test_internal_repeated_whitespace_collapsing(self, processor: QueryProcessor) -> None:
        raw = "database \t\t management   \n\n systems   normalization"
        result = processor.process(raw)
        assert result.original_query == raw
        assert result.processed_query == "database management systems normalization"
        assert result.metadata["whitespace_collapsed"] is True

    # --------------------------------------------------------------------------
    # Empty & Boundary Validations
    # --------------------------------------------------------------------------

    def test_empty_query_rejected(self, processor: QueryProcessor) -> None:
        with pytest.raises(QueryValidationError, match="cannot be empty or whitespace only"):
            processor.process("")

    def test_whitespace_only_query_rejected(self, processor: QueryProcessor) -> None:
        with pytest.raises(QueryValidationError, match="cannot be empty or whitespace only"):
            processor.process("   \t  \r\n  ")

    def test_non_string_query_rejected(self, processor: QueryProcessor) -> None:
        with pytest.raises(QueryValidationError, match="Query must be a string"):
            processor.process(None)  # type: ignore

        with pytest.raises(QueryValidationError, match="Query must be a string"):
            processor.process(12345)  # type: ignore

    def test_maximum_length_query_accepted(self, processor: QueryProcessor) -> None:
        # Exactly 1000 characters of valid query terms
        exact_max_query = "word " * 199 + "word"  # 199 * 5 + 4 = 999 chars
        assert len(exact_max_query) == 999
        result = processor.process(exact_max_query)
        assert result.processed_query == exact_max_query

        exact_1000 = exact_max_query + "a"
        assert len(exact_1000) == settings.RETRIEVAL_MAX_QUERY_LENGTH
        res_1000 = processor.process(exact_1000)
        assert res_1000.character_count == settings.RETRIEVAL_MAX_QUERY_LENGTH

    def test_over_limit_query_rejected(self, processor: QueryProcessor) -> None:
        # 1001 characters
        over_limit_query = "a" * (settings.RETRIEVAL_MAX_QUERY_LENGTH + 1)
        with pytest.raises(QueryValidationError, match="exceeds maximum permitted limit"):
            processor.process(over_limit_query)

    # --------------------------------------------------------------------------
    # Unicode Normalization (NFKC)
    # --------------------------------------------------------------------------

    def test_unicode_ligature_normalization(self, processor: QueryProcessor) -> None:
        # 'ﬁ' (U+FB01) should normalize to 'fi' under NFKC
        raw = "The ﬁrst ﬂight of the process scheduler"
        result = processor.process(raw)
        assert result.processed_query == "The first flight of the process scheduler"
        assert result.metadata["unicode_normalized"] is True

    def test_unicode_fullwidth_character_normalization(self, processor: QueryProcessor) -> None:
        # Full-width Latin characters (e.g. ＡＢＣ１２３) normalize to standard ASCII
        raw = "ＢＣＡ Ｓｅｍ-４ Ｅｘａｍ"
        result = processor.process(raw)
        assert result.processed_query == "BCA Sem-4 Exam"
        assert result.metadata["unicode_normalized"] is True

    def test_unicode_accented_characters_preserved(self, processor: QueryProcessor) -> None:
        # Common accented characters in standard texts must remain correctly represented
        raw = "résumé of café curriculum and naïve Bayes model"
        result = processor.process(raw)
        assert result.processed_query == "résumé of café curriculum and naïve Bayes model"

    # --------------------------------------------------------------------------
    # Control Characters & Security
    # --------------------------------------------------------------------------

    def test_control_character_stripping(self, processor: QueryProcessor) -> None:
        # Null bytes, escapes, and bell characters must be stripped
        raw = "process\x00scheduling\x1b[31mwith\x07IPC"
        result = processor.process(raw)
        assert result.processed_query == "processscheduling[31mwithIPC"
        assert result.metadata["control_chars_stripped"] is True

    def test_sql_input_treated_strictly_as_data(self, processor: QueryProcessor) -> None:
        raw = "DROP TABLE users; --"
        result = processor.process(raw)
        assert result.original_query == raw
        assert result.processed_query == "DROP TABLE users; --"
        assert result.has_technical_tokens is True

    def test_malicious_script_tags_treated_strictly_as_data(
        self, processor: QueryProcessor
    ) -> None:
        raw = "<script>alert('XSS')</script>"
        result = processor.process(raw)
        assert result.original_query == raw
        assert result.processed_query == "<script>alert('XSS')</script>"
        assert result.has_quotes is True

    # --------------------------------------------------------------------------
    # Technical Token & Punctuation Preservation
    # --------------------------------------------------------------------------

    @pytest.mark.parametrize(
        ("query", "expected_token"),
        [
            ("How to program in C++ on Windows?", "C++"),
            ("Building microservices with C# and .NET 8.0", "C#"),
            ("Migrating from ASP.NET to modern .NET Core", ".NET"),
            ("Configuring PostgreSQL pgvector extension for VECTOR(1024)", "PostgreSQL"),
            ("Indexing vectors with pgvector exact cosine search", "pgvector"),
            ("New features in Python 3.12 for async execution", "Python 3.12"),
            ("Handling HTTP 401 Unauthorized in client sessions", "HTTP 401"),
            ("Syllabus requirements for BCA Sem-4 course", "BCA Sem-4"),
            ("Explain the SQL query SELECT * FROM users WHERE active = 1;", "SELECT"),
        ],
    )
    def test_technical_tokens_preserved(
        self, processor: QueryProcessor, query: str, expected_token: str
    ) -> None:
        result = processor.process(query)
        assert expected_token in result.processed_query
        assert result.has_technical_tokens is True

    def test_quoted_phrases_preserved(self, processor: QueryProcessor) -> None:
        raw = "Find passages matching \"machine learning\" and 'neural network'"
        result = processor.process(raw)
        assert result.original_query == raw
        assert (
            result.processed_query
            == "Find passages matching \"machine learning\" and 'neural network'"
        )
        assert result.has_quotes is True

    # --------------------------------------------------------------------------
    # Idempotence & Metadata
    # --------------------------------------------------------------------------

    def test_idempotence(self, processor: QueryProcessor) -> None:
        raw = "   SELECT   *   FROM   documents   WHERE   tag   =   'BCA'  \t\n "
        first_pass = processor.process(raw)
        second_pass = processor.process(first_pass.processed_query)
        third_pass = processor.process(second_pass.processed_query)

        assert first_pass.processed_query == second_pass.processed_query
        assert second_pass.processed_query == third_pass.processed_query
        assert first_pass.processed_query == "SELECT * FROM documents WHERE tag = 'BCA'"

    def test_no_semantic_rewriting(self, processor: QueryProcessor) -> None:
        # Step 11 must NOT perform semantic rewriting or synonym expansion
        raw = "What is BCA attendance?"
        result = processor.process(raw)
        assert result.processed_query == "What is BCA attendance?"
        assert "percentage" not in result.processed_query
        assert "policy" not in result.processed_query

    def test_singleton_getter(self) -> None:
        p1 = get_query_processor()
        p2 = get_query_processor()
        assert p1 is p2


# ------------------------------------------------------------------------------
# Schema Tests
# ------------------------------------------------------------------------------


class TestQuerySchemas:
    """Test suite for QueryProcessingRequest and QueryProcessingResult schemas."""

    def test_request_model(self) -> None:
        req = QueryProcessingRequest(query="what is virtual memory?")
        assert req.query == "what is virtual memory?"

    def test_result_model_defaults(self) -> None:
        res = QueryProcessingResult(
            original_query=" raw query ",
            processed_query="raw query",
            character_count=9,
            token_estimate=2,
        )
        assert res.original_query == " raw query "
        assert res.processed_query == "raw query"
        assert res.character_count == 9
        assert res.token_estimate == 2
        assert res.has_quotes is False
        assert res.has_technical_tokens is False
        assert res.metadata == {}
