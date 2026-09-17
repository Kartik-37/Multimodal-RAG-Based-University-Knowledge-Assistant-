"""
Conservative Deterministic Heuristic Grounding Verifier.

Evaluates whether generated claims exhibit evidence characteristics consistent with
the supplied retrieval context chunks.

Design & Architectural Invariants:
1. Conservative Heuristic Nature:
   - This service is a conservative deterministic heuristic grounding validator.
   - It measures whether claims have lexical and entity characteristics consistent with
     the supplied context.
   - It does NOT prove that a claim is factually true in the real world.
   - It does NOT provide perfect semantic entailment detection.
   - Known limitations:
     * Paraphrases with heavy synonym replacement may be missed.
     * Semantically equivalent wording may exhibit low lexical overlap.
     * High lexical overlap does not guarantee logical truth.
     * Common terms can create false support if not filtered.
     * Entity and numeric matching is an additional heuristic signal.
2. Conservative Status Assignment:
   - Where deterministic heuristics cannot establish support confidently,
     the validator prefers UNVERIFIABLE over incorrectly declaring SUPPORTED.
3. Key Entity and Numerical Invariance:
   - Specific numbers, percentages, dates, and technical acronyms (e.g. FCFS, SJF, 1950)
     asserted in a claim must appear in the cited chunk; missing entities trigger
     UNSUPPORTED or UNVERIFIABLE status.
4. Transparent Evidence Provenance:
   - Extracts the exact matching sentence snippet from the evidence chunk as
     human-verifiable proof of support.
"""

import re
import uuid

from backend.app.core.config import settings
from backend.app.schemas.context_assembly import ContextAssemblyResult, ContextItem
from backend.app.schemas.grounding_validation import ClaimValidationItem, GroundingStatus
from backend.app.services.grounding.sentence_splitter import ExtractedClaim

# Standard English stopword set to filter common non-content words
_STOPWORDS = frozenset(
    {
        "a",
        "about",
        "above",
        "after",
        "again",
        "against",
        "all",
        "am",
        "an",
        "and",
        "any",
        "are",
        "as",
        "at",
        "be",
        "because",
        "been",
        "before",
        "being",
        "below",
        "between",
        "both",
        "but",
        "by",
        "could",
        "did",
        "do",
        "does",
        "doing",
        "down",
        "during",
        "each",
        "few",
        "for",
        "from",
        "further",
        "had",
        "has",
        "have",
        "having",
        "he",
        "her",
        "here",
        "hers",
        "herself",
        "him",
        "himself",
        "his",
        "how",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "itself",
        "just",
        "me",
        "more",
        "most",
        "my",
        "myself",
        "no",
        "nor",
        "not",
        "now",
        "of",
        "off",
        "on",
        "once",
        "only",
        "or",
        "other",
        "our",
        "ours",
        "ourselves",
        "out",
        "over",
        "own",
        "same",
        "she",
        "should",
        "so",
        "some",
        "such",
        "than",
        "that",
        "the",
        "their",
        "theirs",
        "them",
        "themselves",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "to",
        "too",
        "under",
        "until",
        "up",
        "very",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "while",
        "who",
        "whom",
        "why",
        "with",
        "would",
        "you",
        "your",
        "yours",
        "yourself",
        "yourselves",
    }
)

# Regex to extract words for content overlap calculation
_WORD_REGEX = re.compile(r"\b[a-zA-Z]{2,}\b")

# Regex to extract numbers and decimals (e.g. 1950, 4, 3.14, 0.6)
_NUMBER_REGEX = re.compile(r"\b\d+(?:\.\d+)?\b")

# Regex to extract technical acronyms / uppercase identifiers (e.g. FCFS, CPU, FIFO, RAM)
_ACRONYM_REGEX = re.compile(r"\b[A-Z]{2,}\b")


