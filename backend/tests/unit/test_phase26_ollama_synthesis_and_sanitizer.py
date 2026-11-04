"""
Phase 26 Unit Tests: Genuine, Detailed Ollama-Grounded Synthesis & Conservative Sanitizer.

Verifies the 7 Golden Test Scenarios mandated by Phase 26 Master Prompt:
- Test 1: 'What is Flutter?' invokes Ollama, explains naturally, cites evidence, truthful metadata.
- Test 2: 'What is a Flutter widget?' invokes Ollama, explains concept without Python canned text.
- Test 3: 'List the Flutter widget concepts mentioned in my notes' produces a clean list without iPhone drift.
- Test 4: Unrelated query with Flutter-only scope produces truthful out-of-scope refusal without fake citations.
- Test 5: Provider failure triggers at most 1 retry and returns safe generation-failure response (no canned factual answer).
- Test 6: Sanitizer integrity rejects 'The definition of Flutter is provided in.' as invalid and preserves valid Markdown.
- Test 7: Proves no hidden canned-answer path for Act title, Android versions, iOS devices, Flutter definition, Flutter widgets.
"""

import uuid
from unittest.mock import AsyncMock

import pytest

from backend.app.schemas.context_assembly import (
    ContextAssemblyResult,
    ContextItem,
)
from backend.app.schemas.llm import (
    LLMGenerationRequest,
    LLMProviderResponse,
)
from backend.app.services.llm.base import BaseLLMProvider
from backend.app.services.llm.exceptions import LLMResponseError, LLMTimeoutError
from backend.app.services.llm.prompt_builder import (
    GroundedPromptBuilder,
    _response_format_directive,
    response_format_for_query,
)
from backend.app.services.llm.service import (
    LLMGenerationService,
    _sanitize_llm_answer,
    extract_grounded_recovery_answer,
    is_invalid_or_incomplete_answer,
)


class MockConfigurableProvider(BaseLLMProvider):
    """Configurable mock provider that records call count and returns preset responses."""

    def __init__(self, responses: list[str] | str = "Default factual response [source_1].") -> None:
        if isinstance(responses, str):
            self._responses = [responses]
        else:
            self._responses = list(responses)
        self.call_count = 0
        self.invoked_system_instructions: list[str] = []
        self.invoked_user_prompts: list[str] = []

    @property
    def provider_name(self) -> str:
        return "mock_ollama"

    @property
    def model_name(self) -> str:
        return "qwen3:4b"

    async def generate(
        self,
        system_instruction: str,
        user_prompt: str,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        timeout_seconds: float | None = None,
        **kwargs,
    ) -> LLMProviderResponse:
        self.call_count += 1
        self.invoked_system_instructions.append(system_instruction)
        self.invoked_user_prompts.append(user_prompt)

        # Return next response or repeat last
        idx = min(self.call_count - 1, len(self._responses) - 1)
        resp_text = self._responses[idx]
        return LLMProviderResponse(
            content=resp_text,
            model=self.model_name,
            prompt_tokens=100,
            output_tokens=len(resp_text.split()),
            total_duration_ms=85.0,
            safe_metadata={"eval_duration_ms": 70.0},
        )


def make_flutter_item(source_id: str, text: str, page_number: int = 18) -> ContextItem:
    return ContextItem(
        source_id=source_id,
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_title="1-Flutter-Intro.pdf",
        chunk_index=0,
        text=text,
        page_number=page_number,
        section_title="Introduction",
        chunk_metadata={},
        reranker_rank=1,
        reranker_score=0.92,
        rrf_score=0.035,
        estimated_tokens=60,
    )


