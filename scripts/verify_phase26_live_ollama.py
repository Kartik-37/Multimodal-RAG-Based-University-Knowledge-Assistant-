"""
Live Ollama Verification Script for Phase 26 Golden Scenarios.

Runs real queries through the production RAG orchestrator against the indexed
Flutter course document using local Ollama (qwen3:4b).
"""

import asyncio
import json
import sys
import uuid

from backend.app.db.session import SessionLocal
from backend.app.services.rag_orchestrator import get_rag_orchestrator


async def main():
    db = SessionLocal()
    orchestrator = get_rag_orchestrator()
    kb_id = uuid.UUID("a8ed9e38-0e78-42dc-8953-b3c5d745d618")

    queries = [
        "What is Flutter?",
        "What is a Flutter widget?",
        "List the Flutter widget concepts mentioned in my notes",
    ]

    results = []

    for q in queries:
        print(f"\n=======================================================", flush=True)
        print(f"QUERY: {q}", flush=True)
        print(f"=======================================================", flush=True)
        try:
            resp = await orchestrator.execute_query(
                db=db,
                kb_id=kb_id,
                raw_query=q,
            )
            data = {
                "query": q,
                "answer": resp.answer,
                "citations": [
                    {
                        "source_id": c.source_id,
                        "document_name": c.document_name,
                        "page_number": c.page_number,
                    }
                    for c in resp.citations
                ],
                "grounding_status": resp.grounding.status if resp.grounding else "UNKNOWN",
                "is_grounded": resp.grounding.is_grounded if resp.grounding else False,
                "latency_breakdown": resp.latency.model_dump() if resp.latency else {},
            }
            if resp.metadata:
                data["llm_invoked"] = resp.metadata.get("llm_invoked")
                data["generation_mode"] = resp.metadata.get("generation_mode")
            data["model"] = resp.model

            print(f"ANSWER:\n{resp.answer}\n", flush=True)
            print(f"CITATIONS: {[c.source_id for c in resp.citations]}", flush=True)
            print(f"PAGES: {[c.page_number for c in resp.citations]}", flush=True)
            if resp.grounding:
                print(f"GROUNDING: {resp.grounding.status} (is_grounded={resp.grounding.is_grounded})", flush=True)
            print(f"LLM INVOKED: {data.get('llm_invoked')} | MODE: {data.get('generation_mode')} | MODEL: {resp.model}", flush=True)
            if resp.latency:
                print(f"LATENCY: LLM {resp.latency.llm_generation_ms} ms | Total {resp.latency.total_pipeline_ms} ms", flush=True)
            results.append(data)
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr, flush=True)
            import traceback
            traceback.print_exc()

    with open("screenshot/phase26_live_ollama_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("\nResults saved to screenshot/phase26_live_ollama_results.json", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
