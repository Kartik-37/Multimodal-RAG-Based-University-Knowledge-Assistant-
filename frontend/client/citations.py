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
from typing import Any

from frontend.client.models import CitationDTO


@dataclass(frozen=True)
class SemanticCitationRef:
    """Represents a resolved citation reference mapped to its 1-based index and metadata."""

    index: int
    citation: CitationDTO
    raw_marker: str


@dataclass(frozen=True)
class GroupedPageReference:
    """Represents a unique page reference within a document group."""

    page_number: int | None
    citation: CitationDTO
    citation_indices: tuple[int, ...]
    snippets: tuple[str, ...]
    citations: tuple[CitationDTO, ...]


@dataclass(frozen=True)
class DocumentCitationGroup:
    """Represents a canonical document with grouped, deduplicated page references."""

    document_id: str | None
    document_name: str
    course_name: str | None
    knowledge_base_id: str | None
    pages: tuple[GroupedPageReference, ...]
    citations: tuple[CitationDTO, ...]


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


def group_citations_by_document(
    citations: list[CitationDTO],
) -> list[DocumentCitationGroup]:
    """Group citations by canonical document and deduplicate page references.

    Guarantees:
    - Stable canonical document identification: documents with distinct non-empty
      document_id are never merged even if their filenames match.
    - Preserves document discovery order from the citation list.
    - Multiple citations to the same document and same page number are collapsed into
      a single GroupedPageReference containing all associated indices, snippets, and citations.
    - If a source has no page number (page_number is None), it is preserved as None
      without fabricating a page number.
    - Inline citation indices and underlying evidence snippets are fully preserved.
    """
    if not citations:
        return []

    doc_groups_map: dict[Any, dict[str, Any]] = {}
    doc_order: list[Any] = []

    for idx, cit in enumerate(citations, start=1):
        if cit.document_id:
            doc_key = ("id", cit.document_id)
        elif cit.knowledge_base_id and cit.document_name:
            doc_key = ("kb_name", cit.knowledge_base_id, cit.document_name)
        elif cit.document_name:
            doc_key = ("name", cit.document_name)
        else:
            doc_key = ("fallback", id(cit))

        if doc_key not in doc_groups_map:
            doc_order.append(doc_key)
            doc_groups_map[doc_key] = {
                "document_id": cit.document_id,
                "document_name": cit.document_name,
                "course_name": cit.course_name,
                "knowledge_base_id": cit.knowledge_base_id,
                "citations": [],
                "page_order": [],
                "page_map": {},
            }

        group_acc = doc_groups_map[doc_key]
        group_acc["citations"].append(cit)
        if cit.course_name and not group_acc["course_name"]:
            group_acc["course_name"] = cit.course_name
        if cit.knowledge_base_id and not group_acc["knowledge_base_id"]:
            group_acc["knowledge_base_id"] = cit.knowledge_base_id

        page_key = cit.page_number
        if page_key not in group_acc["page_map"]:
            group_acc["page_order"].append(page_key)
            group_acc["page_map"][page_key] = {
                "page_number": cit.page_number,
                "citation": cit,
                "citation_indices": [idx],
                "snippets": [cit.snippet] if cit.snippet else [],
                "citations": [cit],
            }
        else:
            page_acc = group_acc["page_map"][page_key]
            page_acc["citation_indices"].append(idx)
            if cit.snippet and cit.snippet not in page_acc["snippets"]:
                page_acc["snippets"].append(cit.snippet)
            page_acc["citations"].append(cit)

    result: list[DocumentCitationGroup] = []
    for doc_key in doc_order:
        acc = doc_groups_map[doc_key]
        pages: list[GroupedPageReference] = []
        for p_key in acc["page_order"]:
            p_data = acc["page_map"][p_key]
            pages.append(
                GroupedPageReference(
                    page_number=p_data["page_number"],
                    citation=p_data["citation"],
                    citation_indices=tuple(p_data["citation_indices"]),
                    snippets=tuple(p_data["snippets"]),
                    citations=tuple(p_data["citations"]),
                )
            )
        result.append(
            DocumentCitationGroup(
                document_id=acc["document_id"],
                document_name=acc["document_name"],
                course_name=acc["course_name"],
                knowledge_base_id=acc["knowledge_base_id"],
                pages=tuple(pages),
                citations=tuple(acc["citations"]),
            )
        )
    return result
