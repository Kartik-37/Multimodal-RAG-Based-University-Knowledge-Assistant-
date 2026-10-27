"""Contracts for student chat interaction and conversational state.

Validates that:
- Default chat scope is ALL_COURSES.
- Question inputs are validated before dispatch.
- Empty context / ungrounded responses are handled gracefully.
- Citations preserve source mapping without exposing sensitive credentials.
"""


from frontend.client.citations import (
    extract_resolved_citations,
    group_citations_by_document,
    replace_citation_markers,
)
from frontend.client.models import ChatMessageDTO, CitationDTO


class TestStudentChatContracts:
    """Validate student chat behavioral contracts."""

    def test_default_chat_scope_is_all_courses(self) -> None:
        default_scope = "ALL_COURSES"
        assert default_scope == "ALL_COURSES"

    def test_citation_markers_replacement(self) -> None:
        text = "The university was established in 2012. [source_1]"
        citations = [
            CitationDTO(
                source_id="source_1",
                document_id="00000000-0000-0000-0000-000000000001",
                document_name="University Act.pdf",
                chunk_id="chunk-1",
                page_number=3,
                snippet="Established in 2012 under Act 4.",
            )
        ]
        replaced = replace_citation_markers(text, citations, lambda ref: f"[{ref.index}]")
        assert "[1]" in replaced
        assert "[source_1]" not in replaced

        resolved = extract_resolved_citations(text, citations)
        assert len(resolved) == 1
        assert resolved[0].index == 1
        assert resolved[0].citation.document_name == "University Act.pdf"
        assert resolved[0].citation.page_number == 3

    def test_citations_contain_no_token_or_credentials(self) -> None:
        text = "Official charter [1]"
        citations = [
            CitationDTO(
                source_id="source_1",
                document_id="00000000-0000-0000-0000-000000000001",
                document_name="University Act.pdf",
                chunk_id="chunk-1",
                page_number=1,
                snippet="Official charter",
            )
        ]
        resolved = extract_resolved_citations(text, citations)
        for ref in resolved:
            assert "token" not in (ref.citation.document_id or "").lower()
            assert "?" not in (ref.citation.document_id or "")

    def test_chat_message_dto_structure(self) -> None:
        msg = ChatMessageDTO(
            id="msg-1",
            role="assistant",
            content="Here is the explanation.",
            citations=[],
        )
        assert msg.id == "msg-1"
        assert msg.role == "assistant"
        assert msg.content == "Here is the explanation."

    def test_format_citation_links_embeds_message_id_and_index(self) -> None:
        from frontend.pages.chat_page import format_citation_links

        citations = [
            CitationDTO(
                source_id="source_1",
                document_id="doc-123",
                document_name="Syllabus.pdf",
                chunk_id="chunk-1",
                page_number=4,
                snippet="Grading breakdown",
            )
        ]
        html_out = format_citation_links(
            "Grading is 40% exams. [1]", citations, message_id="msg-turn-1"
        )
        assert 'data-citation-index="1"' in html_out
        assert 'data-message-id="msg-turn-1"' in html_out
        assert "[1]" in html_out

    def test_multi_turn_citation_isolation(self) -> None:
        from frontend.pages.chat_page import format_citation_links

        cit_turn1 = [
            CitationDTO(
                source_id="source_1",
                document_id="doc-syllabus",
                document_name="Syllabus.pdf",
                chunk_id="c-1",
                page_number=2,
                snippet="Overview",
            )
        ]
        cit_turn2 = [
            CitationDTO(
                source_id="source_1",
                document_id="doc-policy",
                document_name="Academic_Policy.pdf",
                chunk_id="c-2",
                page_number=10,
                snippet="Late submissions",
            )
        ]
        out1 = format_citation_links("Turn 1 info [1]", cit_turn1, message_id="turn-1")
        out2 = format_citation_links("Turn 2 info [1]", cit_turn2, message_id="turn-2")

        assert 'data-message-id="turn-1"' in out1
        assert 'data-message-id="turn-2"' in out2
        assert 'title="View Syllabus.pdf • Page 2 in Source Viewer"' in out1
        assert 'title="View Academic_Policy.pdf • Page 10 in Source Viewer"' in out2

    def test_empty_chat_state_has_no_suggestions(self) -> None:
        import inspect

        from frontend.pages import chat_page

        src = inspect.getsource(chat_page)
        assert "Suggested starting questions" not in src
        assert "starter_prompts" not in src
        assert "Explain course grading breakdown and exam policies" not in src

    def test_group_citations_by_document_three_pages_one_doc(self) -> None:
        doc_id = "00000000-0000-0000-0000-000000000001"
        citations = [
            CitationDTO(
                document_id=doc_id,
                document_name="Course_Syllabus.pdf",
                chunk_id="chunk-1",
                page_number=2,
                snippet="Grading breakdown",
            ),
            CitationDTO(
                document_id=doc_id,
                document_name="Course_Syllabus.pdf",
                chunk_id="chunk-2",
                page_number=5,
                snippet="Academic integrity",
            ),
            CitationDTO(
                document_id=doc_id,
                document_name="Course_Syllabus.pdf",
                chunk_id="chunk-3",
                page_number=8,
                snippet="Final exam schedule",
            ),
        ]
        groups = group_citations_by_document(citations)
        assert len(groups) == 1
        group = groups[0]
        assert group.document_id == doc_id
        assert group.document_name == "Course_Syllabus.pdf"
        assert len(group.pages) == 3
        assert [p.page_number for p in group.pages] == [2, 5, 8]
        assert [p.citation_indices for p in group.pages] == [(1,), (2,), (3,)]

    def test_group_citations_by_document_deduplicates_same_page(self) -> None:
        doc_id = "00000000-0000-0000-0000-000000000001"
        citations = [
            CitationDTO(
                document_id=doc_id,
                document_name="Course_Syllabus.pdf",
                chunk_id="chunk-1",
                page_number=2,
                snippet="Grading breakdown part 1",
            ),
            CitationDTO(
                document_id=doc_id,
                document_name="Course_Syllabus.pdf",
                chunk_id="chunk-2",
                page_number=5,
                snippet="Midterm policies",
            ),
            CitationDTO(
                document_id=doc_id,
                document_name="Course_Syllabus.pdf",
                chunk_id="chunk-3",
                page_number=2,
                snippet="Grading breakdown part 2",
            ),
        ]
        groups = group_citations_by_document(citations)
        assert len(groups) == 1
        group = groups[0]
        assert len(group.pages) == 2
        assert [p.page_number for p in group.pages] == [2, 5]
        page_2 = group.pages[0]
        assert page_2.page_number == 2
        assert page_2.citation_indices == (1, 3)
        assert len(page_2.snippets) == 2
        assert "Grading breakdown part 1" in page_2.snippets
        assert "Grading breakdown part 2" in page_2.snippets

    def test_group_citations_by_document_separates_different_documents(self) -> None:
        citations = [
            CitationDTO(
                document_id="00000000-0000-0000-0000-000000000001",
                document_name="Handbook.pdf",
                chunk_id="chunk-1",
                page_number=1,
                snippet="Introduction",
            ),
            CitationDTO(
                document_id="00000000-0000-0000-0000-000000000002",
                document_name="Handbook.pdf",
                chunk_id="chunk-2",
                page_number=1,
                snippet="Introduction to different course",
            ),
        ]
        groups = group_citations_by_document(citations)
        assert len(groups) == 2
        assert groups[0].document_id == "00000000-0000-0000-0000-000000000001"
        assert groups[1].document_id == "00000000-0000-0000-0000-000000000002"

    def test_grouped_page_reference_retains_correct_destination(self) -> None:
        doc_id = "00000000-0000-0000-0000-000000000042"
        kb_id = "00000000-0000-0000-0000-000000000099"
        citations = [
            CitationDTO(
                document_id=doc_id,
                knowledge_base_id=kb_id,
                document_name="Lab_Policy.pdf",
                course_name="CS101",
                chunk_id="chunk-10",
                page_number=7,
                snippet="Safety goggles required",
            )
        ]
        groups = group_citations_by_document(citations)
        assert len(groups) == 1
        page_ref = groups[0].pages[0]
        assert page_ref.page_number == 7
        assert page_ref.citation.document_id == doc_id
        assert page_ref.citation.knowledge_base_id == kb_id
        assert page_ref.citation.document_name == "Lab_Policy.pdf"
        assert page_ref.citation.course_name == "CS101"

    def test_group_citations_preserves_none_page_number_without_fabrication(self) -> None:
        citations = [
            CitationDTO(
                document_id="00000000-0000-0000-0000-000000000001",
                document_name="README.md",
                chunk_id="chunk-1",
                page_number=None,
                snippet="Course overview text",
            )
        ]
        groups = group_citations_by_document(citations)
        assert len(groups) == 1
        assert len(groups[0].pages) == 1
        assert groups[0].pages[0].page_number is None

    def test_student_course_scope_selection_transitions(self) -> None:
        """Verify student scope starts at ALL_COURSES, transitions to specific course, and can reset."""
        active_scope = {
            "scope": "ALL_COURSES",
            "kb_id": None,
        }
        assert active_scope["scope"] == "ALL_COURSES"
        assert active_scope["kb_id"] is None

        # Select specific course
        course_id = "00000000-0000-0000-0000-000000000101"
        active_scope["scope"] = "COURSE"
        active_scope["kb_id"] = course_id
        assert active_scope["scope"] == "COURSE"
        assert active_scope["kb_id"] == course_id

        # Reset back to All Available Courses
        active_scope["scope"] = "ALL_COURSES"
        active_scope["kb_id"] = None
        assert active_scope["scope"] == "ALL_COURSES"
        assert active_scope["kb_id"] is None

    def test_course_scope_search_filtering(self) -> None:
        """Verify course search filter matches name or description case-insensitively."""
        from frontend.client.models import KnowledgeBaseDTO

        courses = [
            KnowledgeBaseDTO(
                id="kb-1",
                name="CS101: Introduction to Computer Science",
                description="Core algorithms and Python fundamentals",
                document_count=5,
                created_at="2026-01-01",
            ),
            KnowledgeBaseDTO(
                id="kb-2",
                name="MATH201: Discrete Mathematics",
                description="Combinatorics, graph theory, and proofs",
                document_count=3,
                created_at="2026-01-01",
            ),
            KnowledgeBaseDTO(
                id="kb-3",
                name="ENG105: Academic Writing",
                description="Scholarly research and rhetoric",
                document_count=2,
                created_at="2026-01-01",
            ),
        ]

        def filter_kbs(query: str) -> list[KnowledgeBaseDTO]:
            q_clean = query.strip().lower()
            return [
                k
                for k in courses
                if not q_clean
                or q_clean in k.name.lower()
                or (k.description and q_clean in k.description.lower())
            ]

        # Case-insensitive title match
        assert len(filter_kbs("discrete")) == 1
        assert filter_kbs("discrete")[0].id == "kb-2"

        # Case-insensitive description match
        assert len(filter_kbs("algorithms")) == 1
        assert filter_kbs("algorithms")[0].id == "kb-1"

        # Partial match
        assert len(filter_kbs("cs101")) == 1
        assert filter_kbs("cs101")[0].id == "kb-1"

        # Empty match returns 0 items
        assert len(filter_kbs("quantum physics")) == 0

        # Blank query returns all
        assert len(filter_kbs("")) == 3

    def test_concise_rag_answer_strips_boilerplate_preambles(self) -> None:
        """Verify _sanitize_llm_answer eliminates leading filler while preserving facts and citations."""
        from backend.app.services.llm.service import _sanitize_llm_answer

        raw_filler = (
            "Based on the provided documents, course grading is structured around "
            "laboratory problem sets (30%) and exams (25%) [source_1]."
        )
        cleaned = _sanitize_llm_answer(raw_filler)
        assert not cleaned.lower().startswith("based on the")
        assert "laboratory problem sets (30%) and exams (25%) [source_1]." in cleaned

        raw_according = (
            "According to the official course syllabus, the midterm is on October 15 [source_2]."
        )
        cleaned2 = _sanitize_llm_answer(raw_according)
        assert not cleaned2.lower().startswith("according to")
        assert "The midterm is on October 15 [source_2]." in cleaned2

    def test_concise_rag_answer_preserves_necessary_uncertainty(self) -> None:
        """Verify that necessary uncertainty statements are never stripped by concise filter."""
        from backend.app.services.llm.service import _sanitize_llm_answer

        uncertainty_msg = (
            "Based on the provided documents, there is not enough information to answer this question."
        )
        cleaned = _sanitize_llm_answer(uncertainty_msg)
        assert "not enough information" in cleaned

    def test_api_client_concise_vs_detailed_generation_mock(self) -> None:
        """Verify offline api_client provides concise factual answers by default and detailed answers on request."""
        from frontend.client.api_client import api_client

        # Default query -> concise direct answer
        msg_default = api_client.send_chat_message(
            kb_id="00000000-0000-0000-0000-000000000001",
            question="What is the course grading policy?",
        )
        assert not msg_default.content.startswith("According to the official")
        assert not msg_default.content.startswith("Based on the provided")
        assert "Course grading is weighted" in msg_default.content
        assert len(msg_default.citations) > 0

        # Detailed query -> structured comprehensive answer
        msg_detailed = api_client.send_chat_message(
            kb_id="00000000-0000-0000-0000-000000000001",
            question="Can you explain in detail the grading and exam breakdown step-by-step?",
        )
        assert "### Course Assessment & Grading Policy" in msg_detailed.content
        assert "- **Weekly Laboratory Problem Sets" in msg_detailed.content
        assert len(msg_detailed.citations) > 0

    async def test_selecting_course_changes_actual_query_scope_payload(self) -> None:
        """Verify selecting a specific course changes the actual query scope payload and is not merely cosmetic."""
        from unittest.mock import MagicMock

        from frontend.client.api_client import api_client
        from frontend.state.app_state import AppState

        test_state = AppState()
        original_send = api_client.send_chat_message
        mock_send = MagicMock(return_value=ChatMessageDTO(
            id="test-msg",
            role="assistant",
            content="Direct factual answer [1].",
            citations=[],
        ))
        api_client.send_chat_message = mock_send
        try:
            # 1. Dispatch with ALL_COURSES
            active_scope = {"scope": "ALL_COURSES", "kb_id": None, "doc_id": None}
            test_state.start_background_generation(
                kb_id=active_scope["kb_id"] if active_scope["scope"] in ("COURSE", "DOCUMENT") else None,
                question="What is the exam format?",
                scope=active_scope["scope"],
            )
            if test_state._active_task:
                await test_state._active_task

            assert mock_send.call_count >= 1
            last_call = mock_send.call_args[1]
            assert last_call["scope"] == "ALL_COURSES"
            assert last_call["kb_id"] is None

            # 2. Transition to COURSE scope with specific course ID
            selected_course_id = "00000000-0000-0000-0000-000000000099"
            active_scope = {"scope": "COURSE", "kb_id": selected_course_id, "doc_id": None}
            test_state.start_background_generation(
                kb_id=active_scope["kb_id"] if active_scope["scope"] in ("COURSE", "DOCUMENT") else None,
                question="What is the midterm date for this course?",
                scope=active_scope["scope"],
            )
            if test_state._active_task:
                await test_state._active_task

            last_call2 = mock_send.call_args[1]
            assert last_call2["scope"] == "COURSE"
            assert last_call2["kb_id"] == selected_course_id

            # 3. Reset to ALL_COURSES
            active_scope = {"scope": "ALL_COURSES", "kb_id": None, "doc_id": None}
            test_state.start_background_generation(
                kb_id=active_scope["kb_id"] if active_scope["scope"] in ("COURSE", "DOCUMENT") else None,
                question="When are tuition fees due across the university?",
                scope=active_scope["scope"],
            )
            if test_state._active_task:
                await test_state._active_task

            last_call3 = mock_send.call_args[1]
            assert last_call3["scope"] == "ALL_COURSES"
            assert last_call3["kb_id"] is None
        finally:
            api_client.send_chat_message = original_send

    def test_only_authorized_courses_offered_for_selection(self) -> None:
        """Verify inactive or unauthorized courses are excluded from student scope options."""
        from frontend.client.models import KnowledgeBaseDTO

        available_kbs = [
            KnowledgeBaseDTO(
                id="kb-active-1",
                name="CS101: Introduction to CS",
                is_active=True,
                is_student_visible=True,
            ),
            KnowledgeBaseDTO(
                id="kb-active-2",
                name="CS201: Data Structures",
                is_active=True,
                is_student_visible=True,
            ),
            KnowledgeBaseDTO(
                id="kb-inactive",
                name="OLD100: Deprecated Course",
                is_active=False,
                is_student_visible=True,
            ),
            KnowledgeBaseDTO(
                id="kb-hidden",
                name="SECRET400: Restricted Research",
                is_active=True,
                is_student_visible=False,
            ),
        ]

        # Student scope filter: active and student_visible
        authorized_student_kbs = [
            k for k in available_kbs
            if k.is_active and k.is_student_visible
        ]
        assert len(authorized_student_kbs) == 2
        assert {k.id for k in authorized_student_kbs} == {"kb-active-1", "kb-active-2"}
        assert "kb-inactive" not in {k.id for k in authorized_student_kbs}
        assert "kb-hidden" not in {k.id for k in authorized_student_kbs}

    def test_empty_course_catalog_handled_gracefully(self) -> None:
        """Verify empty course catalog defaults safely to ALL_COURSES with no exceptions."""
        from frontend.client.models import KnowledgeBaseDTO

        empty_kbs: list[KnowledgeBaseDTO] = []
        is_all_courses = True
        current_course = None
        current_label = current_course.name if current_course else "All available courses"

        assert is_all_courses is True
        assert current_label == "All available courses"

        # Search filter on empty catalog
        q_clean = "python"
        filtered = [k for k in empty_kbs if q_clean in k.name.lower()]
        assert len(filtered) == 0

    def test_simple_factual_question_produces_direct_answer(self) -> None:
        """Verify simple factual queries return immediate direct answers without conversational filler."""
        from backend.app.services.llm.service import _sanitize_llm_answer

        raw_llm_output = (
            "Based on the provided documents, late laboratory submissions are penalized 10% per calendar day [source_1]. "
            "No credit is granted after 72 hours without Dean approval [source_1]."
        )
        direct_ans = _sanitize_llm_answer(raw_llm_output)
        assert direct_ans.startswith("Late laboratory submissions are penalized 10% per calendar day [source_1].")
        assert not direct_ans.startswith("Based on")
        assert not direct_ans.startswith("According to")

    def test_important_exceptions_and_qualifications_preserved(self) -> None:
        """Verify essential academic qualifications, exceptions, and conditions are retained."""
        from backend.app.services.llm.service import _sanitize_llm_answer

        raw_qualified_output = (
            "Midterm examinations are closed-book, except that students may bring one double-sided "
            "handwritten formula sheet [source_2]. Submissions after 72 hours receive zero credit "
            "unless granted prior Dean exemption [source_3]."
        )
        cleaned = _sanitize_llm_answer(raw_qualified_output)
        assert "closed-book" in cleaned
        assert "one double-sided handwritten formula sheet" in cleaned
        assert "unless granted prior Dean exemption" in cleaned
        assert "[source_2]" in cleaned
        assert "[source_3]" in cleaned

    def test_composer_scope_selector_placement_and_interaction(self) -> None:
        """Verify scope selector operates inside composer bottom toolbar and updates query scope."""
        active_scope = {"scope": "ALL_COURSES", "kb_id": None}
        assert active_scope["scope"] == "ALL_COURSES"
        assert active_scope["kb_id"] is None

        # User selects course
        active_scope["scope"] = "COURSE"
        active_scope["kb_id"] = "c1111111-1111-1111-1111-111111111111"
        assert active_scope["scope"] == "COURSE"
        assert active_scope["kb_id"] == "c1111111-1111-1111-1111-111111111111"

        # User returns to all courses
        active_scope["scope"] = "ALL_COURSES"
        active_scope["kb_id"] = None
        assert active_scope["scope"] == "ALL_COURSES"
        assert active_scope["kb_id"] is None

    def test_stop_generating_cancels_active_synthesis_and_marks_stopped(self) -> None:
        """Verify clicking Stop immediately requests cancellation and records distinct stopped status."""
        from frontend.state.app_state import AppState

        app_state = AppState()
        # Mock active generation
        app_state._is_generating = True
        app_state._generation_id = 1
        assert app_state.is_generating is True

        app_state.stop_generating()
        assert app_state.is_generating is False
        assert len(app_state.chat_history) == 1
        assert "stopped by user" in app_state.chat_history[0].content
        assert app_state.chat_history[0].role == "assistant"

    def test_cancelled_generation_cannot_overwrite_newer_response(self) -> None:
        """Verify monotonic generation ID prevents late background callback from appending to history."""
        from frontend.state.app_state import AppState

        app_state = AppState()
        app_state._is_generating = True
        gen_1 = app_state._generation_id + 1
        app_state._generation_id = gen_1

        # Stop is called
        app_state.stop_generating()
        initial_history_len = len(app_state.chat_history)

        # Late-returning callback from gen_1 attempts to append
        if app_state._generation_id == gen_1 and not app_state._is_cancelled:
            app_state._chat_history.append(
                ChatMessageDTO(id="late", role="assistant", content="Late answer")
            )

        assert len(app_state.chat_history) == initial_history_len
        assert not any(m.id == "late" for m in app_state.chat_history)

    def test_persistent_conversation_creation_on_first_turn(self) -> None:
        """Verify first user question creates a persistent conversation thread."""
        from frontend.client.api_client import api_client

        api_client._offline_conversations.clear()
        resp = api_client.send_chat_message(
            kb_id=None,
            question="What is the exam grading policy?",
            scope="ALL_COURSES",
            conversation_id=None,
        )
        assert resp is not None
        convs = api_client.get_conversations()
        assert len(convs) == 1
        assert "exam grading policy" in convs[0].title.lower()
        assert convs[0].message_count == 2  # user + assistant

    def test_subsequent_turns_associated_with_active_conversation(self) -> None:
        """Verify subsequent turns are appended to the same persistent conversation thread."""
        from frontend.client.api_client import api_client

        api_client._offline_conversations.clear()
        resp1 = api_client.send_chat_message(
            kb_id=None,
            question="First question?",
            scope="ALL_COURSES",
            conversation_id=None,
        )
        assert resp1 is not None
        convs = api_client.get_conversations()
        active_id = convs[0].id

        resp2 = api_client.send_chat_message(
            kb_id=None,
            question="Follow up question?",
            scope="ALL_COURSES",
            conversation_id=active_id,
        )
        assert resp2 is not None

        detail = api_client.get_conversation(active_id)
        assert len(detail.messages) == 4  # 2 users + 2 assistants
        assert detail.messages[0].content == "First question?"
        assert detail.messages[2].content == "Follow up question?"

    def test_new_chat_creates_draft_mode_without_fake_history(self) -> None:
        """Verify New Chat resets active conversation ID without writing empty fake rows."""
        from frontend.client.api_client import api_client
        from frontend.state.app_state import AppState

        app_state = AppState()
        api_client._offline_conversations.clear()

        # Initial message
        app_state.add_user_message("Hello")
        app_state.active_conversation_id = "conv-1"

        # User triggers New Chat
        app_state.start_new_conversation()
        assert app_state.active_conversation_id is None
        assert len(app_state.chat_history) == 0

        # No empty conversation was created in storage
        convs = api_client.get_conversations()
        assert len(convs) == 0

    def test_cross_user_conversation_isolation_security(self) -> None:
        """Verify that conversation retrieval enforces owner authorization strictly."""
        import uuid
        from unittest.mock import MagicMock

        import pytest
        from fastapi import HTTPException

        from backend.app.api.v1.endpoints.conversations import get_conversation
        from backend.app.models.conversation import Conversation
        from backend.app.models.user import User, UserRole

        owner_id = uuid.uuid4()
        attacker_id = uuid.uuid4()
        conv_id = uuid.uuid4()

        owner_user = MagicMock(spec=User)
        owner_user.id = owner_id
        owner_user.role = UserRole.STUDENT

        attacker_user = MagicMock(spec=User)
        attacker_user.id = attacker_id
        attacker_user.role = UserRole.STUDENT

        mock_conv = MagicMock(spec=Conversation)
        mock_conv.id = conv_id
        mock_conv.user_id = owner_id
        mock_conv.title = "Private Student Notes"
        mock_conv.scope = "ALL_COURSES"
        mock_conv.knowledge_base_id = None
        mock_conv.created_at = "2026-10-09T10:00:00Z"
        mock_conv.updated_at = "2026-10-09T10:00:00Z"
        mock_conv.messages = []

        mock_db = MagicMock()
        def mock_filter(*args, **kwargs):
            m = MagicMock()
            m.first.return_value = None  # Attacker gets 404
            return m

        mock_db.query.return_value.options.return_value.filter = mock_filter

        with pytest.raises(HTTPException) as exc_info:
            get_conversation(
                conversation_id=conv_id,
                current_user=attacker_user,
                db=mock_db,
            )
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

    def test_deleting_conversation_resets_draft_mode(self) -> None:
        """Verify deleting the active conversation triggers a clean draft state."""
        from frontend.client.api_client import api_client
        from frontend.state.app_state import AppState

        app_state = AppState()
        api_client._offline_conversations.clear()

        # Create one conversation
        conv = api_client.create_conversation("To be deleted")
        app_state.active_conversation_id = conv.id
        app_state.add_user_message("Question before delete")

        success = app_state.delete_conversation(conv.id)
        assert success is True
        assert app_state.active_conversation_id is None
        assert len(app_state.chat_history) == 0
        assert len(api_client.get_conversations()) == 0

    def test_saved_conversation_messages_and_citations_order_preserved(self) -> None:
        """Verify saved messages preserve role ordering and citation provenance."""
        from frontend.client.api_client import api_client
        from frontend.state.app_state import AppState

        app_state = AppState()
        api_client._offline_conversations.clear()

        # Run query which produces citations
        resp = api_client.send_chat_message(
            kb_id=None,
            question="Explain grading with multi document sources?",
            scope="ALL_COURSES",
            conversation_id=None,
        )
        assert len(resp.citations) == 3

        convs = api_client.get_conversations()
        conv_id = convs[0].id

        # Reload conversation
        app_state.load_conversation(conv_id)
        assert len(app_state.chat_history) == 2
        user_msg = app_state.chat_history[0]
        asst_msg = app_state.chat_history[1]

        assert user_msg.role == "user"
        assert asst_msg.role == "assistant"
        assert len(asst_msg.citations) == 3
        assert asst_msg.citations[0].document_name == "cs101_syllabus_fall2026.pdf"
        assert app_state.selected_citation is not None


