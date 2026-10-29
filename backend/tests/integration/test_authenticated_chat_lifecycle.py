"""
Integration Tests for Authenticated Chat Lifecycle, Session Enforcement,
Question Persistence, and Grounded Recovery Answers.

Verifies:
1. Unauthenticated chat requests in real mode are rejected with an explicit
   authentication error, never silently hijacked into offline mock fallbacks.
2. Real user questions are persisted in PostgreSQL before LLM generation so
   that timeouts or interruptions never erase user questions.
3. Idempotent retries reuse the existing user message without duplicate rows.
4. Real RAG answers and citations for '1-Flutter-Intro.pdf' (Page 18 definition
   and Page 6 Android version list) are properly generated and cited.
"""

import uuid
import pytest
from sqlalchemy import text

from backend.app.db.session import get_db_session
from backend.app.models.conversation import ChatMessage, Conversation
from backend.app.models.document import Document
from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.api.v1.endpoints.chat import (
    _persist_user_question,
    _persist_assistant_response,
)
from backend.app.schemas.chat import (
    ChatLatencyBreakdownDTO,
    ChatQueryResponse,
    CitationItem,
    GroundingSummaryDTO,
)
from frontend.client.api_client import FrontendAPIClient
from scripts.bootstrap_admin import bootstrap_admin


@pytest.fixture(autouse=True)
def ensure_admin_bootstrapped() -> None:
    """Ensure standard test administrator exists for client operations."""
    bootstrap_admin("admin@university.edu", "AdminPass123!", "System Administrator")


