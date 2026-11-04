"""
Grounded LLM Generation Service.

Orchestrates the grounded generation stage:
1. Validates context availability with deterministic empty-context fast-path.
2. Formats system instructions and untrusted evidence via GroundedPromptBuilder.
3. Invokes the provider-independent BaseLLMProvider.
4. Extracts candidate source references for Step 14 citation validation.
5. Returns safe execution metadata without leaking internal secrets.
"""


import logging
import re
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

from backend.app.schemas.llm import (
    LLMGenerationRequest,
    LLMGenerationResponse,
    LLMProviderResponse,
)
from backend.app.services.llm.base import BaseLLMProvider
from backend.app.services.llm.exceptions import (
    LLMConnectionError,
    LLMProviderError,
    LLMResponseError,
    LLMTimeoutError,
)
from backend.app.services.llm.ollama_provider import OllamaLLMProvider
from backend.app.services.llm.prompt_builder import GroundedPromptBuilder, response_format_for_query

# Matches attribution markers formatted as [source_1], [source_2], etc.
_SOURCE_REF_REGEX = re.compile(r"\[(source_\d+)\]", re.IGNORECASE)

SAFE_INSUFFICIENT_EVIDENCE_ANSWER = (
    "I could not find any relevant information in the available documents to answer your question."
)

INSUFFICIENT_COURSE_EVIDENCE_ANSWER = (
    "I could not find any relevant information in the authorized course materials to answer your question. "
    "As an academic assistant, I can only provide answers verified against authorized course documents and lecture notes. "
    "Please ask a question related to your enrolled courses or course materials."
)

GREETING_WORDS = {
    "hi",
    "hello",
    "hey",
    "greetings",
    "good morning",
    "good afternoon",
    "good evening",
    "howdy",
    "help",
}

REASONING_LEAK_PATTERNS = [
    r"\bthe user\s+(?:says|asks|also asks|is asking|question is|wants|is looking for)\b",
    r"\bwe\s+(?:need to determine|must determine|can answer|are to output|can take|can also note|must see|have multiple|are given)\b",
    r"\bwe have\s+(?:three|two|one|\d+|several)?\s*retrieved\b",
    r"\bretrieved evidence chunks?\b",
    r"\blet'?s (?:examine|look at|check|see|inspect)\b",
    r"\bexamine each source\b",
    r"\bsince the\s+(?:evidence|question|user)\b",
    r"\bthe answer\s+should be\b",
    r"\bimportant:\s*we must\b",
    r"\bwe can answer by\b",
    r"\bwe can answer by listing\b",
    r"\bto answer this question,?\s*we\b",
    r"\boption:\s*[A-Z]",
    r"\bnot directly about\b",
    r"\(other points, but\b",
    r"\ba clean markdown list of\b",
    r"\bthe most complete list of\b",
    r"\b(?:focuses on|about\s+.+,\s*not the definition|not directly about|is about\s+.+,\s*but does not|who is using\s+.+,\s*not the definition)\b",
    r"\btherefore,?\s*the definition of\s+.+\s*is provided in\b",
    r"^(?:internal thinking|thinking|scratchpad):\s*",
    r"\b(?:but wait|as per the (?:user's|prompt) instruction|in the response format|the evidence only tells us|the evidence we have|we cannot provide a list of individual widget)\b",
    r"\b(?:evidence does not contain that information|does not explicitly state the two primary)\b",
    r"\b(?:first,?\s*)?(?:looking at|analyzing|examining)\s+\[?source_\d+\]?\b",
    r"\bfor the question\b",
    r"\b(?:i|we)\s+should\s+(?:focus|cover|explain|highlight|start|mention)\b",
    r"\b(?:i|we)\s+must\s+not\s+mention\b",
    r"\b(?:i'll|i\s+will|we'll|we\s+will)\s+avoid\b",
    r"\bstart with:\s*\"?",
    r"\bthen add(?:\s+the)?:\s*\"?",
    r"\bcite only\s+\[?source_\d+\]?\b",
    r"\bcheck if\s+(?:i'm|we're|i\s+am|we\s+are)\b",
    r"\bthe student-friendly explanation\b",
    r"\bwhat are the concepts mentioned\b",
    r"\bthe key point:\s*the evidence\b",
    r"\b(?:i|we)\s+need to\s+(?:be|cite|check|ensure)\b",
    r"\b(?:i|we)\s+should respond by\b",
    r"\bthe user might be expecting\b",
    r"\b(?:wait|but wait),?\s+(?:the\s+)?instructions?\b",
]


NON_ANSWER_DEFLECTION_PATTERNS = [
    r"\b(?:please\s+)?refer to (?:the\s+)?(?:cited|provided|above|referenced)?\s*(?:material|documents?|sources?|text|details)\b",
    r"\bfor (?:the\s+)?(?:complete|more|further)\s*details,?\s*(?:please\s+)?refer to\b",
    r"\bdetails can be found in (?:the\s+)?(?:cited|provided|above|referenced)\b",
    r"\b(?:please\s+)?see (?:the\s+)?(?:cited|provided|above|referenced)\s*(?:material|documents?|sources?)\b",
    r"\bconsult (?:the\s+)?(?:cited|provided|above|referenced)\s*(?:material|documents?|sources?)\b",
    r"\bcited material for (?:the\s+)?complete details\b",
    r"\bcomplete details (?:can be found|are available|are given) in\b",
    r"\bthe answer (?:can be found|is given) in (?:the\s+)?(?:cited|provided)\b",
    r"\bplease check the cited\b",
    r"\brefer to the citations?\b",
]


