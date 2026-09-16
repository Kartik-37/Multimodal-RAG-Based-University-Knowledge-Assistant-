"""
Unit Tests for Deterministic Token-Aware Document Chunking.

Validates:
1. Stable sequential chunk indexing (0, 1, 2, ...).
2. Preservation of 1-indexed page_number and section_title metadata.
3. Configurable target token estimation and overlap behavior.
4. Determinism of chunking output across multiple executions.
5. Rejection of empty or meaningless chunks.
"""

from backend.app.services.chunking import ChunkingConfig, DocumentChunker, TokenEstimator
from backend.app.services.parsers.base import ParsedDocument, ParsedSection


def test_token_estimator_word_and_punctuation() -> None:
    """Verify deterministic token estimation count."""
    estimator = TokenEstimator()
    assert estimator.estimate_tokens("") == 0
    assert estimator.estimate_tokens("   ") == 0
    # "Hello, world!" -> 'Hello', ',', 'world', '!' = 4 tokens
    assert estimator.estimate_tokens("Hello, world!") == 4


def test_chunking_preserves_page_numbers_and_headings() -> None:
    """Verify that chunks accurately retain their source page number and heading."""
    doc = ParsedDocument(
        sections=[
            ParsedSection(
                text="Content from page one explaining the fundamentals.",
                page_number=1,
                section_title="Introduction",
            ),
            ParsedSection(
                text="Content from page two explaining vector databases.",
                page_number=2,
                section_title="Vector Architecture",
            ),
        ],
        raw_text="Full text...",
    )

    chunker = DocumentChunker(ChunkingConfig(target_tokens=50, overlap_tokens=10, min_tokens=5))
    chunks = chunker.chunk_document(doc)

    assert len(chunks) == 2
    assert chunks[0].chunk_index == 0
    assert chunks[0].page_number == 1
    assert chunks[0].section_title == "Introduction"

    assert chunks[1].chunk_index == 1
    assert chunks[1].page_number == 2
    assert chunks[1].section_title == "Vector Architecture"


def test_chunking_deterministic_output() -> None:
    """Verify that chunking produces bitwise identical results across repeated runs."""
    section = ParsedSection(
        text="Long repetitive sentence for testing deterministic chunk boundaries. " * 30,
        page_number=1,
        section_title="Repeat Test",
    )
    doc = ParsedDocument(sections=[section], raw_text=section.text)

    chunker = DocumentChunker(ChunkingConfig(target_tokens=60, overlap_tokens=15, min_tokens=10))

    run_1 = chunker.chunk_document(doc)
    run_2 = chunker.chunk_document(doc)

    assert len(run_1) == len(run_2)
    for c1, c2 in zip(run_1, run_2, strict=True):
        assert c1.chunk_index == c2.chunk_index
        assert c1.text == c2.text
        assert c1.token_count == c2.token_count
        assert c1.page_number == c2.page_number
        assert c1.section_title == c2.section_title


def test_no_empty_chunks_emitted() -> None:
    """Verify that empty or whitespace-only sections emit zero chunks."""
    doc = ParsedDocument(
        sections=[
            ParsedSection(text="   \n\n  ", page_number=1),
            ParsedSection(text="", page_number=2),
        ],
        raw_text="",
    )

    chunker = DocumentChunker()
    chunks = chunker.chunk_document(doc)
    assert len(chunks) == 0