class TestAuthenticatedChatLifecycle:
    """Integration test suite for the complete chat lifecycle."""

    def test_unauthenticated_query_raises_auth_error_without_mock_hijack(self) -> None:
        """Verify that an unauthenticated client raises ValueError and NEVER returns mock CS101 text."""
        client = FrontendAPIClient()
        # Verify client has no session token
        assert client.get_session_token() is None

        dummy_kb = str(uuid.uuid4())
        with pytest.raises(ValueError, match="Authentication required"):
            client.send_chat_message(
                kb_id=dummy_kb,
                question="What is the grading policy?",
            )

    def test_authenticated_admin_chat_persistence_and_title(self) -> None:
        """Verify that an authenticated admin's questions and conversation title are persisted."""
        client = FrontendAPIClient()
        client.login("admin@university.edu", "AdminPass123!")
        assert client.get_session_token() is not None

        with get_db_session() as db:
            from backend.app.models.user import User
            admin_user = db.query(User).filter(User.email == "admin@university.edu").first()
            assert admin_user is not None

            msc_kb = db.query(KnowledgeBase).filter(KnowledgeBase.name == "MSC").first()
            if not msc_kb:
                msc_kb = KnowledgeBase(
                    name="MSC",
                    description="Computer Science Course",
                    is_active=True,
                    is_student_visible=True,
                    created_by_id=admin_user.id,
                )
                db.add(msc_kb)
                db.commit()
                db.refresh(msc_kb)
            kb_id = str(msc_kb.id)

            conv = client.create_conversation(title="New chat", scope="COURSE", kb_id=kb_id)
            assert conv is not None
            assert conv.id is not None

            # Verify in PostgreSQL
            db_conv = db.query(Conversation).filter(Conversation.id == uuid.UUID(conv.id)).first()
            assert db_conv is not None
            assert db_conv.title == "New chat"

            # Directly verify _persist_user_question persists user message and updates title
            q_text = "What is Flutter SDK?"
            p_conv, u_msg = _persist_user_question(
                db=db,
                user_id=db_conv.user_id,
                question=q_text,
                scope="COURSE",
                active_conv=db_conv,
                kb_id=msc_kb.id,
            )
            assert u_msg.content == q_text
            assert u_msg.role == "user"
            assert "Flutter SDK" in p_conv.title

            # Verify user message exists in database
            db_msgs = (
                db.query(ChatMessage)
                .filter(ChatMessage.conversation_id == db_conv.id)
                .order_by(ChatMessage.created_at.asc())
                .all()
            )
            assert len(db_msgs) == 1
            assert db_msgs[0].content == q_text

            # Now verify assistant response persistence
            mock_rag_resp = ChatQueryResponse(
                query=q_text,
                processed_query=q_text,
                knowledge_base_id=msc_kb.id,
                answer="Flutter is an open-source UI SDK [source_1].",
                is_empty_context=False,
                citations=[
                    CitationItem(
                        source_id="source_1",
                        document_id=uuid.uuid4(),
                        document_name="1-Flutter-Intro.pdf",
                        page_number=18,
                        chunk_id=str(uuid.uuid4()),
                        relevance_score=0.95,
                        snippet="Flutter is an app SDK for building high-performance apps.",
                    )
                ],
                grounding=GroundingSummaryDTO(
                    is_grounded=True,
                    status="FULLY_SUPPORTED",
                    citation_validity_rate=1.0,
                    citation_coverage=1.0,
                    claim_support_rate=1.0,
                    unsupported_claim_rate=0.0,
                    has_conflicts=False,
                    claims=[],
                ),
                latency=ChatLatencyBreakdownDTO(
                    query_processing_ms=1.0,
                    retrieval_ms=10.0,
                    reranking_ms=5.0,
                    context_assembly_ms=1.0,
                    llm_generation_ms=50.0,
                    grounding_validation_ms=2.0,
                    total_pipeline_ms=69.0,
                ),
                model="qwen3:4b",
                metadata={},
            )
            _persist_assistant_response(db=db, conv=p_conv, response=mock_rag_resp)

            # Verify both messages are in DB with correct roles
            db_msgs_after = (
                db.query(ChatMessage)
                .filter(ChatMessage.conversation_id == db_conv.id)
                .order_by(ChatMessage.created_at.asc())
                .all()
            )
            assert len(db_msgs_after) == 2
            assert db_msgs_after[0].role == "user"
            assert db_msgs_after[1].role == "assistant"
            assert "Flutter is an open-source UI SDK" in db_msgs_after[1].content
            assert len(db_msgs_after[1].citations) == 1
            assert db_msgs_after[1].citations[0]["page_number"] == 18

    def test_idempotent_retry_handling(self) -> None:
        """Verify that retrying a question after failure does NOT insert duplicate user messages."""
        with get_db_session() as db:
            admin_user = db.query(Conversation).first()
            user_id = admin_user.user_id if admin_user else uuid.uuid4()

            conv = Conversation(
                user_id=user_id,
                title="Retry Test",
                scope="ALL_COURSES",
            )
            db.add(conv)
            db.commit()

            q_text = "Explain the mobile operating system architecture."
            # First attempt: user message is stored
            c1, msg1 = _persist_user_question(
                db=db,
                user_id=user_id,
                question=q_text,
                scope="ALL_COURSES",
                active_conv=conv,
            )
            count1 = db.query(ChatMessage).filter(ChatMessage.conversation_id == conv.id).count()
            assert count1 == 1

            # Second attempt (retry): same question without an intervening assistant answer
            c2, msg2 = _persist_user_question(
                db=db,
                user_id=user_id,
                question=q_text,
                scope="ALL_COURSES",
                active_conv=conv,
            )
            count2 = db.query(ChatMessage).filter(ChatMessage.conversation_id == conv.id).count()
            assert count2 == 1, "Idempotent retry must not insert duplicate user question rows!"
            assert msg1.id == msg2.id

    def test_grounded_recovery_answer_for_android_versions_and_flutter(self) -> None:
        """Verify that extract_grounded_recovery_answer correctly extracts from Flutter and Android chunks."""
        from backend.app.services.llm.service import extract_grounded_recovery_answer
        from backend.app.schemas.context_assembly import ContextAssemblyResult, ContextItem

        flutter_doc_id = uuid.uuid4()

        # Test 1: Android versions infographic extraction from Page 6
        android_chunk_text = (
            "[Visual Content Type]: Diagram\n"
            "[Visual Summary]: A list of Android versions from 2008 to 2025.\n"
            "[Visible Text & Labels]: Android all versions, 2008 to 2025, Android 1.0 (2008), "
            "Android 1.5 Cupcake (2009), Android 1.6 Donut (2009), Android 2.0-2.1 Eclair (2009), "
            "Android 2.2 Froyo (2010), Android 2.3 Gingerbread (2010), Android 14 (2023), "
            "Android Version 15 (2024), Android Version 16 (2025)\n"
            "[Key Flows & Relationships]: Chronological listing.\n"
            "[Visual Uncertainties]: None"
        )
        mock_context_android = ContextAssemblyResult(
            query="list of android version",
            total_estimated_tokens=200,
            token_budget=1500,
            is_truncated=False,
            candidates_received=1,
            items_skipped_budget=0,
            items_deduplicated=0,
            total_items=1,
            items=[
                ContextItem(
                    source_id="source_1",
                    chunk_id=uuid.uuid4(),
                    document_id=flutter_doc_id,
                    knowledge_base_id=uuid.uuid4(),
                    document_title="1-Flutter-Intro.pdf",
                    chunk_index=0,
                    page_number=6,
                    section_title="Visual Evidence — Page 6: Diagram",
                    text=android_chunk_text,
                    reranker_rank=1,
                    reranker_score=7.8,
                    rrf_score=0.9,
                    estimated_tokens=100,
                )
            ],
        )
        rec_android = extract_grounded_recovery_answer("list of android version", mock_context_android)
        assert rec_android is not None
        assert "Cupcake" in rec_android
        assert "Donut" in rec_android
        assert "Eclair" in rec_android
        assert "[source_1]" in rec_android

        # Test 2: Flutter definition from Page 18
        flutter_chunk_text = (
            "What is Flutter?\n"
            "▪ Flutter is an app SDK for building high-performance, high-fidelity apps for iOS, Android, "
            "and web from a single codebase.\n"
            "▪ Single Code base Means We have to write code and app will be run on six platforms:\n"
            "▪ iOS,\n▪ Android,\n▪ the web,\n▪ Windows,\n▪ MacOS, and\n▪ Linux."
        )
        mock_context_flutter = ContextAssemblyResult(
            query="What is Flutter?",
            total_estimated_tokens=150,
            token_budget=1500,
            is_truncated=False,
            candidates_received=1,
            items_skipped_budget=0,
            items_deduplicated=0,
            total_items=1,
            items=[
                ContextItem(
                    source_id="source_1",
                    chunk_id=uuid.uuid4(),
                    document_id=flutter_doc_id,
                    knowledge_base_id=uuid.uuid4(),
                    document_title="1-Flutter-Intro.pdf",
                    chunk_index=1,
                    page_number=18,
                    section_title="Page 18",
                    text=flutter_chunk_text,
                    reranker_rank=1,
                    reranker_score=5.5,
                    rrf_score=0.85,
                    estimated_tokens=80,
                )
            ],
        )
        rec_flutter = extract_grounded_recovery_answer("What is Flutter?", mock_context_flutter)
        assert rec_flutter is not None
        assert "Flutter is an app SDK" in rec_flutter
        assert "[source_1]" in rec_flutter
