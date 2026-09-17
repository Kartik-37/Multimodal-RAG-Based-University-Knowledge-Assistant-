"""
Deterministic Citation Validation Service.

Validates citation syntax, source existence, duplicate mentions, and provenance
mapping of candidate citation tags extracted from generated LLM answers against
the assembled retrieval context package from Step 12.

Design & Architectural Invariants:
1. Strict Provenance Resolution:
   - Maps every valid citation tag (e.g. '[source_1]') to its exact ContextItem
     provenance (chunk_id, document_id, document_title, page_number, section_title).
2. Malformed & Unknown Citation Detection:
   - Flags nonexistent sources (e.g. '[source_99]') as invalid.
   - Detects malformed syntax variants (e.g. '[source_]', '[source-1]', '(source_1)').
3. Safe Metric Zero-Case Handling:
   - An answer with zero citations receives citation_validity_rate = 0.0 (never 1.0).
4. Security & Computational Bounding:
   - Caps total citations processed at settings.GROUNDING_MAX_CITATIONS_PER_ANSWER.
"""

import re
from dataclasses import dataclass

from backend.app.core.config import settings
from backend.app.schemas.context_assembly import ContextAssemblyResult, ContextItem
from backend.app.schemas.grounding_validation import CitationValidationItem

# Standard citation pattern: matches [source_1], [source_2], etc.
_STANDARD_CITATION_REGEX = re.compile(r"\[(source_\d+)\]", re.IGNORECASE)

# Pattern capturing potential malformed or non-canonical citation syntaxes
_MALFORMED_CANDIDATE_REGEX = re.compile(
    r"\[source(?:[-_: ]\w+)?\]|\(source[-_:\s]?\d+\)|\[source\]",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CitationAnalysis:
    """Summary record of citation validation results."""

    items: list[CitationValidationItem]
    citations_found: int
    unique_citations_found: int
    valid_citations: int
    invalid_citations: int
    malformed_citations_count: int
    citation_validity_rate: float


class CitationValidator:
    """
    Validates citation references in generated answers against ContextAssemblyResult.
    """

    def __init__(self, max_citations: int | None = None) -> None:
        self.max_citations = max_citations or settings.GROUNDING_MAX_CITATIONS_PER_ANSWER

    def validate(self, answer: str, context: ContextAssemblyResult) -> CitationAnalysis:
        """
        Validate all citation tags present in the answer text.

        Args:
            answer: Raw generated LLM answer text.
            context: Assembled evidence context containing authorized ContextItems.

        Returns:
            CitationAnalysis summarizing validity, counts, and provenance mapping.
        """
        if not answer or not answer.strip():
            return CitationAnalysis(
                items=[],
                citations_found=0,
                unique_citations_found=0,
                valid_citations=0,
                invalid_citations=0,
                malformed_citations_count=0,
                citation_validity_rate=0.0,
            )

        # Build fast lookup map from lowercased source_id to ContextItem
        context_map: dict[str, ContextItem] = {
            item.source_id.lower(): item for item in context.items
        }

        # 1. Detect standard citations
        standard_matches = _STANDARD_CITATION_REGEX.findall(answer)
        # Cap citation evaluations
        bounded_matches = standard_matches[: self.max_citations]

        items: list[CitationValidationItem] = []
        valid_count = 0
        invalid_count = 0
        seen_unique_sources: set[str] = set()

        for raw_source in bounded_matches:
            source_id = raw_source.lower()
            seen_unique_sources.add(source_id)

            if source_id in context_map:
                ctx_item = context_map[source_id]
                valid_count += 1
                items.append(
                    CitationValidationItem(
                        raw_citation=f"[{raw_source}]",
                        source_id=source_id,
                        is_valid=True,
                        context_item_id=ctx_item.chunk_id,
                        document_id=ctx_item.document_id,
                        document_title=ctx_item.document_title,
                        page_number=ctx_item.page_number,
                        section_title=ctx_item.section_title,
                        error_reason=None,
                    )
                )
            else:
                invalid_count += 1
                items.append(
                    CitationValidationItem(
                        raw_citation=f"[{raw_source}]",
                        source_id=source_id,
                        is_valid=False,
                        context_item_id=None,
                        document_id=None,
                        document_title=None,
                        page_number=None,
                        section_title=None,
                        error_reason=f"Source '{source_id}' does not exist in assembled context.",
                    )
                )

        citations_found = len(bounded_matches)

        # 2. Detect malformed citation variants that failed standard syntax matching
        all_malformed_matches = _MALFORMED_CANDIDATE_REGEX.findall(answer)
        malformed_count = 0
        for m in all_malformed_matches:
            # If the candidate doesn't match standard syntax, it's malformed
            if not _STANDARD_CITATION_REGEX.fullmatch(m):
                malformed_count += 1

        # 3. Calculate citation validity rate:
        # valid_citations / citations_found when citations_found > 0, otherwise 0.0
        # (An answer with 0 citations receives 0.0, never 1.0).
        if citations_found > 0:
            citation_validity_rate = round(valid_count / citations_found, 4)
        else:
            citation_validity_rate = 0.0

        return CitationAnalysis(
            items=items,
            citations_found=citations_found,
            unique_citations_found=len(seen_unique_sources),
            valid_citations=valid_count,
            invalid_citations=invalid_count,
            malformed_citations_count=malformed_count,
            citation_validity_rate=citation_validity_rate,
        )
