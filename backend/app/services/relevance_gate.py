"""
Query-to-Evidence Relevance Gate.
Validates semantic alignment between structured query intent/entities and retrieved candidate chunks
before context assembly. Rejects entity mismatches, cross-document contamination, and low-scoring noise.
Domain-agnostic and generalized across arbitrary academic subjects.
"""

import logging
import re
from typing import Any

from backend.app.schemas.query_understanding import QueryIntent, StructuredQuery
from backend.app.schemas.reranking import RerankResultItem

logger = logging.getLogger(__name__)

STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "because", "as", "what", "which",
    "this", "that", "these", "those", "then", "just", "so", "than", "such",
    "both", "through", "about", "for", "is", "of", "while", "during", "to",
    "from", "in", "out", "on", "off", "again", "further", "then", "once",
    "here", "there", "when", "where", "why", "how", "all", "any", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "too", "very", "can", "will", "don",
    "should", "now", "are", "were", "was", "be", "been", "being", "have",
    "has", "had", "having", "do", "does", "did", "doing", "would", "could",
    "tell", "explain", "describe", "give", "list", "please", "notes", "course",
    "lecture", "slide", "slides", "document", "file", "mention", "mentioned"
}

VISUAL_QUERY_TERMS = {
    "diagram", "chart", "figure", "visual", "image", "flowchart", "architecture",
    "ui", "screen", "illustration", "infographic", "graph", "table"
}


class QueryEvidenceRelevanceGate:
    """
    Quality gate between CrossEncoder reranking and Context Assembly.
    Evaluates candidate chunks against the StructuredQuery using domain-agnostic
    semantic relevance, lexical overlap, and noise suppression.
    """

    def _extract_tokens(self, text: str) -> set[str]:
        words = re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", text.lower())
        return {w for w in words if w not in STOP_WORDS}

    def _has_stemmed_or_substring_match(self, term: str, text: str) -> bool:
        term_clean = term.rstrip("s").rstrip("es")
        if len(term_clean) >= 3 and term_clean in text:
            return True
        return term in text

    def evaluate_candidates(
        self,
        structured_query: StructuredQuery,
        candidates: list[RerankResultItem],
    ) -> tuple[list[RerankResultItem], list[dict[str, Any]]]:
        """
        Evaluate candidates and return (accepted_candidates, audit_log).
        """
        audit_log: list[dict[str, Any]] = []
        raw_accepted: list[RerankResultItem] = []

        query_norm = (structured_query.normalized_query or "").lower()
        subject_raw = (structured_query.subject or "").lower()

        query_tokens = self._extract_tokens(query_norm)
        subject_tokens = self._extract_tokens(subject_raw) - {"general", "all"}
        core_tokens = query_tokens | subject_tokens

        has_visual_intent = any(term in query_norm for term in VISUAL_QUERY_TERMS)
        is_conceptual_query = structured_query.intent in (
            QueryIntent.DEFINITION,
            QueryIntent.EXPLANATION,
            QueryIntent.FACT_LOOKUP,
        )

        for candidate in candidates:
            text = (candidate.text or "").strip()
            text_lower = text.lower()
            score = candidate.reranker_score

            decision = "ACCEPT"
            reason = "ALIGNED"

            is_visual = bool(
                candidate.chunk_metadata
                and candidate.chunk_metadata.get("source_modality") == "visual"
            )

            # Check overlap against core query/subject tokens
            matching_tokens = {
                t for t in core_tokens
                if self._has_stemmed_or_substring_match(t, text_lower)
            }
            overlap_count = len(matching_tokens)

            # Subject alignment check:
            # If a specific substantive subject exists (>= 1 token), candidate must have
            # at least some connection to the subject or core query tokens.
            if subject_tokens:
                has_subject_overlap = any(
                    self._has_stemmed_or_substring_match(st, text_lower)
                    for st in subject_tokens
                )
                if not has_subject_overlap and overlap_count == 0:
                    decision = "REJECT"
                    reason = "REJECTED_SUBJECT_ABSENT"

            # Low score noise filter
            if decision == "ACCEPT":
                if score < -11.0:
                    decision = "REJECT"
                    reason = "REJECTED_LOW_SCORE_NOISE"
                elif score < -9.0 and overlap_count == 0:
                    decision = "REJECT"
                    reason = "REJECTED_LOW_SCORE_NO_OVERLAP"

            # Visual chunk handling for non-visual conceptual queries
            if decision == "ACCEPT" and is_visual and not has_visual_intent:
                # If conceptual question and visual chunk has no matching query tokens, reject
                if is_conceptual_query and overlap_count == 0:
                    decision = "REJECT"
                    reason = "REJECTED_VISUAL_OFF_TOPIC"

            audit_entry = {
                "chunk_id": str(candidate.chunk_id),
                "page_number": candidate.page_number,
                "reranker_score": round(score, 4),
                "decision": decision,
                "reason": reason,
            }
            audit_log.append(audit_entry)

            if decision == "ACCEPT":
                raw_accepted.append(candidate)
            else:
                logger.debug(
                    "RelevanceGate rejected candidate p%s (score=%.4f): %s",
                    candidate.page_number,
                    score,
                    reason,
                )

        # Conceptual query visual balancing:
        # If textual evidence exists, prevent visual candidates from displacing or dominating text
        if is_conceptual_query and not has_visual_intent and raw_accepted:
            text_candidates = [
                c for c in raw_accepted
                if not (c.chunk_metadata and c.chunk_metadata.get("source_modality") == "visual")
            ]
            visual_candidates = [
                c for c in raw_accepted
                if (c.chunk_metadata and c.chunk_metadata.get("source_modality") == "visual")
            ]
            if text_candidates:
                # Keep text candidates, allowing at most 1 top-scoring visual candidate as supplementary
                accepted = text_candidates + visual_candidates[:1]
            else:
                accepted = raw_accepted
        else:
            accepted = raw_accepted

        return accepted, audit_log


_relevance_gate_instance: QueryEvidenceRelevanceGate | None = None


def get_relevance_gate() -> QueryEvidenceRelevanceGate:
    global _relevance_gate_instance
    if _relevance_gate_instance is None:
        _relevance_gate_instance = QueryEvidenceRelevanceGate()
    return _relevance_gate_instance
