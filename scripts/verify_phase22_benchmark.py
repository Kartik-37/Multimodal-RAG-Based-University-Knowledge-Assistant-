"""
Live End-to-End Benchmark Verification Script for Phase 22.
Runs the complete Section 7 & 8 benchmark matrix against real local PostgreSQL and Ollama models.
"""

import asyncio
import sys
import uuid

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from backend.app.db.session import SessionLocal
from backend.app.services.rag_orchestrator import RAGOrchestrator, get_rag_orchestrator

FLUTTER_DOC_ID = uuid.UUID("aa7598cf-9ea8-497c-bf6c-2f0e11a96000")
FLUTTER_KB_ID = uuid.UUID("a8ed9e38-0e78-42dc-8953-b3c5d745d618")

ACT_DOC_ID = uuid.UUID("c94c8636-6233-4144-b3ff-e535a1e6fa4b")
ACT_KB_ID = uuid.UUID("6a291115-85d8-4257-b9ea-23b9ea3d3624")

BENCHMARK_CASES = [
    {
        "id": "1",
        "name": "Conversational Identity: What is your name?",
        "query": "What is your name?",
        "kb_id": FLUTTER_KB_ID,
        "doc_id": FLUTTER_DOC_ID,
        "checks": [
            lambda r: "Multimodal RAG-Based University Knowledge Assistant" in r.answer or "RAG Assistant" in r.answer,
            lambda r: len(r.citations) == 0,
            lambda r: r.metadata.get("generation_mode") == "conversational_fast_path",
            lambda r: r.metadata.get("llm_invoked") is False,
        ],
    },
    {
        "id": "2",
        "name": "Conversational Identity: Who are you?",
        "query": "Who are you?",
        "kb_id": FLUTTER_KB_ID,
        "doc_id": FLUTTER_DOC_ID,
        "checks": [
            lambda r: len(r.citations) == 0,
            lambda r: r.metadata.get("generation_mode") == "conversational_fast_path",
            lambda r: r.metadata.get("llm_invoked") is False,
        ],
    },
    {
        "id": "3",
        "name": "Conversational Greeting: Hello",
        "query": "Hello",
        "kb_id": FLUTTER_KB_ID,
        "doc_id": FLUTTER_DOC_ID,
        "checks": [
            lambda r: len(r.citations) == 0,
            lambda r: r.metadata.get("generation_mode") == "conversational_fast_path",
            lambda r: r.metadata.get("llm_invoked") is False,
        ],
    },
    {
        "id": "4",
        "name": "Out of Scope: Who is Narendra Modi?",
        "query": "Who is Narendra Modi?",
        "kb_id": FLUTTER_KB_ID,
        "doc_id": FLUTTER_DOC_ID,
        "checks": [
            lambda r: "could not find any relevant information" in r.answer.lower() or "authorized course materials" in r.answer.lower(),
            lambda r: len(r.citations) == 0,
            lambda r: r.metadata.get("generation_mode") == "out_of_scope_refusal",
            lambda r: r.metadata.get("llm_invoked") is False,
        ],
    },
    {
        "id": "5",
        "name": "Ambiguous Query: List",
        "query": "List",
        "kb_id": FLUTTER_KB_ID,
        "doc_id": FLUTTER_DOC_ID,
        "checks": [
            lambda r: "clarify" in r.answer.lower(),
            lambda r: len(r.citations) == 0,
            lambda r: r.metadata.get("generation_mode") == "ambiguous_clarification",
            lambda r: r.metadata.get("llm_invoked") is False,
        ],
    },
    {
        "id": "6",
        "name": "Core Defect A Fix: List of widgets (Must NOT return iPhones!)",
        "query": "List of widgets",
        "kb_id": FLUTTER_KB_ID,
        "doc_id": FLUTTER_DOC_ID,
        "checks": [
            lambda r: "iphone" not in r.answer.lower(),
            lambda r: "ios 26" not in r.answer.lower(),
            lambda r: not any(c.page_number == 8 for c in r.citations),
            lambda r: (
                r.metadata.get("llm_invoked") is True
                or "widget" in r.answer.lower()
                or "not find" in r.answer.lower()
                or "not enough" in r.answer.lower()
                or "does not" in r.answer.lower()
            ),
        ],
    },
    {
        "id": "7",
        "name": "Core Defect A Fix Variation: List the widgets",
        "query": "List the widgets",
        "kb_id": FLUTTER_KB_ID,
        "doc_id": FLUTTER_DOC_ID,
        "checks": [
            lambda r: "iphone" not in r.answer.lower(),
            lambda r: not any(c.page_number == 8 for c in r.citations),
        ],
    },
    {
        "id": "8",
        "name": "Flutter Concept: What is a widget in Flutter?",
        "query": "What is a widget in Flutter?",
        "kb_id": FLUTTER_KB_ID,
        "doc_id": FLUTTER_DOC_ID,
        "checks": [
            lambda r: "widget" in r.answer.lower(),
            lambda r: any(c.page_number == 34 for c in r.citations),
            lambda r: r.grounding.status in ("FULLY_SUPPORTED", "PARTIALLY_SUPPORTED", "CONVERSATIONAL", "UNVERIFIABLE"),
        ],
    },
    {
        "id": "9",
        "name": "Widget Categories: Which widget categories are mentioned in the notes?",
        "query": "Which widget categories are mentioned in the notes?",
        "kb_id": FLUTTER_KB_ID,
        "doc_id": FLUTTER_DOC_ID,
        "checks": [
            lambda r: "material" in r.answer.lower() or "cupertino" in r.answer.lower(),
            lambda r: "iphone" not in r.answer.lower(),
        ],
    },
    {
        "id": "10",
        "name": "iOS Device Query: List of supported iOS devices",
        "query": "List of supported iOS devices",
        "kb_id": FLUTTER_KB_ID,
        "doc_id": FLUTTER_DOC_ID,
        "checks": [
            lambda r: "iphone" in r.answer.lower(),
            lambda r: any(c.page_number == 8 for c in r.citations),
        ],
    },
    {
        "id": "11",
        "name": "Native App Definition: What is a native app?",
        "query": "What is a native app?",
        "kb_id": FLUTTER_KB_ID,
        "doc_id": FLUTTER_DOC_ID,
        "checks": [
            lambda r: "native" in r.answer.lower(),
            lambda r: any(c.page_number == 3 for c in r.citations),
        ],
    },
    {
        "id": "12",
        "name": "Native App Benefits: What are the benefits of native apps?",
        "query": "What are the benefits of native apps?",
        "kb_id": FLUTTER_KB_ID,
        "doc_id": FLUTTER_DOC_ID,
        "checks": [
            lambda r: any(c.page_number in (4, 20) for c in r.citations) or "speed" in r.answer.lower() or "offline" in r.answer.lower(),
        ],
    },
    {
        "id": "13",
        "name": "Hybrid App Definition: What is a hybrid app?",
        "query": "What is a hybrid app?",
        "kb_id": FLUTTER_KB_ID,
        "doc_id": FLUTTER_DOC_ID,
        "checks": [
            lambda r: "hybrid" in r.answer.lower(),
            lambda r: any(c.page_number == 9 for c in r.citations),
        ],
    },
    {
        "id": "14",
        "name": "Cross-Document Isolation: What is the Act name? against Flutter KB",
        "query": "What is the Act name?",
        "kb_id": FLUTTER_KB_ID,
        "doc_id": FLUTTER_DOC_ID,
        "checks": [
            lambda r: "kaushalya" not in r.answer.lower(),
            lambda r: len(r.citations) == 0 or not any("Act" in c.document_name for c in r.citations),
        ],
    },
    {
        "id": "15",
        "name": "Act Short Title Retrieval: What is the Act name? against authorized KSU Act KB",
        "query": "What is the Act name?",
        "kb_id": ACT_KB_ID,
        "doc_id": ACT_DOC_ID,
        "checks": [
            lambda r: "kaushalya" in r.answer.lower(),
            lambda r: any("act" in c.document_name.lower() for c in r.citations),
        ],
    },
]


