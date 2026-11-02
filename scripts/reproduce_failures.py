"""
Reproduction script for Phase 23:
- Question 1: What is Flutter? (Screenshot B)
- Question 2: Can you summarize the Flutter PDF? (Screenshot A)
Captures full stage trace across Query Understanding, Hybrid Retrieval, Reranking, Relevance Gate, Context Assembly, LLM Generation, Grounding, and Citations.
"""

import asyncio
import sys
import uuid

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from backend.app.db.session import SessionLocal
from backend.app.services.rag_orchestrator import get_rag_orchestrator

FLUTTER_DOC_ID = uuid.UUID("aa7598cf-9ea8-497c-bf6c-2f0e11a96000")
FLUTTER_KB_ID = uuid.UUID("a8ed9e38-0e78-42dc-8953-b3c5d745d618")


async def trace_query(query: str):
    orch = get_rag_orchestrator()
    print("=" * 80)
    print(f"REPRODUCING: {query}")
    print("=" * 80)

    with SessionLocal() as db:
        # 1. Query Processing & Understanding
        qp_res = orch.query_processor.process(query)
        sq = orch.query_understanding.analyze(query)
        print(f"[Stage 1] Query Understanding:")
        print(f"  Processed Query: '{qp_res.processed_query}'")
        print(f"  Intent: {sq.intent}")
        print(f"  Subject: '{sq.subject}'")
        print(f"  Target Entity Type: '{sq.target_entity_type}'")
        print(f"  Is Conversational: {sq.is_conversational}")
        print(f"  Is Out of Scope: {sq.is_out_of_scope}")
        print(f"  Is Ambiguous: {sq.is_ambiguous}")

        # 2. Hybrid Retrieval
        hr = await orch.hybrid_service.retrieve(
            db=db,
            kb_id=FLUTTER_KB_ID,
            query=qp_res.processed_query,
            top_k=20,
            document_id=FLUTTER_DOC_ID,
        )
        print(f"\n[Stage 2] Hybrid Retrieval: {len(hr.results)} candidates")
        for i, item in enumerate(hr.results[:5]):
            print(f"  Rank {i+1}: p{item.page_number} (rrf={item.rrf_score:.4f}) - {item.text[:70]}...")

        # 3. Reranking
        rr = await orch.reranking_service.rerank_candidates(
            query=qp_res.processed_query,
            candidates=hr.results,
            top_k=5,
        )
        print(f"\n[Stage 3] Reranking: {len(rr)} candidates")
        for item in rr:
            print(f"  P{item.page_number} (reranker_score={item.reranker_score:.4f}): {item.text[:70]}...")

        # 4. Relevance Gate
        accepted, audit = orch.relevance_gate.evaluate_candidates(sq, rr)
        print(f"\n[Stage 4] Relevance Gate: {len(accepted)} accepted / {len(rr)} evaluated")
        for a in audit:
            print(f"  p{a.get('page_number')} -> {a.get('decision')} ({a.get('reason')})")

        # 5. Full Orchestrator Execution
        print(f"\n[Stage 5] Executing Full Orchestrator Pipeline...")
        resp = await orch.execute_query(
            db=db,
            kb_id=FLUTTER_KB_ID,
            raw_query=query,
            document_id=FLUTTER_DOC_ID,
        )
        print(f"\n--- FINAL ANSWER ---")
        print(resp.answer)
        print(f"--------------------")
        print(f"CITATIONS ({len(resp.citations)}): {[f'p{c.page_number}:{c.document_name}' for c in resp.citations]}")
        print(f"GROUNDING: {resp.grounding.status} (is_grounded={resp.grounding.is_grounded})")
        print(f"GENERATION MODE: {resp.metadata.get('generation_mode')}")
        print(f"LLM INVOKED: {resp.metadata.get('llm_invoked')}")
        print(f"MODEL: {resp.model}")


async def main():
    for q in ["What is Flutter?", "Can you summarize the Flutter PDF?"]:
        await trace_query(q)
        print("\n\n")


if __name__ == "__main__":
    asyncio.run(main())

