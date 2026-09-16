"""
Unit Tests for PostgreSQL Full-Text Lexical Retrieval Layer (Step 8).

Tests query normalization, bounds validation, schema models, query safety,
result mapping, deterministic ordering, and explicit Ollama/embedding independence.
"""

import uuid
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from backend.app.core.config import settings
from backend.app.models.document import DocumentChunk
from backend.app.schemas.lexical_retrieval import (
    LexicalRetrievalRequest,
    LexicalRetrievalResponse,
    LexicalRetrievalResultItem,
)
from backend.app.services.lexical_retrieval import (
    LexicalRetrievalService,
    LexicalRetrievalValidationError,
)


def test_lexical_retrieval_request_valid() -> None:
    """Valid search query and default top_k accepted."""
    req = LexicalRetrievalRequest(query="Operating Systems process scheduling")
    assert req.query == "Operating Systems process scheduling"
    assert req.top_k == settings.LEXICAL_TOP_K


def test_lexical_retrieval_request_custom_top_k() -> None:
    """Custom top_k within configured bounds accepted."""
    req = LexicalRetrievalRequest(query="Database indexes", top_k=7)
    assert req.top_k == 7


@pytest.mark.parametrize("bad_query", ["", "   ", "\t\n  \r\n"])
def test_lexical_retrieval_request_rejects_empty_or_whitespace_query(bad_query: str) -> None:
    """Empty or whitespace-only queries must fail validation with 422 equivalent."""
    with pytest.raises(ValidationError):
        LexicalRetrievalRequest(query=bad_query)


def test_lexical_retrieval_request_rejects_oversized_query() -> None:
    """Query exceeding maximum allowed character length must fail validation."""
    oversized = "x" * (settings.LEXICAL_MAX_QUERY_LENGTH + 1)
    with pytest.raises(ValidationError):
        LexicalRetrievalRequest(query=oversized)


@pytest.mark.parametrize("bad_k", [0, -1, -5, 51, 100])
def test_lexical_retrieval_request_rejects_out_of_bounds_top_k(bad_k: int) -> None:
    """top_k below minimum or above maximum must fail validation."""
    with pytest.raises(ValidationError):
        LexicalRetrievalRequest(query="valid query", top_k=bad_k)


def test_lexical_result_item_safe_metadata_default_factory() -> None:
    """
    Enforces Correction 1:
    chunk_metadata must use default_factory=dict to prevent shared mutable defaults.
    """
    item1 = LexicalRetrievalResultItem(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_title="test.pdf",
        chunk_index=0,
        text="text 1",
        lexical_score=0.5,
    )
    item2 = LexicalRetrievalResultItem(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_title="test.pdf",
        chunk_index=1,
        text="text 2",
        lexical_score=0.4,
    )

    # Mutate item1's metadata
    item1.chunk_metadata["test_key"] = "test_val"

    # item2's metadata must remain completely isolated
    assert item2.chunk_metadata == {}
    assert "test_key" not in item2.chunk_metadata


def test_service_validate_query_normalizes_whitespace() -> None:
    """Surrounding whitespace and newlines must be stripped cleanly."""
    service = LexicalRetrievalService()
    assert (
        service.validate_query("  \nCPU scheduling algorithms \t ") == "CPU scheduling algorithms"
    )


def test_service_validate_query_unicode_preserved() -> None:
    """Unicode characters and academic notation must be preserved."""
    service = LexicalRetrievalService()
    q = "Discrete mathematics: ∀ x ∈ S, P(x) ⇒ Q(x)"
    assert service.validate_query(q) == q


@pytest.mark.parametrize(
    "special_q",
    [
        "C++ & Java | Python",
        "Operating System * and !interrupts",
        "title:database AND index:b-tree",
        '"exact quoted phrase" OR fallback',
        "SELECT * FROM chunks WHERE id = '1';",
    ],
)
def test_service_validate_query_special_characters_accepted(special_q: str) -> None:
    """Queries containing boolean search operators or punctuation pass validation safely."""
    service = LexicalRetrievalService()
    clean = service.validate_query(special_q)
    assert clean == special_q.strip()


def test_service_validate_query_empty_raises_validation_error() -> None:
    """Blank query string raises LexicalRetrievalValidationError."""
    service = LexicalRetrievalService()
    with pytest.raises(LexicalRetrievalValidationError):
        service.validate_query("   ")


def test_service_validate_query_length_exceeded_raises() -> None:
    """Query exceeding maximum allowed character length raises LexicalRetrievalValidationError."""
    service = LexicalRetrievalService()
    with pytest.raises(LexicalRetrievalValidationError):
        service.validate_query("q" * (settings.LEXICAL_MAX_QUERY_LENGTH + 5))


@pytest.mark.parametrize("bad_k", [0, -10, 51, 999])
def test_service_validate_top_k_bounds(bad_k: int) -> None:
    """top_k out of bounds raises LexicalRetrievalValidationError."""
    service = LexicalRetrievalService()
    with pytest.raises(LexicalRetrievalValidationError):
        service.validate_top_k(bad_k)


def test_service_is_completely_independent_from_ollama() -> None:
    """
    Enforces Correction 4:
    Lexical retrieval service must NOT import, initialize, or depend on Ollama or embeddings.
    """
    service = LexicalRetrievalService()
    assert not hasattr(service, "_provider")
    assert not hasattr(service, "embedding_service")
    assert not hasattr(service, "embed_query")


def test_service_result_mapping() -> None:
    """
    Verifies that database rows are mapped accurately to LexicalRetrievalResultItem
    preserving document title, page number, section title, and lexical score.
    """
    service = LexicalRetrievalService()
    chunk_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    kb_id = uuid.uuid4()

    mock_chunk = MagicMock(spec=DocumentChunk)
    mock_chunk.id = chunk_id
    mock_chunk.document_id = doc_id
    mock_chunk.knowledge_base_id = kb_id
    mock_chunk.chunk_index = 3
    mock_chunk.text = "CPU scheduling algorithms determine process execution order."
    mock_chunk.page_number = 2
    mock_chunk.section_title = "Process Management"
    mock_chunk.chunk_metadata = {"source": "os_unit1.pdf"}

    score_val = 0.245678

    mock_db = MagicMock()
    mock_db.execute.return_value.all.return_value = [(mock_chunk, "os_unit1.pdf", score_val)]

    response = service.retrieve(
        db=mock_db,
        kb_id=kb_id,
        query="CPU scheduling",
        top_k=5,
    )

    assert isinstance(response, LexicalRetrievalResponse)
    assert response.total_results == 1
    item = response.results[0]
    assert item.chunk_id == chunk_id
    assert item.document_id == doc_id
    assert item.knowledge_base_id == kb_id
    assert item.document_title == "os_unit1.pdf"
    assert item.chunk_index == 3
    assert item.page_number == 2
    assert item.section_title == "Process Management"
    assert item.lexical_score == round(score_val, 6)
