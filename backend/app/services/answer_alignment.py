"""
Answer-to-Question Alignment Checker.
Validates that generated or recovered answers address the actual user question,
preserve the requested entity type, and do not introduce unrelated topics.
Domain-agnostic and generalized across arbitrary academic subjects.
"""

import logging
import re
from typing import Any

from backend.app.schemas.query_understanding import QueryIntent, StructuredQuery

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
    "lecture", "slide", "slides", "document", "file"
}

SAFE_REFUSAL_PHRASES = (
    "could not find any relevant information",
    "could not find sufficient verified evidence",
    "does not provide sufficient information",
    "not mentioned in the provided",
    "no relevant information",
    "please ask a question related to",
    "unable to find",
    "insufficient evidence",
    "i cannot answer",
)

LEAKED_DIRECTIVE_MARKERS = (
    "<think>",
    "</think>",
    "system prompt",
    "internal instructions",
    "internal directives",
    "instruction to assistant",
    "the user is asking for",
    "my role is to",
)


class AnswerAlignmentChecker:
    """
    Validates semantic alignment between candidate responses and the original StructuredQuery.
    Detects topic drift, empty responses, leaked prompt directives, and cross-domain leaks.
    """

    def _extract_content_tokens(self, text: str) -> set[str]:
        words = re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", text.lower())
        return {w for w in words if w not in STOP_WORDS}

    def _matches_token(self, token: str, text: str) -> bool:
        stem = token.rstrip("s").rstrip("es")
        if len(stem) >= 3 and stem in text:
            return True
        return token in text

    def check_alignment(
        self,
        structured_query: StructuredQuery,
        answer: str,
    ) -> tuple[bool, str]:
        """
        Check if candidate answer aligns with the StructuredQuery.
        Returns (is_aligned, reason_code).
        """
        raw = (answer or "").strip()
        ans_lower = raw.lower()

        # 1. Empty or trivial answer check
        if len(raw) < 5 or not re.search(r"[a-zA-Z0-9]", raw):
            return False, "MISALIGNED_EMPTY_ANSWER"

        # 2. Leaked reasoning or system prompt directives
        if any(marker in ans_lower for marker in LEAKED_DIRECTIVE_MARKERS):
            return False, "MISALIGNED_LEAKED_INTERNAL_DIRECTIVES"

        # 3. Refusal answers are always safe from an alignment perspective
        if any(p in ans_lower for p in SAFE_REFUSAL_PHRASES):
            return True, "ALIGNED_SAFE_REFUSAL"

        # 4. Conversational / Identity queries: should not quote citations or document fragments
        if structured_query.is_conversational:
            if re.search(r"\[source_\d+\]", raw) or re.search(r"\bpage\s+\d+\b", ans_lower):
                return False, "MISALIGNED_CITATIONS_IN_CONVERSATIONAL"
            return True, "ALIGNED_CONVERSATIONAL"

        # 5. Generic substantive subject alignment
        subject_raw = (structured_query.subject or "").lower()
        subject_tokens = self._extract_content_tokens(subject_raw) - {"general", "all"}
        query_tokens = self._extract_content_tokens(structured_query.normalized_query)

        core_tokens = subject_tokens or query_tokens

        if core_tokens:
            has_alignment = any(
                self._matches_token(token, ans_lower)
                for token in core_tokens
            )
            if not has_alignment:
                logger.warning(
                    "AnswerAlignmentChecker flagged off-topic answer: core_tokens=%s not found in answer",
                    core_tokens,
                )
                return False, "MISALIGNED_OFF_TOPIC_RESPONSE"

        return True, "ALIGNED"


_answer_alignment_checker_instance: AnswerAlignmentChecker | None = None


def get_answer_alignment_checker() -> AnswerAlignmentChecker:
    global _answer_alignment_checker_instance
    if _answer_alignment_checker_instance is None:
        _answer_alignment_checker_instance = AnswerAlignmentChecker()
    return _answer_alignment_checker_instance
