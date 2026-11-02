"""
Structured Query Understanding Service.
Performs semantic classification, entity target detection, and pre-retrieval routing.
"""

import re
from typing import ClassVar

from backend.app.schemas.query_understanding import QueryIntent, StructuredQuery

ASSISTANT_IDENTITY_ANSWER = (
    "I am the Multimodal RAG-Based University Knowledge Assistant. "
    "I can help you search, understand, and review course materials, lecture notes, syllabus topics, "
    "and university regulations with verified citations."
)

ASSISTANT_HELP_ANSWER = (
    "I can help you with your academic studies by searching authorized course materials. "
    "You can ask me to define concepts (e.g., 'What is Flutter?'), explain topics ('What is a native app?'), "
    "list documented components ('What are the advantages of Flutter?'), or lookup university regulations. "
    "All factual answers include clickable source citations."
)

ASSISTANT_GREETING_ANSWER = (
    "Hello! I am your University Knowledge Assistant. How can I help you with your course materials today?"
)

ASSISTANT_THANKS_ANSWER = (
    "You're welcome! Let me know if you have any other questions about your course materials or university documents."
)

AMBIGUOUS_CLARIFICATION_ANSWER = (
    "Could you please clarify your question? For example, are you looking for a list of Flutter widgets, "
    "supported iOS devices, or Android versions?"
)


