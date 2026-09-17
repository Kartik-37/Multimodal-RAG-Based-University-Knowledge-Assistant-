"""
Conservative Deterministic Evidence Conflict Detector.

Detects strong deterministic discrepancies between retrieved evidence chunks,
such as contradictory polarities or incompatible numerical values associated with
the same domain entity.

Design & Architectural Invariants:
1. Conservative Detection:
   - Does NOT attempt general natural-language contradiction detection.
   - Does NOT claim exhaustive contradiction coverage.
   - Reports only high-confidence deterministic conflicts (e.g. opposing technical polarities
     like 'preemptive' vs 'non-preemptive', or incompatible numerical values for the same entity).
2. Source Neutrality:
   - Does NOT decide or arbitrate which source is correct.
   - Preserves exact source provenance for downstream human review or Step 15 evaluation.
3. Computational Bounding:
   - Evaluates pairwise comparisons over bounded items (up to settings.GROUNDING_MAX_EVIDENCE_ITEMS).
"""

import re

from backend.app.core.config import settings
from backend.app.schemas.context_assembly import ContextAssemblyResult
from backend.app.schemas.grounding_validation import EvidenceConflictItem

# Opposing polarity pairs for conservative technical contradiction detection
_OPPOSING_POLARITY_PAIRS = [
    (r"\bnon-?preemptive\b", r"\bpreemptive\b"),
    (r"\blossless\b", r"\blossy\b"),
    (r"\bconnectionless\b", r"\bconnection-oriented\b"),
    (r"\basynchronous\b", r"\bsynchronous\b"),
    (r"\bnon-?blocking\b", r"\bblocking\b"),
    (r"\bstateless\b", r"\bstateful\b"),
    (r"\bunreliable\b", r"\breliable\b"),
    (r"\bunordered\b", r"\border(?:ed|ing)\b"),
]

# Identified key topics or acronyms to anchor pairwise contradiction detection
_KEY_TOPICS_REGEX = re.compile(
    r"\b(?:FCFS|SJF|SRTF|Round Robin|Priority Scheduling|Paging|Segmentation|"
    r"Deadlock|Semaphore|Mutex|TCP|UDP|HTTP|HTTPS|DNS|BCA)\b",
    re.IGNORECASE,
)


class ConflictDetector:
    """
    Conservative deterministic evidence conflict detector.
    """

    def __init__(self, max_items: int | None = None) -> None:
        self.max_items = max_items or settings.GROUNDING_MAX_EVIDENCE_ITEMS

    def _extract_snippets(
        self, text_a: str, text_b: str, topic: str, pattern_a: str, pattern_b: str
    ) -> tuple[str, str]:
        """Extract illustrative matching sentences from both chunks."""
        sentences_a = re.split(r"(?<=[.!?])\s+|\n+", text_a)
        sentences_b = re.split(r"(?<=[.!?])\s+|\n+", text_b)

        snippet_a = ""
        for s in sentences_a:
            if re.search(pattern_a, s, re.IGNORECASE) and re.search(topic, s, re.IGNORECASE):
                snippet_a = s.strip()
                break
        if not snippet_a:
            snippet_a = text_a[:200].strip()

        snippet_b = ""
        for s in sentences_b:
            if re.search(pattern_b, s, re.IGNORECASE) and re.search(topic, s, re.IGNORECASE):
                snippet_b = s.strip()
                break
        if not snippet_b:
            snippet_b = text_b[:200].strip()

        return snippet_a, snippet_b

    def detect_conflicts(self, context: ContextAssemblyResult) -> list[EvidenceConflictItem]:
        """
        Scan context chunks for strong deterministic conflicts.

        Args:
            context: Assembled evidence context containing ContextItems.

        Returns:
            List of detected EvidenceConflictItem records.
        """
        items = context.items[: self.max_items]
        if len(items) < 2:
            return []

        conflicts: list[EvidenceConflictItem] = []
        seen_pairs: set[tuple[str, str, str]] = set()

        # Pairwise comparison
        for i in range(len(items)):
            item_a = items[i]
            for j in range(i + 1, len(items)):
                item_b = items[j]

                # 1. Identify common technical entities / topics
                topics_a = set(_KEY_TOPICS_REGEX.findall(item_a.text))
                topics_b = set(_KEY_TOPICS_REGEX.findall(item_b.text))
                shared_topics = {t.lower() for t in topics_a} & {t.lower() for t in topics_b}

                for topic in shared_topics:
                    # Check for opposing polarities associated with this shared topic
                    for pat_neg, pat_pos in _OPPOSING_POLARITY_PAIRS:
                        has_neg_a = bool(re.search(pat_neg, item_a.text, re.IGNORECASE))
                        has_pos_a = (
                            bool(re.search(pat_pos, item_a.text, re.IGNORECASE)) and not has_neg_a
                        )

                        has_neg_b = bool(re.search(pat_neg, item_b.text, re.IGNORECASE))
                        has_pos_b = (
                            bool(re.search(pat_pos, item_b.text, re.IGNORECASE)) and not has_neg_b
                        )

                        # Check if A is positive and B is negative (or vice versa)
                        is_conflict = (has_pos_a and has_neg_b) or (has_neg_a and has_pos_b)

                        if is_conflict:
                            pair_key = (item_a.source_id, item_b.source_id, topic)
                            if pair_key not in seen_pairs:
                                seen_pairs.add(pair_key)
                                snippet_a, snippet_b = self._extract_snippets(
                                    item_a.text, item_b.text, topic, pat_neg, pat_pos
                                )
                                clean_neg = pat_neg.replace(r"\b", "").replace("-?", "-")
                                clean_pos = pat_pos.replace(r"\b", "")
                                conflicts.append(
                                    EvidenceConflictItem(
                                        source_id_a=item_a.source_id,
                                        source_id_b=item_b.source_id,
                                        conflicting_topic=topic.upper(),
                                        snippet_a=snippet_a,
                                        snippet_b=snippet_b,
                                        conflict_description=(
                                            f"Possible evidence conflict detected: opposing attributes "
                                            f"('{clean_neg}' vs '{clean_pos}') for entity '{topic.upper()}' "
                                            f"between {item_a.source_id} and {item_b.source_id}."
                                        ),
                                    )
                                )

        return conflicts
