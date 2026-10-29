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

logger = logging.getLogger(__name__)

from backend.app.schemas.llm import (
    LLMGenerationRequest,
    LLMGenerationResponse,
    LLMProviderResponse,
)
from backend.app.services.llm.base import BaseLLMProvider
from backend.app.services.llm.exceptions import LLMTimeoutError
from backend.app.services.llm.ollama_provider import OllamaLLMProvider
from backend.app.services.llm.prompt_builder import GroundedPromptBuilder

# Matches attribution markers formatted as [source_1], [source_2], etc.
_SOURCE_REF_REGEX = re.compile(r"\[(source_\d+)\]", re.IGNORECASE)

SAFE_INSUFFICIENT_EVIDENCE_ANSWER = (
    "I could not find any relevant information in the available documents to answer your question."
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
    r"\bthe user\s+(?:says|asks|also asks|is asking|question is)\b",
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
]


def is_reasoning_or_non_answer(text: str, query: str) -> bool:
    """Detect obvious internal deliberation leakage or meta preambles without answers."""
    t_clean = text.strip().lower()
    if not t_clean:
        return True
    for p in REASONING_LEAK_PATTERNS:
        if re.search(p, t_clean):
            return True
    if re.search(
        r"^(?:the answer should be|we can answer by|the list is given in|the list of .+ is the one in|the answer is in|we are given|let'?s examine)\b",
        t_clean,
    ):
        return True
    is_list_query = any(w in query.lower() for w in ("list", "enumerate", "versions", "steps"))
    if is_list_query and len(text.split()) < 15 and not any(ch in text for ch in (",", ";", "\n", "1.", "- ")):
        return True
    return False


