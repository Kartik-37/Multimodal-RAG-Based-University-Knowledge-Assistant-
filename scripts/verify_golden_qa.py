"""
Comprehensive Golden QA Verification Benchmark.
Validates the complete suite of canonical benchmark queries across all modalities, scopes, and domains:
1. "Who are you?" (Conversational / Persona)
2. "Who is Narendra Modi?" (Out of Scope / Refusal)
3. "What is Flutter?" (Core Definition / Screenshot B target)
4. "Can you summarize the Flutter PDF?" (Document Summary / Screenshot A target)
5. "What is the name of this act?" (Statutory Entity Extraction)
6. "What are the supported iOS devices?" (Visual Diagram Retrieval & Extraction)
7. "List the Android versions" (Sequential Chronology / Table Extraction)
"""

import asyncio
import sys
import uuid

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from backend.app.db.session import SessionLocal
from backend.app.services.rag_orchestrator import get_rag_orchestrator

FLUTTER_DOC_ID = uuid.UUID("aa7598cf-9ea8-497c-bf6c-2f0e11a96000")
FLUTTER_KB_ID = uuid.UUID("a8ed9e38-0e78-42dc-8953-b3c5d745d618")

ACT_DOC_ID = uuid.UUID("c94c8636-6233-4144-b3ff-e535a1e6fa4b")
ACT_KB_ID = uuid.UUID("6a291115-85d8-4257-b9ea-23b9ea3d3624")


async def run_benchmark():
    orch = get_rag_orchestrator()
    print("=" * 80)
    print("STARTING GOLDEN QA REGRESSION BENCHMARK")
    print("=" * 80)

    test_cases = [
        {
            "category": "Conversational / Identity",
            "query": "Who are you?",
            "kb_id": FLUTTER_KB_ID,
            "doc_id": FLUTTER_DOC_ID,
            "expected_grounding": ("CONVERSATIONAL", "REFUSAL"),
            "check": lambda resp: "assistant" in resp.answer.lower() or "ai" in resp.answer.lower(),
        },
        {
            "category": "Out of Scope Refusal",
            "query": "Who is Narendra Modi?",
            "kb_id": FLUTTER_KB_ID,
            "doc_id": FLUTTER_DOC_ID,
            "expected_grounding": ("REFUSAL", "UNVERIFIABLE", "PARTIALLY_SUPPORTED"),
            "check": lambda resp: any(w in resp.answer.lower() for w in ("outside the scope", "not mentioned", "not found", "cannot answer", "could not find", "insufficient")),
        },
        {
            "category": "Statutory Act Title",
            "query": "What is the name of this act?",
            "kb_id": ACT_KB_ID,
            "doc_id": ACT_DOC_ID,
            "expected_grounding": ("FULLY_SUPPORTED",),
            "check": lambda resp: "kaushalya" in resp.answer.lower() and len(resp.citations) > 0,
        },
        {
            "category": "Supported iOS Devices (Visual/Diagram)",
            "query": "What are the supported iOS devices?",
            "kb_id": FLUTTER_KB_ID,
            "doc_id": FLUTTER_DOC_ID,
            "expected_grounding": ("FULLY_SUPPORTED", "PARTIALLY_SUPPORTED"),
            "check": lambda resp: "iphone" in resp.answer.lower() and len(resp.citations) > 0,
        },
        {
            "category": "Android Versions (List)",
            "query": "List the Android versions",
            "kb_id": FLUTTER_KB_ID,
            "doc_id": FLUTTER_DOC_ID,
            "expected_grounding": ("FULLY_SUPPORTED", "PARTIALLY_SUPPORTED"),
            "check": lambda resp: "android" in resp.answer.lower() and len(resp.citations) > 0,
        },
        {
            "category": "Direct Definition (Screenshot B Target)",
            "query": "What is Flutter?",
            "kb_id": FLUTTER_KB_ID,
            "doc_id": FLUTTER_DOC_ID,
            "expected_grounding": ("FULLY_SUPPORTED",),
            "check": lambda resp: "sdk" in resp.answer.lower() and resp.grounding.is_grounded and any(c.page_number == 18 for c in resp.citations),
        },
        {
            "category": "Document Summary (Screenshot A Target)",
            "query": "Can you summarize the Flutter PDF?",
            "kb_id": FLUTTER_KB_ID,
            "doc_id": FLUTTER_DOC_ID,
            "expected_grounding": ("FULLY_SUPPORTED",),
            "check": lambda resp: "overview" in resp.answer.lower() and resp.grounding.is_grounded and len(resp.citations) >= 3,
        },
    ]

    results = []

    with SessionLocal() as db:
        for idx, tc in enumerate(test_cases, 1):
            print(f"\n[{idx}/{len(test_cases)}] Testing: '{tc['query']}' ({tc['category']})...")
            resp = await orch.execute_query(
                db=db,
                kb_id=tc["kb_id"],
                raw_query=tc["query"],
                document_id=tc["doc_id"],
            )

            passed_check = tc["check"](resp)
            passed_grounding = resp.grounding.status in tc["expected_grounding"]
            passed_all = passed_check and passed_grounding

            results.append({
                "query": tc["query"],
                "category": tc["category"],
                "passed": passed_all,
                "status": resp.grounding.status,
                "is_grounded": resp.grounding.is_grounded,
                "citations": len(resp.citations),
                "mode": resp.metadata.get("generation_mode"),
                "llm_invoked": resp.metadata.get("llm_invoked"),
                "answer_preview": resp.answer[:120].replace("\n", " "),
            })

            print(f"  Result: {'PASS' if passed_all else 'FAIL'}")
            print(f"  Mode: {resp.metadata.get('generation_mode')} | LLM Invoked: {resp.metadata.get('llm_invoked')}")
            print(f"  Grounding: {resp.grounding.status} (is_grounded={resp.grounding.is_grounded})")
            print(f"  Citations: {len(resp.citations)}")
            print(f"  Answer: {resp.answer[:140]}...")

    print("\n" + "=" * 80)
    print("BENCHMARK SUMMARY")
    print("=" * 80)
    total_passed = sum(1 for r in results if r["passed"])
    for r in results:
        status_symbol = "✓" if r["passed"] else "✗"
        print(f"  [{status_symbol}] {r['category']:<35} | {r['status']:<18} | mode={r['mode']} | citations={r['citations']}")

    print(f"\nTOTAL: {total_passed}/{len(results)} PASSED ({(total_passed / len(results)) * 100:.1f}%)")


if __name__ == "__main__":
    asyncio.run(run_benchmark())