class TestPhase26GroundedSynthesis:
    """Verifies that normal academic Q&A uses genuine, detailed LLM synthesis."""

    @pytest.mark.asyncio
    async def test_golden_1_what_is_flutter(self) -> None:
        """Test 1: 'What is Flutter?' invokes Ollama, explains naturally, cites evidence, truthful metadata."""
        flutter_evidence = (
            "What is Flutter?\n"
            "- Flutter is an app SDK for building high-performance, high-fidelity apps for iOS, Android, "
            "and web from a single codebase.\n"
            "- Single Code base Means We have to write code and app will be run on six platforms: iOS, Android, "
            "the web, Windows, MacOS, and Linux.\n"
            "- The goal is to enable developers to deliver high-performance apps that feel natural on different platforms."
        )
        item = make_flutter_item("source_1", flutter_evidence, page_number=18)
        context = ContextAssemblyResult(
            query="What is Flutter?",
            original_query="What is Flutter?",
            items=[item],
            total_items=1,
            total_estimated_tokens=60,
            token_budget=1000,
            candidates_received=1,
            items_skipped_budget=0,
            items_deduplicated=0,
        )

        model_response = (
            "Flutter is an open-source application software development kit (SDK) designed for creating "
            "high-performance, high-fidelity applications across multiple platforms from a single codebase [source_1]. "
            "By writing code once, developers can deploy applications across six distinct targets: iOS, Android, "
            "the web, Windows, macOS, and Linux [source_1]. The primary goal of Flutter is to empower developers "
            "to deliver high-performance applications that feel natural and responsive on each native platform."
        )
        provider = MockConfigurableProvider(model_response)
        service = LLMGenerationService(provider=provider)

        req = LLMGenerationRequest(query="What is Flutter?", context=context)
        resp = await service.generate_grounded_answer(req)

        # 1. Ollama provider was actually invoked
        assert provider.call_count == 1
        assert resp.metadata["llm_invoked"] is True
        assert resp.metadata["generation_mode"] == "primary_llm"
        assert resp.provider == "mock_ollama"
        assert resp.model == "qwen3:4b"

        # 2. Answer begins with direct definition, not filler opening
        assert resp.answer.startswith("Flutter is an open-source application software development kit")
        assert not resp.answer.startswith("The definition of Flutter is provided in")
        assert not resp.answer.startswith("The source says")
        assert not resp.answer.startswith("According to the document")

        # 3. Model explains in natural prose connecting supported details
        assert "single codebase" in resp.answer
        assert "iOS, Android" in resp.answer
        assert "Windows, macOS, and Linux" in resp.answer
        assert "[source_1]" in resp.answer
        assert resp.sources_referenced == ["source_1"]

    @pytest.mark.asyncio
    async def test_golden_2_what_is_a_flutter_widget(self) -> None:
        """Test 2: 'What is a Flutter widget?' invokes Ollama; no hard-coded Flutter widget answer in Python."""
        widget_evidence = (
            "Everything is a Widget\n"
            "- In the flutter app in the UI part, everything is a widget. Even the app itself is a widget!.\n"
            "- If you are familiar with Android and IOS development, widgets are like views in android and UIViews in IOS.\n"
            "- Flutter has a consistent, unified object model that is a widget."
        )
        item = make_flutter_item("source_1", widget_evidence, page_number=34)
        context = ContextAssemblyResult(
            query="What is a Flutter widget?",
            original_query="What is a Flutter widget?",
            items=[item],
            total_items=1,
            total_estimated_tokens=50,
            token_budget=1000,
            candidates_received=1,
            items_skipped_budget=0,
            items_deduplicated=0,
        )

        model_response = (
            "In Flutter, a widget represents the core structural building block of the user interface, where "
            "'everything is a widget'—including layout elements, styling, and even the application itself [source_1]. "
            "Flutter utilizes a consistent, unified object model based on widgets. For developers familiar with "
            "native mobile engineering, widgets serve an analogous purpose to Views in Android and UIViews in iOS."
        )
        provider = MockConfigurableProvider(model_response)
        service = LLMGenerationService(provider=provider)

        req = LLMGenerationRequest(query="What is a Flutter widget?", context=context)
        resp = await service.generate_grounded_answer(req)

        # 1. Provider invoked and returned answer
        assert provider.call_count == 1
        assert resp.metadata["llm_invoked"] is True
        assert resp.metadata["generation_mode"] == "primary_llm"

        # 2. Does NOT contain hardcoded Material/Cupertino categories if not in evidence
        # and does not inject the canned note from Python
        assert "Note: The course notes introduce these core concepts" not in resp.answer
        assert "Everything is a Widget" in resp.answer or "everything is a widget" in resp.answer.lower()
        assert "Views in Android" in resp.answer
        assert "UIViews in iOS" in resp.answer

    @pytest.mark.asyncio
    async def test_golden_3_list_flutter_widget_concepts(self) -> None:
        """Test 3: 'List the Flutter widget concepts mentioned in my notes' produces clean list without iPhone drift."""
        widget_evidence = (
            "Everything is a Widget\n"
            "- In the flutter app in the UI part, everything is a widget. Even the app itself is a widget!.\n"
            "- If you are familiar with Android and IOS development, widgets are like views in android and UIViews in IOS.\n"
            "- Flutter has a consistent, unified object model that is a widget."
        )
        item = make_flutter_item("source_1", widget_evidence, page_number=34)
        context = ContextAssemblyResult(
            query="List the Flutter widget concepts mentioned in my notes",
            original_query="List the Flutter widget concepts mentioned in my notes",
            items=[item],
            total_items=1,
            total_estimated_tokens=50,
            token_budget=1000,
            candidates_received=1,
            items_skipped_budget=0,
            items_deduplicated=0,
        )

        model_response = (
            "The core widget concepts documented in the lecture notes include [source_1]:\n\n"
            "- Everything is a widget (including layouts and the app itself)\n"
            "- Unified object model across the entire UI framework\n"
            "- Analogous structural role to Android Views and iOS UIViews"
        )
        provider = MockConfigurableProvider(model_response)
        service = LLMGenerationService(provider=provider)

        req = LLMGenerationRequest(query="List the Flutter widget concepts mentioned in my notes", context=context)
        resp = await service.generate_grounded_answer(req)

        assert provider.call_count == 1
        assert resp.metadata["llm_invoked"] is True
        assert "iPhone" not in resp.answer
        assert "- Everything is a widget" in resp.answer
        assert "Android Views" in resp.answer

    @pytest.mark.asyncio
    async def test_golden_4_unrelated_query_out_of_scope_refusal(self) -> None:
        """Test 4: Unrelated query with Flutter-only scope returns out-of-scope refusal without fake citations."""
        # Unrelated query chunk with negative reranker score
        item = make_flutter_item("source_1", "Akash Technolabs Flutter notes", page_number=1)
        item.reranker_score = -9.8  # Below calibrated threshold (-8.5)
        context = ContextAssemblyResult(
            query="Explain the evolution of Earth",
            original_query="Explain the evolution of Earth",
            items=[item],
            total_items=1,
            total_estimated_tokens=20,
            token_budget=1000,
            candidates_received=1,
            items_skipped_budget=0,
            items_deduplicated=0,
        )

        provider = MockConfigurableProvider("Earth evolved over billions of years.")
        service = LLMGenerationService(provider=provider)

        req = LLMGenerationRequest(query="Explain the evolution of Earth", context=context)
        resp = await service.generate_grounded_answer(req)

        # Provider must NOT be invoked on negative relevance
        assert provider.call_count == 0
        assert resp.metadata["llm_invoked"] is False
        assert resp.metadata["generation_mode"] == "insufficient_evidence_refusal"
        assert resp.sources_referenced == []
        assert "authorized course materials" in resp.answer

    @pytest.mark.asyncio
    async def test_golden_5_provider_failure_bounded_retry(self) -> None:
        """Test 5: Provider failure triggers at most 1 retry and returns safe failure response (no canned factual answer)."""
        item = make_flutter_item("source_1", "Some content.", page_number=18)
        context = ContextAssemblyResult(
            query="What is Flutter?",
            original_query="What is Flutter?",
            items=[item],
            total_items=1,
            total_estimated_tokens=20,
            token_budget=1000,
            candidates_received=1,
            items_skipped_budget=0,
            items_deduplicated=0,
        )

        provider = MockConfigurableProvider()
        # First call returns invalid fragment, retry call raises response error
        provider.generate = AsyncMock(side_effect=[
            LLMProviderResponse(content="The definition of Flutter is provided in.", model="qwen3:4b"),
            LLMResponseError("Ollama failed to generate valid JSON"),
        ])
        service = LLMGenerationService(provider=provider)

        req = LLMGenerationRequest(query="What is Flutter?", context=context)
        resp = await service.generate_grounded_answer(req)

        # At most 2 provider calls (1 primary + 1 retry)
        assert provider.generate.call_count == 2
        assert resp.metadata["llm_invoked"] is True
        assert resp.metadata["generation_mode"] == "generation_failed"
        # Does NOT return canned Python factual answer!
        assert "Google's UI toolkit" not in resp.answer
        assert "Material Design widgets" not in resp.answer
        assert "could not synthesize" in resp.answer.lower()

    def test_golden_6_sanitizer_integrity(self) -> None:
        """Test 6: Sanitizer integrity rejects 'The definition of Flutter is provided in.' and preserves Markdown."""
        # 1. The exact bad fragment is flagged as invalid/incomplete
        bad_fragment = "The definition of Flutter is provided in."
        assert is_invalid_or_incomplete_answer(bad_fragment, "What is Flutter?") is True

        another_bad = "The answer is given in [source_1]."
        assert is_invalid_or_incomplete_answer(another_bad, "What is Flutter?") is True

        # 2. Valid educational paragraphs remain intact
        valid_prose = (
            "Flutter is an app SDK for building high-performance apps from a single codebase [source_1]. "
            "It targets mobile, web, and desktop platforms."
        )
        cleaned = _sanitize_llm_answer(valid_prose, query="What is Flutter?")
        assert cleaned == valid_prose
        assert is_invalid_or_incomplete_answer(cleaned, "What is Flutter?") is False

        # 3. Code blocks, tables, lists, and headings remain intact
        markdown_content = (
            "# Flutter Overview\n\n"
            "Flutter is a cross-platform framework [source_1].\n\n"
            "```dart\n"
            "void main() => runApp(MyApp());\n"
            "```\n\n"
            "| Platform | Supported |\n"
            "| --- | --- |\n"
            "| Android | Yes |\n"
            "| iOS | Yes |\n\n"
            "- Fast development with Hot Reload [source_1]\n"
            "- Expressive and flexible UI"
        )
        cleaned_md = _sanitize_llm_answer(markdown_content)
        assert "# Flutter Overview" in cleaned_md
        assert "```dart\nvoid main() => runApp(MyApp());\n```" in cleaned_md
        assert "| Platform | Supported |" in cleaned_md
        assert "- Fast development with Hot Reload [source_1]" in cleaned_md

    @pytest.mark.asyncio
    async def test_golden_7_prove_no_hidden_canned_answer_path(self) -> None:
        """Test 7: For factual queries (Act title, Android versions, iOS devices, Flutter definition, Flutter widgets):
        - Provider is called.
        - Answer comes from provider output after safe sanitization.
        - No domain-specific Python-generated answer replaces provider result.
        """
        queries_and_responses = [
            (
                "What is the Act title?",
                "The Act is titled the Kaushalya Skill University Act [source_1].",
            ),
            (
                "List the Android versions",
                "The Android versions mentioned are [source_1]:\n- Android 10\n- Android 11\n- Android 12",
            ),
            (
                "List the supported iPhone devices",
                "Supported devices include [source_1]:\n- iPhone 12\n- iPhone 13\n- iPhone 14",
            ),
            (
                "What is Flutter?",
                "Flutter is Google's UI toolkit for multi-platform apps [source_1].",
            ),
            (
                "What is a Flutter widget?",
                "Widgets are the basic building blocks in Flutter [source_1].",
            ),
        ]

        for query, model_text in queries_and_responses:
            item = make_flutter_item("source_1", f"Sample evidence for {query}", page_number=1)
            context = ContextAssemblyResult(
                query=query,
                original_query=query,
                items=[item],
                total_items=1,
                total_estimated_tokens=30,
                token_budget=1000,
                candidates_received=1,
                items_skipped_budget=0,
                items_deduplicated=0,
            )

            provider = MockConfigurableProvider(model_text)
            service = LLMGenerationService(provider=provider)

            req = LLMGenerationRequest(query=query, context=context)
            resp = await service.generate_grounded_answer(req)

            # Provider was invoked
            assert provider.call_count == 1, f"Provider not called for query: {query}"
            assert resp.metadata["llm_invoked"] is True
            assert resp.metadata["generation_mode"] == "primary_llm"

            # Answer comes from the provider output after safe sanitization, NOT a hard-coded Python template
            expected_core = model_text.splitlines()[0]
            assert expected_core.rstrip(":") in resp.answer
            assert "The Act is titled the **" not in resp.answer
            assert "The course materials highlight two primary widget categories" not in resp.answer

            # Confirm extract_grounded_recovery_answer returns None
            assert extract_grounded_recovery_answer(query, context) is None

    def test_prompt_builder_has_no_topic_specific_directives(self) -> None:
        """Verify that prompt builder contains only neutral formatting guidelines without topic facts."""
        # 1. Widget query produces general 'list' or 'explanation' directive, not hardcoded Flutter categories
        widget_directive = _response_format_directive("What is a widget?")
        assert "Material Design widgets for Google style" not in widget_directive
        assert "Cupertino widgets for iOS style" not in widget_directive
        assert "EXPLANATION FORMAT:" in widget_directive

        list_directive = _response_format_directive("List the widgets")
        assert "Material Design widgets" not in list_directive
        assert "LIST FORMAT:" in list_directive
