"""
Deterministic Context Assembly Service.

Selects, deduplicates, and packages Step 10 CrossEncoder reranked candidates
into a bounded, token-budgeted, provenance-preserving context payload for
downstream prompt construction (Step 13).

Design & Architectural Invariants:
1. Evidence Integrity:
   - Chunk text is strictly immutable: no truncation, summarization, rewriting,
     cleaning, normalization, merging, or punctuation alteration.
   - If a candidate does not fit within the remaining token budget, it is skipped.
   - Subsequent smaller candidates continue to be evaluated against the remaining budget.
   - If no candidate fits within the token budget, an empty context item list is returned.
2. Deduplication:
   - Evaluates candidate chunk IDs and exact content hashes (SHA-256 of text.strip()).
   - Drops exact duplicates while preserving the earliest (highest-ranked) instance.
   - Does NOT merge partially overlapping chunks.
3. Ranking Preservation:
   - Evaluates candidates strictly in their incoming Step 10 CrossEncoder rank order.
   - Generates sequential, deterministic source attribution identifiers ('source_1', 'source_2', ...).
4. Query Transparency:
   - Preserves original user query and Step 11 processed query independently.
   - Performs no query mutation, expansion, or normalization.
5. Isolation & Integrity:
   - Verifies knowledge base ID consistency if a target knowledge_base_id is supplied.
   - Relies on existing API/service boundaries for authentication and authorization.
"""

import hashlib
import threading
import uuid
from typing import Any

from backend.app.schemas.context_assembly import (
    ContextAssemblyRequest,
    ContextAssemblyResult,
    ContextItem,
)
from backend.app.schemas.reranking import RerankResultItem
from backend.app.services.chunking import TokenEstimator


class ContextAssembler:
    """
    Deterministic context assembly engine.

    Packages reranked retrieval candidates into token-budgeted, provenance-rich
    context items ready for LLM prompt construction.
    """

    def __init__(self, token_estimator: TokenEstimator | None = None) -> None:
        """
        Initialize the context assembler with a token estimator.

        Args:
            token_estimator: Optional TokenEstimator instance. If None,
                instantiates the standard deterministic TokenEstimator.
        """
        self.token_estimator = token_estimator or TokenEstimator()

    def assemble(self, request: ContextAssemblyRequest) -> ContextAssemblyResult:
        """
        Assemble candidates into a bounded, deduplicated context result.

        Args:
            request: Validated ContextAssemblyRequest containing candidates,
                token budget, max items, and query metadata.

        Returns:
            ContextAssemblyResult containing selected ContextItems, token accounting,
            and deduplication/budget diagnostics.

        Raises:
            ValueError: If a candidate's knowledge_base_id does not match the
                request's specified knowledge_base_id.
        """
        # Knowledge-base integrity validation
        if request.knowledge_base_id is not None:
            for candidate in request.candidates:
                if candidate.knowledge_base_id != request.knowledge_base_id:
                    raise ValueError(
                        f"Candidate chunk '{candidate.chunk_id}' belongs to knowledge base "
                        f"'{candidate.knowledge_base_id}', which does not match expected "
                        f"target knowledge base '{request.knowledge_base_id}'."
                    )

        selected_items: list[ContextItem] = []
        seen_chunk_ids: set[uuid.UUID] = set()
        seen_content_hashes: set[str] = set()
        used_tokens: int = 0
        items_skipped_budget: int = 0
        items_deduplicated: int = 0

        for candidate in request.candidates:
            # Enforce maximum items limit
            if len(selected_items) >= request.max_items:
                break

            # Deduplication 1: chunk_id
            if candidate.chunk_id in seen_chunk_ids:
                items_deduplicated += 1
                continue

            # Deduplication 2: exact text content hash (SHA-256)
            content_hash = hashlib.sha256(candidate.text.strip().encode("utf-8")).hexdigest()
            if content_hash in seen_content_hashes:
                items_deduplicated += 1
                continue

            # Estimate candidate token count using TokenEstimator
            candidate_tokens = self.token_estimator.estimate_tokens(candidate.text)
            remaining_budget = request.token_budget - used_tokens

            # Budget check: If candidate exceeds remaining budget, skip it and continue
            # checking subsequent candidates to allow smaller chunks to fit.
            if candidate_tokens > remaining_budget:
                items_skipped_budget += 1
                continue

            # Candidate accepted: assign 1-based sequential source attribution ID
            source_id = f"source_{len(selected_items) + 1}"

            context_item = ContextItem(
                source_id=source_id,
                chunk_id=candidate.chunk_id,
                document_id=candidate.document_id,
                knowledge_base_id=candidate.knowledge_base_id,
                document_title=candidate.document_title,
                chunk_index=candidate.chunk_index,
                text=candidate.text,  # Exact unmodified chunk text
                page_number=candidate.page_number,
                section_title=candidate.section_title,
                chunk_metadata=candidate.chunk_metadata,
                reranker_rank=candidate.reranker_rank,
                reranker_score=candidate.reranker_score,
                rrf_score=candidate.rrf_score,
                estimated_tokens=candidate_tokens,
            )

            selected_items.append(context_item)
            seen_chunk_ids.add(candidate.chunk_id)
            seen_content_hashes.add(content_hash)
            used_tokens += candidate_tokens

        return ContextAssemblyResult(
            query=request.query,
            original_query=request.original_query,
            items=selected_items,
            total_items=len(selected_items),
            total_estimated_tokens=used_tokens,
            token_budget=request.token_budget,
            candidates_received=len(request.candidates),
            items_skipped_budget=items_skipped_budget,
            items_deduplicated=items_deduplicated,
            metadata={
                "max_items": request.max_items,
                "remaining_tokens": request.token_budget - used_tokens,
                "estimator": "TokenEstimator",
            },
        )

    def assemble_from_candidates(
        self,
        query: str,
        candidates: list[RerankResultItem],
        original_query: str | None = None,
        token_budget: int | None = None,
        max_items: int | None = None,
        knowledge_base_id: uuid.UUID | None = None,
    ) -> ContextAssemblyResult:
        """
        Convenience wrapper to assemble context directly from candidate parameters.

        Args:
            query: Processed or active search query.
            candidates: Ranked Step 10 candidate list.
            original_query: Optional raw user query.
            token_budget: Optional explicit token budget override.
            max_items: Optional explicit max items override.
            knowledge_base_id: Optional target knowledge base identifier.

        Returns:
            ContextAssemblyResult.
        """
        kwargs: dict[str, Any] = {
            "query": query,
            "original_query": original_query,
            "candidates": candidates,
            "knowledge_base_id": knowledge_base_id,
        }
        if token_budget is not None:
            kwargs["token_budget"] = token_budget
        if max_items is not None:
            kwargs["max_items"] = max_items

        request = ContextAssemblyRequest(**kwargs)
        return self.assemble(request)


# Thread-safe singleton
_assembler_instance: ContextAssembler | None = None
_assembler_lock = threading.Lock()


def get_context_assembler() -> ContextAssembler:
    """
    Return the singleton ContextAssembler instance.
    """
    global _assembler_instance
    if _assembler_instance is None:
        with _assembler_lock:
            if _assembler_instance is None:
                _assembler_instance = ContextAssembler()
    return _assembler_instance