async def run_benchmark():
    orchestrator = get_rag_orchestrator()
    passed_count = 0
    total_count = len(BENCHMARK_CASES)

    print("================================================================================")
    print("PHASE 22 END-TO-END BENCHMARK VERIFICATION SUITE")
    print("================================================================================")

    with SessionLocal() as db:
        for case in BENCHMARK_CASES:
            case_id = case["id"]
            name = case["name"]
            query = case["query"]
            kb_id = case["kb_id"]
            doc_id = case.get("doc_id")

            print(f"\n[{case_id}/{total_count}] {name}")
            print(f"  QUERY: {query}")

            try:
                resp = await orchestrator.execute_query(
                    db=db,
                    kb_id=kb_id,
                    raw_query=query,
                    document_id=doc_id,
                )

                ans_preview = resp.answer.replace("\n", " ")[:140]
                print(f"  ANSWER: {ans_preview}...")
                print(f"  MODE: {resp.metadata.get('generation_mode')} | LLM_INVOKED: {resp.metadata.get('llm_invoked')}")
                print(f"  GROUNDING: {resp.grounding.status} (is_grounded={resp.grounding.is_grounded})")

                cit_list = [f"p{c.page_number}:{c.document_name}" for c in resp.citations]
                print(f"  CITATIONS ({len(resp.citations)}): {', '.join(cit_list) if cit_list else 'None'}")

                case_passed = True
                for i, check in enumerate(case["checks"]):
                    if not check(resp):
                        print(f"  [!] FAILED check #{i+1}")
                        case_passed = False

                if case_passed:
                    print("  --> RESULT: PASSED")
                    passed_count += 1
                else:
                    print("  --> RESULT: FAILED")

            except Exception as e:
                print(f"  [ERROR] Execution raised: {e}")
                print("  --> RESULT: FAILED (EXCEPTION)")

    print("\n================================================================================")
    print(f"BENCHMARK SUMMARY: {passed_count}/{total_count} PASSED ({(passed_count/total_count)*100:.1f}%)")
    print("================================================================================")


if __name__ == "__main__":
    asyncio.run(run_benchmark())

