"""
Framework-Independent Semantic Citation Processing Module.

Provides pure-python citation reference parsing, resolution, and semantic mapping.
Separates citation semantics (indices, document metadata, source anchors) from
visual presentation markup (HTML, Tailwind, CSS pills).

Rules:
- Strictly framework-independent: NO NiceGUI, HTML rendering, or UI dependencies.
- Purely deterministic mapping and regex transformations.
- Protects citation-like markers inside inline code (`...`) and fenced code blocks (```...```).
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from frontend.client.models import CitationDTO


@dataclass(frozen=True)
class SemanticCitationRef:
    """Represents a resolved citation reference mapped to its 1-based index and metadata."""

    index: int
    citation: CitationDTO
    raw_marker: str


# Regex matching:
# 1. Fenced code blocks: ```...``` or ~~~...~~~
# 2. Inline code: `...`
# 3. Citation markers: [1], [2], or [source_1], [source_2] not followed by '(' (Markdown link syntax)
CODE_OR_CITATION_PATTERN = re.compile(
    r"(?P<fenced>```[\s\S]*?```|~~~[\s\S]*?~~~)|"
    r"(?P<inline>`[^`\n]*?`)|"
    r"(?P<citation>\[(?:source_)?(?P<num>\d+)\](?!\())",
    re.IGNORECASE,
)


def build_citation_lookup(citations: list[CitationDTO]) -> dict[str, tuple[int, CitationDTO]]:
    """Build a fast lookup dictionary mapping citation keys to (1-based index, CitationDTO).

    Supports:
    - 1-based position strings: '1', '2', ...
    - source_id strings: 'source_1', 'source_2', ...
    - numeric portion extracted from source_id: e.g. '1' from 'source_1'
    """
    lookup: dict[str, tuple[int, CitationDTO]] = {}
    for i, c in enumerate(citations, start=1):
        lookup[str(i)] = (i, c)
        if c.source_id:
            lookup[c.source_id.lower()] = (i, c)
            m = re.match(r"source_(\d+)", c.source_id, re.IGNORECASE)
            if m:
                lookup[m.group(1)] = (i, c)
    return lookup


def resolve_citation_marker(
    marker: str, citations: list[CitationDTO]
) -> SemanticCitationRef | None:
    """Resolve a single marker (e.g. '[1]', '[source_1]') against the citations list.

    Returns SemanticCitationRef if resolved, or None if invalid or out of bounds.
    """
    m = re.fullmatch(r"\[(?:source_)?(\d+)\]", marker.strip(), re.IGNORECASE)
    if not m:
        return None
    key = m.group(1).lower()
    lookup = build_citation_lookup(citations)
    if key in lookup:
        idx, cit = lookup[key]
        return SemanticCitationRef(index=idx, citation=cit, raw_marker=marker.strip())
    return None


def extract_resolved_citations(
    text: str, citations: list[CitationDTO]
) -> list[SemanticCitationRef]:
    """Scan text and return all validly resolved citation references in order of appearance.

    Excludes citation-like text inside inline code or fenced code blocks.
    """
    if not text or not citations:
        return []

    lookup = build_citation_lookup(citations)
    resolved: list[SemanticCitationRef] = []
    for m in CODE_OR_CITATION_PATTERN.finditer(text):
        if m.group("citation"):
            key = m.group("num").lower()
            if key in lookup:
                idx, cit = lookup[key]
                resolved.append(
                    SemanticCitationRef(index=idx, citation=cit, raw_marker=m.group("citation"))
                )
    return resolved


def replace_citation_markers(
    text: str,
    citations: list[CitationDTO],
    formatter: Callable[[SemanticCitationRef], str],
) -> str:
    """Replace valid citation markers in text using the provided formatter callback.

    Invalid markers, standard Markdown links, and citation-like markers inside code blocks
    are preserved intact.
    """
    if not text or not citations:
        return text

    lookup = build_citation_lookup(citations)

    def _replace_match(m: re.Match[str]) -> str:
        if m.group("citation"):
            key = m.group("num").lower()
            if key in lookup:
                idx, cit = lookup[key]
                ref = SemanticCitationRef(index=idx, citation=cit, raw_marker=m.group("citation"))
                return formatter(ref)
            return m.group(0)
        # Fenced code block or inline code: preserve without modifications
        return m.group(0)

    return CODE_OR_CITATION_PATTERN.sub(_replace_match, text)