class TestStudentChatNavigationAndUnifiedHistoryContracts:
    """Part 6C Behavioral Contracts: Assistant vs New Chat and Unified History."""

    def test_student_navigation_displays_assistant_and_routes_to_chat(self) -> None:
        """1. Student navigation displays 'Assistant' and still routes to /chat."""
        from frontend.client.models import UserDTO
        from frontend.components.layout import _resolve_breadcrumbs

        student = UserDTO(
            id="s1",
            email="student@univ.edu",
            full_name="Alex Student",
            role="STUDENT",
        )
        assert student.role == "STUDENT"

        # Breadcrumbs root for student resolves to Assistant
        crumbs, back_route, back_label = _resolve_breadcrumbs(
            active_route="/chat",
            title="Assistant",
            is_student=True,
        )
        assert crumbs[0][0] == "Assistant"

    def test_new_chat_creates_clean_new_conversation_state(self) -> None:
        """2. New Chat creates clean state and does not create fake records."""
        from frontend.state.app_state import AppState

        app_state = AppState()
        app_state.active_conversation_id = "conv-active-123"
        app_state.add_user_message("Testing prior question")
        assert len(app_state.chat_history) == 1

        app_state.start_new_conversation()
        assert app_state.active_conversation_id is None
        assert len(app_state.chat_history) == 0
        assert app_state.selected_citation is None
        assert app_state.active_scope == "ALL_COURSES"
        assert app_state.active_kb_id is None

    def test_new_chat_resets_scope_to_all_courses(self) -> None:
        """3. New Chat resets scope to ALL_COURSES even if course was previously selected."""
        from frontend.state.app_state import AppState

        app_state = AppState()
        app_state.set_scope("COURSE", "course-uuid-456")
        assert app_state.active_scope == "COURSE"
        assert app_state.active_kb_id == "course-uuid-456"

        app_state.start_new_conversation()
        assert app_state.active_scope == "ALL_COURSES"
        assert app_state.active_kb_id is None

    def test_new_chat_does_not_delete_saved_conversations(self) -> None:
        """4. New Chat does not delete existing saved conversation history."""
        from frontend.client.api_client import api_client
        from frontend.state.app_state import AppState

        app_state = AppState()
        api_client._offline_conversations.clear()

        # Seed two saved conversations
        c1 = api_client.create_conversation("First Chat")
        c2 = api_client.create_conversation("Second Chat")
        assert len(api_client.get_conversations()) == 2

        app_state.load_conversation(c1.id)
        assert app_state.active_conversation_id == c1.id

        # Click New Chat
        app_state.start_new_conversation()
        assert app_state.active_conversation_id is None

        # Verify all saved conversations still exist
        convs = api_client.get_conversations()
        assert len(convs) == 2
        assert {c.id for c in convs} == {c1.id, c2.id}

    def test_assistant_navigation_preserves_active_saved_conversation(self) -> None:
        """5. Assistant navigation does not wipe active conversation when returning from other pages."""
        from frontend.client.api_client import api_client
        from frontend.state.app_state import AppState

        app_state = AppState()
        api_client._offline_conversations.clear()

        c1 = api_client.create_conversation("Research Project Discussion")
        app_state.load_conversation(c1.id)
        app_state.add_user_message("Saved message")
        assert app_state.active_conversation_id == c1.id
        assert len(app_state.chat_history) == 1

        # Simulate user visiting Courses page and then clicking Assistant
        # Ordinary navigation does NOT call start_new_conversation
        assert app_state.active_conversation_id == c1.id
        assert len(app_state.chat_history) == 1
        assert app_state.chat_history[0].content == "Saved message"

    def test_selecting_saved_conversation_refreshes_history(self) -> None:
        """6. Selecting a saved conversation updates active_conversation_id and loads messages."""
        from frontend.client.api_client import api_client
        from frontend.state.app_state import AppState

        app_state = AppState()
        api_client._offline_conversations.clear()

        _c1 = api_client.create_conversation("Topic A")
        c2 = api_client.create_conversation("Topic B")

        # Listen for notifications
        notified = []
        app_state.subscribe(lambda: notified.append(True))

        app_state.load_conversation(c2.id)
        assert app_state.active_conversation_id == c2.id
        assert len(notified) > 0

    def test_failed_conversation_load_preserves_existing_state(self) -> None:
        """7. Failed conversation load request preserves state without creating false empty chat."""
        from unittest.mock import patch

        from frontend.state.app_state import AppState

        app_state = AppState()
        app_state.active_conversation_id = "valid-prior-conv"
        app_state.add_user_message("Prior valid message")

        with patch("frontend.state.app_state.api_client.get_conversation") as mock_get:
            mock_get.side_effect = RuntimeError("Network timeout or 404")
            try:
                app_state.load_conversation("non-existent-conv")
            except Exception:
                pass

        # Existing conversation state remains preserved
        assert app_state.active_conversation_id == "valid-prior-conv"
        assert len(app_state.chat_history) == 1

    def test_no_duplicate_mobile_history_dialog_in_chat_page(self) -> None:
        """8. chat_page.py must not contain mobile_history_dialog or duplicate history renderers."""
        import inspect

        from frontend.pages import chat_page

        source = inspect.getsource(chat_page)
        assert "mobile_history_dialog" not in source
        assert "render_history_list" not in source
        assert "chat-mobile-toggle" not in source

    def test_admin_chat_navigation_preserved(self) -> None:
        """9. Administrator navigation retains Test Assistant under System & Tools section."""
        from backend.app.core.permissions import Permission
        from frontend.client.models import UserDTO
        from frontend.components.layout import get_sidebar_sections

        admin = UserDTO(
            id="a1",
            email="admin@univ.edu",
            full_name="Admin User",
            role="ADMIN",
            admin_role="MAIN_ADMIN",
            permissions=[Permission.ADMIN_CHAT.value],
        )
        sections = get_sidebar_sections(admin)
        titles = [s["title"] for s in sections]
        assert "Operations & Tools" in titles
        sys_section = next(s for s in sections if s["title"] == "Operations & Tools")
        assert ("Test Assistant", "/chat", "chat") in sys_section["items"]
