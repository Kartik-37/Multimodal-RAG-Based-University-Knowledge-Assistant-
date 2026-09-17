"""
Deterministic Sentence and Claim Segmentation Service.

Partitions generated LLM answer text into discrete, sequential claim statements
with robust protections for abbreviations, numeric decimals, technical terms,
Markdown lists, code spans, and citation annotations.

Design & Architectural Invariants:
1. Deterministic Segmentation:
   - Does NOT rely on external NLP tokenizers or heavy neural models.
   - Uses conservative regex boundary detection with negative guards.
2. Structure & Notation Protection:
   - Protects abbreviations (e.g. 'e.g.', 'i.e.', 'Dr.', 'vs.', 'etc.').
   - Protects numeric decimals and version indicators (e.g. '3.14', 'v1.2.3').
   - Preserves citation tags (e.g. '[source_1]') associated with each claim.
3. Conversational Framing Classification:
   - Identifies conversational preambles, disclaimers, or refusal statements
     so they are not falsely penalized as unsupported factual assertions.
4. Security & Computational Bounding:
   - Caps total evaluated claims at settings.GROUNDING_MAX_CLAIMS_PER_ANSWER.
   - Caps input text length at settings.GROUNDING_MAX_ANSWER_LENGTH.
"""

import re
from dataclasses import dataclass

from backend.app.core.config import settings
from backend.app.services.normalization import normalize_text

# Citations pattern matching [source_1], [source_2], etc.
_CITATION_TAG_REGEX = re.compile(r"\[(source_\d+)\]", re.IGNORECASE)

# Known abbreviations that should not trigger sentence boundaries
_ABBREVIATIONS = (
    "e.g.",
    "i.e.",
    "etc.",
    "dr.",
    "prof.",
    "vs.",
    "al.",
    "fig.",
    "no.",
    "approx.",
    "dept.",
    "vol.",
    "inc.",
    "ltd.",
    "co.",
    "univ.",
)

# Placeholder token used to temporarily escape periods in protected terms
_PERIOD_ESCAPE = "___ESC_DOT___"

# Matches conversational preamble, disclaimer, or standard refusal statements
_CONVERSATIONAL_REGEX = re.compile(
    r"^(?:"
    r"here (?:is|are)\b|"
    r"based on (?:the )?(?:provided|supplied|retrieved|available) (?:documents?|evidence|context|sources?)|"
    r"according to (?:the )?(?:provided|supplied|retrieved|available) (?:documents?|evidence|context|sources?)|"
    r"as stated in (?:the )?(?:provided|retrieved) (?:documents?|evidence)|"
    r"i could not find|"
    r"there is (?:no|not enough) (?:relevant )?information|"
    r"in summary|"
    r"to summarize|"
    r"in conclusion|"
    r"i hope this helps|"
    r"please let me know|"
    r"feel free to ask|"
    r"note that"
    r")",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ExtractedClaim:
    """In-memory representation of an individual parsed claim segment."""

    claim_index: int
    text: str  # Clean statement text with citation markers stripped
    raw_text: str  # Original sentence as parsed from answer
    is_conversational: bool
    cited_source_ids: list[str]


class SentenceSplitter:
    """
    Deterministic sentence and claim segmenter.
    """

    def __init__(self, max_claims: int | None = None) -> None:
        self.max_claims = max_claims or settings.GROUNDING_MAX_CLAIMS_PER_ANSWER

    def split(self, text: str) -> list[ExtractedClaim]:
        """
        Segment raw answer text into ExtractedClaim instances.

        Args:
            text: Raw generated LLM answer text.

        Returns:
            List of ExtractedClaim objects, up to max_claims.
        """
        if not text or not text.strip():
            return []

        # 1. Enforce input length bound
        bounded_text = text[: settings.GROUNDING_MAX_ANSWER_LENGTH]
        normalized = normalize_text(bounded_text)

        # 2. Protect periods in known abbreviations (preserving original case)
        protected = normalized
        for abbr in _ABBREVIATIONS:
            pattern = re.compile(r"\b" + re.escape(abbr), re.IGNORECASE)

            def _preserve_abbr(m: re.Match[str]) -> str:
                return m.group(0).replace(".", _PERIOD_ESCAPE)

            protected = pattern.sub(_preserve_abbr, protected)

        # 3. Protect periods in numeric decimals and version indicators (e.g. 3.14, v1.2.3)
        while re.search(r"\d+\.\d+", protected):
            protected = re.sub(r"(\d+)\.(\d+)", rf"\1{_PERIOD_ESCAPE}\2", protected)

        # 4. Protect code blocks or backtick spans
        def _escape_backticks(match: re.Match[str]) -> str:
            return match.group(0).replace(".", _PERIOD_ESCAPE)

        protected = re.sub(r"`[^`\n]+`", _escape_backticks, protected)

        # 5. Partition by line breaks first (protects lists, headers, bullet points)
        lines = [line.strip() for line in protected.split("\n") if line.strip()]

        raw_segments: list[str] = []
        # Forward-matching pattern capturing sentences with optional trailing citation markers.
        sentence_extractor = re.compile(
            r"[^\n.!?]+(?:[.!?]+(?:\s*\[source_\d+\])*)|[^\n]+",
            re.IGNORECASE,
        )

        for line in lines:
            # Strip leading list markers from line before extracting sentences
            line_no_prefix = re.sub(r"^\s*\d+\.\s+", "", line)
            line_no_prefix = re.sub(r"^\s*[-*•]\s+", "", line_no_prefix).strip()
            if not line_no_prefix:
                continue

            matches = sentence_extractor.findall(line_no_prefix)
            for m in matches:
                s_clean = m.strip()
                if s_clean:
                    raw_segments.append(s_clean)

        claims: list[ExtractedClaim] = []
        claim_idx = 1

        for seg in raw_segments:
            # Restore escaped periods
            seg_restored = seg.replace(_PERIOD_ESCAPE, ".").strip()
            if not seg_restored:
                continue

            # Strip leading list markers like "1. ", "- ", "* "
            clean_seg = re.sub(r"^[-*•]\s+", "", seg_restored)
            clean_seg = re.sub(r"^\d+\.\s+", "", clean_seg).strip()
            if not clean_seg:
                continue

            # Extract cited source identifiers
            cited_sources: list[str] = []
            for match in _CITATION_TAG_REGEX.findall(clean_seg):
                source_id = match.lower()
                if source_id not in cited_sources:
                    cited_sources.append(source_id)

            # Clean text without citation markers for claim evaluation
            text_without_citations = _CITATION_TAG_REGEX.sub("", clean_seg).strip()
            # Collapse any double spaces left from removing citations
            text_without_citations = re.sub(r"\s+", " ", text_without_citations).strip()

            # Skip empty remnants
            if not text_without_citations:
                continue

            # Check if this segment is conversational preamble or refusal
            is_conversational = bool(_CONVERSATIONAL_REGEX.search(text_without_citations))

            claims.append(
                ExtractedClaim(
                    claim_index=claim_idx,
                    text=text_without_citations,
                    raw_text=seg_restored,
                    is_conversational=is_conversational,
                    cited_source_ids=cited_sources,
                )
            )
            claim_idx += 1

            if len(claims) >= self.max_claims:
                break

        return claims