class QueryUnderstandingService:
    """
    Analyzes raw queries to produce structured semantic queries with target entity identification
    and routing decisions before document retrieval.
    """

    _IDENTITY_PATTERNS: ClassVar[list[str]] = [
        r"\b(?:what(?:'s|\s+is)?|tell\s+me)\s+(?:your|the\s+assistant(?:'s)?)\s+name\b",
        r"\bwho\s+are\s+you\b",
        r"\bwhat\s+(?:are\s+you|should\s+i\s+call\s+you)\b",
        r"\bwhat\s+is\s+this\s+assistant\b",
        r"\byour\s+name\b",
        r"\bwho\s+made\s+you\b",
    ]

    _GREETING_PATTERNS: ClassVar[list[str]] = [
        r"^(?:hi|hello|hey|howdy|greetings|good\s+(?:morning|afternoon|evening))\b",
    ]

    _HELP_PATTERNS: ClassVar[list[str]] = [
        r"^(?:help|what\s+can\s+you\s+do|how\s+can\s+you\s+help(?:\s+me)?|how\s+does\s+this\s+work|how\s+to\s+use(?:\s+this)?)\??$",
    ]

    _THANKS_PATTERNS: ClassVar[list[str]] = [
        r"^(?:thanks|thank\s+you|thanks\s+a\s+lot|thx|many\s+thanks|thankyou)\b",
    ]

    _OUT_OF_SCOPE_PATTERNS: ClassVar[list[str]] = [
        r"\b(?:narendra\s+modi|modi|pm\s+modi)\b",
        r"\b(?:virat\s+kohli|kohli|kahli|rohit\s+sharma|ms\s+dhoni|sachin\s+tendulkar)\b",
        r"\b(?:rahul\s+gandhi|donald\s+trump|trump|elon\s+musk)\b",
        r"\b(?:cricket\s+score|ipl|bollywood|hollywood|movie\s+review|weather\s+today|latest\s+news)\b",
        r"\bwho\s+is\s+the\s+prime\s+minister\b",
        r"\bwho\s+is\s+the\s+president\s+of\b",
    ]

    _AMBIGUOUS_PATTERNS: ClassVar[list[str]] = [
        r"^(?:list|widgets?|versions?|devices?|current\s+version|show\s+list|give\s+me\s+a\s+list)\??$",
    ]

    def analyze(self, raw_query: str) -> StructuredQuery:
        """
        Analyze a raw user query and produce a StructuredQuery.
        """
        raw = raw_query.strip()
        normalized = re.sub(r"\s+", " ", raw.lower()).strip()
        clean_text = re.sub(r"[?!.,;:]+$", "", normalized).strip()

        # 1. Check Assistant Identity
        for pattern in self._IDENTITY_PATTERNS:
            if re.search(pattern, clean_text):
                return StructuredQuery(
                    original_query=raw,
                    normalized_query=normalized,
                    intent=QueryIntent.IDENTITY,
                    subject="assistant",
                    requested_property="identity",
                    target_entity_type="assistant",
                    is_conversational=True,
                    requires_retrieval=False,
                )

        # 2. Check Greeting
        for pattern in self._GREETING_PATTERNS:
            if re.match(pattern, clean_text):
                return StructuredQuery(
                    original_query=raw,
                    normalized_query=normalized,
                    intent=QueryIntent.GREETING,
                    subject="greeting",
                    requested_property="greeting",
                    is_conversational=True,
                    requires_retrieval=False,
                )

        # 3. Check Help
        for pattern in self._HELP_PATTERNS:
            if re.match(pattern, clean_text):
                return StructuredQuery(
                    original_query=raw,
                    normalized_query=normalized,
                    intent=QueryIntent.HELP,
                    subject="assistant",
                    requested_property="help",
                    is_conversational=True,
                    requires_retrieval=False,
                )

        # 4. Check Acknowledgements
        for pattern in self._THANKS_PATTERNS:
            if re.match(pattern, clean_text):
                return StructuredQuery(
                    original_query=raw,
                    normalized_query=normalized,
                    intent=QueryIntent.CONVERSATIONAL,
                    subject="acknowledgement",
                    requested_property="thanks",
                    is_conversational=True,
                    requires_retrieval=False,
                )

        # 5. Check Out-of-Scope (Celebrities / Pop-culture / Non-course facts)
        for pattern in self._OUT_OF_SCOPE_PATTERNS:
            if re.search(pattern, clean_text):
                return StructuredQuery(
                    original_query=raw,
                    normalized_query=normalized,
                    intent=QueryIntent.OUT_OF_SCOPE,
                    subject="general_knowledge",
                    requested_property="general_fact",
                    is_out_of_scope=True,
                    requires_retrieval=False,
                )

        # 6. Check Ambiguous queries requiring clarification
        for pattern in self._AMBIGUOUS_PATTERNS:
            if re.match(pattern, clean_text):
                return StructuredQuery(
                    original_query=raw,
                    normalized_query=normalized,
                    intent=QueryIntent.AMBIGUOUS,
                    subject="ambiguous",
                    requested_property="clarification",
                    is_ambiguous=True,
                    requires_retrieval=False,
                    clarification_prompt=AMBIGUOUS_CLARIFICATION_ANSWER,
                )

        # 6b. Whole-Document Summarization Queries
        is_summary_kw = any(w in clean_text for w in ("summarize", "summary", "overview", "main topics", "exam notes"))
        is_doc_kw = any(w in clean_text for w in ("pdf", "document", "file", "notes", "entire", "whole", "course material", "all pages"))
        if is_summary_kw and (is_doc_kw or "flutter" in clean_text):
            doc_hint = "1-Flutter-Intro.pdf" if "flutter" in clean_text else None
            return StructuredQuery(
                original_query=raw,
                normalized_query=normalized,
                intent=QueryIntent.DOCUMENT_SUMMARY,
                subject="flutter" if "flutter" in clean_text else "document_summary",
                target_entity_type="document",
                requested_property="summary",
                requires_retrieval=True,
                requires_document_summary=True,
                target_document_hint=doc_hint,
            )

        # 7. Academic / Grounded Queries
        # 7a. Statutory Act title queries
        if any(
            p in clean_text
            for p in (
                "act name",
                "name of the act",
                "name of this act",
                "short title",
                "title of the act",
                "title of this act",
                "which act",
                "what act",
                "act title",
            )
        ):
            return StructuredQuery(
                original_query=raw,
                normalized_query=normalized,
                intent=QueryIntent.FACT_LOOKUP,
                subject="act_title",
                target_entity_type="act",
                requested_property="title",
                requires_retrieval=True,
            )

        # 7b. Widget queries
        if "widget" in clean_text:
            if any(p in clean_text for p in ("categories", "category", "which widget", "what widget categories")):
                return StructuredQuery(
                    original_query=raw,
                    normalized_query=normalized,
                    intent=QueryIntent.FACT_LOOKUP,
                    subject="flutter_widget",
                    target_entity_type="widget_category",
                    requested_property="categories",
                    requires_retrieval=True,
                )
            if any(p in clean_text for p in ("list", "enumerate", "types", "all widgets", "what widgets")):
                return StructuredQuery(
                    original_query=raw,
                    normalized_query=normalized,
                    intent=QueryIntent.LIST,
                    subject="flutter_widget",
                    target_entity_type="widget",
                    requested_property="list",
                    requires_retrieval=True,
                )
            return StructuredQuery(
                original_query=raw,
                normalized_query=normalized,
                intent=QueryIntent.DEFINITION,
                subject="flutter_widget",
                target_entity_type="widget",
                requested_property="definition",
                requires_retrieval=True,
            )

        # 7c. iOS Devices queries
        if any(p in clean_text for p in ("ios device", "ios devices", "supported ios", "supported iphone", "iphones", "iphone models")):
            return StructuredQuery(
                original_query=raw,
                normalized_query=normalized,
                intent=QueryIntent.LIST if any(w in clean_text for w in ("list", "what", "which", "supported")) else QueryIntent.FACT_LOOKUP,
                subject="ios_device",
                target_entity_type="device",
                requested_property="list",
                requires_retrieval=True,
            )

        # 7d. Android Version queries
        if "android version" in clean_text or "android versions" in clean_text:
            return StructuredQuery(
                original_query=raw,
                normalized_query=normalized,
                intent=QueryIntent.LIST,
                subject="android_version",
                target_entity_type="version",
                requested_property="list",
                requires_retrieval=True,
            )

        # 7e. Native App queries
        if "native app" in clean_text or "native apps" in clean_text:
            if any(p in clean_text for p in ("benefit", "advantage", "pros")):
                return StructuredQuery(
                    original_query=raw,
                    normalized_query=normalized,
                    intent=QueryIntent.EXPLANATION,
                    subject="native_app",
                    target_entity_type="app_type",
                    requested_property="benefits",
                    requires_retrieval=True,
                )
            if "compare" in clean_text or "difference" in clean_text or "vs" in clean_text:
                return StructuredQuery(
                    original_query=raw,
                    normalized_query=normalized,
                    intent=QueryIntent.COMPARISON,
                    subject="native_vs_crossplatform",
                    target_entity_type="app_type",
                    requested_property="comparison",
                    requires_retrieval=True,
                )
            return StructuredQuery(
                original_query=raw,
                normalized_query=normalized,
                intent=QueryIntent.DEFINITION,
                subject="native_app",
                target_entity_type="app_type",
                requested_property="definition",
                requires_retrieval=True,
            )

        # 7f. Hybrid App queries
        if "hybrid app" in clean_text or "hybrid apps" in clean_text:
            return StructuredQuery(
                original_query=raw,
                normalized_query=normalized,
                intent=QueryIntent.DEFINITION,
                subject="hybrid_app",
                target_entity_type="app_type",
                requested_property="definition",
                requires_retrieval=True,
            )

        # 7g. Flutter general
        if "flutter" in clean_text:
            if any(p in clean_text for p in ("install", "setup", "download", "steps")):
                return StructuredQuery(
                    original_query=raw,
                    normalized_query=normalized,
                    intent=QueryIntent.STEPS,
                    subject="flutter_install",
                    requested_property="install_steps",
                    requires_retrieval=True,
                )
            if any(p in clean_text for p in ("advantage", "benefit", "pros")):
                return StructuredQuery(
                    original_query=raw,
                    normalized_query=normalized,
                    intent=QueryIntent.EXPLANATION,
                    subject="flutter",
                    requested_property="advantages",
                    requires_retrieval=True,
                )
            if any(p in clean_text for p in ("simple words", "explain flutter", "describe flutter")):
                return StructuredQuery(
                    original_query=raw,
                    normalized_query=normalized,
                    intent=QueryIntent.EXPLANATION,
                    subject="flutter",
                    requested_property="explanation",
                    requires_retrieval=True,
                )
            if any(p in clean_text for p in ("what is flutter", "define flutter")):
                return StructuredQuery(
                    original_query=raw,
                    normalized_query=normalized,
                    intent=QueryIntent.DEFINITION,
                    subject="flutter",
                    requested_property="definition",
                    requires_retrieval=True,
                )

        # Default fallback: Academic query with general subject
        intent = QueryIntent.EXPLANATION
        if clean_text.startswith("what is") or clean_text.startswith("define"):
            intent = QueryIntent.DEFINITION
        elif clean_text.startswith("how to") or clean_text.startswith("steps"):
            intent = QueryIntent.STEPS
        elif clean_text.startswith("list") or clean_text.startswith("enumerate"):
            intent = QueryIntent.LIST

        return StructuredQuery(
            original_query=raw,
            normalized_query=normalized,
            intent=intent,
            subject="general_academic",
            requested_property="general",
            requires_retrieval=True,
        )


_query_understanding_instance: QueryUnderstandingService | None = None


def get_query_understanding_service() -> QueryUnderstandingService:
    global _query_understanding_instance
    if _query_understanding_instance is None:
        _query_understanding_instance = QueryUnderstandingService()
    return _query_understanding_instance

