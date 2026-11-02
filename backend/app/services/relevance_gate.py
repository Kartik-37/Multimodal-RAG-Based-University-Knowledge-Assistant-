"""
Query-to-Evidence Relevance Gate.
Validates semantic alignment between structured query intent/entities and retrieved candidate chunks
before context assembly. Rejects entity mismatches, cross-document contamination, and low-scoring noise.
"""

import logging
import re
from typing import Any

from backend.app.schemas.query_understanding import QueryIntent, StructuredQuery
from backend.app.schemas.reranking import RerankResultItem

logger = logging.getLogger(__name__)


class QueryEvidenceRelevanceGate:
    """
    Quality gate between CrossEncoder reranking and Context Assembly.
    Evaluates each candidate chunk against the StructuredQuery to ensure candidate evidence
    addresses the requested subject, property, and entity type.
    """

    def evaluate_candidates(
        self,
        structured_query: StructuredQuery,
        candidates: list[RerankResultItem],
    ) -> tuple[list[RerankResultItem], list[dict[str, Any]]]:
        """
        Evaluate candidates and return (accepted_candidates, audit_log).
        """
        accepted: list[RerankResultItem] = []
        audit_log: list[dict[str, Any]] = []

        target_entity = (structured_query.target_entity_type or "").lower()
        subject = (structured_query.subject or "").lower()
        query_norm = structured_query.normalized_query

        for candidate in candidates:
            text = (candidate.text or "").strip()
            text_lower = text.lower()
            score = candidate.reranker_score

            decision = "ACCEPT"
            reason = "ALIGNED"

            # -------------------------------------------------------------
            # 1. Target Entity: Widget
            # -------------------------------------------------------------
            if target_entity in ("widget", "widget_category") or "widget" in subject:
                # Explicit negative check: iOS device / iPhone list is NOT a widget list
                if any(p in text_lower for p in ("list of supported ios", "iphone 16", "iphone 15", "ios 26 compatibility")) and "everything is a widget" not in text_lower:
                    decision = "REJECT"
                    reason = "REJECTED_ENTITY_MISMATCH_IPHONES_NOT_WIDGETS"
                # Android version list is NOT a widget list
                elif "list of android version" in text_lower and "everything is a widget" not in text_lower:
                    decision = "REJECT"
                    reason = "REJECTED_ENTITY_MISMATCH_ANDROID_VERSIONS_NOT_WIDGETS"
                # Must discuss widgets
                elif "widget" not in text_lower:
                    decision = "REJECT"
                    reason = "REJECTED_ENTITY_MISMATCH_NO_WIDGET"

            # -------------------------------------------------------------
            # 2. Target Entity: Device (Supported iOS / iPhones)
            # -------------------------------------------------------------
            elif target_entity == "device" or subject == "ios_device":
                if not any(p in text_lower for p in ("ios", "iphone", "apple", "device")):
                    decision = "REJECT"
                    reason = "REJECTED_ENTITY_MISMATCH_NOT_DEVICE"
                elif "everything is a widget" in text_lower:
                    decision = "REJECT"
                    reason = "REJECTED_ENTITY_MISMATCH_WIDGETS_NOT_DEVICES"

            # -------------------------------------------------------------
            # 3. Target Entity: Version (Android Versions)
            # -------------------------------------------------------------
            elif target_entity == "version" or subject == "android_version":
                if "android" not in text_lower or not any(w in text_lower for w in ("version", "versions", "cupcake", "donut", "kitkat", "oreo")):
                    decision = "REJECT"
                    reason = "REJECTED_ENTITY_MISMATCH_NOT_ANDROID_VERSION"

            # -------------------------------------------------------------
            # 4. Target Entity: Statutory Act Title
            # -------------------------------------------------------------
            elif target_entity == "act" or subject == "act_title":
                # Must contain statutory naming formula or act title clause
                if not any(p in text_lower for p in ("this act may be called", "short title", "act, 20", "act 20", "act, 19", "act 19")):
                    decision = "REJECT"
                    reason = "REJECTED_ENTITY_MISMATCH_NO_ACT_TITLE_FORMULA"

            # -------------------------------------------------------------
            # 5. Subject: Native App
            # -------------------------------------------------------------
            elif subject == "native_app":
                if "native" not in text_lower:
                    decision = "REJECT"
                    reason = "REJECTED_SUBJECT_MISMATCH_NO_NATIVE"
                elif any(p in text_lower for p in ("list of supported ios", "list of android version")):
                    decision = "REJECT"
                    reason = "REJECTED_SUBJECT_MISMATCH_DEVICE_LIST"

            # -------------------------------------------------------------
            # 6. Subject: Hybrid App
            # -------------------------------------------------------------
            elif subject == "hybrid_app":
                if "hybrid" not in text_lower:
                    decision = "REJECT"
                    reason = "REJECTED_SUBJECT_MISMATCH_NO_HYBRID"

            # -------------------------------------------------------------
            # 7. Subject: Flutter (General)
            # -------------------------------------------------------------
            elif subject in ("flutter", "flutter_install"):
                # Must contain Flutter or mobile development concepts
                if "flutter" not in text_lower and "sdk" not in text_lower:
                    decision = "REJECT"
                    reason = "REJECTED_SUBJECT_MISMATCH_NO_FLUTTER"
                # Reject statutory acts or device compatibility tables when asking about Flutter definition/install
                elif "this act may be called" in text_lower:
                    decision = "REJECT"
                    reason = "REJECTED_DOC_SCOPE_MISMATCH_ACT_CHUNK"

            # -------------------------------------------------------------
            # 8. Score Calibration Gate for General Academic Queries
            # -------------------------------------------------------------
            if decision == "ACCEPT":
                # If score is very negative (< -8.5) and lacks core query terms, reject as noise
                if score < -8.5:
                    query_words = set(re.findall(r"\b[a-z]{3,}\b", query_norm)) - {
                        "what", "is", "the", "are", "and", "for", "with", "from", "how", "can", "explain", "list"
                    }
                    text_words = set(re.findall(r"\b[a-z]{3,}\b", text_lower))
                    overlap = query_words & text_words
                    if not overlap:
                        decision = "REJECT"
                        reason = "REJECTED_LOW_SCORE_UNVERIFIED"

            audit_entry = {
                "chunk_id": str(candidate.chunk_id),
                "page_number": candidate.page_number,
                "reranker_score": round(score, 4),
                "decision": decision,
                "reason": reason,
            }
            audit_log.append(audit_entry)

            if decision == "ACCEPT":
                accepted.append(candidate)
            else:
                logger.debug(
                    "RelevanceGate rejected candidate p%s (score=%.4f): %s",
                    candidate.page_number,
                    score,
                    reason,
                )

        return accepted, audit_log


_relevance_gate_instance: QueryEvidenceRelevanceGate | None = None


def get_relevance_gate() -> QueryEvidenceRelevanceGate:
    global _relevance_gate_instance
    if _relevance_gate_instance is None:
        _relevance_gate_instance = QueryEvidenceRelevanceGate()
    return _relevance_gate_instance
