"""
Unit Tests for Deterministic CitationValidator.
"""

import uuid

from backend.app.schemas.context_assembly import ContextAssemblyResult, ContextItem
from backend.app.services.grounding.citation_validator import CitationValidator


def _make_dummy_context(source_ids: list[str]) -> ContextAssemblyResult:
    items = []
    for idx, sid in enumerate(source_ids):
        items.append(
            ContextItem(
                source_id=sid,
                chunk_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                knowledge_base_id=uuid.uuid4(),
                document_title=f"Doc_{sid}.pdf",
                chunk_index=idx,
                text=f"Text for {sid} containing sample content.",
                page_number=idx + 1,
                section_title=f"Section {sid}",
                chunk_metadata={},
                reranker_rank=idx + 1,
                reranker_score=0.9 - (idx * 0.1),
                rrf_score=0.03,
                estimated_tokens=50,
            )
        )
    return ContextAssemblyResult(
        query="test query",
        items=items,
        total_items=len(items),
        total_estimated_tokens=len(items) * 50,
        token_budget=1000,
        candidates_received=len(items),
        items_skipped_budget=0,
        items_deduplicated=0,
    )


def test_citation_validator_valid_and_unknown_sources() -> None:
    context = _make_dummy_context(["source_1", "source_2"])
    validator = CitationValidator()

    answer = "Claim from valid source [source_1] and fake source [source_99]."
    analysis = validator.validate(answer=answer, context=context)

    assert analysis.citations_found == 2
    assert analysis.unique_citations_found == 2
    assert analysis.valid_citations == 1
    assert analysis.invalid_citations == 1
    assert analysis.citation_validity_rate == 0.5

    assert analysis.items[0].source_id == "source_1"
    assert analysis.items[0].is_valid is True
    assert analysis.items[0].document_title == "Doc_source_1.pdf"
    assert analysis.items[0].page_number == 1

    assert analysis.items[1].source_id == "source_99"
    assert analysis.items[1].is_valid is False
    assert "does not exist in assembled context" in (analysis.items[1].error_reason or "")


def test_citation_validator_duplicate_mentions() -> None:
    context = _make_dummy_context(["source_1"])
    validator = CitationValidator()

    answer = "First point [source_1]. Second point [source_1]."
    analysis = validator.validate(answer=answer, context=context)

    assert analysis.citations_found == 2
    assert analysis.unique_citations_found == 1
    assert analysis.valid_citations == 2
    assert analysis.invalid_citations == 0
    assert analysis.citation_validity_rate == 1.0


def test_citation_validator_zero_citations_returns_zero_rate() -> None:
    context = _make_dummy_context(["source_1"])
    validator = CitationValidator()

    answer = "This answer contains absolutely no citations whatsoever."
    analysis = validator.validate(answer=answer, context=context)

    assert analysis.citations_found == 0
    assert analysis.unique_citations_found == 0
    assert analysis.valid_citations == 0
    # Mandatory rule: An answer with zero citations must not receive 1.0, it receives 0.0
    assert analysis.citation_validity_rate == 0.0


def test_citation_validator_malformed_syntax_detection() -> None:
    context = _make_dummy_context(["source_1"])
    validator = CitationValidator()

    answer = "Valid [source_1], but also malformed [source_] and (source_2) and [source:3]."
    analysis = validator.validate(answer=answer, context=context)

    assert analysis.valid_citations == 1
    assert analysis.citations_found == 1
    assert analysis.malformed_citations_count >= 2


def test_citation_validator_empty_and_whitespace_answer() -> None:
    context = _make_dummy_context(["source_1"])
    validator = CitationValidator()

    analysis = validator.validate(answer="", context=context)
    assert analysis.citations_found == 0
    assert analysis.citation_validity_rate == 0.0
