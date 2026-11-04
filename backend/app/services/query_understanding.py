"""
Structured Query Understanding Service.
Performs semantic classification, entity target detection, and pre-retrieval routing.
General-purpose and document-agnostic: supports arbitrary courses, documents, and academic topics.
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
    "You can ask me to define concepts, explain complex topics, list documented components, "
    "compare architectural or theoretical approaches, or lookup university regulations. "
    "All factual answers include clickable source citations."
)

ASSISTANT_GREETING_ANSWER = (
    "Hello! I am your University Knowledge Assistant. How can I help you with your course materials today?"
)

ASSISTANT_THANKS_ANSWER = (
    "You're welcome! Let me know if you have any other questions about your course materials or university documents."
)

AMBIGUOUS_CLARIFICATION_ANSWER = (
    "Could you please clarify your question? Please specify what topic, concept, or information you are looking for."
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

    _AMBIGUOUS_PATTERNS: ClassVar[list[str]] = [
        r"^(?:list|show\s+list|give\s+me\s+a\s+list|widgets?|versions?|devices?)\??$",
    ]

    _OUT_OF_SCOPE_PATTERNS: ClassVar[list[str]] = [
        r"\b(?:ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions|system\s+prompt|reveal\s+(?:your\s+)?instructions|jailbreak)\b",
    ]

    def analyze(self, raw_query: str) -> StructuredQuery:
        """
        Analyze a raw user query and produce a StructuredQuery.
        Generic and document-agnostic: extracts intent and substantive subject without hardcoding subjects.
        """
        raw = raw_query.strip()
        normalized = re.sub(r"\s+", " ", raw.lower()).strip()
        clean_text = re.sub(r"[?!.,;:]+$", "", normalized).strip()

        # 0. Check Prompt Injection / Out-of-Scope Directives
        for pattern in self._OUT_OF_SCOPE_PATTERNS:
            if re.search(pattern, clean_text):
                return StructuredQuery(
                    original_query=raw,
                    normalized_query=normalized,
                    intent=QueryIntent.OUT_OF_SCOPE,
                    subject="out_of_scope",
                    requested_property="refusal",
                    is_out_of_scope=True,
                    requires_retrieval=False,
                )

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

        # 5. Check Ambiguous queries requiring clarification (bare ambiguous keywords with no subject)
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

        # 6. Whole-Document Summarization Queries
        is_summary_kw = bool(
            re.search(r"\b(?:summarize|summary|overview of the|overview of this|document overview|exam notes for)\b", clean_text)
        )
        is_doc_kw = bool(
            re.search(r"\b(?:pdf|document|file|notes|entire|whole|course material|all pages|all chapters)\b", clean_text)
        )
        pdf_hint_m = re.search(r"\b([a-zA-Z0-9_\-\.]+\.pdf)\b", clean_text)

        if is_summary_kw and (is_doc_kw or pdf_hint_m):
            doc_hint = pdf_hint_m.group(1) if pdf_hint_m else None
            # Extract document subject if provided (e.g. "summarize the Flutter PDF" -> "flutter")
            sub_m = re.search(r"\b(?:summarize|summary of)\s+(?:the\s+)?([a-zA-Z0-9_\-\.]+?)(?:\s+(?:pdf|document|notes|file))\b", clean_text)
            subj = sub_m.group(1).strip() if sub_m else "document"
            return StructuredQuery(
                original_query=raw,
                normalized_query=normalized,
                intent=QueryIntent.DOCUMENT_SUMMARY,
                subject=subj,
                target_entity_type="document",
                requested_property="summary",
                requires_retrieval=True,
                requires_document_summary=True,
                target_document_hint=doc_hint,
            )

        # 7. Generic Academic / Grounded Queries
        # 7a. Comparison intent
        m_comp1 = re.match(r"^(?:compare|difference between|differences between|differentiate between)\s+(?:the\s+)?(.+)$", clean_text)
        if m_comp1:
            return StructuredQuery(
                original_query=raw,
                normalized_query=normalized,
                intent=QueryIntent.COMPARISON,
                subject=m_comp1.group(1).strip(),
                requested_property="comparison",
                requires_retrieval=True,
            )
        m_comp2 = re.match(r"^(.+?)\s+(?:vs\.?|versus)\s+(.+)$", clean_text)
        if m_comp2:
            return StructuredQuery(
                original_query=raw,
                normalized_query=normalized,
                intent=QueryIntent.COMPARISON,
                subject=f"{m_comp2.group(1).strip()} vs {m_comp2.group(2).strip()}",
                requested_property="comparison",
                requires_retrieval=True,
            )

        # 7b. Steps / Procedure intent
        m_steps = re.match(r"^(?:how\s+to|steps\s+to|steps\s+for|procedure\s+for|how\s+do\s+i)\s+(.+)$", clean_text)
        if m_steps:
            return StructuredQuery(
                original_query=raw,
                normalized_query=normalized,
                intent=QueryIntent.STEPS,
                subject=m_steps.group(1).strip(),
                requested_property="procedure",
                requires_retrieval=True,
            )

        # 7c. List / Enumerate intent
        m_list = re.match(r"^(?:list|enumerate|what\s+are\s+the\s+types\s+of|name\s+all|name\s+the|give\s+me\s+a\s+list\s+of|show\s+all)\s+(?:the\s+)?(.+)$", clean_text)
        if m_list:
            return StructuredQuery(
                original_query=raw,
                normalized_query=normalized,
                intent=QueryIntent.LIST,
                subject=m_list.group(1).strip(),
                target_entity_type="item",
                requested_property="list",
                requires_retrieval=True,
            )
        if re.search(r"\b(?:list\s+of|all\s+the|types\s+of|versions\s+of|devices\s+supported|categories\s+of)\b", clean_text):
            return StructuredQuery(
                original_query=raw,
                normalized_query=normalized,
                intent=QueryIntent.LIST,
                subject=self._extract_substantive_subject(clean_text),
                target_entity_type="item",
                requested_property="list",
                requires_retrieval=True,
            )

        # 7d. Definition intent
        m_def = re.match(r"^(?:what\s+is|what\s+are|define|definition\s+of|meaning\s+of)\s+(?:a\s+|an\s+|the\s+)?(.+)$", clean_text)
        if m_def:
            return StructuredQuery(
                original_query=raw,
                normalized_query=normalized,
                intent=QueryIntent.DEFINITION,
                subject=m_def.group(1).strip(),
                requested_property="definition",
                requires_retrieval=True,
            )

        # 7e. Explanation intent (including "tell me about X", "describe X", "how does X work")
        m_exp = re.match(r"^(?:tell\s+me\s+about|can\s+you\s+tell\s+me\s+about|describe|can\s+you\s+describe|explain|can\s+you\s+explain|give\s+(?:me\s+)?an\s+overview\s+of)\s+(?:a\s+|an\s+|the\s+)?(.+)$", clean_text)
        if m_exp:
            return StructuredQuery(
                original_query=raw,
                normalized_query=normalized,
                intent=QueryIntent.EXPLANATION,
                subject=m_exp.group(1).strip(),
                requested_property="explanation",
                requires_retrieval=True,
            )
        if re.match(r"^(?:how\s+does|how\s+do|why\s+is|why\s+are|why\s+does)\s+(.+)$", clean_text):
            return StructuredQuery(
                original_query=raw,
                normalized_query=normalized,
                intent=QueryIntent.EXPLANATION,
                subject=self._extract_substantive_subject(clean_text),
                requested_property="explanation",
                requires_retrieval=True,
            )

        # 7f. Fact lookup intent (specific attributes / mentions)
        m_mentioned = re.match(r"^(?:which|what)\s+(.+?)\s+(?:are|is|were|was)\s+(?:mentioned|discussed|covered|included|listed)\b", clean_text)
        if m_mentioned:
            return StructuredQuery(
                original_query=raw,
                normalized_query=normalized,
                intent=QueryIntent.FACT_LOOKUP,
                subject=m_mentioned.group(1).strip(),
                requested_property="fact",
                requires_retrieval=True,
            )

        m_fact = re.match(r"^(?:what\s+is\s+the\s+(?:title|name|date|version|number)\s*(?:of\s+)?|what\s+is\s+(?:the\s+)?(?:\w+\s+)?(?:name|title)|when\s+was|who\s+wrote|who\s+created|who\s+is)\s*(?:the\s+)?(.*)$", clean_text)
        if m_fact:
            subj = m_fact.group(1).strip() if m_fact.group(1) else self._extract_substantive_subject(clean_text)
            return StructuredQuery(
                original_query=raw,
                normalized_query=normalized,
                intent=QueryIntent.FACT_LOOKUP,
                subject=subj,
                requested_property="fact",
                requires_retrieval=True,
            )

        # 7g. Default Academic Query
        return StructuredQuery(
            original_query=raw,
            normalized_query=normalized,
            intent=QueryIntent.EXPLANATION,
            subject=self._extract_substantive_subject(clean_text),
            requested_property="general",
            requires_retrieval=True,
        )

    @staticmethod
    def _extract_substantive_subject(text: str) -> str:
        """Extract substantive topic terms from query text by removing common grammatical prefixes."""
        stop = {
            "what", "is", "are", "the", "a", "an", "and", "or", "for", "with", "from",
            "how", "can", "tell", "me", "about", "describe", "explain", "give", "show",
            "please", "in", "on", "at", "to", "of", "by", "my", "your", "this", "that",
            "mentioned", "notes", "course", "lecture"
        }
        words = [w for w in re.findall(r"\b[a-zA-Z0-9_\-]+\b", text.lower()) if w not in stop]
        return " ".join(words) if words else text.strip()


_query_understanding_instance: QueryUnderstandingService | None = None


def get_query_understanding_service() -> QueryUnderstandingService:
    global _query_understanding_instance
    if _query_understanding_instance is None:
        _query_understanding_instance = QueryUnderstandingService()
    return _query_understanding_instance

