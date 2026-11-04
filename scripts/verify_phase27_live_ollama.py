"""
Live Ollama Verification Script for Phase 27 Generalized RAG Answer Pipeline.

Evaluates the real, generalized RAG orchestrator with local Ollama (qwen3:4b):
1. 'What is Flutter?' -> Complete definition in connected prose, no canned phrases.
2. 'What is a widget in Flutter?' -> Genuine explanatory synthesis, not raw chunk copies or precomposed bullets.
3. 'What is the name of this Act?' (BCA KB with KSU-Act-English.pdf) -> Genuine LLM synthesis of statutory title.
4. 'What are ACID properties in relational databases?' (BCA KB) -> Genuine evidence-based refusal without hallucination.

Saves benchmark results to screenshot/phase27_live_ollama_results.json.
"""

import asyncio
import json
import sys
import uuid
from pathlib import Path

from backend.app.db.session import SessionLocal
from backend.app.services.rag_orchestrator import get_rag_orchestrator


async def main():
    db = SessionLocal()
    orchestrator = get_rag_orchestrator()

    msc_kb_id = uuid.UUID("a8ed9e38-0e78-42dc-8953-b3c5d745d618")
    bca_kb_id = uuid.UUID("49745dda-3cb9-41c3-bc7a-1716ee5a41fa")

    test_cases = [
        {
            "kb_id": msc_kb_id,
            "course": "MSC (Flutter)",
            "query": "What is Flutter?",
            "expectation": "Complete definition in connected prose, no truncated phrases",
        },
        {
            "kb_id": msc_kb_id,
            "course": "MSC (Flutter)",
            "query": "What is a widget in Flutter?",
            "expectation": "Genuine explanatory synthesis from evidence, not pre-composed canned bullets",
        },
        {
            "kb_id": bca_kb_id,
            "course": "BCA (KSU Act)",
            "query": "What is the name of this Act?",
            "expectation": "Genuine LLM synthesis of Kaushalya The Skill University Act, 2021",
        },
        {
            "kb_id": bca_kb_id,
            "course": "BCA (KSU Act)",
            "query": "What are ACID properties in relational databases?",
            "expectation": "Generic safe refusal (not mentioned in course materials), no hallucination",
        },
    ]

    results = []

    for tc in test_cases:
        q = tc["query"]
        kb_id = tc["kb_id"]
        course = tc["course"]
        print(f"\n=======================================================", flush=True)
        print(f"COURSE: {course} | QUERY: {q}", flush=True)
        print(f"EXPECTATION: {tc['expectation']}", flush=True)
        print(f"=======================================================", flush=True)

        try:
            resp = await orchestrator.execute_query(
                db=db,
                kb_id=kb_id,
                raw_query=q,
            )

            data = {
                "course": course,
                "query": q,
                "expectation": tc["expectation"],
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
                "model": resp.model,
                "latency_breakdown": resp.latency.model_dump() if resp.latency else {},
            }

            if resp.metadata:
                data["llm_invoked"] = resp.metadata.get("llm_invoked")
                data["generation_mode"] = resp.metadata.get("generation_mode")
                data["provider_calls"] = resp.metadata.get("provider_calls", 1)
                data["retry_occurred"] = resp.metadata.get("retry_occurred", False)

            print(f"ANSWER:\n{resp.answer}\n", flush=True)
            print(f"CITATIONS: {[c.source_id for c in resp.citations]} (pages: {[c.page_number for c in resp.citations]})", flush=True)
            if resp.grounding:
                print(f"GROUNDING: {resp.grounding.status} (is_grounded={resp.grounding.is_grounded})", flush=True)
            print(
                f"LLM INVOKED: {data.get('llm_invoked')} | MODE: {data.get('generation_mode')} | "
                f"PROVIDER CALLS: {data.get('provider_calls')} | RETRY: {data.get('retry_occurred')} | "
                f"MODEL: {resp.model}",
                flush=True,
            )
            if resp.latency:
                print(
                    f"LATENCY: LLM {resp.latency.llm_generation_ms} ms | Total {resp.latency.total_pipeline_ms} ms",
                    flush=True,
                )

            results.append(data)

        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr, flush=True)
            import traceback
            traceback.print_exc()

    output_path = Path("screenshot/phase27_live_ollama_results.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nPhase 27 Live Ollama Benchmark results saved to {output_path}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())