def is_reasoning_or_non_answer(text: str, query: str) -> bool:
    """Detect obvious internal deliberation leakage, generic deflections, or meta preambles without answers."""
    t_clean = text.strip().lower()
    if not t_clean:
        return True
    for p in REASONING_LEAK_PATTERNS:
        if re.search(p, t_clean):
            return True
    for p in NON_ANSWER_DEFLECTION_PATTERNS:
        if re.search(p, t_clean):
            return True
    if re.search(
        r"\b(?:the answer should be|we can answer by|the list is given in|the list of .+ is the one in|the answer is in|we are given|let'?s examine|but wait|as per the user'?s instruction|evidence only tells us)\b",
        t_clean,
    ):
        return True
    # Dangling fragment ending with preposition or incomplete connector (e.g. "provided in.")
    if re.search(r"(?i)\b(?:is provided in|provided in|is stated in|stated in|is given in|can be found in)\s*[\.\!\?]?$", t_clean):
        return True
    is_list_query = any(w in query.lower() for w in ("list", "enumerate", "versions", "steps"))
    if is_list_query:
        has_items = any(ch in text for ch in ("\n-", "\n*", "\n1.", "\n2.", "•", "▪", "●", "▸"))
        if not has_items and len(text.split()) < 25 and not any(w in text.lower() for w in ("widget", "concept", "category", "categories")):
            return True
    return False


def is_invalid_or_incomplete_answer(text: str, query: str = "") -> bool:
    """
    Validate whether sanitized model output is incomplete, pure deflection, or non-answer.
    Ensures that trailing fragments, deflections, or scratchpad outputs trigger bounded retry.
    """
    t_clean = (text or "").strip()
    if not t_clean:
        return True

    # Check for truncated prose output: prose paragraphs should terminate naturally
    last_line = t_clean.splitlines()[-1].strip()
    is_bullet = bool(re.match(r"^(?:[-*•▪●▸]|\d+\.)\s+", last_line))
    if not is_bullet:
        if last_line and not any(last_line.endswith(term) for term in (".", "!", "?", '"', "'", ")", "]", "```", "~~~")):
            return True

    # Incomplete sentence / dangling preposition fragment / pure deflection
    # e.g., "The definition of Flutter is provided in." or "The answer is given in [source_1]."
    if re.search(
        r"(?i)\b(?:is provided in|provided in|is stated in|stated in|is given in|can be found in|refer to the cited|see the cited)\s*(?:\[source_\d+\]\s*)?[\.\!\?]?$",
        t_clean,
    ):
        return True

    # Dangling trailing connective / preposition / auxiliary / incomplete fragment (e.g. "I'll avoid", "consists of.")
    if re.search(
        r"(?i)\b(?:is|are|in|on|at|to|from|for|with|of|by|about|that|which|avoid|check|if|i'm|i'll|we'll|can|will|should|would|must|including|such as)\s*[\.\!\?]?$",
        t_clean,
    ):
        return True

    # Pure non-answer deflection patterns
    for p in NON_ANSWER_DEFLECTION_PATTERNS:
        if re.search(p, t_clean.lower()) and len(t_clean.split()) < 25:
            return True

    # Pure reasoning leakage without substantive answer
    if is_reasoning_or_non_answer(t_clean, query):
        return True

    # Extremely short non-answer (fewer than 5 words that don't express lack of info)
    if len(t_clean.split()) < 5 and not any(
        kw in t_clean.lower()
        for kw in ("not enough information", "insufficient", "could not find", "no information")
    ):
        return True

    return False


