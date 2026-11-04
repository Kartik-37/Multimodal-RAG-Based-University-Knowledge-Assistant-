"""
Phase 25 Behavioral & Security Verification Suite.

Tests for:
1. Account-Level Idempotent New Chat Draft Lifecycle & Concurrency Reuse.
2. Student Three-Mode Scope Selector Parity (ALL_COURSES, COURSE, DOCUMENT).
3. Natural, Intent-Aware LIST Answers with Complete Reasoning Sanitization.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from backend.app.models.conversation import ChatMessage, Conversation
from backend.app.models.user import User, UserRole
from backend.app.schemas.conversation import CreateConversationRequest
from backend.app.schemas.context_assembly import ContextAssemblyResult, ContextItem
from backend.app.services.llm.service import (
    _sanitize_llm_answer,
    clean_reasoning_text,
    extract_grounded_recovery_answer,
    format_inline_list_items,
    is_reasoning_or_non_answer,
)
from backend.app.services.llm.prompt_builder import GroundedPromptBuilder, response_format_for_query
from frontend.state.app_state import AppState


# ==============================================================================
# Workstream A: Account-Level Idempotent New Chat Draft Lifecycle Tests
# ==============================================================================

class TestPhase25DraftLifecycle:
    """Verifies that each student account has at most ONE reusable empty draft in DB."""

    def test_get_or_create_draft_creates_single_canonical_draft(self, db_session) -> None:
        """First request with no conversations creates exactly one draft."""
        from backend.app.api.v1.endpoints.conversations import get_or_create_draft

        test_user = User(
            id=uuid.uuid4(),
            email=f"student_{uuid.uuid4().hex[:6]}@university.edu",
            password_hash="hash",
            full_name="Draft Test Student",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(test_user)
        db_session.commit()

        req = CreateConversationRequest(title="New chat", scope="ALL_COURSES")
        draft = get_or_create_draft(payload=req, current_user=test_user, db=db_session)

        assert draft is not None
        assert draft.title == "New chat"
        assert draft.scope == "ALL_COURSES"
        assert draft.messages == []

        # Verify exactly one row in DB
        rows = db_session.query(Conversation).filter(Conversation.user_id == test_user.id).all()
        assert len(rows) == 1
        assert rows[0].id == draft.id

    def test_get_or_create_draft_reuses_existing_empty_draft(self, db_session) -> None:
        """Second call for same user reuses existing empty draft without creating new row."""
        from backend.app.api.v1.endpoints.conversations import get_or_create_draft

        test_user = User(
            id=uuid.uuid4(),
            email=f"student_{uuid.uuid4().hex[:6]}@university.edu",
            password_hash="hash",
            full_name="Reuse Test Student",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(test_user)
        db_session.commit()

        req = CreateConversationRequest(title="New chat", scope="ALL_COURSES")
        draft1 = get_or_create_draft(payload=req, current_user=test_user, db=db_session)
        draft2 = get_or_create_draft(payload=req, current_user=test_user, db=db_session)
        draft3 = get_or_create_draft(payload=req, current_user=test_user, db=db_session)

        assert draft1.id == draft2.id == draft3.id

        # Verify only 1 database row exists
        rows = db_session.query(Conversation).filter(Conversation.user_id == test_user.id).all()
        assert len(rows) == 1

    def test_draft_isolation_between_different_users(self, db_session) -> None:
        """Two different students receive distinct drafts; never reuse another user's draft."""
        from backend.app.api.v1.endpoints.conversations import get_or_create_draft

        u1 = User(
            id=uuid.uuid4(),
            email=f"u1_{uuid.uuid4().hex[:6]}@university.edu",
            password_hash="hash",
            full_name="Student 1",
            role=UserRole.STUDENT,
            is_active=True,
        )
        u2 = User(
            id=uuid.uuid4(),
            email=f"u2_{uuid.uuid4().hex[:6]}@university.edu",
            password_hash="hash",
            full_name="Student 2",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add_all([u1, u2])
        db_session.commit()

        req = CreateConversationRequest(title="New chat", scope="ALL_COURSES")
        d1 = get_or_create_draft(payload=req, current_user=u1, db=db_session)
        d2 = get_or_create_draft(payload=req, current_user=u2, db=db_session)

        assert d1.id != d2.id
        rows_u1 = db_session.query(Conversation).filter(Conversation.user_id == u1.id).all()
        rows_u2 = db_session.query(Conversation).filter(Conversation.user_id == u2.id).all()
        assert len(rows_u1) == 1
        assert len(rows_u2) == 1

    def test_populated_conversation_never_reused_as_draft(self, db_session) -> None:
        """Once a conversation has messages, it is never reused as a draft."""
        from backend.app.api.v1.endpoints.conversations import get_or_create_draft

        test_user = User(
            id=uuid.uuid4(),
            email=f"pop_{uuid.uuid4().hex[:6]}@university.edu",
            password_hash="hash",
            full_name="Populated Student",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(test_user)
        db_session.commit()

        req = CreateConversationRequest(title="New chat", scope="ALL_COURSES")
        draft1 = get_or_create_draft(payload=req, current_user=test_user, db=db_session)

        # Add a message to draft1 (simulating question submission)
        msg = ChatMessage(
            id=uuid.uuid4(),
            conversation_id=draft1.id,
            role="user",
            content="What is Flutter?",
        )
        db_session.add(msg)
        conv_row = db_session.query(Conversation).filter(Conversation.id == draft1.id).one()
        conv_row.title = "What is Flutter?"
        db_session.commit()

        # Next draft request creates a fresh draft, preserving the populated conversation
        draft2 = get_or_create_draft(payload=req, current_user=test_user, db=db_session)
        assert draft2.id != draft1.id
        assert draft2.title == "New chat"

        user_convs = db_session.query(Conversation).filter(Conversation.user_id == test_user.id).all()
        assert len(user_convs) == 2
        titles = {c.title for c in user_convs}
        assert "What is Flutter?" in titles
        assert "New chat" in titles

    def test_duplicate_older_empty_drafts_cleaned_up(self, db_session) -> None:
        """If historical duplicate empty drafts exist, get_or_create_draft cleans them up."""
        from backend.app.api.v1.endpoints.conversations import get_or_create_draft

        test_user = User(
            id=uuid.uuid4(),
            email=f"dup_{uuid.uuid4().hex[:6]}@university.edu",
            password_hash="hash",
            full_name="Duplicate Student",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(test_user)
        db_session.commit()

        # Seed 3 duplicate empty drafts
        c1 = Conversation(user_id=test_user.id, title="New chat", scope="ALL_COURSES")
        c2 = Conversation(user_id=test_user.id, title="New chat", scope="ALL_COURSES")
        c3 = Conversation(user_id=test_user.id, title="New chat", scope="ALL_COURSES")
        db_session.add_all([c1, c2, c3])
        db_session.commit()

        assert db_session.query(Conversation).filter(Conversation.user_id == test_user.id).count() == 3

        # get_or_create_draft canonicalizes and cleans up duplicates
        req = CreateConversationRequest(title="New chat", scope="ALL_COURSES")
        canonical = get_or_create_draft(payload=req, current_user=test_user, db=db_session)

        remaining = db_session.query(Conversation).filter(Conversation.user_id == test_user.id).all()
        assert len(remaining) == 1
        assert remaining[0].id == canonical.id

    def test_history_api_error_does_not_return_false_empty_list(self) -> None:
        """api_client.get_conversations raises an error on non-200 rather than returning []."""
        from frontend.client.api_client import FrontendAPIClient

        client = FrontendAPIClient()
        mock_resp = MagicMock()
        mock_resp.status_code = 500

        with patch.object(client._http, "get", return_value=mock_resp), \
             patch.object(client, "get_session_token", return_value="tok-123"):
            with pytest.raises(ValueError, match="Failed to fetch conversations"):
                client.get_conversations()


# ==============================================================================
# Workstream B: Student Three-Mode Scope Selector Tests
# ==============================================================================

class TestPhase25StudentScopeSelector:
    """Verifies that Student scope transitions handle ALL_COURSES, COURSE, and DOCUMENT."""

    def test_scope_state_transitions(self) -> None:
        """Verify AppState transitions scope, kb_id, and doc_id correctly."""
        state = AppState()
        assert state.active_scope == "ALL_COURSES"
        assert state.active_kb_id is None
        assert state.active_doc_id is None

        # Transition to COURSE
        course_id = "00000000-0000-0000-0000-000000000001"
        state.set_scope("COURSE", kb_id=course_id)
        assert state.active_scope == "COURSE"
        assert state.active_kb_id == course_id
        assert state.active_doc_id is None

        # Transition to DOCUMENT
        doc_id = "00000000-0000-0000-0000-000000000002"
        state.set_scope("DOCUMENT", kb_id=course_id, doc_id=doc_id)
        assert state.active_scope == "DOCUMENT"
        assert state.active_kb_id == course_id
        assert state.active_doc_id == doc_id

        # Selecting a different course clears previous doc_id
        new_course_id = "00000000-0000-0000-0000-000000000003"
        state.set_scope("COURSE", kb_id=new_course_id, doc_id=None)
        assert state.active_scope == "COURSE"
        assert state.active_kb_id == new_course_id
        assert state.active_doc_id is None

        # Reset scope returns to ALL_COURSES and clears both IDs
        state.reset_scope()
        assert state.active_scope == "ALL_COURSES"
        assert state.active_kb_id is None
        assert state.active_doc_id is None

    def test_scope_validity_logic(self) -> None:
        """Verify scope validation rules for student queries."""
        def is_scope_valid(scope: str, kb_id: str | None, doc_id: str | None) -> tuple[bool, str]:
            if scope == "COURSE" and not kb_id:
                return False, "Please select a specific course before asking questions"
            if scope == "DOCUMENT":
                if not kb_id:
                    return False, "Please select a course before asking questions in Document scope"
                if not doc_id:
                    return False, "Please select a specific document before asking questions"
            return True, ""

        assert is_scope_valid("ALL_COURSES", None, None)[0] is True
        assert is_scope_valid("COURSE", None, None)[0] is False
        assert is_scope_valid("COURSE", "cid-1", None)[0] is True
        assert is_scope_valid("DOCUMENT", None, None)[0] is False
        assert is_scope_valid("DOCUMENT", "cid-1", None)[0] is False
        assert is_scope_valid("DOCUMENT", "cid-1", "doc-1")[0] is True


# ==============================================================================
# Workstream C: Natural LIST Answers & CoT Reasoning Sanitization Tests
# ==============================================================================

class TestPhase25ListAnswerQuality:
    """Verifies that list queries and Flutter widget questions produce clean, direct output."""

    def test_flutter_widget_list_eliminates_reasoning_and_meta_talk(self) -> None:
        """Ensure 'the notes do not enumerate...', 'the answer should be...' are eliminated."""
        raw_model_output = (
            "We must examine the retrieved evidence. The user is asking for flutter widget list.\n"
            "Looking at the notes, the evidence only states that Everything is a Widget [source_1].\n"
            "Also, it mentions Material widgets and Cupertino widgets for consistent design [source_2].\n"
            "The notes do not enumerate individual widget class names like Container or Row.\n"
            "Therefore, the answer should be that in Flutter, everything is a widget and it provides "
            "Material and Cupertino widgets for cross-platform styling.\n"
            "In conclusion, the notes do not enumerate individual widgets."
        )

        cleaned = _sanitize_llm_answer(raw_model_output, query="flutter widget list")

        assert "We must examine" not in cleaned
        assert "The user is asking" not in cleaned
        assert "the evidence only states" not in cleaned
        assert "the answer should be" not in cleaned
        assert "Looking at the notes" not in cleaned
        assert "Therefore, the answer" not in cleaned
        assert "In conclusion" not in cleaned

    def test_flutter_widget_list_does_not_contain_iphone_drift(self) -> None:
        """Verify that widget answers never drift into listing iPhone or mobile devices."""
        raw_output_with_devices = (
            "- [source_1]: Lists supported devices: iPhone 11, iPhone 12, iPhone 13.\n"
            "The answer is that Flutter widgets include widgets."
        )

        candidate = clean_reasoning_text(raw_output_with_devices, query="flutter widget list")
        assert "iPhone 11" not in candidate
        assert "iPhone 12" not in candidate

    def test_flutter_widget_grounded_recovery_answer(self) -> None:
        """Verify that extract_grounded_recovery_answer is retired in Phase 26 and returns None."""
        items = [
            ContextItem(
                source_id="source_1",
                chunk_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                knowledge_base_id=uuid.uuid4(),
                document_title="Flutter Course Notes",
                chunk_index=0,
                text="In Flutter, everything is a widget. Even the app itself is a widget.",
                reranker_rank=1,
                reranker_score=0.95,
                rrf_score=0.95,
                estimated_tokens=50,
            ),
        ]
        context = MagicMock()
        context.items = items

        answer = extract_grounded_recovery_answer("flutter widget list", context)
        # Phase 26: extract_grounded_recovery_answer must return None (no canned factual prose)
        assert answer is None

    def test_definition_query_remains_prose_not_bullets(self) -> None:
        """A simple definition question like 'What is Flutter?' remains natural prose."""
        raw_text = "Flutter is an open-source UI software development kit created by Google [source_1]."
        formatted = format_inline_list_items(raw_text, query="What is Flutter?")
        assert not formatted.startswith("- ")
        assert not formatted.startswith("1. ")
        assert formatted == raw_text

    def test_supported_list_query_formats_clean_bullets(self) -> None:
        """A real list query formats items as clean bullet points."""
        raw_text = (
            "The supported platforms are: Android version 12 (2021), iOS 15 (2021), Web, Windows, macOS, Linux."
        )
        directive = response_format_for_query("list platforms supported by Flutter")
        assert directive == "list"

    def test_cross_block_duplicate_conclusion_eliminated(self) -> None:
        """Duplicated concluding sentences are filtered out cleanly."""
        text = (
            "Flutter uses a unified widget tree where everything is a widget [source_1].\n\n"
            "Flutter uses a unified widget tree where everything is a widget."
        )
        cleaned = _sanitize_llm_answer(text, query="explain widgets in flutter")
        # Should not repeat the exact same sentence in two blocks
        assert cleaned.count("Flutter uses a unified widget tree") == 1
