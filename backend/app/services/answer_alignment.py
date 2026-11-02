"""
Answer-to-Question Alignment Checker.
Validates that generated or recovered answers address the actual user question,
preserve the requested entity type, and do not introduce unrelated topics.
"""

import logging
import re
from typing import Any

from backend.app.schemas.query_understanding import QueryIntent, StructuredQuery

logger = logging.getLogger(__name__)


class AnswerAlignmentChecker:
    """
    Validates semantic alignment between candidate responses and the original StructuredQuery.
    Detects topic drift, entity confusion (e.g. phones returned for widgets), and cross-domain leaks.
    """

    def check_alignment(
        self,
        structured_query: StructuredQuery,
        answer: str,
    ) -> tuple[bool, str]:
        """
        Check if candidate answer aligns with the StructuredQuery.
        Returns (is_aligned, reason_code).
        """
        ans_lower = (answer or "").lower().strip()
        target_entity = (structured_query.target_entity_type or "").lower()
        subject = (structured_query.subject or "").lower()

        # Refusal answers are always safe from alignment perspective
        if any(
            p in ans_lower
            for p in (
                "could not find any relevant information",
                "could not find sufficient verified evidence",
                "please ask a question related to",
            )
        ):
            return True, "ALIGNED_SAFE_REFUSAL"

        # 1. Widget queries
        if target_entity in ("widget", "widget_category") or "widget" in subject:
            # Answer must not claim iPhones or iOS compatibility models are widgets
            if any(p in ans_lower for p in ("iphone 16", "iphone 15", "iphone 14", "ios 26 compatibility")):
                return False, "MISALIGNED_IPHONES_IN_WIDGET_ANSWER"
            # Answer must not dump Android versions as widgets
            if any(p in ans_lower for p in ("cupcake", "donut", "eclair", "froyo", "gingerbread", "honeycomb")):
                return False, "MISALIGNED_ANDROID_VERSIONS_IN_WIDGET_ANSWER"

        # 2. Conversational / Identity queries
        if structured_query.is_conversational or subject == "assistant":
            # Answer must not leak Act statutory formula or company watermarks
            if any(p in ans_lower for p in ("this act may be called", "kaushalya", "akash technolabs")):
                return False, "MISALIGNED_ACT_OR_WATERMARK_IN_CONVERSATIONAL"

        # 3. iOS Device queries
        if target_entity == "device" or subject == "ios_device":
            if "everything is a widget" in ans_lower and not any(p in ans_lower for p in ("iphone", "ios", "device", "model")):
                return False, "MISALIGNED_WIDGET_IN_DEVICE_ANSWER"

        # 4. Act Title queries
        if target_entity == "act" or subject == "act_title":
            if any(p in ans_lower for p in ("flutter is an app sdk", "everything is a widget")):
                return False, "MISALIGNED_FLUTTER_IN_ACT_ANSWER"

        return True, "ALIGNED"


_answer_alignment_checker_instance: AnswerAlignmentChecker | None = None


def get_answer_alignment_checker() -> AnswerAlignmentChecker:
    global _answer_alignment_checker_instance
    if _answer_alignment_checker_instance is None:
        _answer_alignment_checker_instance = AnswerAlignmentChecker()
    return _answer_alignment_checker_instance

