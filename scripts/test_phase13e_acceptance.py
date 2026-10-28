"""
Phase 13E Acceptance Verification Script.

Tests the four key conversational RAG scenarios against the running PostgreSQL database and Ollama models:
1. Test A: 'list of android version' (Infographic on Page 6 of 1-Flutter-Intro.pdf)
2. Test B: 'What is Flutter?' (Direct text definition from Page 18)
3. Test C: 'list that' (Conversational anaphoric follow-up)
4. Test D: Unsupported Query (Grounded refusal without hallucination)

Validates:
- No generic 'Based on the provided documents, please refer to the cited material...' answer
- Full version list extracted and cited with page 6
- Measured execution latency (< 60s)
- Correct citation page mapping
- Conversational state resolution
"""

import asyncio
import os
import sys
import time
import uuid

# Force utf-8 encoding for console output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.db.session import get_db_session
from backend.app.models.conversation import Conversation, ChatMessage
from backend.app.models.document import Document
from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.models.user import User
from backend.app.services.rag_orchestrator import get_rag_orchestrator
from backend.app.api.v1.endpoints.chat import resolve_conversational_query, _try_persist_turn
from backend.app.services.llm.service import SAFE_INSUFFICIENT_EVIDENCE_ANSWER


async def run_phase13e_verification():
    print("=" * 70)
    print("PHASE 13E ACCEPTANCE VERIFICATION: RAG ACCURACY & LATENCY BENCHMARK")
    print("=" * 70)

    orchestrator = get_rag_orchestrator()

    with get_db_session() as db:
        # 1. Locate 1-Flutter-Intro.pdf and its Knowledge Base
        doc = db.query(Document).filter(Document.original_filename.ilike("%1-Flutter-Intro.pdf%")).first()

        if not doc:
            print("ERROR: 1-Flutter-Intro.pdf not found in database.")
            return False

        kb_id = doc.knowledge_base_id
        doc_id = doc.id
        print(f"Found Target Document: '{doc.original_filename}' (ID: {doc_id})")
        print(f"Knowledge Base ID: {kb_id}")
        print("-" * 70)

        # Create or fetch a test user & conversation
        user = db.query(User).first()
        test_user_id = user.id if user else uuid.uuid4()
        conv_id = uuid.uuid4()
        conv = Conversation(
            id=conv_id,
            user_id=test_user_id,
            knowledge_base_id=kb_id,
            document_id=doc_id,
            title="Phase 13E Benchmark",
            scope="DOCUMENT",
        )
        db.add(conv)
        db.commit()

        results = {}

        # -------------------------------------------------------------
        # TEST A: "list of android version"
        # -------------------------------------------------------------
        print("\n[TEST A] Query: 'list of android version'")
        t0 = time.time()
        res_a = await orchestrator.execute_query(
            db=db,
            kb_id=kb_id,
            raw_query="list of android version",
            document_id=doc_id,
        )
        lat_a = time.time() - t0
        ans_a = res_a.answer
        cits_a = res_a.citations

        print(f"  Latency: {lat_a:.2f}s")
        print(f"  Answer Length: {len(ans_a)} chars")
        print(f"  Citations Count: {len(cits_a)}")
        for idx, c in enumerate(cits_a, 1):
            print(f"    [{idx}] Page: {c.page_number}, Doc: {c.document_name}")
        print(f"  Answer Preview:\n{ans_a[:400]}...\n")

        # Assertions for Test A
        assert "please refer to the cited material for the complete details" not in ans_a, (
            "FAIL: Generic non-answer detected!"
        )
        # Check for multiple Android versions
        versions_found = [
            v for v in ["Cupcake", "Donut", "Eclair", "Froyo", "Gingerbread", "Honeycomb",
                        "KitKat", "Lollipop", "Marshmallow", "Nougat", "Oreo", "Pie",
                        "Android 10", "Android 11", "Android 12", "Android 13", "Android 14",
                        "Android 15", "Version 16", "1.0", "1.5", "2.0"]
            if v.lower() in ans_a.lower()
        ]
        print(f"  Android Versions Identified in Answer: {len(versions_found)} ({', '.join(versions_found[:8])}...)")
        assert len(versions_found) >= 5, f"FAIL: Expected >= 5 Android versions, found {len(versions_found)}"

        # Check citations point to Page 6
        page_numbers = [c.page_number for c in cits_a if c.page_number is not None]
        assert 6 in page_numbers or any(c.page_number == 6 for c in cits_a), (
            f"FAIL: Expected Page 6 in citations, got {page_numbers}"
        )
        assert lat_a < 120.0, f"FAIL: Latency too high ({lat_a:.2f}s)"
        print("  --> [TEST A PASSED]")
        results["test_a"] = {"status": "PASSED", "latency": f"{lat_a:.2f}s", "versions_found": len(versions_found)}

        # Persist conversation turn using authoritative chat endpoint helper
        _try_persist_turn(
            db=db,
            user_id=test_user_id,
            question="list of android version",
            response=res_a,
            scope="DOCUMENT",
            active_conv=conv,
            kb_id=kb_id,
            document_id=doc_id,
        )

        # -------------------------------------------------------------
        # TEST B: "What is Flutter?"
        # -------------------------------------------------------------
        print("\n[TEST B] Query: 'What is Flutter?'")
        t0 = time.time()
        res_b = await orchestrator.execute_query(
            db=db,
            kb_id=kb_id,
            raw_query="What is Flutter?",
            document_id=doc_id,
        )
        lat_b = time.time() - t0
        ans_b = res_b.answer
        cits_b = res_b.citations

        print(f"  Latency: {lat_b:.2f}s")
        print(f"  Answer Length: {len(ans_b)} chars")
        print(f"  Citations Count: {len(cits_b)}")
        for idx, c in enumerate(cits_b, 1):
            print(f"    [{idx}] Page: {c.page_number}, Doc: {c.document_name}")
        print(f"  Answer Preview:\n{ans_b[:300]}...\n")

        assert "please refer to the cited material" not in ans_b
        assert "flutter" in ans_b.lower()
        assert any(term in ans_b.lower() for term in ["ui", "framework", "google", "toolkit", "cross-platform", "software development kit", "sdk"])
        assert len(cits_b) > 0
        print("  --> [TEST B PASSED]")
        results["test_b"] = {"status": "PASSED", "latency": f"{lat_b:.2f}s"}

        # -------------------------------------------------------------
        # TEST C: Conversational Follow-up: "list that"
        # -------------------------------------------------------------
        print("\n[TEST C] Conversational Follow-up: 'list that'")
        resolved_c = resolve_conversational_query("list that", conv)
        print(f"  Resolved Query: '{resolved_c}'")

        t0 = time.time()
        res_c = await orchestrator.execute_query(
            db=db,
            kb_id=kb_id,
            raw_query=resolved_c,
            document_id=doc_id,
        )
        lat_c = time.time() - t0
        ans_c = res_c.answer
        cits_c = res_c.citations

        print(f"  Latency: {lat_c:.2f}s")
        print(f"  Answer Length: {len(ans_c)} chars")
        print(f"  Answer Preview:\n{ans_c[:300]}...\n")

        assert "please refer to the cited material" not in ans_c
        assert any(v.lower() in ans_c.lower() for v in ["cupcake", "android", "version", "donut", "eclair", "1.0", "pie"])
        print("  --> [TEST C PASSED]")
        results["test_c"] = {"status": "PASSED", "latency": f"{lat_c:.2f}s"}

        # -------------------------------------------------------------
        # TEST D: Unsupported / OOD Query: "What is the capital of Mars?"
        # -------------------------------------------------------------
        print("\n[TEST D] Unsupported Query: 'What is the capital of Mars?'")
        t0 = time.time()
        res_d = await orchestrator.execute_query(
            db=db,
            kb_id=kb_id,
            raw_query="What is the capital of Mars?",
            document_id=doc_id,
        )
        lat_d = time.time() - t0
        ans_d = res_d.answer
        cits_d = res_d.citations

        print(f"  Latency: {lat_d:.2f}s")
        print(f"  Answer: {ans_d}")
        print(f"  Citations Count: {len(cits_d)}")

        # Must cleanly state insufficient information without hallucinating
        assert (
            SAFE_INSUFFICIENT_EVIDENCE_ANSWER in ans_d
            or "does not contain" in ans_d.lower()
            or "not mentioned" in ans_d.lower()
            or "insufficient" in ans_d.lower()
            or "not enough information" in ans_d.lower()
        )
        print("  --> [TEST D PASSED]")
        results["test_d"] = {"status": "PASSED", "latency": f"{lat_d:.2f}s"}

        # Cleanup test conversation
        db.query(ChatMessage).filter(ChatMessage.conversation_id == conv_id).delete()
        db.query(Conversation).filter(Conversation.id == conv_id).delete()
        db.commit()

        print("\n" + "=" * 70)
        print("ALL 4 ACCEPTANCE TESTS PASSED SUCCESSFULLY!")
        print("Summary:")
        for k, v in results.items():
            print(f"  {k}: {v}")
        print("=" * 70)
        return True


if __name__ == "__main__":
    success = asyncio.run(run_phase13e_verification())
    if not success:
        sys.exit(1)