class ClaimVerifier:
    """
    Conservative deterministic heuristic claim verifier.
    """

    def __init__(self, min_overlap_threshold: float | None = None) -> None:
        self.min_overlap_threshold = (
            min_overlap_threshold
            if min_overlap_threshold is not None
            else settings.GROUNDING_MIN_OVERLAP_THRESHOLD
        )

    def extract_content_words(self, text: str) -> set[str]:
        """Extract lowercased non-stopword tokens from text."""
        words = _WORD_REGEX.findall(text.lower())
        return {w for w in words if w not in _STOPWORDS}

    def extract_numbers(self, text: str) -> set[str]:
        """Extract numeric and decimal tokens from text."""
        return set(_NUMBER_REGEX.findall(text))

    def extract_acronyms(self, text: str) -> set[str]:
        """Extract uppercase domain acronyms from text."""
        return set(_ACRONYM_REGEX.findall(text))

    def find_best_sentence_snippet(self, claim_words: set[str], chunk_text: str) -> str:
        """
        Extract the single sentence in chunk_text with highest content word overlap.
        """
        if not chunk_text or not claim_words:
            return ""

        # Split chunk text into candidate sentences
        sentences = re.split(r"(?<=[.!?])\s+|\n+", chunk_text)
        best_sentence = ""
        best_overlap = -1

        for sentence in sentences:
            s_clean = sentence.strip()
            if not s_clean:
                continue
            s_words = self.extract_content_words(s_clean)
            overlap = len(claim_words & s_words)
            if overlap > best_overlap:
                best_overlap = overlap
                best_sentence = s_clean

        return best_sentence

    def verify_claim(
        self,
        claim: ExtractedClaim,
        context: ContextAssemblyResult,
        context_map: dict[str, ContextItem],
    ) -> ClaimValidationItem:
        """
        Verify a single claim against the assembled context using conservative heuristics.
        """
        # 1. Handle Conversational/Refusal statements
        if claim.is_conversational:
            return ClaimValidationItem(
                claim_index=claim.claim_index,
                text=claim.text,
                raw_text=claim.raw_text,
                is_conversational=True,
                cited_source_ids=claim.cited_source_ids,
                resolved_context_item_ids=[],
                status=GroundingStatus.CONVERSATIONAL,
                overlap_score=0.0,
                supporting_evidence_snippets=[],
                unsupported_reason=None,
            )

        claim_content_words = self.extract_content_words(claim.text)
        claim_numbers = self.extract_numbers(claim.text)
        claim_acronyms = self.extract_acronyms(claim.text)

        # 2. Case: Claim explicitly cites one or more sources
        if claim.cited_source_ids:
            valid_cited_items: list[ContextItem] = []
            resolved_ids: list[uuid.UUID] = []

            for src in claim.cited_source_ids:
                if src in context_map:
                    item = context_map[src]
                    valid_cited_items.append(item)
                    resolved_ids.append(item.chunk_id)

            # If no cited source exists in context
            if not valid_cited_items:
                return ClaimValidationItem(
                    claim_index=claim.claim_index,
                    text=claim.text,
                    raw_text=claim.raw_text,
                    is_conversational=False,
                    cited_source_ids=claim.cited_source_ids,
                    resolved_context_item_ids=[],
                    status=GroundingStatus.UNSUPPORTED,
                    overlap_score=0.0,
                    supporting_evidence_snippets=[],
                    unsupported_reason="Cited source identifier(s) do not exist in retrieved context.",
                )

            # Evaluate each valid cited item
            best_overlap = 0.0
            best_snippet = ""
            has_entity_mismatch = False
            missing_entities: list[str] = []

            for item in valid_cited_items:
                chunk_numbers = self.extract_numbers(item.text)
                chunk_acronyms = self.extract_acronyms(item.text)
                chunk_words = self.extract_content_words(item.text)

                # Check number & acronym invariance
                missing_nums = claim_numbers - chunk_numbers
                missing_acrs = claim_acronyms - chunk_acronyms
                if missing_nums or missing_acrs:
                    has_entity_mismatch = True
                    missing_entities.extend(sorted(missing_nums | missing_acrs))

                # Calculate content word recall
                if claim_content_words:
                    overlap = len(claim_content_words & chunk_words) / len(claim_content_words)
                else:
                    overlap = 1.0 if not (missing_nums or missing_acrs) else 0.0

                if overlap > best_overlap:
                    best_overlap = overlap
                    best_snippet = self.find_best_sentence_snippet(claim_content_words, item.text)

            best_overlap = round(best_overlap, 4)

            # Check if entities missing (strict entity and numerical invariance)
            if has_entity_mismatch:
                missing_str = ", ".join(missing_entities[:3])
                return ClaimValidationItem(
                    claim_index=claim.claim_index,
                    text=claim.text,
                    raw_text=claim.raw_text,
                    is_conversational=False,
                    cited_source_ids=claim.cited_source_ids,
                    resolved_context_item_ids=resolved_ids,
                    status=GroundingStatus.UNSUPPORTED,
                    overlap_score=best_overlap,
                    supporting_evidence_snippets=[best_snippet] if best_snippet else [],
                    unsupported_reason=f"Asserted numbers or key entities ({missing_str}) not found in cited source.",
                )

            # Check if threshold met
            if best_overlap >= self.min_overlap_threshold:
                return ClaimValidationItem(
                    claim_index=claim.claim_index,
                    text=claim.text,
                    raw_text=claim.raw_text,
                    is_conversational=False,
                    cited_source_ids=claim.cited_source_ids,
                    resolved_context_item_ids=resolved_ids,
                    status=GroundingStatus.SUPPORTED,
                    overlap_score=best_overlap,
                    supporting_evidence_snippets=[best_snippet] if best_snippet else [],
                    unsupported_reason=None,
                )

            # Claim fell below threshold in cited source. Check if supported elsewhere in context
            other_support_found = False
            other_source_id = ""
            for other_item in context.items:
                if other_item.source_id.lower() in claim.cited_source_ids:
                    continue
                other_words = self.extract_content_words(other_item.text)
                if claim_content_words:
                    other_overlap = len(claim_content_words & other_words) / len(
                        claim_content_words
                    )
                else:
                    other_overlap = 0.0
                if other_overlap >= self.min_overlap_threshold:
                    other_support_found = True
                    other_source_id = other_item.source_id
                    break

            if other_support_found:
                return ClaimValidationItem(
                    claim_index=claim.claim_index,
                    text=claim.text,
                    raw_text=claim.raw_text,
                    is_conversational=False,
                    cited_source_ids=claim.cited_source_ids,
                    resolved_context_item_ids=resolved_ids,
                    status=GroundingStatus.UNSUPPORTED,
                    overlap_score=best_overlap,
                    supporting_evidence_snippets=[best_snippet] if best_snippet else [],
                    unsupported_reason=(
                        f"Claim not supported by cited source(s), but consistent evidence "
                        f"found in another source ({other_source_id})."
                    ),
                )

            # Otherwise, prefer UNVERIFIABLE under conservative heuristic
            return ClaimValidationItem(
                claim_index=claim.claim_index,
                text=claim.text,
                raw_text=claim.raw_text,
                is_conversational=False,
                cited_source_ids=claim.cited_source_ids,
                resolved_context_item_ids=resolved_ids,
                status=GroundingStatus.UNVERIFIABLE,
                overlap_score=best_overlap,
                supporting_evidence_snippets=[best_snippet] if best_snippet else [],
                unsupported_reason=(
                    f"Insufficient evidence in cited source (content overlap {best_overlap:.2f} "
                    f"< threshold {self.min_overlap_threshold})."
                ),
            )

        # 3. Case: Factual claim with NO cited sources (uncited claim)
        best_overlap = 0.0
        best_snippet = ""
        best_uncited_item: ContextItem | None = None

        bounded_items = context.items[: settings.GROUNDING_MAX_EVIDENCE_ITEMS]
        for item in bounded_items:
            chunk_numbers = self.extract_numbers(item.text)
            chunk_acronyms = self.extract_acronyms(item.text)

            # Must not have contradictory missing entities
            if (claim_numbers - chunk_numbers) or (claim_acronyms - chunk_acronyms):
                continue

            chunk_words = self.extract_content_words(item.text)
            if claim_content_words:
                overlap = len(claim_content_words & chunk_words) / len(claim_content_words)
            else:
                overlap = 0.0

            if overlap > best_overlap:
                best_overlap = overlap
                best_uncited_item = item
                best_snippet = self.find_best_sentence_snippet(claim_content_words, item.text)

        best_overlap = round(best_overlap, 4)

        if best_overlap >= self.min_overlap_threshold and best_uncited_item is not None:
            return ClaimValidationItem(
                claim_index=claim.claim_index,
                text=claim.text,
                raw_text=claim.raw_text,
                is_conversational=False,
                cited_source_ids=[],
                resolved_context_item_ids=[best_uncited_item.chunk_id],
                status=GroundingStatus.SUPPORTED_UNCITED,
                overlap_score=best_overlap,
                supporting_evidence_snippets=[best_snippet] if best_snippet else [],
                unsupported_reason=(
                    f"Claim is consistent with retrieved source '{best_uncited_item.source_id}', "
                    "but lacks an attribution citation marker."
                ),
            )

        return ClaimValidationItem(
            claim_index=claim.claim_index,
            text=claim.text,
            raw_text=claim.raw_text,
            is_conversational=False,
            cited_source_ids=[],
            resolved_context_item_ids=[],
            status=GroundingStatus.UNVERIFIABLE,
            overlap_score=best_overlap,
            supporting_evidence_snippets=[best_snippet] if best_snippet else [],
            unsupported_reason="Uncited claim cannot be verified from available retrieved context.",
        )