def clean_reasoning_text(text: str, query: str = "") -> str:
    """
    Extract clean final answer conclusion from reasoning or deliberation text if present.
    Does not synthesize artificial sentences, stitch quotes, or salvage fragments.
    """
    conclusion_match = re.search(
        r"(?:So the answer should be:|The answer should be:|The answer is:?|Final\s+Answer:|Conclusion:|In\s+summary,?|Therefore,?\s*(?:the answer is:?)?)\s*(.+)$",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if conclusion_match:
        cand = conclusion_match.group(1).strip()
        if not any(re.search(p, cand, re.IGNORECASE) for p in REASONING_LEAK_PATTERNS) and len(cand.split()) >= 5:
            return cand

    return text


def extract_grounded_recovery_answer(
    query: str,
    context: Any,
) -> str | None:
    """
    Deprecated recovery helper.

    In Phase 26, factual answers must be synthesized directly by the configured
    LLM provider (Ollama) rather than constructed via deterministic Python templates.
    Returns None so that primary LLM synthesis or safe refusal is authoritative.
    """
    return None


def format_inline_list_items(text: str, query: str | None = None) -> str:
    """Repair an inline list only when the user explicitly requested that shape.

    This deliberately avoids parsing arbitrary prose into bullets. Android/version
    entries are split only at complete ``Android [version] N`` item boundaries; a
    bare ``Version 12`` is never treated as a new item boundary, which previously
    separated "Android version 12 (2021)" into two unrelated fragments.
    """
    if not text or response_format_for_query(query) not in {"list", "steps"}:
        return text

    # Existing Markdown lists already have explicit boundaries; preserve them.
    existing_items = re.findall(
        r"(?m)^\s*(?:[-*•▪●▸]|\d+\.)\s+\S+",
        text,
    )
    if len(existing_items) >= 2:
        return text

    flattened = re.sub(r"\s+", " ", text).strip()
    if not flattened:
        return text

    android_boundary = re.compile(
        r"(?i)(?<![A-Za-z0-9])Android\s+(?:version\s+)?\d+(?:\.\d+)?"
    )
    android_matches = list(android_boundary.finditer(flattened))
    if len(android_matches) >= 2:
        items = [
            flattened[match.start() : android_matches[index + 1].start()].strip(" \t,;:-")
            if index + 1 < len(android_matches)
            else flattened[match.start() :].strip(" \t,;:-")
            for index, match in enumerate(android_matches)
        ]
        prefix = flattened[: android_matches[0].start()].strip(" \t:-")
        items = [item for item in items if item]
        if len(items) >= 2:
            header = _clean_list_header(prefix)
            list_body = "\n".join(f"- {item}" for item in items)
            return f"{header}\n\n{list_body}" if header else list_body

    # Repair a compact, sequential inline enumeration without interpreting decimal
    # versions or years as list numbers. Preserve ordered numbering for a step query.
    number_pattern = re.compile(r"(?<![A-Za-z0-9])([1-9]\d{0,2})\.\s+(?=\S)")
    number_matches = list(number_pattern.finditer(flattened))
    if len(number_matches) >= 2:
        numbers = [int(match.group(1)) for match in number_matches]
        if numbers == list(range(numbers[0], numbers[0] + len(numbers))) and numbers[0] == 1:
            prefix = flattened[: number_matches[0].start()].strip(" \t:-")
            items = [
                flattened[match.end() : number_matches[index + 1].start()].strip(" \t,;:-")
                if index + 1 < len(number_matches)
                else flattened[match.end() :].strip(" \t,;:-")
                for index, match in enumerate(number_matches)
            ]
            items = [item for item in items if item]
            if len(items) >= 2:
                if response_format_for_query(query) == "steps":
                    list_body = "\n".join(
                        f"{index}. {item}" for index, item in enumerate(items, start=1)
                    )
                else:
                    list_body = "\n".join(f"- {item}" for item in items)
                header = _clean_list_header(prefix)
                return f"{header}\n\n{list_body}" if header else list_body

    return text


def _clean_list_header(prefix: str) -> str:
    """Keep a meaningful intro but discard orphaned citation-only prefixes."""
    cleaned = re.sub(r"\[(?:source_\d+)\]", "", prefix, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" \t:-;,.\u2014")
    if not cleaned or len(cleaned.split()) > 24:
        return ""
    return cleaned


def deduplicate_list_citations(text: str) -> str:
    """Consolidate identical source tags on a list, including tags repeated mid-item.

    When every list item cites one and the same source, put that citation on the
    list introduction (or on the first item when no introduction exists). If items
    use different sources, preserve those distinctions while removing duplicate
    occurrences of the same source within an individual item.
    """
    if not text:
        return text

    lines = text.splitlines()
    bullet_pattern = re.compile(r"^(\s*(?:[-*•▪●▸]|\d+\.)\s+)(.*)$")
    bullet_indexes = [
        index for index, line in enumerate(lines) if bullet_pattern.match(line)
    ]
    if len(bullet_indexes) < 2:
        return text

    per_item_sources: list[list[str]] = []
    for index in bullet_indexes:
        match = bullet_pattern.match(lines[index])
        assert match is not None
        sources = [source.lower() for source in _SOURCE_REF_REGEX.findall(match.group(2))]
        per_item_sources.append(sources)

    all_sources = {source for sources in per_item_sources for source in sources}
    if not all_sources:
        any_source = _SOURCE_REF_REGEX.findall(text)
        if any_source:
            source_tag = any_source[0].lower()
            canonical = f"[{source_tag}]"
            first_bullet = bullet_indexes[0]
            first = bullet_pattern.match(lines[first_bullet])
            if first:
                lines[first_bullet] = f"{first.group(1)}{first.group(2).rstrip()} {canonical}"
            return "\n".join(lines)

    same_single_source = (
        len(all_sources) == 1
        and all(sources for sources in per_item_sources)
    )

    if same_single_source:
        source_tag = next(iter(all_sources))
        canonical = f"[{source_tag}]"
        for index in bullet_indexes:
            match = bullet_pattern.match(lines[index])
            assert match is not None
            body = _SOURCE_REF_REGEX.sub("", match.group(2))
            body = re.sub(r"\s+([,.;:!?])", r"\1", body)
            body = re.sub(r"[ \t]{2,}", " ", body).strip()
            lines[index] = f"{match.group(1)}{body}"

        first_bullet = bullet_indexes[0]
        previous_nonblank = next(
            (i for i in range(first_bullet - 1, -1, -1) if lines[i].strip()),
            None,
        )
        if previous_nonblank is not None:
            header = _SOURCE_REF_REGEX.sub("", lines[previous_nonblank]).strip()
            header = header.rstrip(" :")
            lines[previous_nonblank] = f"{header} {canonical}:" if header else canonical
        else:
            # A citation on the first item is clearer than inventing a generic heading.
            first = bullet_pattern.match(lines[first_bullet])
            assert first is not None
            lines[first_bullet] = f"{first.group(1)}{first.group(2).rstrip()} {canonical}"
        return "\n".join(lines)

    # For multi-source lists, only collapse a repeated identical tag within a single
    # item; do not remove a distinct source that supports another item.
    for index in bullet_indexes:
        match = bullet_pattern.match(lines[index])
        assert match is not None
        seen: set[str] = set()

        def keep_first(source_match: re.Match[str]) -> str:
            source = source_match.group(1).lower()
            if source in seen:
                return ""
            seen.add(source)
            return f"[{source}]"

        body = _SOURCE_REF_REGEX.sub(keep_first, match.group(2))
        body = re.sub(r"[ \t]{2,}", " ", body).strip()
        lines[index] = f"{match.group(1)}{body}"

    return "\n".join(lines)


def _sanitize_llm_answer(text: str, query: str | None = None) -> str:
    """
    Strip model self-reasoning preambles, chain-of-thought evaluations, and instruction leaks.
    Extracts the clean, direct factual answer with verified citations while preserving valid
    paragraphs, lists, headings, tables, and fenced code blocks.
    """
    if not text:
        return text

    # 1. Strip private reasoning channels and <think> blocks
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    # Protect code blocks and tables from line-level stripping, capitalizing, or flattening
    code_blocks: list[str] = []

    def _save_cb(m: re.Match) -> str:
        code_blocks.append(m.group(0))
        return f"\n\n__CODE_BLOCK_{len(code_blocks)-1}__\n\n"

    cleaned = re.sub(r"(?s)(?:```|~~~).*?(?:```|~~~)", _save_cb, cleaned)

    tables: list[str] = []

    def _save_tb(m: re.Match) -> str:
        tables.append(m.group(0).strip())
        return f"\n\n__TABLE_BLOCK_{len(tables)-1}__\n\n"

    cleaned = re.sub(r"(?m)^(?:\|[^\n]+\|\s*(?:\r?\n|$)){2,}", _save_tb, cleaned)

    # 2. Check for explicit conclusion marker, unless content already contains an itemized list
    raw_lines = cleaned.splitlines()
    has_itemized_list = any(re.match(r"^\s*[-*•▪●▸\d+.]\s+[A-Za-z0-9]", line) for line in raw_lines)

    if not has_itemized_list:
        therefore_match = re.search(
            r"(?:Therefore|In conclusion|Consequently|The sequence is:?|The workflow is:?|The failover sequence is:?|The automated failover sequence is:?|The answer is:?|Sequence:)\s*(.+)",
            cleaned,
            re.IGNORECASE | re.DOTALL,
        )
        if therefore_match:
            preceding = cleaned[:therefore_match.start()].strip()
            preceding_has_citation = bool(re.search(r"\[source_\d+\]", preceding, re.IGNORECASE))
            preceding_is_reasoning = any(re.search(p, preceding, re.IGNORECASE) for p in REASONING_LEAK_PATTERNS)
            if not (preceding_has_citation and not preceding_is_reasoning and len(preceding.split()) >= 8):
                conclusion = therefore_match.group(1).strip()
                conclusion = conclusion.lstrip(",;: \t\n\"'")
                # Drop meta-notes like 'But note: ...' and subsequent source breakdowns
                conclusion = re.split(
                    r"(?:\"?\s*-\s*(?:This source|source_|Figure|Visual|Visible|Key Flows)|\n+\s*(?:But note|Note:|However, note|The user question is|Answer:))",
                    conclusion,
                    flags=re.IGNORECASE,
                )[0].strip().rstrip("\"' \t\n")
                if (
                    conclusion
                    and not any(re.search(p, conclusion, re.IGNORECASE) for p in REASONING_LEAK_PATTERNS)
                    and not re.search(r"^(?:we\s+output|we\s+can\s+output|the\s+list\s+is\s+from|the\s+answer\s+is\s+in)\b", conclusion, re.IGNORECASE)
                ):
                    marker_raw = therefore_match.group(0).lower()
                    prefix = ""
                    if "sequence" in marker_raw and not conclusion.lower().startswith("the sequence is"):
                        prefix = "The sequence is: "
                    elif "workflow" in marker_raw and not conclusion.lower().startswith("the workflow is"):
                        prefix = "The workflow is: "
                    capped = conclusion[0].upper() + conclusion[1:] if conclusion else ""
                    cleaned = prefix + capped

    # 3. Strip trailing prompt instruction echoes and scaffolding leaks
    cleaned = re.sub(r'(?i)\b(?:important:?\s*)?(?:the\s+)?(?:core\s+)?directive\b.*?(?:explicitly\s+present[^\.]*\.|\.|\Z)', '', cleaned)
    cleaned = re.sub(r'(?i)\bgrounding:\s*answer\s+using\s+only\s+facts\b.*?(?:explicitly\s+present[^\.]*\.|\.|\Z)', '', cleaned)
    cleaned = re.sub(r'(?:\[source_\d+\]\s*)?(?:states|says|provides):\s*$', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
    cleaned = re.sub(r'^\s*\d+\s*(?:\[source_\d+\]\s*)?[\.:\)]\s*', '', cleaned)
    split_parts = re.split(
        r"\n+\s*(?:(?:however|note|but),?\s+)?(?:we\s+must\s+(?:output|be\s+precise|ensure)|(?:the\s+)?user\s+question\b|question:|answer:)",
        cleaned,
        flags=re.IGNORECASE,
    )
    if len(split_parts) > 1:
        first_part = split_parts[0].strip()
        if len(first_part.split()) >= 15 or any(ch in first_part for ch in ("\n-", "\n*", "\n1.")):
            cleaned = first_part
        else:
            rest = "\n".join(split_parts[1:]).strip()
            if rest:
                cleaned = rest

    # 4. Line by line filter of reasoning prefixes, internal scratchpads, and bullet evaluations
    reasoning_step_regex = re.compile(
        r"^step\s*\d+\s*:?\s*(?:"
        r"analyze|analyse|review|check|inspect|examine|look at|consider|"
        r"determine|evaluate|read|understand|identify|extract|verify whether|"
        r"consult|summarize the sources?"
        r")\s+(?:the\s+)?(?:source|prompt|question|directive|context|retrieved|evidence|provided|document)",
        re.IGNORECASE,
    )
    source_header_regex = re.compile(
        r"^[-*•]?\s*(?:"
        r"(?:flowchart|diagram|figure|visual|table)\s+on\s+page\s+\d+|"
        r"page\s+\d+\s+of\s+[^\n]+|"
        r"figure\s+\d+\s*:|"
        r"source\s*\d+\s*:"
        r")[^\n]*$",
        re.IGNORECASE,
    )
    label_prefix_regex = re.compile(
        r"^[-*•]?\s*(?:Summary|Text|Content)\s*:\s*",
        re.IGNORECASE,
    )
    boilerplate_intro_regex = re.compile(
        r"^(?:(?:So\s+)?Based (?:solely )?on (?:the |all |\[?source_\d+\]? )?(?:[A-Za-z0-9_-]+\s+){0,4}(?:documents?|context|evidence|materials?|syllabus|source_\d+)\.?,?\s*|According to (?:the |all )?(?:[A-Za-z0-9_-]+\s+){0,4}(?:documents?|context|evidence|materials?|syllabus)\.?,?\s*)",
        re.IGNORECASE,
    )

    lines = cleaned.splitlines()
    kept_lines: list[str] = []
    reasoning_prefixes = (
        "the user",
        "a clean markdown",
        "clean markdown",
        "the most complete",
        "we are given",
        "we must",
        "we have",
        "we see",
        "we note",
        "let's",
        "let me",
        "looking at",
        "from source",
        "source_",
        "- source",
        "* source",
        "- from",
        "* from",
        "- content",
        "* content",
        "content:",
        "same as source",
        "both sources",
        "all sources",
        "the evidence provided",
        "- this source",
        "this source",
        "- visual",
        "- visible",
        "- key flows",
        "describes the context",
        "- describes the context",
        "* describes the context",
        "context:",
        "- context:",
        "* context:",
        "according to the prompt",
        "according to the instruction",
        "operating directives",
        "hierarchy of authority",
        "grounding invariance",
        "adversarial resistance",
        "citation attribution",
        "insufficient evidence policy",
        "conflicting evidence",
        "direct output without source evaluation",
        "the most relevant evidence",
        "the relevant evidence",
        "we do not have conflicting",
        "we have no conflicting",
        "no conflicting evidence",
        "only [source_",
        "1. we are to provide",
        "2. we must use only",
        "3. we must cite each",
        "we are to provide",
        "we must use only the facts",
        "we need to",
        "we should",
        "the key sentence",
        "the key fact",
        "extract the facts",
        "as per the evidence",
        "according to the evidence",
        "based on the retrieved evidence",
        "key facts from",
        "key fact from",
        "key facts:",
        "* [source_",
        "- [source_",
        "so here we have:",
        "the user question is",
        "the user question asks",
        "the user asks",
        "the user also asks",
        "the retrieved evidence",
        "from [source",
        "the evidence states",
        "the evidence says",
        "the answer should be",
        "therefore, the answer",
        "therefore the answer",
        "therefore,",
        "therefore",
        "in conclusion",
        "in conclusion,",
        "however, note",
        "however,",
        "however",
        "based solely on",
        "based on source",
        "we write",
        "we can write",
        "so we write",
        "user question:",
        "answer:",
        "internal thinking:",
        "internal thinking",
        "thinking:",
        "scratchpad:",
        "first, looking at",
        "looking at [source",
        "for the question",
        "the student-friendly explanation",
        "important: i must",
        "important: we must",
        "start with:",
        "then add",
        "cite only",
        "check if",
        "i'll avoid",
        "i will avoid",
        "we'll avoid",
        "what are the concepts mentioned",
        "the key point:",
    )
    for line in lines:
        s = line.strip()
        if not s:
            if kept_lines and kept_lines[-1] != "":
                kept_lines.append("")
            continue
        if s.startswith("__CODE_BLOCK_") or s.startswith("__TABLE_BLOCK_"):
            kept_lines.append(s)
            continue
        if reasoning_step_regex.search(s):
            continue
        if source_header_regex.match(s):
            continue
        if re.search(r"(?i)\bakash\s+technolabs\b|\bwww\.[a-z0-9\-]+\.[a-z]+\b", s):
            continue
        if any(s.lower().startswith(p) for p in reasoning_prefixes):
            continue
        if s.lower().startswith("but note:") or s.lower().startswith("however, note:"):
            continue
        if re.search(r"^(?:(?:however|note|but),?\s+)?(?:the\s+)?user\s+(?:question|might|may|asked)\b", s, re.IGNORECASE):
            continue
        if re.search(r"^(?:(?:however|note|but),?\s+)?(?:i|we)\s+(?:must|should|need to|can only|will)\b", s, re.IGNORECASE):
            continue
        if re.search(r"^(?:(?:so\s+)?based on the evidence,?\s+)?(?:i|we)\s+can\s+only\b", s, re.IGNORECASE):
            continue
        if re.search(r"^(?:wait|but wait),?\s+(?:the\s+)?instructions?\b", s, re.IGNORECASE):
            continue
        if re.search(r"^(?:we\s+do\s+not\s+have\s+conflicting|only\s+\[source_\d+\]\s+provides)\b", s, re.IGNORECASE):
            continue
        if re.search(r"^the\s+(?:most\s+)?relevant\s+evidence\b", s, re.IGNORECASE):
            continue
        if re.search(r"^steps\s*:\s*$", s, re.IGNORECASE):
            continue
        if re.search(r"^\d+\.\s+we\s+(?:are\s+to|must)\b", s, re.IGNORECASE):
            continue
        if re.search(r"talks\s+about\b.*\bdoesn'?t\s+define\b", s, re.IGNORECASE):
            continue
        if re.search(r"^key\s+facts?\s+(?:from|are|include)\b", s, re.IGNORECASE):
            continue

        # Clean meta-evidence preamble from opening sentences (e.g. "First, looking at [source_1]: It clearly defines...")
        s = re.sub(
            r"^(?:(?:first|second|next|finally),?\s*)?(?:looking at|from|analyzing|examining)\s+\[?source_\d+\]?[^:]*:\s*(?:it\s+(?:clearly\s+)?(?:defines|states|explains|says|shows)\s+(?:that\s+)?)?",
            "",
            s,
            flags=re.IGNORECASE,
        ).strip()
        if re.search(r"(?i)\b(?:avoid|check|i'm|i'll|we'll)\b", s) and len(s.split()) <= 4:
            continue

        s = label_prefix_regex.sub("", s).strip()
        if s.startswith('"') and s.endswith('"') and len(s) > 2:
            s = s[1:-1].strip()

        # Drop dangling single-word/two-word connective fragments
        if s.lower() in ("however,", "however", "therefore,", "therefore", "moreover,", "furthermore,", "in addition,", "note:", "note that:"):
            continue
        if len(s.split()) <= 3 and s.endswith((",", ":", "-", "–")) and not any(ch.isdigit() for ch in s):
            continue

        # Strip leading generic boilerplate if present and not communicating uncertainty
        is_uncertain = any(
            kw in s.lower()
            for kw in (
                "not enough information",
                "insufficient information",
                "could not find",
                "no information",
                "not mentioned",
                "cannot find",
            )
        )
        if not is_uncertain:
            stripped_s = boilerplate_intro_regex.sub("", s).strip()
            if stripped_s:
                s = stripped_s[0].upper() + stripped_s[1:]

        if not s:
            continue
        if kept_lines and s.lower() == kept_lines[-1].lower():
            continue

        kept_lines.append(s)

    formatted_lines: list[str] = []
    for line in kept_lines:
        if line == "":
            if formatted_lines and formatted_lines[-1] != "":
                formatted_lines.append("")
            continue
        is_bullet = bool(re.match(r"^(?:[-*•▪●▸]|\d+\.)\s+", line.strip()))
        if is_bullet and formatted_lines:
            prev_is_bullet = bool(re.match(r"^(?:[-*•▪●▸]|\d+\.)\s+", formatted_lines[-1].strip()))
            if not prev_is_bullet and formatted_lines[-1].strip():
                formatted_lines.append("")
        formatted_lines.append(line)

    source_text = "\n".join(formatted_lines).strip() or cleaned
    norm_text = re.sub(
        r'(?m)^(#{1,6}\s+[A-Za-z0-9\s&/\'\-]{2,50}?)(?:\s*[:—–-]\s*|\.\s+|\s{2,})([A-Z][^\n]+)$',
        r'\1\n\n\2',
        source_text,
    )
    norm_text = re.sub(r'(?m)^(#{1,6}\s+[^\n]+)$', r'\n\n\1\n\n', norm_text)

    raw_blocks = [b.strip() for b in re.split(r'\n{2,}', norm_text) if b.strip()]
    cleaned_blocks: list[str] = []
    all_seen_items: list[str] = []

    for block in raw_blocks:
        if block.startswith("__CODE_BLOCK_"):
            cleaned_blocks.append(block)
        elif block.startswith("__TABLE_BLOCK_"):
            cleaned_blocks.append(block)
        elif re.match(r'^#{1,6}\s+', block):
            if re.match(r'^#{1,6}\s+(?:Document\s+Overview|Overview|Executive\s+Summary)\b', block, re.IGNORECASE):
                continue
            h_clean = re.sub(r'[:.]\s*$', '', block).strip()
            cleaned_blocks.append(h_clean)
        elif block.startswith('```') or block.startswith('~~~'):
            cleaned_blocks.append(block)
        elif block.startswith('|') and '\n|' in block:
            cleaned_blocks.append(block)
        elif re.match(r'^[-*_]{3,}\s*$', block):
            cleaned_blocks.append(block)
        elif any(re.match(r'^(?:[-*•▪●▸]|\d+\.)\s+', l.strip()) for l in block.splitlines()):
            filtered_list_lines: list[str] = []
            for l in block.splitlines():
                line_str = l.strip()
                if not line_str:
                    continue
                m_bullet = re.match(r'^((?:[-*•▪●▸]|\d+\.)\s+)(.*)$', line_str)
                if m_bullet:
                    bullet_prefix = m_bullet.group(1)
                    item_text = m_bullet.group(2).strip()
                else:
                    bullet_prefix = "- "
                    item_text = line_str

                if (item_text.startswith('"') and item_text.endswith('"')) or (item_text.startswith("'") and item_text.endswith("'")):
                    item_text = item_text[1:-1].strip()

                item_clean = item_text.lower()
                if any(item_clean.startswith(p) for p in reasoning_prefixes):
                    continue

                words = set(re.findall(r"\b[a-z]{4,}\b", item_clean))
                is_dup = False
                for prev in all_seen_items:
                    prev_words = set(re.findall(r"\b[a-z]{4,}\b", prev))
                    if len(words) >= 2 and len(prev_words) >= 2:
                        overlap = len(words & prev_words) / min(len(words), len(prev_words))
                        if overlap > 0.85:
                            is_dup = True
                            break
                if is_dup:
                    continue
                all_seen_items.append(item_clean)
                filtered_list_lines.append(f"{bullet_prefix}{item_text}")

            if filtered_list_lines:
                cleaned_blocks.append('\n'.join(filtered_list_lines))
        else:
            # Prose paragraph: preserve complete educational content and sentences without destructive deletion
            p_text = block.strip()
            if is_reasoning_or_non_answer(p_text, query or "") and not re.search(r'\[source_\d+\]', p_text, re.IGNORECASE):
                cand = clean_reasoning_text(p_text, query or "")
                if cand != p_text and not is_reasoning_or_non_answer(cand, query or ""):
                    cleaned_blocks.append(cand)
                continue

            # Deduplicate near-identical prose blocks (e.g. repeated concluding sentence)
            block_clean = re.sub(r"\[source_\d+\]", "", p_text).strip().lower()
            words = set(re.findall(r"\b[a-z]{4,}\b", block_clean))
            is_dup = False
            for prev in all_seen_items:
                prev_words = set(re.findall(r"\b[a-z]{4,}\b", prev))
                if len(words) >= 3 and len(prev_words) >= 3:
                    overlap = len(words & prev_words) / min(len(words), len(prev_words))
                    if overlap > 0.80:
                        is_dup = True
                        break
            if is_dup:
                continue
            all_seen_items.append(block_clean)
            cleaned_blocks.append(p_text)

    if cleaned_blocks:
        candidate_answer = "\n\n".join(cleaned_blocks).strip()
    else:
        candidate_answer = cleaned

    # 5. Normalize citation tags to canonical lower-case [source_X]
    canonical_answer = re.sub(
        r"(?:\[|\(|\b)(source_\d+)(?:\]|\)|\b)",
        lambda m: f"[{m.group(1).lower()}]",
        candidate_answer,
        flags=re.IGNORECASE,
    )
    # Normalize double periods around citation tags (e.g. '. [source_1].' -> ' [source_1].')
    canonical_answer = re.sub(
        r"\.\s*(\[source_\d+\])\.?",
        r" \1.",
        canonical_answer,
    )
    formatted = format_inline_list_items(canonical_answer, query=query)
    result = deduplicate_list_citations(formatted)
    for i, cb in enumerate(code_blocks):
        result = result.replace(f"__CODE_BLOCK_{i}__", cb)
    for i, tb in enumerate(tables):
        result = result.replace(f"__TABLE_BLOCK_{i}__", tb)
    return result


class LLMGenerationService:
    """
    Orchestration service for grounded LLM answer generation.
    """

    def __init__(
        self,
        provider: BaseLLMProvider | None = None,
        prompt_builder: GroundedPromptBuilder | None = None,
    ) -> None:
        self.provider = provider or OllamaLLMProvider()
        self.prompt_builder = prompt_builder or GroundedPromptBuilder()

    async def generate_grounded_answer(
        self, request: LLMGenerationRequest
    ) -> LLMGenerationResponse:
        # 1. Deterministic empty-context fast-path
        if request.context.total_items == 0 or not request.context.items:
            return LLMGenerationResponse(
                answer=SAFE_INSUFFICIENT_EVIDENCE_ANSWER,
                query=request.query,
                original_query=request.original_query,
                provider=self.provider.provider_name,
                model=request.model or self.provider.model_name,
                sources_available=[],
                sources_referenced=[],
                is_empty_context=True,
                prompt_tokens=0,
                output_tokens=0,
                latency_ms=0.0,
                metadata={
                    "generation_mode": "empty_context_refusal",
                    "llm_invoked": False,
                    "fast_path": True,
                    "provider_calls": 0,
                    "reason": "empty_context",
                },
            )

        # 2. Extract available source identifiers
        sources_available = [item.source_id for item in request.context.items]

        # Conversational greeting fast-path: avoid multi-minute LLM loop for simple greetings
        clean_q = request.query.strip().lower().rstrip("!?.")
        if clean_q in GREETING_WORDS:
            greeting_msg = (
                "Hello! I am your RAG Assistant. I can help you search and understand course materials, "
                "lecture notes, syllabus topics, and university regulations with verified citations. How can I assist you today?"
            )
            return LLMGenerationResponse(
                answer=greeting_msg,
                query=request.query,
                original_query=request.original_query,
                provider=self.provider.provider_name,
                model=request.model or self.provider.model_name,
                sources_available=sources_available,
                sources_referenced=[],
                is_empty_context=False,
                prompt_tokens=0,
                output_tokens=len(greeting_msg.split()),
                latency_ms=0.0,
                metadata={
                    "generation_mode": "greeting",
                    "llm_invoked": False,
                    "fast_path": True,
                    "provider_calls": 0,
                    "reason": "greeting",
                },
            )

        # 2b. Out-of-scope / low-relevance fast-path
        # When all retrieved context chunks have a negative CrossEncoder score below the calibrated
        # threshold (< -8.5), none of the available course documents contain relevant information for the query.
        max_score = max(
            (getattr(item, "reranker_score", 0.0) or 0.0)
            for item in request.context.items
        )
        if max_score < -8.5:
            return LLMGenerationResponse(
                answer=INSUFFICIENT_COURSE_EVIDENCE_ANSWER,
                query=request.query,
                original_query=request.original_query,
                provider=self.provider.provider_name,
                model=request.model or self.provider.model_name,
                sources_available=sources_available,
                sources_referenced=[],
                is_empty_context=True,
                prompt_tokens=0,
                output_tokens=len(INSUFFICIENT_COURSE_EVIDENCE_ANSWER.split()),
                latency_ms=0.0,
                metadata={
                    "generation_mode": "insufficient_evidence_refusal",
                    "llm_invoked": False,
                    "fast_path": True,
                    "provider_calls": 0,
                    "reason": "low_relevance",
                    "max_reranker_score": max_score,
                },
            )

        # 3. Build system instruction and untrusted evidence prompt
        system_instruction = self.prompt_builder.build_system_instruction(request.query)
        user_prompt = self.prompt_builder.build_user_prompt(
            query=request.query, context=request.context
        )

        # 4. Invoke the configured LLM provider (Primary generation + Bounded retry)
        start_time = time.perf_counter()
        provider_resp: LLMProviderResponse | None = None
        generation_path: str = "primary_llm"
        provider_calls: int = 0
        retry_occurred: bool = False
        cleaned_content: str = ""

        try:
            provider_calls += 1
            provider_resp = await self.provider.generate(
                system_instruction=system_instruction,
                user_prompt=user_prompt,
                temperature=request.temperature,
                max_output_tokens=request.max_output_tokens or 896,
                timeout_seconds=request.timeout_seconds,
            )
            cleaned_content = _sanitize_llm_answer(provider_resp.content, query=request.query)

            # 5a. Detect invalid, incomplete, or pure deliberation output and perform bounded single retry
            if is_invalid_or_incomplete_answer(cleaned_content, request.query):
                if request.allow_retry:
                    retry_instruction = (
                        system_instruction
                        + "\n\nRETRY INSTRUCTION: The previous response was incomplete or contained meta-commentary. "
                        "Synthesize and output ONLY the direct, student-friendly factual answer explaining the concepts from the evidence. "
                        "Do not include reasoning preambles, analysis of sources, or deflections such as 'the definition is provided in'. "
                        "If the evidence is insufficient, state that plainly."
                    )
                    try:
                        provider_calls += 1
                        retry_occurred = True
                        retry_resp = await self.provider.generate(
                            system_instruction=retry_instruction,
                            user_prompt=user_prompt,
                            temperature=0.0,
                            max_output_tokens=min(request.max_output_tokens or 1024, 1024),
                            timeout_seconds=request.timeout_seconds or 180.0,
                        )
                        cleaned_retry = _sanitize_llm_answer(retry_resp.content, query=request.query)
                        if not is_invalid_or_incomplete_answer(cleaned_retry, request.query):
                            cleaned_content = cleaned_retry
                            provider_resp = retry_resp
                            generation_path = "llm_retry"
                        else:
                            cleaned_content = (
                                "I could not synthesize a complete and verified answer from the available course evidence. "
                                "Please try rephrasing your question or checking your course materials."
                            )
                            generation_path = "generation_failed"
                    except Exception as retry_err:
                        logger.warning("LLM generation retry failed: %s", retry_err)
                        cleaned_content = (
                            "I could not synthesize a complete and verified answer from the available course evidence. "
                            "Please try rephrasing your question or checking your course materials."
                        )
                        generation_path = "generation_failed"
                else:
                    cleaned_content = (
                        "I could not synthesize a complete and verified answer from the available course evidence. "
                        "Please try rephrasing your question or checking your course materials."
                    )
                    generation_path = "generation_failed"
        except (LLMTimeoutError, LLMConnectionError) as exc:
            latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            logger.warning("LLM provider communication error (%s) after %s ms", exc, latency_ms)
            raise exc
        except (LLMResponseError, LLMProviderError) as exc:
            logger.warning("LLM generation response error: %s", exc)
            cleaned_content = (
                "I could not synthesize a complete and verified answer from the available course evidence. "
                "Please try rephrasing your question or checking your course materials."
            )
            generation_path = "generation_failed"

        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        llm_invoked = provider_calls > 0

        if provider_resp is None:
            provider_resp = LLMProviderResponse(
                content=cleaned_content,
                model=getattr(self.provider, "model_name", "qwen3:4b"),
                prompt_tokens=0,
                output_tokens=len(cleaned_content.split()),
                safe_metadata={
                    "generation_mode": generation_path,
                    "generation_path": generation_path,
                    "llm_invoked": llm_invoked,
                    "provider_calls": provider_calls,
                    "retry_occurred": retry_occurred,
                },
            )
        else:
            if not provider_resp.safe_metadata:
                provider_resp.safe_metadata = {}
            provider_resp.safe_metadata["generation_mode"] = generation_path
            provider_resp.safe_metadata["generation_path"] = generation_path
            provider_resp.safe_metadata["llm_invoked"] = llm_invoked
            provider_resp.safe_metadata["provider_calls"] = provider_calls
            provider_resp.safe_metadata["retry_occurred"] = retry_occurred

        # 5b. Attribute supporting context items to uncited factual claims
        has_list = any(re.match(r"^\s*[-*•▪●▸\d+.]\s+[A-Za-z0-9]", line) for line in cleaned_content.splitlines())
        if request.context.items and (not has_list or not _SOURCE_REF_REGEX.search(cleaned_content)):
            from backend.app.services.grounding.claim_verifier import ClaimVerifier
            from backend.app.services.grounding.sentence_splitter import SentenceSplitter

            verifier = ClaimVerifier()
            splitter = SentenceSplitter()
            claims = splitter.split(cleaned_content)

            for claim in claims:
                seg = claim.raw_text.strip()
                if not seg:
                    continue
                # If claim already has a citation tag or is conversational framing, do not modify
                if _SOURCE_REF_REGEX.search(seg) or claim.is_conversational:
                    continue

                c_words = verifier.extract_content_words(seg)
                if len(c_words) < 4:
                    continue
                best_items = []
                for item in request.context.items:
                    item_words = verifier.extract_content_words(item.text)
                    if c_words:
                        overlap = len(c_words & item_words) / len(c_words)
                        if overlap >= 0.35:
                            is_visual = (
                                1
                                if (
                                    item.chunk_metadata
                                    and item.chunk_metadata.get("source_modality") == "visual"
                                )
                                else 0
                            )
                            best_items.append((overlap, is_visual, item))

                if best_items:
                    best_items.sort(key=lambda x: (x[0], x[1]), reverse=True)
                    top_item = best_items[0][2]
                    tag = f"[{top_item.source_id.lower()}]"

                    punc = ""
                    core_seg = seg
                    if core_seg.endswith((".", "!", "?")):
                        punc = core_seg[-1]
                        core_seg = core_seg[:-1].rstrip()
                    attributed_seg = f"{core_seg} {tag}{punc}"

                    if seg in cleaned_content:
                        cleaned_content = cleaned_content.replace(seg, attributed_seg, 1)

        # Deduplicate any adjacent identical citation markers
        cleaned_content = re.sub(r"(\[source_\d+\])(?:\s*,?\s*\1)+", r"\1", cleaned_content, flags=re.IGNORECASE)

        # 6. Extract referenced candidate source identifiers for Step 14 citation validation
        raw_matches = _SOURCE_REF_REGEX.findall(cleaned_content)
        seen_refs: set[str] = set()
        sources_referenced: list[str] = []
        for ref in raw_matches:
            ref_lower = ref.lower()
            if ref_lower not in seen_refs:
                seen_refs.add(ref_lower)
                sources_referenced.append(ref_lower)

        # 7. Safe metadata assembly (excluding internals or raw traces)
        safe_metadata = dict(provider_resp.safe_metadata)
        safe_metadata["generation_mode"] = safe_metadata.get("generation_mode", generation_path)
        safe_metadata["generation_path"] = safe_metadata.get("generation_path", generation_path)
        safe_metadata["llm_invoked"] = safe_metadata.get("llm_invoked", generation_path in ("primary_llm", "llm_retry"))
        safe_metadata["sources_available_count"] = len(sources_available)
        safe_metadata["sources_referenced_count"] = len(sources_referenced)

        return LLMGenerationResponse(
            answer=cleaned_content,
            query=request.query,
            original_query=request.original_query,
            provider=self.provider.provider_name,
            model=provider_resp.model,
            sources_available=sources_available,
            sources_referenced=sources_referenced,
            is_empty_context=False,
            prompt_tokens=provider_resp.prompt_tokens,
            output_tokens=provider_resp.output_tokens,
            latency_ms=latency_ms,
            metadata=safe_metadata,
        )


# Thread-safe singleton
_service_instance: LLMGenerationService | None = None
_service_lock = threading.Lock()


def get_llm_generation_service() -> LLMGenerationService:
    """
    Return the singleton LLMGenerationService instance.
    """
    global _service_instance
    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = LLMGenerationService()
    return _service_instance
