"""
Real Inference Integration Tests for Local Hugging Face CrossEncoder Provider.

Verifies that the CrossEncoder model (cross-encoder/ms-marco-MiniLM-L-6-v2):
- Actually loads locally without paid APIs or external inference services.
- Reuses the loaded model instance across invocations (lazy, thread-safe lifecycle).
- Accepts query/text candidate pairs.
- Returns a score count exactly equal to the candidate count.
- Produces finite numeric float scores for every candidate (no NaN, no Inf).
- Preserves 1-to-1 input order mapping between candidate texts and scores.
- Passes a relevant vs. irrelevant smoke test comparison without relying on brittle absolute thresholds.
"""

import math

import pytest

from backend.app.core.config import settings
from backend.app.services.reranking.cross_encoder_provider import (
    HuggingFaceCrossEncoderProvider,
)


@pytest.mark.asyncio
class TestRealCrossEncoderProvider:
    """Integration test suite executing real local inference via CrossEncoder."""

    async def test_provider_inference_contract(self) -> None:
        """
        Verify real model loading, query/text inference, score count match,
        numeric finiteness, and input order mapping.
        """
        provider = HuggingFaceCrossEncoderProvider(
            model_name=settings.RERANKER_MODEL,
            batch_size=settings.RERANK_BATCH_SIZE,
            device="cpu",
        )

        assert provider.model_name == settings.RERANKER_MODEL

        # 1. Verify model lazy initialization and reuse (lifecycle check)
        model_first = provider._get_or_load_model()
        model_second = provider._get_or_load_model()
        assert model_first is model_second, "Model instance must be reused, not recreated"

        # 2. Verify empty candidates handling
        empty_scores = await provider.compute_scores("test query", [])
        assert empty_scores == []

        # 3. Test real candidates inference
        query = "What is process scheduling in an operating system?"
        candidates = [
            "Process scheduling is an essential operating system function that decides which process runs on the CPU.",
            "Baking chocolate chip cookies requires flour, butter, sugar, and chocolate chips.",
            "The Process Control Block (PCB) contains scheduling state and priority information for the CPU scheduler.",
            "The Eiffel Tower is a wrought-iron lattice tower located in Paris, France.",
        ]

        scores = await provider.compute_scores(query=query, texts=candidates)

        # 4. Verify score count matches candidate count
        assert len(scores) == len(candidates), (
            f"Expected {len(candidates)} scores, got {len(scores)}"
        )

        # 5. Verify every score is a finite float
        for idx, s in enumerate(scores):
            assert isinstance(s, float), f"Score at index {idx} must be float, got {type(s)}"
            assert math.isfinite(s), f"Score at index {idx} must be finite, got {s}"

        # 6. Verify input order mapping: scores must map to candidates in the exact input order.
        # Calling compute_scores with inverted candidate order should yield inverted scores.
        inverted_candidates = [candidates[1], candidates[0]]
        inverted_scores = await provider.compute_scores(query=query, texts=inverted_candidates)

        # candidates[1] was cookie text; candidates[0] was scheduling text
        assert math.isclose(inverted_scores[0], scores[1], rel_tol=1e-4), (
            "Scores must map to candidate texts in input order"
        )
        assert math.isclose(inverted_scores[1], scores[0], rel_tol=1e-4), (
            "Scores must map to candidate texts in input order"
        )

        # 7. Smoke test: domain-relevant texts should score higher than completely irrelevant texts
        # candidates[0] (scheduling) and candidates[2] (PCB scheduler) vs candidates[1] (cookies) and candidates[3] (Paris)
        assert scores[0] > scores[1], (
            f"Expected scheduling text ({scores[0]}) to score higher than cookie text ({scores[1]})"
        )
        assert scores[2] > scores[3], (
            f"Expected PCB text ({scores[2]}) to score higher than Paris text ({scores[3]})"
        )