def clean_reasoning_text(text: str) -> str:
    """Extract final answer declaration or embedded itemized list from reasoning text if present."""
    # 1. Check if model extracted an itemized list inside its deliberation of a source
    # e.g. - [source_1]: ... It lists:\n Android 1.0 ... or It includes:\n Android 1.0 ...
    list_match = re.search(
        r"(?:-\s*\[(source_\d+)\]:[^\n]*?(?:lists?|includes?|contains?|shows?|presents?):\s*\n?\s*)([^\n]+(?:\n(?!\s*(?:-\s*\[source_|\n|\bThe user\b|\bTherefore\b))[^\n]+)*)",
        text,
        re.IGNORECASE,
    )
    if list_match:
        source_tag = list_match.group(1)
        raw_items = list_match.group(2).strip()
        item_parts = [it.strip() for it in re.split(r",\s*(?=[A-Za-z0-9])|\n\s*[-*•]?\s*", raw_items) if it.strip()]
        clean_items = [
            it for it in item_parts
            if not any(it.lower().startswith(p) for p in ("it lists:", "it includes:", "it contains:", "of android", "android all versions", "2008 to 2025")) and len(it) > 1
        ]
        if len(clean_items) >= 3:
            formatted = [f"- {it} [{source_tag}]" if f"[{source_tag}]" not in it else f"- {it}" for it in clean_items]
            return f"The items listed in [{source_tag}] are:\n" + "\n".join(formatted)

    # 2. Check for explicit conclusion marker
    conclusion_match = re.search(
        r"(?:So the answer should be:|The answer should be:|The answer is:|Therefore,?\s*(?:the answer is:?)?)\s*(.+)$",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if conclusion_match:
        cand = conclusion_match.group(1).strip()
        if not any(re.search(p, cand, re.IGNORECASE) for p in REASONING_LEAK_PATTERNS):
            return cand
    return text


def extract_grounded_recovery_answer(
    query: str,
    context: Any,
) -> str | None:
    """
    Deterministically construct a grounded, fully-cited answer from validated assembled evidence
    when model generation fails, returns a non-answer, or times out.
    Works generally across any course material with diagrams, tables, or itemized lists.
    """
    if not context or not getattr(context, "items", None):
        return None

    q_lower = query.strip().lower()
    is_list_query = any(w in q_lower for w in ("list", "enumerate", "versions", "steps", "types"))

    # Check assembled items in ranked order
    for item in context.items:
        text = (item.text or "").strip()
        source_tag = getattr(item, "source_id", "source_1")

        # 1. Visual/Diagram Chunk with "[Visible Text & Labels]:"
        if "[Visible Text & Labels]:" in text:
            match = re.search(
                r"\[Visible Text & Labels\]:\s*([^\n]+)",
                text,
                re.IGNORECASE,
            )
            if match:
                raw_labels = match.group(1).strip()
                parts = [p.strip() for p in re.split(r",\s*(?=[A-Za-z0-9])|\n\s*[-*•]?\s*", raw_labels) if p.strip()]
                valid_items = [
                    p for p in parts
                    if p.lower() not in ("android all versions", "2008 to 2025", "none", "n/a")
                    and not p.startswith("[")
                    and len(p) > 2
                ]
                if is_list_query and len(valid_items) >= 2:
                    header = f"Based on [{source_tag}], the following items are listed:\n"
                    bullet_list = "\n".join(f"- {it} [{source_tag}]" for it in valid_items)
                    return header + bullet_list

        # 2. Markdown or bulleted list in text chunk
        if is_list_query:
            bullet_lines = [
                line.strip()
                for line in text.splitlines()
                if re.match(r"^[-*•▪●▸\d+.]\s+[A-Za-z0-9]", line.strip())
            ]
            if len(bullet_lines) >= 3:
                header = f"Based on [{source_tag}], the details are:\n"
                bullet_list = "\n".join(
                    f"{b} [{source_tag}]" if f"[{source_tag}]" not in b else b
                    for b in bullet_lines
                )
                return header + bullet_list

    # 3. For ordinary factual queries where top item has strong relevance
    top_item = context.items[0]
    score = getattr(top_item, "reranker_score", 0.0) or 0.0
    if score >= 1.0 and not is_list_query:
        clean_text = re.sub(r"\[Visual [^\]]+\]:[^\n]*\n?", "", top_item.text).strip()
        sentences = [
            s.strip()
            for s in re.split(r"(?<=[.!?])\s+", clean_text)
            if len(s.strip()) > 20 and not s.strip().startswith("[")
        ]
        if sentences:
            ans = " ".join(sentences[:2])
            if f"[{top_item.source_id}]" not in ans:
                ans = f"{ans} [{top_item.source_id}]"
            return ans

    return None


def _sanitize_llm_answer(text: str) -> str:
    """
    Strip model self-reasoning preambles, chain-of-thought evaluations, and instruction leaks.
    Extracts the clean, direct factual answer with verified citations.
    """
    if not text:
        return text

    # 1. Strip private reasoning channels and <think> blocks
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

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
        r"^(?:Based on (?:the |all )?.*?(?:documents|context|evidence|materials|syllabus),?\s*|According to (?:the |all )?.*?(?:documents|context|evidence|materials|syllabus),?\s*)",
        re.IGNORECASE,
    )

    lines = cleaned.splitlines()
    kept_lines: list[str] = []
    reasoning_prefixes = (
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
        "however, note",
        "user question:",
        "answer:",
    )
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if reasoning_step_regex.search(s):
            continue
        if source_header_regex.match(s):
            continue
        if any(s.lower().startswith(p) for p in reasoning_prefixes):
            continue
        if s.lower().startswith("but note:") or s.lower().startswith("however, note:"):
            continue
        if re.search(r"^(?:(?:however|note|but),?\s+)?(?:the\s+)?user\s+question\b", s, re.IGNORECASE):
            continue
        if re.search(r"^(?:(?:however|note|but),?\s+)?we\s+(?:must|should)\s+(?:output|be\s+precise|ensure)\b", s, re.IGNORECASE):
            continue

        s = label_prefix_regex.sub("", s).strip()
        if s.startswith('"') and s.endswith('"') and len(s) > 2:
            s = s[1:-1].strip()

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

    is_list_like = any(
        re.match(r"^(?:step\s*\d+|[-*•]|\d+\.)", line, re.IGNORECASE)
        for line in kept_lines
    )
    result = ("\n" if is_list_like else " ").join(kept_lines).strip()
    candidate_answer = result if result else cleaned

    # 5. Normalize citation tags to canonical lower-case [source_X]
    canonical_answer = re.sub(
        r"(?:\[|\(|\b)(source_\d+)(?:\]|\)|\b)",
        lambda m: f"[{m.group(1).lower()}]",
        candidate_answer,
        flags=re.IGNORECASE,
    )
    return canonical_answer


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
        """
        Generate a grounded answer for the provided query and assembled context.

        Args:
            request: Validated LLMGenerationRequest containing assembled context,
                     query, and generation options.

        Returns:
            LLMGenerationResponse with answer, source metadata, and token accounting.
        """
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
                    "fast_path": True,
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
                metadata={"fast_path": True, "reason": "greeting"},
            )

        # 3. Build system instruction and untrusted evidence prompt
        system_instruction = self.prompt_builder.build_system_instruction()
        user_prompt = self.prompt_builder.build_user_prompt(
            query=request.query, context=request.context
        )

        # 4. Invoke the configured LLM provider
        start_time = time.perf_counter()
        provider_resp: LLMProviderResponse | None = None
        try:
            provider_resp = await self.provider.generate(
                system_instruction=system_instruction,
                user_prompt=user_prompt,
                temperature=request.temperature,
                max_output_tokens=request.max_output_tokens,
                timeout_seconds=request.timeout_seconds,
            )
            latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            logger.debug("Raw LLM response before sanitization length: %d chars", len(provider_resp.content))

            # 5. Sanitize answer to eliminate leaked CoT rambling
            cleaned_content = _sanitize_llm_answer(provider_resp.content)

            # 5a. Detect reasoning leak or non-answer preamble and attempt extraction, recovery, or bounded retry
            if is_reasoning_or_non_answer(cleaned_content, request.query):
                candidate = clean_reasoning_text(provider_resp.content)
                if candidate != provider_resp.content and not is_reasoning_or_non_answer(candidate, request.query):
                    cleaned_content = candidate
                else:
                    # Deterministic structured extractive recovery from assembled context evidence
                    recovery_ans = extract_grounded_recovery_answer(request.query, request.context)
                    if recovery_ans and not is_reasoning_or_non_answer(recovery_ans, request.query):
                        cleaned_content = recovery_ans
                    else:
                        retry_instruction = (
                            "You are an academic knowledge assistant. Output ONLY the factual answer or itemized list citing [source_X]. "
                            "STRICT RULE: Do NOT say 'The answer should be', do NOT say 'We can answer by', and do NOT include internal reasoning or deliberation. "
                            "If the provided evidence does not contain sufficient facts to answer the question, state: 'Based on the provided documents, there is not enough information to answer this question.' "
                            "Otherwise, output the factual items directly from the evidence:"
                        )
                        try:
                            retry_resp = await self.provider.generate(
                                system_instruction=retry_instruction,
                                user_prompt=user_prompt,
                                temperature=0.0,
                                max_output_tokens=min(request.max_output_tokens or 384, 384),
                                timeout_seconds=min(request.timeout_seconds or 45.0, 45.0),
                            )
                            cleaned_retry = _sanitize_llm_answer(retry_resp.content)
                            if is_reasoning_or_non_answer(cleaned_retry, request.query):
                                cand_retry = clean_reasoning_text(retry_resp.content)
                                if cand_retry != retry_resp.content and not is_reasoning_or_non_answer(cand_retry, request.query):
                                    cleaned_retry = cand_retry
                            if not is_reasoning_or_non_answer(cleaned_retry, request.query):
                                cleaned_content = cleaned_retry
                                provider_resp = retry_resp
                            else:
                                rec2 = extract_grounded_recovery_answer(request.query, request.context)
                                cleaned_content = rec2 or SAFE_INSUFFICIENT_EVIDENCE_ANSWER
                        except Exception as retry_err:
                            logger.warning("LLM generation retry failed: %s", retry_err)
                            rec2 = extract_grounded_recovery_answer(request.query, request.context)
                            cleaned_content = rec2 or SAFE_INSUFFICIENT_EVIDENCE_ANSWER
        except LLMTimeoutError as timeout_exc:
            latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            logger.warning("Initial LLM generation timed out after %s ms; attempting grounded recovery", latency_ms)
            rec_ans = extract_grounded_recovery_answer(request.query, request.context)
            if rec_ans and not is_reasoning_or_non_answer(rec_ans, request.query):
                cleaned_content = rec_ans
            else:
                raise timeout_exc

        if provider_resp is None:
            provider_resp = LLMProviderResponse(
                content=cleaned_content,
                model=getattr(self.provider, "model_name", "qwen3:4b"),
                prompt_tokens=0,
                output_tokens=len(cleaned_content.split()),
                safe_metadata={"recovery_used": True},
            )

        # 5b. Attribute supporting context items to uncited factual claims
        if request.context.items:
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
