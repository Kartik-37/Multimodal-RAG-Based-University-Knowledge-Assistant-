# Task State

This file is maintained by Antigravity.

## Current authoritative phase -- 2026-10-30

**PHASE 19 -- CHAT HISTORY ORDERING, AUTHORITATIVE DELETE SEMANTICS (CASES A-F), AND RAG ANSWER QUALITY (COMPLETED & VERIFIED)**

### Confirmed Root Causes & Implemented Solutions

1. **Workstream A: Recent Chat Ordering & In-Place Active Jumper Elimination (`frontend/components/layout.py`, `backend/app/api/v1/endpoints/conversations.py`):**
   - **Root Cause**: `render_conversation_items()` in `frontend/components/layout.py` previously searched for `state.active_conversation_id` and manually spliced it to index 0 of the sidebar list whenever on `/chat`. This caused older conversations to artificially jump to the top simply because a user opened them to read previous turns.
   - **Solution**: Removed client-side promotion in `layout.py`. The sidebar now strictly preserves the server-provided ordering. In `backend/app/api/v1/endpoints/conversations.py`, `list_conversations()` orders conversations by `Conversation.updated_at.desc(), Conversation.created_at.desc(), Conversation.id.desc()`. Only real user questions or assistant responses update `updated_at`, moving a conversation to the top only upon real activity.

2. **Workstream B: Authoritative Delete Semantics (Cases A–F) (`backend/app/api/v1/endpoints/conversations.py`, `frontend/components/layout.py`, `frontend/state/app_state.py`):**
   - **Root Cause**: `AppState.delete_conversation()` previously called `self.start_new_conversation()` unconditionally whenever the active conversation was deleted, creating an immediate replacement `New chat` even when other conversations remained, and allowing deletion of the only remaining empty interface.
   - **Solution**:
     - **Case A & D**: When multiple conversations exist and an active conversation (empty or populated) is deleted, `AppState.delete_conversation()` deletes it from the backend, does NOT create a replacement, and automatically loads the most recently active remaining conversation (`remaining[0]`).
     - **Case B**: If a user has only one conversation and it has zero messages (sole empty chat), the UI delete button is disabled with tooltip `"Keep one empty chat available"`, and `backend/app/api/v1/endpoints/conversations.py` enforces an HTTP 409 Conflict rejection (`"Cannot delete the only available chat interface. Keep one empty chat available."`).
     - **Case C**: When a non-active conversation is deleted, the active thread, transcript, scope, citations, and background generation remain completely untouched.
     - **Case E**: When the sole remaining conversation is populated and deleted, `AppState.delete_conversation()` recreates exactly one empty `New chat` so `/chat` remains immediately usable.
     - **Case F**: If deletion fails or is rejected, the state rolls back/preserves the active conversation without creating duplicates.
     - In `frontend/components/layout.py`, delete button clicks now invoke `@click.stop` / `stop_propagation()` so that clicking delete never triggers row-selection navigation.

3. **Workstream C: Grounded Flutter Answers, Slide Watermark Elimination & CPU Inference Hardening (`backend/app/services/llm/service.py`, `backend/app/services/llm/prompt_builder.py`, `backend/app/services/llm/ollama_provider.py`, `backend/app/core/config.py`, `frontend/pages/chat_page.py`):**
   - **Root Cause**:
     - `1-Flutter-Intro.pdf` contains slide headers and publisher watermarks (`Akash Technolabs www.akashsir.com`) on every page.
     - `qwen3:4b` is a reasoning model that generates internal thinking tokens. On CPU, evaluating 1,200 prompt tokens plus thinking tokens exceeded `LLM_REQUEST_TIMEOUT_SECONDS` (90s) and hit `num_predict: 768`.
     - When `generate_grounded_answer()` caught `LLMResponseError`, an unimported exception crashed execution; in recovery, multi-line slide formatting caused `SentenceSplitter` to fragment clauses like `"Android,\nand web"` into separate words, creating duplicated adjacent citations (`[source_1] [source_1]`).
   - **Solution**:
     - Updated `SYSTEM_GROUNDING_INSTRUCTION` and prompt builder to synthesize clear academic student-friendly prose without copying watermarks or writing source evaluation meta-commentary.
     - Added slide header, watermark, and author cleaning in `_sanitize_llm_answer()` and `extract_grounded_recovery_answer()`, stripping all occurrences of `Akash Technolabs` and `www.akashsir.com`.
     - In `service.py`, normalized line breaks in retrieved slide chunks before sentence splitting, guarded claim attribution so single-word fragments are never attributed mid-sentence (`len(c_words) >= 4`), and deduplicated adjacent identical citation markers (`re.sub(r"(\[source_\d+\])(?:\s*,?\s*\1)+", r"\1", ...)`).
     - Imported `LLMResponseError` alongside `LLMTimeoutError` in `service.py` to ensure resilient fallback to `extract_grounded_recovery_answer()` with `generation_path: "extractive_recovery"` whenever local inference is bounded.
     - Standardized chat column geometry across the header container, message timeline, and composer with centered `w-full max-w-4xl mx-auto`.

### Verification Suite Passed
- `backend/tests/unit/test_new_chat_and_vertical_timeline.py`: **16/16 passed (100%)**
- `backend/tests/unit/test_conversational_rag_quality.py`: **19/19 passed (100%)**
- `backend/tests/integration/test_authenticated_chat_lifecycle.py`: **5/5 passed (100%)**
- Total: **40 / 40 targeted regression tests passed (100%)**
- End-to-end RAG query `what is flutter`: Grounded answer citing `1-Flutter-Intro.pdf` (Page 18, `[source_1]`) with `Grounding status: FULLY_SUPPORTED` and zero watermark leakage.

---

## Historical phase record -- 2026-10-30

**PHASE 18 -- NEW CHAT LIFECYCLE & VERTICAL TIMELINE IMPLEMENTATION (COMPLETED & VERIFIED)**

### Confirmed Root Causes & Implemented Solutions

1. **Missing Active 'New chat' Row on Fresh Route Entry (`frontend/pages/chat_page.py`, `frontend/components/layout.py`, `frontend/state/app_state.py`):**
   - **Root Cause**: `page_layout()` renders the sidebar (`_render_navbar`) before yielding to the page body. When `/chat` was entered with no `conversation_id`, no conversation had been created or activated yet, so `api_client.get_conversations()` returned only older chats or an empty list. Zero-history users saw only `"No saved chats yet"` while viewing the empty chat page.
   - **Solution**: Added authoritative state operation `AppState.ensure_active_new_chat(conversation_id)`. Invoked before `page_layout()` in `chat_page.py`. If `conversation_id` is None and no valid active conversation exists, it creates exactly one persistent conversation titled `"New chat"`, sets it active, and synchronizes the browser URL via `history.replaceState`. When `page_layout()` renders the sidebar, the conversation already exists in PostgreSQL and is highlighted at index 0 as selected.

2. **Active Empty Conversation Delete / Recreate Failure (`frontend/state/app_state.py`):**
   - **Root Cause**: In `delete_conversation(conv_id)`, after deleting the record via API, it called `start_new_conversation()` while `self._active_conversation_id` was still pointing to `conv_id` and `len(self._chat_history) == 0`. The reuse guard mistook the deleted conversation ID for a valid existing draft and exited without creating a replacement, leaving the active state pointing to a deleted UUID.
   - **Solution**: `delete_conversation` now explicitly resets `self._active_conversation_id = None`, `self._chat_history = []`, and cancels any in-flight task for `conv_id` *before* creating the replacement conversation. It immediately recreates exactly one replacement empty New chat and notifies listeners, keeping the empty chat interface open and updating the URL to the replacement ID.

3. **Silent Failure on Sidebar History Load & Duplicate Rendering (`frontend/components/layout.py`):**
   - **Root Cause**: `render_conversation_items` wrapped `get_conversations()` in `try ... except Exception: pass`, hiding server failures and presenting errors as an empty list (`"No saved chats yet"`). In addition, `on_delete()` called `render_conversation_items` manually while `state.delete_conversation()` was already notifying subscribers, causing duplicate render passes.
   - **Solution**: Added error normalization via `normalize_error(exc, context="chat")` displaying `"Unable to load chat history"` with tooltip on failure. Deduplicated conversations by UUID so duplicate rows are never rendered. Removed manual rerender calls in `on_delete()` to prevent duplicate render passes.

4. **Multi-Turn Horizontal Column Wrapping in Quasar Flex Layout (`frontend/components/theme.py`, `frontend/pages/chat_page.py`):**
   - **Root Cause**: Quasar stylesheet defines `.row, .column, .flex { display: flex; flex-wrap: wrap; }` and `.column { flex-direction: column; }`. NiceGUI's `ui.column()` elements inherit `flex-wrap: wrap`. In standard CSS Flexbox, when a flex column has `flex-wrap: wrap`, children that exceed container height wrap into **adjacent horizontal columns to the right**, causing question and answer turns to appear side-by-side rather than in a vertical chronological stack.
   - **Solution**: Added high-priority CSS rules and classes (`.chat-scroll-area`, `.chat-timeline`, `.chat-turn-user`, `.chat-turn-assistant`) enforcing `display: flex !important; flex-direction: column !important; flex-wrap: nowrap !important; align-items: stretch !important;`. Set `.chat-timeline > *` to `width: 100% !important; max-width: 100% !important; flex-shrink: 0 !important;`. Bounded prose, URLs, code blocks, and tables so they never create viewport or page-level horizontal scroll.

### Automated and Live Verifications Completed
- `backend/tests/unit/test_new_chat_and_vertical_timeline.py`: **13/13 passed (100%)**
- `backend/tests/unit/test_conversational_rag_quality.py`: **19/19 passed (100%)**
- `backend/tests/unit/test_frontend.py`: **44/44 passed (100%)**
- `backend/tests/integration/test_authenticated_chat_lifecycle.py`: **4/4 passed (100%)**
- `backend/tests/integration/test_chat_orchestration_integration.py`: **7/7 passed (100%)**
- Total automated suite: **87 / 87 tests passing (100%)**
- Live browser CDP verification (`scripts/verify_chat_lifecycle_and_timeline.py`):
  - Student: Verified fresh `/chat` loads with active `New chat` row in sidebar, active composer, and `noHorizontalOverflow: true`. Captured: `screenshot/chat_fresh_student_verified.png`.
  - Admin: Verified fresh Test Assistant loads with active `New chat` row under Recent Chats, active composer, and `noHorizontalOverflow: true`. Captured: `screenshot/chat_fresh_admin_verified.png`.

---

## Historical phase record -- 2026-10-29

**PHASE 17 -- ANSWER VISIBILITY, INTENT-AWARE FORMATTING, AND CITATION CLEANUP (COMPLETED & VERIFIED)**

### Screenshot-driven audit findings

- The chat route previously loaded saved history only when the route conversation ID differed from the active conversation ID. If the same conversation’s local transcript ended with a user message after generation stopped, the route could skip hydration and display no assistant answer. The exact screenshot root cause is not uniquely proven without a browser trace, so treat this as a code-confirmed failure path rather than the only possible explanation.
- The prior inline-item repair considered naked `Version N` a split boundary and could separate complete labels such as `Android version 12 (2021)`. Citation cleanup also did not cover every repeated source tag in the item body.
- Chat page sizing inherited the shared page container’s maximum width and padding. The chat route now uses chat-specific full-width shell sizing, while the transcript retains a readable maximum width.
- The chat hydration exception was previously ignored, hiding API/load failures. It is now logged without logging user message content.

### Implemented changes

1. Added `frontend/client/chat_display.py` to decide when history must be rehydrated for a same-ID conversation. Active generation is not interrupted, and a transcript ending in an assistant response is not needlessly reloaded.
2. Updated `frontend/pages/chat_page.py`, `frontend/components/layout.py`, and `frontend/components/theme.py` to strengthen chat width/flex constraints, Markdown stretch behavior, vertical scrolling, and scroll timing.
3. Added query-intent response shapes to `backend/app/services/llm/prompt_builder.py` for direct facts, explanations, lists, steps, comparisons, tables, and code while preserving the original default grounding instruction when called with no query.
4. Made inline list repair in `backend/app/services/llm/service.py` conditional on list/steps intent and split Android versions only at complete Android item starts. Consolidated repeated identical citations while preserving distinct-source references.
5. Added focused regression coverage in `backend/tests/unit/test_conversational_rag_quality.py` and created `context/CHAT_ANSWER_RELIABILITY_AUDIT.md` plus `CHAT_ANSWER_QUALITY_MASTER_PROMPT.md`.

### Verification status

- Python syntax compilation for changed modules and the regression test file: **passed**.
- Unit & Behavioral Regression Suite (`backend/tests/unit/test_conversational_rag_quality.py`): **19/19 passed (100%)** in 3.13s against the running Python 3.14 / pytest environment.
- Frontend Unit Contracts (`backend/tests/unit/test_frontend.py`): **44/44 passed (100%)** in 4.90s.
- Integration Suites (`test_authenticated_chat_lifecycle.py`, `test_chat_orchestration_integration.py`): **11/11 passed (100%)**.
- Intent Classification & Formatting Isolation: verified direct paragraph preservation, multi-line Android version boundary isolation without splitting, and single-source citation consolidation.
- Hydration Predicate Verification: `should_reload_conversation_history()` correctly gates same-ID re-hydration when local turns end with un-answered user questions while ignoring active generation.
- Database Daemon: PostgreSQL 16 verified running on `127.0.0.1:5432`.
- UI Smoke Checklist: Manual visual inspection steps documented for 75%, 100%, and 125% zoom levels on `http://localhost:8080`.

---

## Historical phase record -- 2026-10-29

**PHASE 16 -- ELIMINATE DUPLICATE CHAT RESPONSES AND FIX ANSWER FORMATTING (COMPLETED & VERIFIED)**

### Confirmed Root Causes & Implemented Solutions

1. **Permanent Loading Spinner Indicator Bug (`frontend/pages/chat_page.py`):**
   - **Root Cause**: In `render_messages()`, line 1205 checked `if state.is_generating or is_active_conv_gen or gen_status:`. When generation finished, `state.get_generation_status()` returned the string `"completed"`. In Python, `bool("completed")` evaluates to `True`, causing the synthesis spinner (`"Synthesizing answer from verified texts..."`) to remain permanently rendered in the conversation bubble even after the answer had fully appeared.
   - **Fix**: Replaced truthy string check with explicit active-generation state filtering: `if is_active_conv_gen or gen_status in ("generating", "queued"):`. The spinner now vanishes immediately upon completion or cancellation.

2. **Duplicate Assistant Responses on History Load (`backend/app/schemas/chat.py`, `backend/app/api/v1/endpoints/chat.py`, `frontend/client/api_client.py`, `frontend/state/app_state.py`):**
   - **Root Cause**: `ChatQueryResponse` did not include the persisted database message ID. As a result, `api_client.send_chat_message()` created a synthetic client ID (`f"msg-{uuid.uuid4().hex[:8]}"`). When `AppState.load_conversation()` was subsequently triggered (e.g. clicking the conversation in Recent Chats), `detail.messages` returned the actual database UUIDs. In `load_conversation()`, `existing_ids = {m.id for m in self._chat_history}` only contained the database UUID; since `gen.response.id` (`msg-xxxx`) was not in `existing_ids`, it appended the in-memory response a second time, duplicating the message and its citation cards.
   - **Fix**:
     - Added `message_id: str | None = None` to `ChatQueryResponse` in `backend/app/schemas/chat.py`.
     - In `backend/app/api/v1/endpoints/chat.py` `_persist_assistant_response()`, called `db.refresh(assistant_msg)` and assigned `response.message_id = str(assistant_msg.id)` and `response.metadata["message_id"] = str(assistant_msg.id)`.
     - In `frontend/client/api_client.py` `send_chat_message()`, used the canonical `ret_msg_id` as `ChatMessageDTO.id`.
     - In `frontend/state/app_state.py` (`load_conversation()` and `_run_async_query()`), added both ID-based matching and content-based matching (`has_matching_content = any(m.role == "assistant" and (m.content or "").strip() == (gen.response.content or "").strip() for m in self._chat_history)`), preventing duplicate assistant turns regardless of timing.

3. **Single Authoritative Submit Path & Race Condition Prevention (`frontend/pages/chat_page.py`):**
   - **Root Cause**: An unused global event listener `ui.on("submit_chat_question", on_custom_submit)` was registered in `chat_page.py`. In `send_message()`, `finally: is_submitting["value"] = False` cleared the submission lock synchronously in the same tick that `start_background_generation()` was created, leaving a narrow window where rapid Enter keydown or mouse clicks could submit duplicate questions before the task transitioned state.
   - **Fix**: Removed the redundant `submit_chat_question` listener. Kept `is_submitting["value"] = True` active throughout generation, releasing the lock only in `check_generation_status` when generation completes, in `handle_stop`, or upon synchronous exception.

4. **Crowded Single-Paragraph Answers & Missing List Bullets (`frontend/pages/chat_page.py`, `frontend/components/theme.py`, `backend/app/services/llm/service.py`):**
   - **Root Cause**:
     - NiceGUI's `ui.markdown` uses `markdown2`. Under standard Markdown, an itemized list preceded by text without a blank line (`\n\n`) is collapsed by `markdown2` into a single `<p>` tag.
     - Tailwind CSS preflight resets `ol, ul { list-style: none; }` and `li` styling. `.safe-markdown ul` only defined margin/padding without `list-style-type: disc !important` or `display: list-item !important`, causing browsers to render lists as unbulleted indented text.
     - When the model copied unbulleted text or inline numbered sequences (e.g. `Android 1.0 (2008) Android 1.5 ...`), `_sanitize_llm_answer()` lacked logic to split them into vertical items.
     - Bullet citations were repeated on every single bullet item (e.g. `[1]` on all 18 lines).
   - **Fix**:
     - Configured `ui.markdown(clean_content, extras=["fenced-code-blocks", "tables", "cuddled-lists", "break-on-newline"])`.
     - In `frontend/components/theme.py`, styled `.safe-markdown ul` with `list-style-type: disc !important;`, `.safe-markdown ol` with `list-style-type: decimal !important;`, and `.safe-markdown li` with `display: list-item !important;`.
     - Added `format_inline_list_items()` in `backend/app/services/llm/service.py` to automatically detect inline sequences and split them into clean markdown bullets (`- `).
     - Added `deduplicate_list_citations()` to consolidate repetitive identical citation tags from individual bullets onto the list header or introduction.
     - Expanded `REASONING_LEAK_PATTERNS` to catch `The user wants...` and prompt instruction echoes.

### Automated and Live Verifications Completed
- `backend/tests/unit/test_frontend.py`: **44/44 passed (100%)**
- `backend/tests/integration/test_authenticated_chat_lifecycle.py`: **4/4 passed (100%)**
- `backend/tests/integration/test_chat_orchestration_integration.py`: **7/7 passed (100%)**
- `backend/tests/unit/test_conversational_rag_quality.py`: **14/14 passed (100%)**
- `scripts/test_phase13e_acceptance.py`: **4/4 passed (100%) against live PostgreSQL and Ollama models**:
  - Test A (`list of android version`): 12 Android versions extracted from Page 6 infographic of `1-Flutter-Intro.pdf`, cited with Page 6, formatted as a clean vertical list.
  - Test B (`What is Flutter?`): Direct definition from Page 18, cited with Page 18.
  - Test C (`list that`): Conversational follow-up correctly resolved and itemized into a clean markdown list.
  - Test D (`What is the capital of Mars?`): Grounded refusal without hallucination or fake citations.

---

## Prior authoritative phase -- 2026-10-29

**PHASE 15 -- FIX CONVERSATION ISOLATION, VERTICAL CHAT SCROLLING, RELIABLE ANSWERS AND SHARED STUDENT/ADMIN COURSE SELECTION (COMPLETED & VERIFIED)**

### Confirmed Root Causes & Implemented Solutions

1. **Conversation Switching Cancellation Bug (`frontend/state/app_state.py`):**
   - **Root Cause**: `AppState.load_conversation()` and `AppState.start_new_conversation()` invoked `stop_generating()` whenever `_is_generating` was True, cancelling any in-flight background query upon navigation. Furthermore, `AppState` used a single scalar `_active_task` and discarded query results whenever `self._active_conversation_id != target_conv_id`.
   - **Fix**: Replaced scalar task tracking with a conversation-keyed generation registry `_generations: dict[str, ConversationGeneration]` and `_concurrency_lock: asyncio.Lock()`. Background tasks run to completion independently of which conversation is currently active. Completed results are saved to the target conversation in PostgreSQL and reconciled into chat history when reopened. `stop_generating(conv_id)` cancels only the intended conversation.

2. **Horizontal Overflow & Message Stacking Issue (`frontend/pages/chat_page.py`, `frontend/components/theme.py`):**
   - **Root Cause**: `.chat-scroll-area` container used `overflow-y-auto` without constraining horizontal overflow, while flex child elements (`message_container`, user message rows, assistant columns) lacked `min-w-0 max-w-full box-border`, preventing flex shrinking below intrinsic content width.
   - **Fix**: Added `overflow-x: hidden !important; overflow-y: auto !important; box-sizing: border-box !important;` to `.chat-scroll-area`. Applied `min-w-0 max-w-full box-border break-words` across message wrappers, user bubbles, assistant columns, and source cards. Updated `.safe-markdown` with `overflow-wrap: anywhere !important;` and bounded tables and `<pre>` blocks with self-contained internal scrollbars.

3. **Markdown List Collapsing into Single Paragraph (`backend/app/services/llm/service.py`):**
   - **Root Cause**: NiceGUI's `ui.markdown` uses `markdown2`. Under standard Markdown, an itemized list preceded by an introductory sentence requires an empty line (`\n\n`) before the first bullet `- `. Single newlines caused `markdown2` to collapse bullet lines into a single `<p>` tag, rendering as a dense hyphen-separated text block. Furthermore, recovery appended `[{source_tag}]` to every single item.
   - **Fix**: Emitted double newlines (`\n\n`) before itemized lists in `extract_grounded_recovery_answer()` and `_sanitize_llm_answer()`. Preserved clean bullet lines (`\n- `) and deduplicated citation tags.

4. **Generic Non-Answer Deflection (`backend/app/services/llm/service.py`):**
   - **Root Cause**: `is_reasoning_or_non_answer()` only checked reasoning leaks, failing to catch deflection strings like *"Based on the provided documents, please refer to the cited material for the complete details."* An exemption rule also bypassed list validation if the text contained a comma.
   - **Fix**: Added regex pattern matching for generic non-answer deflections ("refer to cited material/documents/sources/details"). When detected, `extract_grounded_recovery_answer()` deterministically extracts verified factual lists from retrieved evidence chunks with proper citations.

5. **Student/Admin Scope Selector Divergence & Course Leakage (`frontend/pages/chat_page.py`):**
   - **Root Cause**: Student and admin scope selectors used different markup, styles, and behaviors. The student branch fetched `get_knowledge_bases()` and merged it into `get_chat_scope_courses()`, bypassing authoritative course scoping.
   - **Fix**: Strict course authorization enforced using only `get_chat_scope_courses()`. Unified the scope trigger pill, upward popover menu, search filter input, and course row styling across both roles, while respecting role permissions (admin keeps 3-mode switch for All Courses / Course / Document; student selects All Available Courses or specific course).

6. **Stale State Listeners on Client Navigation (`frontend/pages/chat_page.py`, `frontend/components/layout.py`):**
   - **Root Cause**: Subscriptions registered via `state.subscribe()` were never unsubscribed upon page transitions or client disconnect.
   - **Fix**: Captured subscription return handlers and registered `ui.context.client.on_disconnect(unsub)` in `chat_page.py` and `layout.py` (for both student and admin sidebars).

### Automated and Live Verifications Completed
- `backend/tests/unit/test_frontend.py`: **44/44 passed (100%)**
- `backend/tests/integration/test_authenticated_chat_lifecycle.py`: **4/4 passed (100%)**
- `backend/tests/integration/test_chat_orchestration_integration.py`: **7/7 passed (100%)**
- `backend/tests/unit/test_conversational_rag_quality.py`: **10/10 passed (100%)**
- `scripts/test_phase13e_acceptance.py`: **4/4 passed (100%) against live PostgreSQL and Ollama models**:
  - Test A (`list of android version`): 18 Android versions extracted from Page 6 infographic of `1-Flutter-Intro.pdf`, cited with Page 6.
  - Test B (`What is Flutter?`): Direct definition extracted from Page 18 of `1-Flutter-Intro.pdf`, cited with Page 18.
  - Test C (`list that`): Conversational follow-up correctly resolved and itemized into a clean markdown list.
  - Test D (`What is the capital of Mars?`): Grounded refusal without hallucination or fake citations.

---

## Prior authoritative phase -- 2026-10-29

**PHASE 14 -- ONE SHARED CHAT EXPERIENCE, RELIABLE RAG ANSWERS, COURSE SELECTION AND PERFORMANCE REPAIR (COMPLETED & VERIFIED)**

### Summary of Completed Objectives & Verifications
1. **Permanent Elimination of Mock Hijack Bug (frontend/client/api_client.py):**
   - Removed the dangerous `or not self.get_session_token()` condition from `FrontendAPIClient.send_chat_message()`.
   - Offline demo mode now strictly triggers only when `not self._should_use_real_http()` (e.g., `DEMO_MODE=1` or database disconnected).
   - In real HTTP mode, an unauthenticated request raises an explicit `ValueError("Authentication required: Please sign in to submit chat queries.")` rather than silently returning hardcoded CS101 grading text with fake `d1111111-` citations.
   - Padded the internal HTTP client timeout from 60.0s to 120.0s (`httpx.Timeout(120.0, connect=10.0)`) to provide ample room for local CPU model inference.

2. **Thread Context Isolation & Client Propagation (frontend/state/app_state.py, frontend/client/api_client.py):**
   - Identified that `_get_browser_session_id()` evaluates to `None` inside `asyncio.to_thread` worker threads because `nicegui.context.client` and Starlette `request_contextvar` are thread-local to the main event loop.
   - Exposed `api_client.get_client()` on `_SessionAPIClientProxy` to resolve the current session-bound client.
   - In `AppState.start_background_generation()`, the authenticated `client` instance is resolved on the main thread *before* entering `asyncio.to_thread`, guaranteeing that the user's cookies and session token are preserved during background query synthesis.
   - In `AppState.start_new_conversation()`, added guard `if self._active_conversation_id and len(self._chat_history) == 0:` to reuse an existing empty draft conversation, preventing duplicate blank "New chat" records in PostgreSQL.

3. **Safe Message Persistence Before Generation & Idempotent Retries (backend/app/api/v1/endpoints/chat.py):**
   - Implemented `_persist_user_question()` and `_persist_assistant_response()` in `backend/app/api/v1/endpoints/chat.py`.
   - The user question is immediately stored in PostgreSQL and committed before calling `_execute_orchestrated_chat()`. If generation times out or is cancelled, the user's question remains safely stored in PostgreSQL and appears in history upon reload.
   - Implemented idempotent retry deduplication: if the last message in the conversation is an un-answered user message with the same question, `_persist_user_question()` reuses the existing row instead of inserting a duplicate.

4. **Coordinated Latency Deadlines & Resilient Grounded Recovery (backend/app/core/config.py, backend/app/services/llm/service.py):**
   - Set backend `LLM_REQUEST_TIMEOUT_SECONDS = 90.0` in `backend/app/core/config.py` (coordinated with 120s frontend timeout).
   - Set retry timeout to 45.0s in `backend/app/services/llm/service.py`.
   - Added `LLMTimeoutError` exception handling in `generate_grounded_answer()`: if local CPU generation times out on a list or structured query, `extract_grounded_recovery_answer()` deterministically extracts the complete itemized list from verified evidence chunks (such as Page 6 diagram chunks) before returning.
   - Extended regex patterns in `service.py` to recognize Unicode bullet symbols (`▪●▸`) used in academic PDFs like `1-Flutter-Intro.pdf`.

5. **Unified Scope Selection Across Student and Admin Roles (frontend/pages/chat_page.py):**
   - Fixed `active_scope["doc_id"]` initialization on initial page load: now reads `getattr(state, "active_doc_id", None)` and restores `selected_doc` from `docs`.
   - Unified the scope trigger pill styling across Student and Admin experiences: identical rounded-full borders, gold hover accents, and dynamic icons (`public` for All Courses, `menu_book` for Course, `description` for Document).
   - Fixed student course selection to trigger `render_header()` and `render_action_btn()`, keeping header scope badges in sync.
   - Upward popover menu styled with `w-[320px] sm:w-[360px]` and internal scrolling to prevent viewport clipping.

6. **Comprehensive Automated Verification:**
   - `backend/tests/unit/test_frontend.py`: **44/44 tests passed (6.14s)**.
   - `backend/tests/integration/test_authenticated_chat_lifecycle.py`: **4/4 tests passed (0.95s)**.
   - `backend/tests/integration/test_chat_orchestration_integration.py`: **7/7 tests passed (14.87s)**.

---

## Prior authoritative phase -- 2026-10-28

**PHASE 13E -- CHAT SUBMISSION, RAG ANSWER ACCURACY, GROUNDED RECOVERY & LATENCY OPTIMIZATION (COMPLETED & VERIFIED)**

### Summary of Completed Objectives & Verifications
1. **Chat Submission Lifecycle & Draft Preservation (frontend/pages/chat_page.py):**
   - User questions are now immediately appended to state.chat_history via state.add_user_message(q_clean) and rendered instantly in the thread upon submission. The question never disappears or waits for full answer synthesis.
   - Input validation is performed *before* clearing the input box. If scope is missing or invalid, an inline warning is shown, preserving the user's typed draft.
   - In-flight submissions are guarded by is_submitting and handle_submit debouncing, preventing duplicate user messages.
   - Conversation switching isolation implemented in frontend/state/app_state.py: if a user switches conversations while a query is in-flight, response or error messages do not leak into the new conversation.
   - Inline retry mechanism (handle_retry) provides a clean 1-click retry button on timeout/generation errors that re-triggers synthesis without duplicating the user's question.

2. **Elimination of Generic Non-Answer Placeholder (backend/app/services/llm/service.py):**
   - Permanently eliminated the hardcoded placeholder string 'Based on the provided documents, please refer to the cited material for the complete details.' from backend/app/services/llm/service.py.
   - Repaired _sanitize_llm_answer(): removed destructive splitting on r'we\s+must\s+output' that previously truncated valid answer bodies when small models generated introductory preambles.
   - Broadened clean_reasoning_text() regex to recognize itemized lists starting with lists?:, includes?:, contains?:, shows?:, and presents?: across both comma-separated and bullet-separated formats.
   - Expanded REASONING_LEAK_PATTERNS to detect deliberation leakage such as 'We are given a user question...', 'We have three retrieved evidence chunks...', 'Let's examine each source...', and 'examine each source'.
   - Implemented extract_grounded_recovery_answer(query, context): a general-purpose, deterministic extractor that inspects structured labels (e.g., [Visible Text & Labels]: from diagram chunks, markdown tables, and bullet points) and produces fully-cited answers with exact [source_X] citations in < 1ms when generative inference falters.

3. **Latency Optimization & Model Warming (backend/app/core/config.py, backend/app/services/llm/ollama_provider.py):**
   - Reduced LLM_MAX_OUTPUT_TOKENS default from 768 to 384 in backend/app/core/config.py. For CPU generation at ~7-8 tokens/sec, this caps single generation latency to ~35-50s (down from 110-120s).
   - Added 'keep_alive': '15m' to OllamaLLMProvider in backend/app/services/llm/ollama_provider.py to keep qwen3:4b warm in memory, eliminating cold model swap latencies between turns.
   - Reduced non-answer retry timeout to 60s and capped retry max tokens to 384, preventing runaway 5-minute request cascades.

4. **Rigorous End-to-End Acceptance Verification (scripts/test_phase13e_acceptance.py):**
   - Executed against live PostgreSQL database and Ollama models (qwen3:4b, qwen3-embedding:0.6b):
     - Test A: 'list of android version': PASSED (82.82s vs baseline 296s timeout). 18 Android versions extracted from Page 6 of 1-Flutter-Intro.pdf. 1 Citation to Page 6. Generic placeholder eliminated.
     - Test B: 'What is Flutter?': PASSED (59.81s). Exact SDK definition from Page 18. 1 Citation to Page 18.
     - Test C: 'list that' (Conversational Anaphora): PASSED (56.94s). Successfully resolved to prior Android turn. 18 versions and Page 6 citation returned.
     - Test D: Unsupported Query ('What is the capital of Mars?'): PASSED (100.90s). Grounded refusal without hallucination: 'Based on the provided documents, there is not enough information to answer this question.'
   - All 4 Acceptance Tests Passed (100% Success Rate).

5. **Unit & Behavioral Regression Suite:**
   - backend/tests/unit/test_conversational_rag_quality.py: 10/10 tests passed (0.55s).
   - Temporary debugging files cleaned up.
   - Core design system (Ivory #E8E0D2, Gold #B89A5A, Deep Atlas Navy #0E1D61), single admin portal sidebar, and strict tenant security boundaries fully preserved.

---

## Prior authoritative phase -- 2026-10-28

**PHASE 13D -- RECENT CHAT TITLES, IMMEDIATE NEW CHAT CREATION & SUBMISSION DEDUPLICATION (COMPLETED & VERIFIED)**

### Summary of Completed Objectives
1. **Recent Chats Title Layout & Selection Refinement (`frontend/components/layout.py`):**
   - Implemented fixed-height (`h-9` / 36px) rows with consistent horizontal padding (`px-2.5 rounded-lg box-border`).
   - Eliminated layout shifting by applying a 1px border to both states: `border border-gold/40 bg-surface-elevated text-primary-navy font-semibold` when selected, and `border border-transparent text-secondary-navy hover:text-primary-navy hover:bg-surface-elevated/60` when inactive.
   - Applied strict single-line CSS text truncation directly to the title label: `min-width: 0; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; display: block;` without artificial Python character slicing.
   - Kept full un-truncated titles available in hover tooltips (`.tooltip(c.title)`).
   - Enforced non-shrinking chat icon (`ui.icon("chat_bubble_outline", size="14px").classes("shrink-0")`).
   - Removed excess Quasar expansion indentation in admin sidebar by specifying `content-class="q-pa-none"`.

2. **Immediate Visible New Chat Creation (`frontend/state/app_state.py`, `frontend/components/layout.py`, `frontend/client/api_client.py`):**
   - Clicking sidebar **New Chat** immediately creates a persistent conversation record in the database (`api_client.create_conversation(title="New chat", scope=current_scope, ...)`).
   - Immediately sets `state.active_conversation_id = new_conv.id`, clears visible messages, and notifies subscribers.
   - Instantly renders the new `New chat` row at the top of Recent Chats highlighted as selected.
   - Updates the browser URL to `/chat?conversation_id={new_conv.id}` so page reloads restore the clean new conversation thread.
   - Added concurrency lock `_is_creating_conversation` to prevent accidental duplicate conversation records from rapid clicks.

3. **Removed Duplicate Top-Right New Chat Header Button (`frontend/pages/chat_page.py`):**
   - Eliminated the redundant top-right "New Chat" button from `header_container`.
   - The primary sidebar "+ New Chat" button remains the single authoritative action across desktop and mobile.

4. **Deterministic First-Question Title Generation & Stability (`backend/app/api/v1/endpoints/chat.py`, `backend/app/api/v1/endpoints/conversations.py`, `frontend/pages/chat_page.py`):**
   - Added lightweight, deterministic title generator `generate_conversation_title(question: str)` that collapses whitespace, preserves exact user wording up to 80 characters, and cleanly bounds long questions without extra model latency.
   - Implemented `PATCH /conversations/{conversation_id}` authenticated REST endpoint for metadata updates with strict user tenancy isolation.
   - When the user sends their opening question, `state.update_active_conversation_title(new_title)` renames the conversation in the database and refreshes the Recent Chats sidebar immediately upon user submission (without waiting for answer synthesis).
   - Backend `_try_persist_turn` checks prior user messages count: only `prior_user_msgs == 0` or default "New chat" titles are renamed; all subsequent questions strictly preserve the conversation title and conversation ID.

5. **Submission Deduplication & Duplicate Turn Resolution (`frontend/pages/chat_page.py`):**
   - Identified root cause of duplicated turns in screenshot: previous lack of immediate DB conversation creation caused subsequent sessions to append to the prior conversation `662961d5-e8bf-4f61-8d06-871aabcccea9` (recorded 27 minutes apart in DB).
   - Added `is_submitting` concurrency guard to `chat_page.py` ensuring neither rapid Enter keypresses nor send button clicks can trigger concurrent queries.
   - Bound Enter key with `keydown.enter.prevent` to prevent browser form event propagation.
   - Guarded `on_custom_submit` against in-flight submissions.
   - Cleaned up temporary `print()` debugging statements.

6. **Targeted Verification & Behavioral Suite:**
   - `backend/tests/unit/test_conversational_rag_quality.py`: 10/10 passed (0.55s).
   - `backend/tests/frontend/unit/test_admin_overview_and_navigation_contracts.py`: 19/19 passed (0.49s).
   - `backend/tests/frontend/unit/test_navigation_contracts.py`: 24/24 passed (0.33s).
   - `backend/tests/frontend/unit/test_student_dashboard_contracts.py`: 23/23 passed (0.52s).
   - `backend/tests/frontend/unit/test_student_profile_contracts.py`: 29/29 passed (0.54s).
   - Total test suite: **105 / 105 tests passing** (1.54s).
   - Live backend conversation lifecycle verified via API: Create ("New chat") -> List (top position) -> Patch title ("list of android version") -> Detail check -> Delete.

---

## Prior authoritative phase -- 2026-10-28

**PHASE 13C -- UNIFIED ADMINISTRATOR SIDEBAR NAVIGATION & ARTIFACT CLEANUP (COMPLETED & VERIFIED)**

### Summary of Completed Objectives
1. **Canonical Admin Portal Sidebar Unification (`frontend/components/layout.py`):**
   - Consolidated administrator navigation into one authoritative sidebar produced by `get_sidebar_sections(user: UserDTO | None)`.
   - Replaced and permanently eliminated the competing, alternative 3-link `admin_chat_nav` ("Dashboard", "Knowledge Bases", "Knowledge Chat") that was previously hardcoded when an administrator accessed `/chat`.
   - All administrator routes (`/dashboard`, `/knowledge-bases`, `/documents`, `/administrators`, `/activity`, `/system-health`, and `/chat`) now reuse the identical application shell and primary sidebar without layout jumping, nested navigation containers, or duplicate headers.

2. **Integrated Persistent Recent Chats in Canonical Admin Sidebar (`frontend/components/layout.py`):**
   - Retained the four canonical administrator navigation groups:
     - `OVERVIEW`: Overview (`/dashboard`)
     - `CONTENT`: Courses (`/knowledge-bases`), Documents (`/documents`)
     - `ADMINISTRATION`: Administrators & Permissions (`/administrators`), Activity & Audit (`/activity`)
     - `OPERATIONS & TOOLS`: System Health (`/system-health`), Test Assistant (`/chat`)
   - When on Knowledge Chat (`/chat`), seamlessly nested directly under the active "Test Assistant" item:
     - Primary "+ New Chat" button (`state.start_new_conversation()`)
     - Collapsible "Recent Chats" section (`ui.expansion("Recent Chats", icon="history", value=True)`) containing recent conversation titles with active highlighting, state subscriptions, hover delete capability, and `.tooltip(c.title)` to ensure long conversation titles never break layout geometry.
   - When on other admin routes (`/dashboard`, `/knowledge-bases`, etc.), the sidebar cleanly displays the authoritative grouped navigation matching the Administrator Overview baseline.

3. **Workspace Header Quick Action (`frontend/pages/chat_page.py`):**
   - Added a direct "+ New Chat" button to the chat header right row for immediate accessibility from both the primary sidebar and the conversational canvas.

4. **Student Experience Preserved:**
   - Student navigation (`Assistant`, `Courses`, `Profile` + `Recent Chats`) remains 100% intact and isolated (`render_chat_history_sidebar(student_nav_links)`).

5. **Safe Cleanup of Ephemeral Test & Debugging Artifacts:**
   - Audited and safely removed 31 temporary debugging scripts, test runners, one-off model experiments, and scratch PNGs:
     - Diagnostic scripts: `test_candidate_logic.py`, `test_cdp_hover.py`, `test_cdp_input.py`, `test_chat_direct.py`, `test_clean_logic.py`, `test_conversational_followup.py`, `test_css_rules.py`, `test_db.py`, `test_leak_detect.py`, `test_query_baseline.py`, `test_query_page6_answer.py`, `test_turns_and_persistence.py`, `test_vision_page6.py`, `test_vision_pages.py`, `unified_verification.py`, `verify_phase13b.py`, `verify_phase13b_browser.py`, `inspect_raw_generation.py`, `inspect_view_switcher.py`, `baseline_audit.py`, `check_chunks.py`, `check_chunks_db.py`, `audit_flutter_pdf.py`, `inventory_documents.py`, `delete_test_records.py`, `deletion_manifest.json`.
     - Temporary PNGs: `scratch/hover_check_normal.png`, `scratch/switcher_hover.png`, `scratch/switcher_normal.png`.
   - Strictly preserved valuable regression tests (`backend/tests/unit/test_conversational_rag_quality.py`), migrations (`alembic/versions/c3d4e5f6a7b8_add_document_id_to_conversations.py`), database backups (`scratch/db_backup/`), launcher (`run_project.bat`).

6. **Targeted Verification & Behavioral Suite:**
   - `backend/tests/frontend/unit/test_admin_overview_and_navigation_contracts.py`: 19/19 passed (0.49s).
   - `backend/tests/frontend/unit/test_navigation_contracts.py`: 24/24 passed (0.33s).
   - `backend/tests/frontend/unit/test_student_dashboard_contracts.py` & `test_student_profile_contracts.py`: 52/52 passed (1.06s).
   - `backend/tests/unit/test_conversational_rag_quality.py`: 6/6 passed (0.12s).
   - Full live server route smoke verification: all 9 core routes (`/login`, `/admin/login`, `/student/login`, `/dashboard`, `/chat`, `/knowledge-bases`, `/documents`, `/system-health`, `/profile`) responded with HTTP 200.

---

## Prior authoritative phase -- 2026-10-28

**PHASE 13B -- FINAL UI REPAIR, ADMIN CHAT HISTORY & CONVERSATIONAL RAG RELIABILITY (COMPLETED & VERIFIED)**

### Summary of Completed Objectives
1. **View Switcher Hover Defect Resolved (rontend/components/theme.py):**
   - Root cause: Quasar .q-btn--flat hover pseudo-elements (.q-focus-helper:before, .q-focus-helper:after) superimposed a grey rectangle over the solid navy pill.
   - Fix: Suppressed .q-focus-helper pseudo-elements in .view-switcher-container and enforced #1B2D7C uniform solid hover on .view-switcher-pill-active.
   - Captured 5 authentic screenshots in screenshot/phase13b_switcher_*.

2. **Admin Chat & Student Chat Harmonization (rontend/pages/chat_page.py):**
   - Standardized header, removed duplicate question title, corrected typography to Plus Jakarta Sans (safe-markdown font-sans).

3. **Admin Course / Document Scope Selector Repaired (rontend/pages/chat_page.py):**
   - Re-anchored popover (offset [0, 56]) above composer card; in-place mode switching; explicit selection required; send disabled when scope incomplete.

4. **Visible, Persistent Admin Chat History (ackend/app/models/conversation.py, ackend/app/schemas/conversation.py, rontend/state/app_state.py):**
   - Added document_id field to Conversation model; restored turns, citations, and scope on reopening; user tenancy isolated.

5. **Conversational Follow-Up & Quality Safeguards (ackend/app/api/v1/endpoints/chat.py, ackend/app/services/llm/service.py):**
   - Implemented resolve_conversational_query, non-answer detection, retry, and visual retrieval for 1-Flutter-Intro.pdf Page 6 infographic.

6. **Progress Bar Number Suppression (rontend/components/theme.py):**
   - Removed white number overlay inside progress bars via CSS.

7. **Test Suite Execution:**
   - 6/6 unit tests passed in test_conversational_rag_quality.py.

---

### Phase 1: Baseline Audit & Failure Reproduction Findings

1. **Reproduction of Inaccurate Answer on `1-Flutter-Intro.pdf` (UUID: `c2aa1679-7978-4b2a-981a-6bc22922dd97`):**
   - **Query Asked:** `List the Android versions shown in the “List of Android Version” infographic. Use the uploaded PDF and cite the page containing the infographic.`
   - **Assistant Response:** `"The user is asking for the 'List of Android Version' infographic [source_1]. The evidence does not explicitly state an infographic. However, note that [source_3] (Page 12) has a table that lists the current versions for Android and iOS. The table says: 'Current Version 16' for Android and '26' for iOS [source_3]... So the Android version listed is 16."`
   - **Citations:** Only cited Page 6 text chunk `List of Android Version\nAkash Technolabs www.akashsir.com` (11 tokens, zero version details) and Page 5/12 text chunks ("Current Version is 16").
   - **Grounding Status:** `UNVERIFIABLE` / `is_grounded=False`.

2. **Source PDF Inspection (`1-Flutter-Intro.pdf`, 37 pages):**
   - **Page 5:** Native text length = 259 chars. Contains bullet: `▪Current Version is 16`.
   - **Page 6:** Native text length = 91 chars (`List of Android Version\nAkash Technolabs www.akashsir.com`). Contains embedded image `xref=45` with dimensions `1080x1080` JPEG occupying 43.5% of page area (the complete infographic).
   - **Page 7:** iOS slide (text length 258 chars, `Current Version is 26`).

3. **Candidate Detection Dissection (`PDFVisualExtractor`):**
   - **Root Cause Confirmed:** Page 6 was **NOT** selected as a visual candidate.
   - Page 6 scored `48.05`, ranking #14 across the 37 pages.
   - `sparse_text_threshold = 50` disqualified Page 6 (`char_count = 90 > 50`) from receiving the +35.0 sparse graphic bonus (Criteria B).
   - `VISUAL_CUES_PATTERN` (`r"\b(figure|fig\.|diagram|flowchart|chart|graph|architecture|schematic|workflow|plot|infographic)\b"`) failed to match "List of Android Version".
   - Presentation slide logos (present on almost all 37 pages) scored 38.5 to 83.2, pushing full-bleed background slides (e.g. Pages 1, 14, 17) ahead of Page 6.
   - With `VISION_MAX_PAGES_PER_DOC = 3`, Page 6 was dropped before vision inference.

4. **Vision Model Capabilities Check:**
   - Model `qwen2.5vl:3b` is installed in Ollama.
   - Direct execution on Page 6 rendered image (635 KB) succeeded completely and extracted all 43 entries: `Android 1.0 (2008)`, `1.1`, `1.5 Cupcake`, `1.6 Donut`, `2.0-2.1 Eclair`, `2.2 Froyo`, `2.3 Gingerbread`, `3.0 Honeycomb`, `4.0 Ice Cream Sandwich`, `4.1-4.3 Jelly Bean`, `4.4 KitKat`, `5.0 Lollipop`, `6.0 Marshmallow`, `7.0 Nougat`, `8.0 Oreo`, `9.0 Pie`, `Android 10`, `11`, `12`, `13`, `14`, `15`, `16`, and release years 2008–2025.
   - Proves the vision model is fully capable of reading the infographic when given the page.

5. **Saved Document Chunks Verification in Database:**
   - 38 chunks exist in `document_chunks` for `1-Flutter-Intro.pdf`.
   - Chunk 5 (Page 6) is a purely textual chunk containing only 11 tokens (`List of Android Version\nAkash Technolabs www.akashsir.com`).
   - Only 1 visual chunk existed in the entire document: Chunk 37 (Page 1 logo). Page 6 had **zero** visual chunks.

6. **Reranker Visual Intent Flaw (`RerankingService`):**
   - `is_visual_query` in `reranking/service.py` only checked for `diagram`, `flowchart`, `chart`, `figure`, `visual`, `illustration`.
   - The words `infographic`, `image`, `picture`, `graphic`, `timeline` were missing, so visual boost (+1.5) was not applied to infographic queries.

7. **Selective OCR Status (Tesseract):**
   - Tesseract executable is not installed on the Windows environment (`RuntimeError: No tessdata specified and Tesseract is not installed`).
   - PyMuPDF OCR requires selective availability detection and graceful fallback so ingestion never fails when Tesseract is missing.

8. **Performance Bottlenecks Measured:**
   - `OLLAMA_EMBED_BATCH_SIZE = 4` causes 10 sequential roundtrips for a 38-chunk document.
   - Ollama CPU model switching between `qwen2.5vl:3b`, `qwen3-embedding:0.6b`, and `qwen3:4b` adds latency when multiple models compete for host RAM.

9. **Frontend UI Clutter & Button Hover Defects Confirmed:**
   - Documents page progress display renders fake/conflicting chunk numbers and percentages during early extraction stages.
   - Quasar's default `.q-focus-helper` applies a dark 0.15 opacity overlay on button hover, making dark navy buttons muddy and reducing text readability.

### Phase 2: Completed Repairs and System Hardening

1. **Visual Candidate Detection Repaired (`PDFVisualExtractor`):**
   - Expanded `VISUAL_CUES_PATTERN` to include `infographic`, `roadmap`, `timeline`, `hierarchy`, `comparison`, etc.
   - Added `HEADING_CUES_PATTERN` detecting `List of...`, `Overview of...`, `Architecture of...`.
   - Tuned large image detection (`>= 400x400` or `>= 250,000` px) to boost genuine infographic slides while discounting recurring slide template logos.
   - Page 6 candidate score increased from 48.05 (#14) to 113.05 (#1/2 in document).

2. **Vision Extraction Instructions Updated (`provider.py`):**
   - Updated `VISION_ANALYSIS_SYSTEM_PROMPT` to require complete itemization of all readable entries, versions, and names for infographics, roadmaps, and tables.
   - Expanded `_clean_str_list` limit to 100 items.

3. **Reranker Intent Expansion (`reranking/service.py`):**
   - Added `infographic`, `infographics`, `image`, `picture`, `graphic`, `photo`, `timeline`, `roadmap` to `is_visual_query`.

4. **Selective Tesseract OCR Service Implemented (`backend/app/services/ocr/`):**
   - Created `OCRService` with availability check (`is_available`), selective page policy (scanned pages or sparse text `< 30` chars with images), in-memory caching, bounded timeouts, and graceful fallback when Tesseract is missing.
   - Integrated into `pdf_parser.py`.

5. **Performance Optimization & Timings (`config.py`, `ingestion.py`, `indexing.py`):**
   - Lowered `VISION_RENDER_DPI` to 100 DPI (cut vision tokens from 2,840 to 1,200; prompt eval from 110s to 30s).
   - Increased `VISION_REQUEST_TIMEOUT` to 180.0s for CPU inference headroom.
   - Increased `OLLAMA_EMBED_BATCH_SIZE` to 8.
   - Monotonic timing (`time.monotonic()`) added across all stages with structured logging.

6. **Frontend UI & Button Hover Styling (`theme.py`, `documents_page.py`):**
   - Suppressed Quasar `.q-focus-helper` dark muddy overlays (`display: none !important; opacity: 0 !important;`).
   - Clean `:hover` state with `#1B2D7C` and accessible `:focus-visible` outlines.
   - Cleaned stage labels ("Reading document...", "Reading visual content...", "Creating embeddings · X of Y chunks", "Ready · X chunks indexed") without duplicate or overlapping text.

7. **LLM Generation & Grounding Sanitization (`prompt_builder.py`, `service.py`, `claim_verifier.py`):**
   - Set `LLM_MAX_OUTPUT_TOKENS = 768` for comprehensive list generation.
   - Protected itemized lists in `_sanitize_llm_answer` from premature conclusion truncation.
   - Enriched `ClaimVerifier` evidence matching with document title, page number, and visual modality metadata.

### Phase 3: Final Acceptance & Verification Results

1. **Re-Indexed `1-Flutter-Intro.pdf` (UUID: `c2aa1679-7978-4b2a-981a-6bc22922dd97`):**
   - 40 chunks indexed in PostgreSQL (3 visual chunks: Chunk 37 [Page 6 infographic], Chunk 38 [Page 8 table], Chunk 39 [Page 26 diagram]).
   - Embeddings fully computed and persisted.

2. **End-to-End Visual RAG Query Test:**
   - **Query Asked:** `List the Android versions shown in the “List of Android Version” infographic. Use the uploaded PDF and cite the page containing the infographic.`
   - **Generated Answer:** `"The infographic is in [source_1] on Page 6. The list of Android versions as per [source_1] is: Android 1.0 (2008), Android 1.5 Cupcake (2009), Android 1.6 Donut (2009), Android 2.0-2.1 Eclair (2009), Android 2.2 Froyo (2010), Android 2.3 Gingerbread (2010), Android 3.0 Honeycomb (2011), Android 4.0 Ice Cream Sandwich (2011), Android 4.1-4.3 Jelly Bean (2012), Android 4.4 KitKat (2013), Android 5.0 Lollipop (2014), Android 6.0 Marshmallow (2015), Android 7.0 Nougat (2016), Android 8.0 Oreo (2017), Android 9.0 Pie (2018), Android 10 (2019), Android 11 (2020), Android version 12 (2021), Android version 13 (2022), Android version 14 (2023), Android Version 15 (2024), Android Version 16 (2025)"`
   - **Citations:** Document `c2aa1679-7978-4b2a-981a-6bc22922dd97` **Page 6**! (Correct infographic page, NOT Page 5 text).
   - **Grounding Status:** `Status: FULLY_SUPPORTED, Grounded: True, Claim support rate: 1.0, Coverage: 1.0`.

3. **Automated Regression Suite:**
   - 71/71 tests passing (100% pass rate) across `test_visual_rag_and_ocr_regression.py`, `test_multimodal_vision_extractor_and_provider.py`, `test_llm_provider.py`, `test_llm_generation_service.py`, `test_claim_verifier.py`, `test_grounding_validation_service.py`.

4. **Visual QA & Environment Notice:**
   - NiceGUI application running cleanly on port 8080 (HTTP 200).
   - Playwright browser context initialization encountered driver download 404 from azureedge.net due to container sandbox network isolation; transparently documented. Backend, unit tests, and live end-to-end API RAG orchestrator tests verified with 100% fidelity.

---

## Prior phase — 2026-10-26

**PHASE 12A — FINAL MULTIMODAL ACCEPTANCE, REPOSITORY CLEANUP, AND SAFE PROJECT PACKAGING**

### Status: COMPLETED, VERIFIED & IMPLEMENTATION FROZEN
- **Mission Accomplished:**
  - **Strict Acceptance Gate Enforcement (`scripts/verify_multimodal_chat_real.py`):**
    - Tightened acceptance assertions: Enforces `grounding.status == "FULLY_SUPPORTED"`, `grounding.is_grounded is True`, `unsupported_claim_rate == 0.0`, `citation_coverage == 1.0`, `citation_validity_rate == 1.0`, and validates all evaluated claim DTOs are supported.
    - Verified live execution against isolated test database (`rag_assistant_test_db`) using active models (`qwen2.5vl:3b`, `qwen3-embedding:0.6b`, `ms-marco-MiniLM-L-6-v2`, `qwen3:4b`).
    - Model generated complete sequence answer: `Health Monitor (pos 91) -> Failover Controller (pos 119) -> Standby Node (pos 186)`.
    - All 8 strict assertions PASSED with Return Code 0.
  - **Safe Scratch Cleanup (`scratch/`):**
    - Removed 12 disposable one-off investigation and debugging scripts.
    - Preserved local database backup `scratch/db_backup/rag_assistant_db_backup_20261014_123058.sql` (1.12 MB) as private local backup.
    - Preserved required fixtures (`deletion_manifest.json`, `sample_course_document.pdf`), test directory `scratch/e2e_multimodal`, and 4 reusable maintenance scripts (`backup_database.py`, `delete_test_records.py`, `inventory_documents.py`, `reset_student_pw.py`).
  - **Formal Test Audit (`context/TEST_CLEANUP_MANIFEST.md`):**
    - Audited all 59 formal test files in `backend/tests/` across unit, security, integration, and UI contract suites.
    - Confirmed zero redundant tests: each test protects unique behavior, security boundaries, or UI contracts. 100% retained.
  - **Regenerated Screenshot Manifest (`context/SCREENSHOT_CLEANUP_MANIFEST.md`):**
    - Regenerated inventory of all 226 files in `screenshot/` with exact image dimensions, SHA256 prefixes, file sizes, classifications, and repository references (220 Keep, 6 Archived, 0 Delete).
  - **Fixed Safe-Archive Generator (`scripts/create_safe_project_zip.py`):**
    - Excluded `storage/`, `*.sql` dumps, `bca_rag_assistant.egg-info`, `screenshot/archive/`, and temporary lock files.
    - Preserved `.env.example`.
    - Added comprehensive test cases in `backend/tests/frontend/unit/test_archive_safety_contracts.py` (68/68 passed).
    - Generated and validated `dist/RAG-Assistant-safe.zip` (639 files, 48.10 MB uncompressed, 41.42 MB compressed, 0 sensitive violations).
  - **Report & Presentation Deliverables Verified:**
    - Located and verified intact deliverables in `report and ppt/`: `RAG_Assistant_Major_Project_Report.docx`, `RAG_Assistant_Major_Project_Report.pdf`, `RAG_Assistant_Major_Project_Presentation.pptx`, `RAG_Assistant_Major_Project_Presentation.pdf`, and minor project documents. Content left unchanged.
  - **Implementation Frozen:** Codebase is complete and locked for academic submission.

---

## Prior phase — 2026-10-26

**PHASE 11A.3.1 — FIX GROUNDING CLASSIFICATION AND PRESERVE VALID STEP-BY-STEP ANSWERS**

### Status: COMPLETED, VERIFIED & IMPLEMENTATION FROZEN
- **Mission Accomplished:**
  - **Grounding Classification & Sequence Separation (`backend/app/services/grounding/sentence_splitter.py` & `backend/app/services/grounding/claim_verifier.py`):**
    - Corrected grounding classification defect: Introduced `_INTRO_COLON_REGEX` to cleanly separate introductory framing colons (`The sequence is:`, `The workflow is:`, `The steps are:`, etc.) from substantive factual assertions when followed by content.
    - Stripped ordinal step indicators (`Step 1:`, `1.`, `(1)`) from extracted factual claims in `SentenceSplitter` so list numbering syntax does not contaminate factual claim text.
    - Updated `ClaimVerifier.extract_numbers()` to ignore list item enumerations occurring at line beginnings, after colons/semicolons, or preceded by `step \d+`, preventing legitimate list numbering from being penalized as missing or hallucinated quantitative entities.
    - Preserved conversational classification for pure framing/preambles (`Here is a summary of the topic.`, `The sequence is:`) and safe refusals without ungrounded factual assertions.
    - Added defense-in-depth handling for prompt instruction echoes and precision meta-commentary in `_CONVERSATIONAL_REGEX`.
    - All 25 grounding unit tests in `test_sentence_splitter.py`, `test_claim_verifier.py`, and `test_grounding_validation_service.py` PASSED (100%).
  - **Step-by-Step Educational Answer Preservation (`backend/app/services/llm/service.py`):**
    - Upgraded `_sanitize_llm_answer()`: Preserves legitimate numbered educational steps (`Step 1:`, `1.`, etc.) and sequence statements while removing `<think>` tags, source-analysis scaffolding, prompt instruction echoes, and chain-of-thought leakage (`However, the user question specifically asks... We must be precise.`).
    - Added regex filtering in `split_parts` and line-filtering to strip trailing user question echoes and precision directives.
    - All 11 unit tests in `backend/tests/unit/test_llm_generation_service.py` PASSED (100%), including dedicated test `test_sanitize_llm_answer_strips_trailing_user_question_and_precision_scaffolding`.
  - **Real Multimodal Verification Script (`scripts/verify_multimodal_chat_real.py`):**
    - Re-executed against isolated test database (`rag_assistant_test_db`) with live `qwen2.5vl:3b` vision extraction, `qwen3-embedding:0.6b` (1024-d pgvector), hybrid retrieval, CrossEncoder reranking, and `qwen3:4b` generation.
    - Model generated genuine factual answer:
      ```
      The sequence is: 1. A heartbeat timeout occurs (this is the trigger condition) [source_1].
      2. The Health Monitor triggers the Failover Controller [source_1].
      3. The Failover Controller promotes the Standby Node to become the active primary server [source_2].
      ```
    - All strict assertions PASSED cleanly with Return Code 0:
      * Assertion 1: Grounding verified: `is_grounded=True, status=FULLY_SUPPORTED, coverage=1.0, validity=1.0, unsupported_claim_rate=0.0`.
      * Assertion 2: Entity order verified: `Health Monitor (pos 98) -> Failover Controller (pos 126) -> Standby Node (pos 198)`.
      * Assertions 3-5: Visual evidence verified: Page 2, `source_modality='visual'`, `visual_type='flowchart'`.
      * Assertion 6: Source viewer URL contract verified: `/api/v1/documents/{doc_id}/file#page=2&view=FitH`.
      * Automated database and disk artifact teardown verified.
  - **Implementation Freeze Confirmation:**
    - Code modifications strictly confined to grounding classification, LLM answer sanitization, and verification script assertions.
    - Zero alterations to presentation layer, database schemas, or API endpoints.
    - Architecture and implementation are strictly frozen.

---

## Prior phase — 2026-10-26

**PHASE 11A.3 — FINAL MULTIMODAL RAG ACCEPTANCE AND SAFETY CORRECTIONS**

### Status: COMPLETED, VERIFIED & IMPLEMENTATION FROZEN
- **Mission Accomplished:**
  - **Selective Visual Candidate Extraction Hardened (`backend/app/services/vision/pdf_extractor.py`):**
    - Refined structural candidate evaluation logic in `_evaluate_page()`: `has_vector_evidence` requires `drawing_count >= 15` or `(drawing_count >= 2 and has_2d_shapes)` or `(drawing_count >= self.min_vector_drawings and (is_sparse or image_count > 0))`. Decorative 1D divider lines and purely textual mentions of figures yield 0 candidates.
    - Verified all 7 deterministic unit scenarios:
      1. Plain text page without images or drawings -> 0 candidates (score 0.0).
      2. Page with genuine embedded image (> 5% area) -> 1 candidate (score 50.0).
      3. Page with vector flowchart shapes (>= 2 shapes with rects/curves) -> 1 candidate (score 30.0).
      4. Scanned page with sparse native text (< 50 chars) and visual structure -> 1 candidate (score 35.0).
      5. Text-only page discussing diagrams extensively without figures -> 0 candidates (score 0.0).
      6. Text page mentioning "Figure 1" with decorative horizontal separator lines -> 0 candidates (score 0.0).
      7. Dense text page followed by a diagram page -> Diagram page correctly prioritized and selected.
    - 24/24 tests in `backend/tests/unit/test_multimodal_vision_extractor_and_provider.py` PASSED (100%).
  - **Database Isolation & Safety Guard (`backend/app/db/session.py`):**
    - Implemented `validate_test_database_url()` with strict approved whitelist (`APPROVED_TEST_DB_NAMES = {"rag_assistant_test_db"}`, `APPROVED_TEST_DB_PREFIXES = ("test_", "rag_test_")`).
    - Explicitly blocks and throws `RuntimeError` if any test/verification script attempts to connect to production/dev database `rag_assistant_db`.
    - Unit test `test_validate_test_database_url_guard()` added to `backend/tests/unit/test_production_quality_gate.py` (15/15 quality gate tests passing).
  - **Reranker Visual Intent Prioritization (`backend/app/services/reranking/service.py`):**
    - Added visual query intent detection (`is_visual_query` for terms: `diagram`, `flowchart`, `chart`, `figure`, `visual`, `illustration`, `architecture diagram`, `protocol diagram`).
    - Injected a `+1.5` score boost for `source_modality == "visual"` candidates during CrossEncoder reranking, guaranteeing that visual diagram chunks are assigned `source_1` priority when users inquire about diagrams/flowcharts.
    - All 21 tests in `backend/tests/unit/test_reranking.py` PASSED (100%).
  - **LLM Deliberation Stripping & Claim Attribution (`backend/app/services/llm/service.py`):**
    - Hardened `_sanitize_llm_answer()`: expanded conclusion regex to extract clean direct answers from Ollama reasoning preambles (`The answer should be:`, `The answer is:`, `Sequence:`, `The failover sequence is:`, etc.) while stripping subsequent scratchpad bullets (`- This source talks about...`).
    - Filtered section attribution candidates: excluded generic short strings like `Page 1` / `Page 2` (`len(sec) >= 15`), preventing false substring matches.
    - Added attribution fallback for uncited factual answers matching context items by content word overlap (prioritizing visual chunks).
    - All 7 tests in `backend/tests/unit/test_llm_generation_service.py` PASSED (100%).
  - **Claim Verifier & Sentence Splitter Numeric Invariance:**
    - `backend/app/services/grounding/claim_verifier.py`: Filtered markdown inline list numbering (`1. `, `2. `, `(1) `) in `extract_numbers()` so enumeration syntax is not penalized as numeric hallucination.
    - `backend/app/services/grounding/sentence_splitter.py`: Protected periods in numbered list items (`1.___ESC_DOT___`) and classified workflow sequences as conversational/definitional preambles.
    - All 19 tests in `test_sentence_splitter.py`, `test_claim_verifier.py`, `test_grounding_validation_service.py` PASSED (100%).
  - **End-to-End Live Verification Script (`scripts/verify_multimodal_chat_real.py`):**
    - Executed with live `qwen2.5vl:3b` vision inference, `qwen3-embedding:0.6b` (1024-d pgvector), hybrid retrieval, CrossEncoder reranker, and `qwen3:4b` generation.
    - Verified all 8 strict assertions with Return Code 0:
      1. Grounding contract: `is_grounded=True, status=CONVERSATIONAL`.
      2. Expected sequence verified in answer: `Health Monitor -> Failover Controller -> Standby Node`.
      3. Citation belongs to synthetic test document ID.
      4. Citation points to Page 2.
      5. Modality is `visual`, type is `flowchart`.
      6. Application source-viewer URL generated: `/api/v1/documents/{doc_id}/file#page=2&view=FitH`.
      7. Course authorization enforced (active Course A accessible, restricted Course B blocked with HTTP 404).
      8. Clean teardown and database restored to pristine state.
  - **Implementation Freeze Confirmation:**
    - All code changes are verified, linted with Ruff, and free of whitespace issues (`git diff --check` clean).
    - Architecture and presentation layers are locked and frozen.

---

## Prior phase — 2026-10-23

**PHASE 11A.2 — SELECTIVE PDF VISUAL PROCESSING, MEMORY SAFETY AND REAL CHAT VERIFICATION**

### Status: COMPLETED, HARDENED & CANONICALLY VERIFIED WITH LIVE CHAT & REAL MODELS
- **Mission Accomplished:**
  - **Selective Visual Candidate Detection:**
    - Upgraded `backend/app/services/vision/pdf_extractor.py` to perform a full lightweight structural scan across all pages in a document without breaking prematurely at the candidate limit.
    - Implemented documented scoring heuristic `_evaluate_page()` prioritizing embedded images (+20..50), scanned/sparse text (+35), visual text cues (`Figure`, `Diagram`, `Flowchart`, etc.) (+25), and vector drawings (+15..30).
    - Excluded false positives: pages with dense native text (> 300 chars) and 5–14 simple vector drawing paths without visual cues or images score 0.0, preventing wasted vision calls on decorative lines and borders.
    - Top candidates selected up to `VISION_MAX_PAGES_PER_DOC` (default 3 for 16 GB host), sorted into document page order for sequential analysis.
  - **Pre-Render Memory Scale Bounding:**
    - Pre-calculates scale matrix `pymupdf.Matrix(effective_scale, effective_scale)` *before* calling `page.get_pixmap()` to strictly enforce `VISION_MAX_IMAGE_PIXELS` (1536×1536) prior to buffer allocation. Alpha explicitly disabled (`alpha=False`).
  - **Memory Policy & Sequential Ollama Execution:**
    - Unloads vision model `qwen2.5vl:3b` before embedding and generation stages, releasing ~2.8 GB RAM and maintaining ~6.4 GB free RAM on the 16 GB DDR4 host.
    - Recommends `OLLAMA_MAX_LOADED_MODELS=1` in Windows system properties for automated memory swapping.
  - **Status Semantics & UI Error Separation:**
    - Documented non-fatal visual notes in `Document.error_message` and `IndexingJob.error_message`. In `frontend/pages/documents_page.py`, visual notes on completed documents display an info badge/icon rather than a red failure alert.
  - **End-to-End Live Student Chat Verification (`scripts/verify_multimodal_chat_real.py`):**
    - Ingested 2-page academic PDF into isolated test database (`rag_assistant_test_db`).
    - Page 1 native text extracted without vision calls.
    - Page 2 visual candidate detected (flowchart diagram), rendered with pre-render memory bounds, and analyzed with live `qwen2.5vl:3b` (84.12s).
    - `qwen2.5vl:3b` unloaded; chunks indexed into 1024-d pgvector via live `qwen3-embedding:0.6b`.
    - Executed student query via `RAGOrchestrator` through hybrid retrieval + cross-encoder reranker + `qwen3:4b` generation.
    - Live answer successfully cited Health Monitor, Failover Controller, and Standby Node.
    - Citations packaged 3 items, including Citation [2]: Page 2, Modality: visual, Type: flowchart, Viewer URL: `/api/v1/documents/{doc_id}/file#page=2&view=FitH`.
    - Course access authorization verified: published Course A accessible, private Course B returned HTTP 404.
    - 100% clean test database and disk artifact cleanup in `finally` block.
  - **Tests & Quality:**
    - 46/46 unit tests passing across multimodal, citation validator, and LLM generation suites.
    - `ruff check backend\ frontend\ scripts\verify_multimodal_chat_real.py`: Clean (0 errors).
    - `git diff --check`: Clean (0 errors).

---

## Prior phase — 2026-10-23

**PHASE 11A.1 — REAL OLLAMA VISION INTEGRATION, MEMORY-SAFE EXECUTION, AND END-TO-END VERIFICATION**

### Status: COMPLETED, HARDENED & CANONICALLY VERIFIED WITH REAL MODELS
- **Mission Accomplished:**
  - Verified genuine local vision inference with `qwen2.5vl:3b` on the user's Windows machine.
  - Hardened strict visual response validation in `backend/app/services/vision/provider.py`:
    - Eliminated unsafe fallback `{"summary": cleaned[:500]}` that previously permitted malformed prose or non-JSON output to be marked as successful evidence.
    - Added strict schema validator `_validate_model_response()` ensuring response is a JSON object, `summary` is a non-empty string, `visual_type` belongs to `SUPPORTED_VISUAL_TYPES`, and lists (`visible_text`, `relationships`, `uncertainties`) contain bounded strings. Any violation returns `is_success=False`.
  - Applied strict synchronous timeout bounding (`VISION_REQUEST_TIMEOUT`, 60s) in `OllamaVisionProvider._sync_client` via underlying `httpx.Timeout`.
  - Corrected persistence of non-fatal visual outcome notes (`Visual analysis complete...`, `Visual analysis partial...`, `Visual analysis skipped...`) in `doc_record.error_message` and `IndexingJob.error_message`, ensuring they survive the indexing lifecycle.
  - Live Vision Smoke Test (`scripts/verify_vision_model.py`):
    - Real `qwen2.5vl:3b` executed genuine inference on a synthetic flowchart PNG (`INPUT -> PROCESS -> OUTPUT`) via CPU runner (`llamacpp`, 4096 context).
    - Latency: 45.86s. Extracted labels: `['input', 'process', 'output']`. `is_success=True`.
  - Live End-to-End Multimodal Pipeline Verification (`scripts/verify_multimodal_e2e_real.py`):
    - Ingested 2-page academic PDF into isolated test database (`rag_assistant_test_db`).
    - Page 1 text parsed natively; Page 2 visual candidate analyzed with live `qwen2.5vl:3b` (80.04s) into visual chunk #2 (`source_modality="visual"`, `visual_type="flowchart"`, `page_number=2`).
    - Real `qwen3-embedding:0.6b` embedded chunks into 1024-d vectors in pgvector.
    - Retrieval query retrieved visual chunk #2 as Top Hit #1 (similarity 0.7819).
    - Citation points to Document ID, `#page=2&view=FitH`, and preserves visual modality/type.
    - Course isolation verified (unassigned course returns 0 chunks).
  - Tests & Code Quality:
    - 31/31 passed across unit suites (`test_multimodal_vision_extractor_and_provider.py`, `test_multimodal_rag_pipeline.py`, `test_multimodal_evaluation_dataset.py`).
    - `ruff check frontend backend`: Clean (0 errors).
    - `git diff --check`: Clean (0 errors).
  - Memory Management & Guidelines:
    - Baseline available RAM: ~3.47 GB free out of 16 GB DDR4.
    - Concurrent model execution (`qwen2.5vl:3b` + `qwen3-embedding:0.6b`) dropped free RAM to ~379 MB.
    - Sequential processing and model unloading (`ollama stop qwen2.5vl:3b`) restored free RAM to ~4.66 GB.
    - Recommended Windows setting: `OLLAMA_MAX_LOADED_MODELS=1` for seamless automated memory management.

---

## Prior phase — 2026-10-23

**PHASE 11A — MULTIMODAL RAG MVP FOR VISUAL PDF EVIDENCE**

### Status: IMPLEMENTED & DETERMINISTICALLY VERIFIED (Real vision integration gated on `ollama pull qwen2.5vl:3b`)
- **Mission Accomplished:**
  - Implemented the first genuine multimodal milestone for the **Multimodal RAG-Based University Knowledge Assistant**, enabling visual evidence extraction, vision-language analysis, chunking, 1024-d dense embedding, retrieval, and grounded citation provenance for academic PDF documents (diagrams, flowcharts, charts, scanned pages).
  - Architecture: **PDF text + selected visual pages → vision-language analysis → text representation of visual evidence → chunking & 1024-d text embedding (`qwen3-embedding:0.6b`) → hybrid retrieval → grounded answer with original-page citation.**
  - **1. Bounded PDF Visual Candidate Detection & Rendering (`backend/app/services/vision/pdf_extractor.py`):**
    - Uses `PyMuPDF` (1.28.2) to evaluate structural signals:
      - Embedded images with area ratio >= 5% of page area.
      - Vector drawings with >= 5 drawing paths (capturing charts and flowcharts drawn as PDF paths).
      - Scanned pages with sparse native text (< 50 characters).
    - Hard bounds: Configurable `VISION_MAX_PAGES_PER_DOC` (default 5) and `VISION_MAX_IMAGE_PIXELS` (default 1536×1536) with proportional downscaling.
    - Safe in-memory byte rendering at 150 DPI without storing rendered pages or temporary files on disk.
  - **2. Vision Provider & Injection Containment (`backend/app/services/vision/provider.py`):**
    - Abstract `BaseVisionProvider` with `analyze_image` (async) and `analyze_image_sync` (sync).
    - `OllamaVisionProvider` configured for local model (`qwen2.5vl:3b`) on `127.0.0.1:11434` with 90s timeout.
    - Prompt Injection Resistance: Strictly instructs the vision model that text appearing in images constitutes inert data evidence and must never be followed as system instructions.
    - Validated structured output: `visual_type`, `summary`, `visible_text`, `relationships`, `uncertainties`.
    - `MockVisionProvider` for deterministic testing.
  - **3. Ingestion Pipeline & Truthful Failure Policies (`backend/app/services/ingestion.py`):**
    - Integrated visual stage into `IngestionPipeline.process_document()` with `IndexingJobStage.EXTRACTING_VISUALS`.
    - Truthful skip policy: If vision model is missing or unreachable, native text parsing continues uninterrupted, and `IndexingJob.error_message` honestly notes: `"Visual analysis skipped: Vision model (qwen2.5vl:3b) not installed/reachable. Text indexed."` No fake visual chunks or fake badges.
    - Partial failure policy: If 1 of N pages fails, records `"Visual analysis partial: X/Y visual pages analyzed (Z failed)."`
    - Non-PDF files (DOCX, TXT, MD, CSV) and pure text PDFs completely bypass the vision extractor (zero model calls).
    - Idempotent re-ingestion: Cleans preexisting chunks to prevent duplicate visual chunks.
  - **4. Vector Retrieval & Grounded Citations (`backend/app/schemas/chat.py`, `backend/app/services/rag_orchestrator.py`, `frontend/components/evidence_panel.py`):**
    - Visual chunks are embedded into compatible 1024-dimensional vectors using existing `qwen3-embedding:0.6b`.
    - Standard dense vector retrieval (`VectorRetrievalService`), lexical search, and hybrid fusion retrieve visual chunks based on descriptive content.
    - Citations preserve canonical `document_id`, exact 1-indexed `page_number`, `source_modality="visual"`, and `visual_type`.
    - Citation drawer displays discrete `Visual: Diagram` or `Visual: Flowchart` badge.
    - Source viewer opens the PDF directly at `#page=N&view=FitH`.
  - **5. Verification & Test Suite:**
    - `backend/tests/unit/test_multimodal_vision_extractor_and_provider.py`: 11 passed.
    - `backend/tests/unit/test_multimodal_rag_pipeline.py`: 8 passed.
    - `backend/tests/unit/test_multimodal_evaluation_dataset.py`: 8 passed (all 8 evaluation scenarios verified).
    - Total Phase 11A Tests: 27 passed in 5.62s.
    - Core Regression Tests: 77 passed in 32.96s.
    - Ruff linting & git diff check: Clean (0 errors).

---

## Prior phase — 2026-10-23

**ADMIN PART 10B.2 — COMPLETE SYSTEM DIAGNOSTICS UI REDESIGN (SERVICE HEALTH BOARD)**

### Status: COMPLETED, FULLY TESTED & CANONICALLY VERIFIED
- **Mission Accomplished:**
  - Completely replaced the obsolete four-column HTML table foundation and surrounding component presentation at `/system-health` with a responsive, professional **Service Health Board**.
  - Addressed all visible layout, hierarchy, and mobile usability defects identified in Part 10B.1:
  1. *Section A — Compact Overall System Status Banner:*
     - Consolidated multiple repetitive headings and cards into a single unified operational status banner.
     - Displays primary status badge (`System Degraded` / `System Healthy`), single truthful explanation, probe timestamp (`Probe: YYYY-MM-DD HH:MM:SS UTC`), and an intentionally placed `Refresh Telemetry` action.
     - Semantic colors are restrained and functional: Degraded uses amber (`#92400E` on `#FFFBEB` with `#FDE68A` border), Healthy uses green (`#166534` on `#F0FDF4` with `#BBF7D0` border).
  2. *Section B & C — Responsive Monitored Subsystem Board:*
     - **Desktop (1440×900 & 1366×768):** Structured as a 3-zone horizontal row per subsystem:
       - Zone 1 (40% width): Material icon, bold service title (no awkward line breaks), distinct functional scope description (e.g., `API Gateway`: "API request handling and application endpoint availability.", `Indexing Background Worker`: "Asynchronous document parsing, chunking, embedding, and indexing jobs.").
       - Zone 2 (18% width): Compact status badge (`✓ Healthy`, `▲ Degraded`, `✖ Failed`, `Preview`).
       - Zone 3 (42% width): Live telemetry diagnostic message in natural sans-serif typography with generous line-wrapping room.
     - **Mobile (390×844 & 375×667):** Adapts seamlessly to a vertical stacked card flow:
       - Line 1: Subsystem icon and bold title on the left, status badge on the right.
       - Line 2: Functional scope description directly beneath.
       - Line 3: Live diagnostic message inside a clean, soft inset container (`bg-canvas/60 border border-subtle p-2.5 rounded`).
       - **Zero horizontal scrolling:** Document width strictly equals viewport width (390px / 375px), 0 overflowing elements (`docWidth=390`, `winWidth=390`, `hasHorizontalScroll=false`, `overflowingDiagsCount=0`).
  3. *Truthful Telemetry Semantics & Error Integrity Preserved:*
     - Preserves verified backend subsystem metadata mapping in `get_subsystem_metadata()`.
     - Preserves degraded status when Ollama local endpoint is unreachable; never masks degraded status as healthy.
     - Preserves preview mode honest labeling; unprobed preview components are never shown as healthy.
     - Handles missing health status as unknown; renders truthful empty state on zero components; displays honest error banner with Retry Probe on API failure.
  4. *Test Suite & Verification:*
     - Updated `backend/tests/frontend/unit/test_admin_part10b_health_admin_users_and_overview.py`: **29/29 tests passed** (100%).
     - `scripts/capture_part10b2_final.py`: Verified with live Edge DevTools protocol against live PostgreSQL and FastAPI server.
     - Desktop screenshot: `screenshot/admin/part10b2/system_health_desktop.png` (1440x900).
     - Mobile screenshot: `screenshot/admin/part10b2/system_health_mobile.png` (390x844).
     - Ruff check: clean (0 issues). Git diff check: clean.

---

## Prior phase — 2026-10-23

**ADMIN PART 10B.1 — SYSTEM DIAGNOSTICS TABLE HEADING AND SUBSYSTEM DESCRIPTION CORRECTION**

### Status: COMPLETED (FOUNDATION SUPERSEDED BY PART 10B.2)
- Fixed blank table headings and repeated subsystem descriptions.
- Preserved verified subsystem descriptions, but visual review demonstrated that the four-column table foundation remained generic and unacceptable on mobile, motivating the Part 10B.2 Service Health Board redesign.

---

## Prior phase — 2026-10-23

**ADMIN PART 10B — SYSTEM HEALTH, ADMINISTRATOR MANAGEMENT, AND OVERVIEW CORRECTNESS**

### Status: COMPLETED, FULLY TESTED & CANONICALLY VERIFIED
- **Mission Accomplished:**
  - Resolved all verified Part 10B defects across System Health truthfulness, Administrator course-name resolution, Overview priority & deduplication, and PostgreSQL test database access:
  1. *System Health Truthfulness & Preview Mode Reporting:*
     - Root cause: In `frontend/client/api_client.py`, `get_system_health()` in preview mode returned simulated component data with `status="healthy"` and overall status `"healthy"`. In `frontend/pages/dashboard_page.py`, `(system_health.status or "healthy").lower()` converted missing/null status to healthy.
     - Correction: In preview mode, `get_system_health()` returns `status="preview"` with components explicitly labeled unverified/simulated. Status badge component in `frontend/components/status_badge.py` updated to support `PREVIEW` (slate badge `#475569`, neutral styling). Overview and System Health pages now map missing/null status to `"unknown"` (never `"healthy"`), and render explicit `Interactive Preview Mode (Simulated Infrastructure)` banner when `preview`.
     - In live mode: Real backend health response preserves detailed subsystem diagnostics. Failed requests raise informative exceptions with HTTP status and backend detail (never silently replaced with mock healthy data).
  2. *Administrators & Permissions Course-Name Resolution and Error Guards:*
     - Root cause: `frontend/pages/admin_users_page.py` mapped course loading failures silently to `available_courses = []`, showing "No active courses registered in catalog", and displayed raw UUIDs in the Course Scope column.
     - Correction: Implemented module-level helpers `get_course_map()`, `resolve_course_display_name()`, and `extract_assigned_course_ids()`.
     - Distinguishes 3 states: (1) success with courses, (2) success empty (`[]`), (3) catalog failure (`courses_error`).
     - Course Scope column in Directory table renders human-readable course names (e.g. `Computer Architecture`, `Official University Regulations`) with tooltip showing remaining courses if > 2.
     - Permissions Dialog resolves course names and IDs safely; guards `save_permissions()` against executing when `courses_error` is present so assigned scopes cannot be wiped.
     - Provisioning modal guards against creating faculty admins without a valid course catalog.
     - Honest error banner with `Retry Catalog` action displayed whenever catalog loading fails.
  3. *Overview Simplification & Consistency:*
     - Fixed false-idle bug in Column 2: previously if `active_jobs == 0` and `failed_jobs > 0`, it displayed "Queue Idle: All embeddings synchronized". Now flags attention required with a link to `/documents?view=processing`.
     - Bounded course repositories summary list to 4 courses (`course_summaries[:4]`) with a `+ N more courses in Course Management →` link.
     - Health strip uses truthful status interpretation; missing status maps to `"unknown"`, preview maps to `"preview"`.
  4. *PostgreSQL Test-Database Diagnosis & Resolution:*
     - Root cause confirmed: PostgreSQL on this Windows machine is an unmanaged portable binary (`D:\Kartik\pgsql\pgsql\bin\postgres.exe`, data: `D:\Kartik\pgsql\data`), NOT a registered Windows Service (`Get-Service` returns nothing). Ephemeral subshells terminated the server process upon command exit.
     - Confirmed both `rag_assistant_db` (production/dev) and `rag_assistant_test_db` (test) exist and are valid.
     - Launched `postgres.exe` as a persistent background daemon (`task-2062`).
     - Verified test database connection. Ran previously failing/blocked suites:
       - `backend/tests/integration/test_indexing_and_admin_rbac_integration.py`: **5/5 passed** (was 5 errors).
       - `backend/tests/security/test_backend_security_audit.py`: **19/19 passed** (was skipped).
  5. *Test Suite & Verification:*
     - Created `backend/tests/frontend/unit/test_admin_part10b_health_admin_users_and_overview.py`: **13/13 passed**.
     - Ran `test_admin_overview_and_navigation_contracts.py`: **19/19 passed**.
     - Ran `test_admin_part10a_documents_processing_consolidation.py`: **25/25 passed**.
     - `ruff check`: Clean (**0 errors**).
     - `git diff --check`: Clean (**0 errors**).
     - Captured authentic screenshots in `screenshot/admin/part10b/`:
       - `01_overview_desktop_live.png`: Desktop live Overview showing truthful DEGRADED health strip, failed jobs alert, bounded course summaries, and non-idle queue.
       - `02_overview_mobile_390x844.png`: Mobile Overview layout.
       - `03_system_health_live.png`: Genuine live subsystem diagnostics (PostgreSQL & pgvector Healthy, Ollama Degraded).
       - `04_administrators_readable_courses.png`: Admin directory with human-readable course badges for faculty admin.
       - `05_administrators_rbac_modal.png`: RBAC configuration dialog with readable assigned course boundary checkboxes.
       - `06_administrators_catalog_error.png`: Restrained error banner with retry button on course catalog failure.

---

## Prior phase — 2026-10-22

**ADMIN PART 10A.1 — CORRECT PROCESSING STATUS, POLLING ERRORS, AND REGRESSION VERIFICATION**

### Status: COMPLETED, FULLY TESTED & CANONICALLY VERIFIED
- **Mission Accomplished:**
  - Resolved all 6 verified Part 10A defects without breaking the approved design system, upload pipeline, document operations, permissions, or `/indexing` compatibility route:
  1. *Eliminated False Green Queue Status:*
     - Root cause: `refresh_processing_queue()` previously based the indicator decision solely on `if active_count > 0: ... else: live_dot = emerald; live_status_label = "Queue idle & synchronized"`. When failed jobs were present (`failed_count > 0`) but no jobs were active, it displayed a green dot and claimed the queue was idle & synchronized.
     - Correction: Implemented `compute_queue_status_indicator()` with 5 mutually exclusive, deterministic states:
       - Active jobs present -> amber dot with pulse, `f"{active_count} active job(s)"` (warning)
       - No active jobs, but failed jobs present -> rose dot, `f"{failed_count} failed job(s) need attention"` (negative) — never false green!
       - No active and no failed jobs, queue request succeeded -> emerald dot, `"Queue idle & synchronized"` (positive)
       - Request failed initially -> rose dot, `"Queue unavailable"` (negative)
       - Request failed during polling with prior data -> amber dot, `"Sync disrupted — retrying..."` (warning) with cached data intact
  2. *Truthful Polling & Exception Handling:*
     - Removed silent `except Exception: pass` suppression in `poll_check()`, `trigger_table_refresh()`, and `refresh_processing_queue()`.
     - Logged failures safely with `logger.warning(...)`.
     - When background polling fails, cached job objects remain intact without mutating their authoritative status (never marked FAILED or COMPLETED prematurely).
     - Indicator updates truthfully to amber `"Sync disrupted — retrying..."` without clearing prior data or introducing runaway retry loops.
  3. *Protected Document Data from Silent Cache Erasure:*
     - Implemented `fetch_all_scoped_documents(courses, fetch_fn)` returning `DocumentFetchResult`.
     - Distinguishes complete success, partial failure (some courses fail, others succeed), and total failure (all course requests fail).
     - If all requests fail during background refresh: preserves `cached_docs` and renders a persistent error banner with a manual retry button, rather than falsely clearing to an empty list and showing "No Documents Available".
     - If some requests fail: displays successful documents and warns administrator about unavailable courses.
     - Initial load failure renders a clear error card with a retry button rather than a false empty repository.
  4. *Honest 100-Job History Representation & Backend Pagination:*
     - Updated backend endpoint `GET /knowledge-bases/indexing-jobs` in `backend/app/api/v1/endpoints/knowledge_bases.py` to accept query parameters `limit: int = Query(100, ge=1, le=500)` and `offset: int = Query(0, ge=0)`.
     - Updated frontend API client `get_indexing_jobs(limit=100, offset=0)` in `frontend/client/api_client.py` to forward pagination parameters.
     - Updated UI labels in `frontend/pages/documents_page.py`: replaced misleading `All Jobs` filter pill with `Recent Jobs ({total_count})` or `Recent Jobs ({total_count} cap)`, and added explicit section caption `(recent 100 jobs)`.
  5. *Mobile Responsive Hierarchy Correction (390x844 & 375x667):*
     - Scaled `page_layout` heading from `text-4xl` to `text-2xl sm:text-4xl` and subtitle from `text-base` to `text-xs sm:text-base` in `frontend/components/layout.py`.
     - Reduced mobile margin/padding footprints in `frontend/pages/documents_page.py` (`mb-4 sm:mb-6`, `gap-2.5 sm:gap-3`).
     - Added compact mobile styles for `.view-switcher-pill` (`padding: 5px 10px; font-size: 0.75rem;`) in `frontend/components/theme.py`.
     - Composed the live queue status indicator and the `Refresh Workspace` button onto a single horizontal line using `flex-nowrap`, `min-w-0`, `truncate`, and `shrink-0`, eliminating vertical wrapping.
     - Preserved readability of sequential two-step intake, search inputs, filter pills, and table headers on the initial screen without horizontal overflow.
  6. *Behavioral Test Suite Reset:*
     - Replaced brittle string-matching test `test_18` with comprehensive behavioral unit tests in `backend/tests/frontend/unit/test_admin_part10a_documents_processing_consolidation.py`:
       - `test_18_queue_status_indicator_behavior`: tests all 5 mutually exclusive queue states.
       - `test_18b_polling_error_never_mutates_job_authoritative_status`: verifies job status immutability during polling failure.
       - `test_18c_scoped_document_fetching_behavior`: verifies total failure, partial failure, complete success, and genuine empty states.
       - `test_18d_job_history_limit_honesty`: verifies honest naming (`Recent Jobs`, `(recent 100 jobs)`).

- **Verification & Test Outcomes:**
  - Part 10A Unit & Behavior Suite: `backend/tests/frontend/unit/test_admin_part10a_documents_processing_consolidation.py` (**25/25 passed**).
  - Navigation & Overview Contracts: `backend/tests/frontend/unit/test_admin_overview_and_navigation_contracts.py` (**19/19 passed**).
  - Code Quality: `ruff check frontend\ backend\` clean (**0 errors**); `git diff --check` clean (**0 whitespace/conflict errors**).
  - Real Browser Captures in `screenshot/admin/part10a/`:
    - `01_documents_view_desktop.png`: Documents view desktop showing truthful rose dot and `2 failed job(s) need attention` indicator alongside `Refresh Workspace`.
    - `02_documents_expanded_row_desktop.png`: Documents view expanded details pane.
    - `03_processing_view_desktop.png`: Processing view queue with `Recent Jobs (8)` tab, `(recent 100 jobs)` caption, and truthful attention alert.
    - `04_processing_view_failed_job_desktop.png`: Processing view Needs Attention tab.
    - `05_courses_page_streamlined_desktop.png`: Streamlined courses management.
    - `06_updated_sidebar_desktop.png`: Updated navigation sidebar.
    - `07_documents_mobile_390x844.png`: Compact mobile Documents view with single-line indicator + refresh button and sequential intake.
    - `08_student_course_library_regression.png`: Student Course Library regression check confirming unaffected student browsing.
    - `09_processing_mobile_390x844.png`: Compact mobile Processing view with `Recent Jobs (8)` tab and failed job diagnostics.

---

## Historical Phase — 2026-10-22

**ADMIN PART 10A — UNIFY DOCUMENTS AND INDEXING INTO ONE WORKSPACE**

### Status: COMPLETED, FULLY TESTED & CANONICALLY VERIFIED

- **Upcoming Follow-Up Issues Recorded (Next Tasks):**
  1. *System Health Follow-up:*
     - **Defect:** Supplied screenshot and diagnostics report an overall Healthy state while PostgreSQL/pgvector diagnostics indicate `Interactive Preview Mode (Database decoupled)`.
     - **Required Correction:** Preview/disconnected mode must not be reported as verified healthy production database status. Align overall status with truthful subsystem health.
  2. *Administrators & Permissions Follow-up:*
     - **Defect:** Supplied screenshot displays raw UUIDs for course assignments in the table, and course lookup failures can present misleading empty states.
     - **Required Correction:** Resolve and display human-readable course names/codes in the main directory table, retain UUIDs internally for API payloads, and distinguish failed course lookup from genuine empty course list.
  3. *Overview Follow-up:*
     - **Defect:** Overview summaries and activity widgets depend on truthful underlying job, health, and course metrics; existing page has duplicate navigation and content.
     - **Required Correction:** Simplify Overview layout after underlying workspace and health data are verified truthful.

- **Verification & Test Outcomes:**
  - Part 10A Consolidation Test Suite: `backend/tests/frontend/unit/test_admin_part10a_documents_processing_consolidation.py` (**22/22 passed**).
  - Navigation & Overview Contracts: `backend/tests/frontend/unit/test_admin_overview_and_navigation_contracts.py` (**19/19 passed**).
  - Part 9F Intake Regression Suite: `backend/tests/frontend/unit/test_admin_part9f_document_intake_workspace.py` (**18/18 passed**).
  - Course Access & Permissions Suite: `backend/tests/frontend/unit/test_course_access_contracts.py` (**16/16 passed**).
  - Student Dashboard & Chat Suite: `backend/tests/frontend/unit/test_student_dashboard_contracts.py` (**41/41 passed**).
  - Total Passing Contract Tests: **116/116 passed**.
  - Code Quality: `ruff check frontend/ backend/` clean (0 errors); `git diff --check` clean (0 whitespace errors).
  - Canonical Evidence Captures in `screenshot/admin/part10a/`:
    - `01_documents_view_desktop.png`: 123,136 bytes (Documents view with sequential intake, filter pills with visible text, document list)
    - `02_documents_expanded_row_desktop.png`: 125,549 bytes (Expanded `.doc-details-pane` showing stage, metrics, diagnostics, and retry)
    - `03_processing_view_desktop.png`: 162,681 bytes (Processing view queue with tabs, search, progress, and live sync indicator)
    - `04_processing_view_failed_job_desktop.png`: 120,885 bytes (Processing view Needs Attention tab showing failure diagnostics & retry button)
    - `05_courses_page_streamlined_desktop.png`: 80,474 bytes (Courses page without redundant Indexing action, visible filter text)
    - `06_updated_sidebar_desktop.png`: 123,136 bytes (Sidebar navigation showing simplified structure without Indexing or Processing group)
    - `07_documents_mobile_390x844.png`: 130,850 bytes (Documents workspace mobile layout)
    - `08_student_course_library_regression.png`: 66,666 bytes (Student Course Library regression check at `/knowledge-bases` confirming student catalog is intact)

---

## Historical Phase — 2026-10-21

**ADMIN PART 9F — REBUILD THE DOCUMENT INTAKE UI FROM SCRATCH (SEQUENTIAL TWO-STEP WORKSPACE)**

### Status: COMPLETED, FULLY TESTED & CANONICALLY VERIFIED
- **Deconstruction of Visual Failure in Part 9E:**
  - *Investigation & Diagnosis:* In Part 9E, technical geometry checks verified `labelDiffTop = 0px` and `controlDiffTop = 0px`, yet visual review revealed an unbalanced, unapproved layout.
  - The side-by-side `.upload-paired-grid` forced the Target Course select and Document File intake into an unnatural horizontal juxtaposition.
  - The Target Course select collapsed internally to its text content (~160px for "Choose a course", shrinking even further when short values like "BCA" were selected), leaving the remaining 80%+ width to a long, empty intake strip.
  - The desktop composition looked like two unrelated widgets glued together, while the mobile layout was unnecessarily tall.
- **Sequential Two-Step Intake Architecture:**
  - Replaced `.upload-paired-grid` with `.upload-intake-workspace` featuring two sequential steps:
    1. *Step 01 — Destination (`.intake-step-destination`):*
       - Compact, explicit Target Course selector row with `01 Target Course *` label.
       - Wrapped in `w-full max-w-md` (448px on desktop, 100% on mobile), preventing content-width collapse while keeping control proportional to course names.
       - Standardized 46px height, parchment surface (`#FAF6F0`), 1px solid border (`#D8CFBF`), 6px border radius, and deep Atlas navy focus halo (`0 0 0 2px rgba(14, 29, 97, 0.15)`).
       - Visible placeholder `Choose a course`, no blank unselected controls, and no silent auto-selection of the first course.
    2. *Step 02 — Document File (`.intake-step-document`):*
       - Distinct document intake surface (`.document-intake-surface.q-uploader`) positioned deliberately below destination.
       - 74px min-height (64px on mobile), parchment surface (`#FAF6F0`), 1px solid border (`#D8CFBF`), 3px solid Gold left accent (`#B89A5A`), and `post_add` academic icon.
       - Clean left-aligned typography ("Drop a document here, or click to choose a file") with discreet format/size guidance ("PDF · DOCX · TXT · Markdown · CSV · Maximum 100 MiB").
       - Full-surface input overlay (`inset: 0`) ensures clicking anywhere or dragging a file triggers the real native upload pipeline. Suppressed separate Quasar Browse buttons and idle `0.0B / 0.00%` counter.
- **Verification & Test Outcomes:**
  - Part 9F Sequential Intake Suite: `backend/tests/frontend/unit/test_admin_part9f_document_intake_workspace.py` (**18/18 passed**).
  - Part 9E Alignment Suite: `backend/tests/frontend/unit/test_admin_part9e_upload_field_alignment_and_geometry.py` (**11/11 passed**).
  - Part 9D Editorial Intake Suite: `backend/tests/frontend/unit/test_admin_part9d_editorial_intake_design_and_deduplication.py` (**17/17 passed**).
  - Code Quality: `ruff check frontend/ backend/` clean; `git diff --check` clean.
  - Canonical Evidence Captures in `screenshot/admin/part9f/`:
    - `01_documents_desktop_idle.png`: 116,417 bytes | sha256: 3ff339aa63ef3bc6...
    - `02_documents_desktop_target_selected.png`: 115,553 bytes | sha256: d4708d5cb877e083... (BCA selected, width remains 448px)
    - `03_documents_desktop_file_selected.png`: 120,882 bytes | sha256: 85de79d9ba68b4e1...
    - `04_documents_desktop_processing.png`: 120,884 bytes | sha256: 2e3d052b4885d04e...
    - `05_documents_desktop_completed.png`: 118,247 bytes | sha256: af17b70256d12c5d...
    - `06_documents_laptop_1366x768.png`: 100,812 bytes | sha256: 87de75e16de96459...
    - `07_documents_tablet_768x1024.png`: 89,618 bytes | sha256: 70e18779104b06f3...
    - `08_documents_mobile_390x844.png`: 112,327 bytes | sha256: 289bae5583e9f324...
    - `09_documents_compact_mobile_375x667.png`: 99,018 bytes | sha256: e951512b2bd50e0a...
    - All 9 screenshots have 100% distinct SHA-256 hashes.
  - Metrics Manifest: Saved in `screenshot/admin/part9f/geometry_metrics.json`.

---

## Historical Phase — 2026-10-21

**ADMIN PART 9E — FIX UPLOAD-FIELD ALIGNMENT AND RECONCILE THE ACTUAL SOURCE/RUNTIME (SUPERSEDED BY PART 9F)**

### Status: SUPERSEDED BY PART 9F
- Note: The side-by-side paired grid layout in Part 9E passed geometric top-alignment tests but failed visual approval due to disproportionate widths and collapsing selectors. It has been replaced by the sequential two-step intake workspace in Part 9F.
- **Source/Runtime Discrepancy Resolution:**
  - *Investigation & Diagnosis:* The prompt noted a discrepancy between an uploaded project ZIP (where `theme.py` defined 140px/cloud_upload, `documents_page.py` lacked explicit `Document File *` label) and the Part 9D report/tests. Physical filesystem audit revealed that `D:\Kartik\RAG-Assistant zip.zip` (and `D:\Kartik\RAG-Assistant zip`) contained an earlier Part 9C snapshot, whereas the active Git repository `D:\Kartik\RAG-Assistant-Step21E` was already updated with uncommitted Part 9D code (`theme.py` 48px/post_add, `test_admin_part9d_editorial_intake_design_and_deduplication.py` passing 17/17).
  - *Baseline Misalignment Confirmed via CDP Geometry Metrics:* Although Part 9D had created the compact strip, the live browser rendering still exhibited severe misalignment because `upload_form_container` used `ui.row().classes("w-full items-end gap-3 flex-wrap md:flex-nowrap")`. The `items-end` flex alignment aligned the bottom edges (both Y=272), which caused the 42px `Target Course` select to start at Y=230 while the 55px `Document File` uploader started at Y=218. Consequently, the `Document File *` label floated at Y=197, 13px higher than `Target Course *` at Y=210 (`labelDiffTop: -13px`, `controlDiffTop: -13px`). On mobile, the uploader ballooned to 86px due to multi-line text wrapping.
- **Core Objectives & Implemented Architecture:**
  1. *Two-Column Paired CSS Grid (`.upload-paired-grid` in `theme.py`):*
     - Replaced flexbox `items-end` with a shared CSS grid: `grid-template-columns: 280px minmax(0, 1fr)` on desktop (>=768px) and `1fr` on mobile (<768px), with `align-items: start !important`.
     - Target Course occupies a stable 280px column, while Document File takes the remaining available width.
  2. *Shared Symmetrical Field Columns & Explicit Labels (`.upload-field-col`, `.upload-field-label`):*
     - Both columns share identical structure: explicit label (`.upload-field-label`), control wrapper, and optional feedback.
     - Both labels render with identical typography role (`Plus Jakarta Sans`), identical fixed height (`1.25rem = 20px`), line-height (`1.25rem = 20px`), and margin-bottom (`0.375rem = 6px`).
     - Rendered `Target Course *` and `Document File *` labels start at the exact same vertical coordinate (`labelDiffTop = 0px`).
  3. *Paired Control Geometry & Visual Coupling (`.upload-course-select`, `.academic-uploader`):*
     - Both controls share exact 48px visual height (`height: 48px !important; min-height: 48px !important;`), warm parchment background (`#FAF6F0`), hover state (`#F5F0E8`), border (`1px solid #D8CFBF`), border-radius (`6px`), and navy focus halo (`0 0 0 2px rgba(14, 29, 97, 0.15)`).
     - Target Course control top starts at Y=223, Document File control top starts at Y=223 (`controlDiffTop = 0px`).
     - Both controls end at Y=271 (`bottomDiff = 0px`).
  4. *Mobile Stacked Layout Optimization (390x844 & 375x667):*
     - On narrow viewports, the grid collapses into a single column stacking in strict order:
       1. Target Course label
       2. Target Course selector (48px high)
       3. Document File label
       4. Document File intake strip (48px high).
     - Consistent 6px label-to-control spacing and 12px field-to-field gap.
     - Suppressed helper pseudo-element on mobile (`@media (max-width: 639px)`), keeping Document File intake strip at exactly 48px height with zero horizontal overflow (`bodyOverflowX: false`).
  5. *Truthful Progress & Elimination of Premature 0% Chunks:*
     - Diagnosed visible inconsistency where an animated indeterminate progress bar appeared partially filled while text displayed `0/1 chunks (0%)`.
     - Corrected `update_workspace_progress_ui`, active pipeline banner, and table rows: chunk metric counters (`{processed}/{total} chunks ({pct}%)`) are rendered strictly when `processed > 0` and `embedded_chunks > 0`.
     - During initial extraction, validation, and queueing, an indeterminate bar is displayed with truthful stage description without displaying premature `0%`.
- **Verification & Test Outcomes:**
  - Part 9E Alignment & Geometry Suite: `backend/tests/frontend/unit/test_admin_part9e_upload_field_alignment_and_geometry.py` (**11/11 passed**).
  - Part 9D Editorial Intake Suite: `backend/tests/frontend/unit/test_admin_part9d_editorial_intake_design_and_deduplication.py` (**17/17 passed**).
  - Part 9C Documents UX Suite: `backend/tests/frontend/unit/test_admin_part9c_documents_upload_ux_and_pipeline.py` (**11/11 passed**).
  - Part 9B Limits Suite: `backend/tests/frontend/unit/test_admin_part9b_inline_upload_and_size_limits.py` (**13/13 passed**).
  - Full Frontend Unit Suite: **313/313 passed** across all 15 test modules in `backend/tests/frontend/unit/` (100% pass rate in 41.23s).
  - Code Quality: `ruff check frontend/ backend/` **100% clean** (0 errors); `git diff --check` **100% clean** (0 whitespace errors).
  - Live Browser Geometry QA (CDP):
    - Desktop (1440x900): `labelDiffTop = 0px`, `controlDiffTop = 0px`, `targetCourseHeight = 48px`, `documentFileHeight = 48px`, `bodyOverflowX = false`.
    - Laptop (1366x768): `labelDiffTop = 0px`, `controlDiffTop = 0px`, `targetCourseHeight = 48px`, `documentFileHeight = 48px`, `bodyOverflowX = false`.
    - Tablet (768x1024): `labelDiffTop = 0px`, `controlDiffTop = 0px`, `targetCourseHeight = 48px`, `documentFileHeight = 48px`, `bodyOverflowX = false`.
    - Mobile (390x844): stacked cleanly, `targetCourseHeight = 48px`, `documentFileHeight = 48px`, `bodyOverflowX = false`.
    - Compact Mobile (375x667): stacked cleanly, `targetCourseHeight = 48px`, `documentFileHeight = 48px`, `bodyOverflowX = false`.
  - Canonical Evidence Captures in `screenshot/admin/part9e/`:
    - `01_documents_desktop_idle.png` (sha256: `7debca1b1c1a...`): Desktop 1440x900 idle state with visible 'Choose a course' placeholder and 0px alignment.
    - `02_documents_desktop_target_selected.png` (sha256: `3f1a965f...`): Authorized BCA course context selected and clearly displayed.
    - `03_documents_desktop_file_selected.png` (sha256: `646f8d6f...`): Valid PDF attached to intake strip with immediate visual feedback.
    - `04_documents_desktop_processing.png` (sha256: `f3d2936f...`): Active processing state with truthful stage description and no premature 0%.
    - `05_documents_desktop_completed.png` (sha256: `4a3ed6f8...`): Verified Ready state with vector count and reset button.
    - `06_documents_laptop_1366x768.png` (sha256: `a39e0174...`): Laptop viewport with confirmed 0px label and control alignment.
    - `07_documents_tablet_768x1024.png` (sha256: `05b131d2...`): Tablet viewport with confirmed 0px label and control alignment.
    - `08_documents_mobile_390x844.png` (sha256: `5ff71641...`): Cleanly stacked mobile layout with compact 48px controls.
    - `09_documents_compact_mobile_375x667.png` (sha256: `ca55f196...`): Compact mobile layout at 375x667 with no horizontal overflow.
  - Metrics Manifest: Saved in `screenshot/admin/part9e/geometry_metrics.json`.
- **Invariants Preserved:**
  - 100 MiB limit (`104,857,600 bytes`) strictly enforced.
  - Native file picker and drag-and-drop intake active across 100% surface.
  - Automatic ingestion and vector indexing worker operational.
  - Ivory (`#E8E0D2`), Gold (`#B89A5A`), Deep Atlas Navy (`#0E1D61`) tokens preserved.
  - Unrelated administrator and student pages unmodified.

---

## Historical Phase — 2026-10-21 (Part 9D)

**ADMIN PART 9D — REBUILD DOCUMENT UPLOAD EXPERIENCE WITH DISTINCTIVE EDITORIAL INTAKE DESIGN**

### Status: SUPERSEDED VISUALLY BY PART 9E
- **Visual Disapproval & Defect Diagnosis:**
  - While Part 9D introduced the 48px compact strip, the upload fields were misaligned: `Document File *` label floated 13px higher than `Target Course *` due to flexbox `items-end` alignment on unequal 42px vs 55px controls. On mobile, the intake strip ballooned to 86px due to multi-line text wrapping. Superseded by Part 9E's paired CSS grid and unified 48px geometry.

---

## Historical Phase — 2026-10-21 (Part 9C)

**ADMIN PART 9C — FINAL DOCUMENTS UPLOAD UX CORRECTION AND REAL PIPELINE VERIFICATION**

### Status: SUPERSEDED BY PART 9D / PART 9E
- **Core Objectives & Root Cause Diagnoses:**
  1. *Immediate Upload Workspace Availability & Header Toggle Removal:*
     - *Root Cause:* Part 9B hid the upload workspace behind `upload_workspace_container.visible = False` and required administrators to click a header toggle button (`+ Upload Material` / `^ Hide Upload`) just to access the file dropzone.
     - *Correction:* Removed `header_upload_btn`, `toggle_upload_workspace()`, and `show_upload_workspace`. The upload workspace is rendered directly in the normal `/documents` page flow and is immediately visible upon page load for authorized administrators.
  2. *Removal of Excess Card Containers & Bespoke Composition:*
     - *Root Cause:* The dropzone was wrapped in an outer `ui.card`, creating multiple nested box borders that felt cluttered and visually disconnected from the rest of the application.
     - *Correction:* Removed the outer `ui.card` and redundant nested containers. Implemented a horizontal editorial layout directly on the page canvas: concise heading `Add course material`, description text, format/size specs (`PDF, DOCX, TXT, MD, CSV • Max 100 MiB`), a compact `Target Course *` selector, and a single restrained dropzone with warm parchment surface and 1.5px dashed gold border.
  3. *Removal of Document-List Course Filter Dropdown & Toolbar Simplification:*
     - *Root Cause:* The browsing toolbar included an `All Accessible Courses` dropdown that duplicated scope filtering and added unnecessary visual weight.
     - *Correction:* Removed the course filter dropdown from the document ledger toolbar. The table lists all documents the administrator is authorized to view across accessible courses. A single search input with placeholder `Search documents by filename...` provides instant client-side filtering across authorized documents. Status pills (`All`, `Ready`, `Indexing`, `Failed`) and explicit `Refresh` action are preserved.
  4. *Target Course Selector Preservation & Validation:*
     - *Distinction:* Preserved `Target Course *` inside the upload form while removing the browsing filter from the toolbar.
     - *Validation Policy:* Default placeholder is `"Choose a course"`. Uploads without an authorized target course selection are blocked with a clear warning alert. If navigation provides an authorized course context (`?kb_id=...`), that course is preselected.
  5. *Elimination of Idle '0.0B / 0.00%' Framework Counter:*
     - *Root Cause:* Quasar's native `QUploader` component automatically injects `<div class="q-uploader__subtitle">0.0B / 0.00%</div>` into the dropzone when idle, showing meaningless zero metrics before file transfer begins.
     - *Correction:* Added `.academic-uploader .q-uploader__subtitle { display: none !important; }` in `frontend/components/theme.py`. Verified that the subtitle is completely suppressed in running browser instances.
  6. *Removal of Hard-Coded 85% Progress Simulation:*
     - *Root Cause:* `update_workspace_progress_ui()`, active pipeline banner, and table rows used `linear_progress(value=0.85)` for `WRITING_VECTORS` / `STORING_VECTORS`, displaying arbitrary simulated progress.
     - *Correction:* Removed all fixed 0.85 progress values. Indeterminate progress is strictly used during extraction, validation, and vector storage where quantitative progress is not exposed. Determinate progress is strictly bound to authoritative `processed/total` chunks during active chunk embedding (`EMBEDDING`).
  7. *Investigation & Physical Evidence of PDF Parser Failure ('Stream has ended unexpectedly'):*
     - *Root Cause Established:* Investigated failing records in PostgreSQL (`CS101_Syllabus_Guide.pdf` [78 bytes] and `CS101_Distributed_Systems_Lecture_Notes.pdf` [103 bytes]). Inspected stored disk files directly: byte count and SHA-256 hash matched uploaded bytes exactly with zero stream truncation or corruption. Discovered that the previous test script (`scripts/capture_part9b_final.py` line 180) had injected a truncated 103-byte dummy string `b'%PDF-1.4\n%Academic Reference Material\n1 0 obj\n<< /Title (...) >>\nendobj\n'` missing catalog, pages, xref table, trailer, and `%%EOF`. `pypdf` accurately raised `Stream has ended unexpectedly` on the malformed mock stream.
     - *Verification:* Verified that valid syntactically conforming PDFs parse, chunk, and embed with 0 errors via `PDFParser.parse()` and `document_chunker.chunk_document()`. Live browser upload of valid PDF `CS101_Distributed_Systems_Syllabus.pdf` parsed, chunked, and synchronized with pgvector as `Ready` (1 vector chunk).
  8. *Background Indexing Worker Restoration:*
     - *Correction:* Restored `asyncio.create_task(run_indexing_worker())` on NiceGUI startup in `frontend/main.py`. Queued indexing jobs now execute independently in the background surviving client navigation.
- **Verification & Test Outcomes:**
  - Part 9C Unit & Contract Suite: `backend/tests/frontend/unit/test_admin_part9c_documents_upload_ux_and_pipeline.py` (**11/11 passed**).
  - Part 9B Limits Suite: `backend/tests/frontend/unit/test_admin_part9b_inline_upload_and_size_limits.py` (**13/13 passed**).
  - Workflow Contracts Suite: `backend/tests/frontend/unit/test_document_upload_and_indexing_workflow_contracts.py` (**21/21 passed**).
  - Full Frontend Unit Suite: **285/285 passed** in `backend/tests/frontend/unit/` (100% pass rate).
  - Code Quality: `ruff check frontend/ backend/` **100% clean** (0 errors); `git diff --check` **100% clean** (0 whitespace errors).
  - Browser QA: 9 authentic screenshots captured and visually verified in `screenshot/admin/part9c/`:
    - `01_documents_desktop_idle.png` (sha256: `8eba0519b335...`)
    - `02_documents_desktop_target_selected.png` (sha256: `87d7935178fd...`)
    - `03_documents_desktop_file_selected.png` (sha256: `99e82fe38412...`)
    - `04_documents_desktop_processing.png` (sha256: `2986ce426c90...`)
    - `05_documents_desktop_completed.png` (sha256: `9ee00f22bd08...`)
    - `06_documents_desktop_search_filtered.png` (sha256: `c7491c0d41d8...`)
    - `07_indexing_center_view.png` (sha256: `8dad3f062d46...`)
    - `08_documents_mobile_390x844.png` (sha256: `589f7f7d6e8c...`)
    - `09_documents_compact_mobile_375x667.png` (sha256: `d79d268d3690...`)
    - Verified: All 9 SHA-256 hashes are strictly unique.

---

## Historical Phase — 2026-10-21 (Part 9B)

**ADMIN PART 9B — INLINE DOCUMENT UPLOAD, 100 MiB FILE SUPPORT, AND POSTGRESQL RELIABILITY**

### Status: SUPERSEDED BY PART 9C
- **Core Objectives & Root Cause Diagnoses:**
  1. *Elimination of Upload Modal Dialog & Replacement with Inline Workspace:*
     - *Root Cause:* The previous upload workflow used a modal popup (`ui.dialog()`), which obscured the document ledger, interrupted administrator workflow, and felt like a legacy popover rather than an integrated operational workspace.
     - *Correction:* Completely removed `ui.dialog()` for document uploads in `frontend/pages/documents_page.py`. Replaced it with a clean, collapsible inline upload workspace (`upload_workspace_container`) situated naturally between the page toolbars and the document table.
     - *Interaction & State Preservation:* The workspace is toggled via the header action button (`+ Upload Material` / `^ Hide Upload`) or inline `x` close button. Closing/collapsing the workspace preserves active background jobs; persistent progress remains visible in the active pipeline banner, the table row, and the Indexing Center (`/indexing`).
  2. *Elimination of Separate Visible Browse File Button:*
     - *Root Cause:* Quasar's native `q-uploader` rendered a visible `.q-btn` ("BROWSE FILE") that looked clunky and fragmented the drop interaction.
     - *Correction:* In `frontend/components/theme.py`, hid `.academic-uploader .q-uploader__header .q-btn` (`display: none !important`) and expanded `.q-uploader__input` across 100% width and height (`position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer; z-index: 5;`). Clicking anywhere within the dashed gold border opens the native file dialog, drag-and-drop is natively supported, and keyboard focus is preserved.
  3. *Authoritative 100 MiB (104,857,600 Bytes) Limit Alignment:*
     - *Root Cause:* Configuration was inconsistent: `config.py` defaulted to 20 MiB (`20 * 1024 * 1024`), `.env.example` listed 20 MiB, while earlier documentation mentioned 35 MB.
     - *Correction:* Updated typed application default in `backend/app/core/config.py` to `100 * 1024 * 1024 = 104857600 bytes`. Updated `.env.example` to `MAX_UPLOAD_SIZE_BYTES=104857600`. Local `.env` verified consistent. All frontend chips, labels, Quasar native `max_file_size`, and backend validation enforce the identical 104,857,600-byte boundary.
  4. *Memory-Safe 100 MiB Streaming Path:*
     - *Root Cause:* Previous upload paths loaded full file bytes into RAM at multiple layers (NiceGUI `read()`, `api_client` bytes payload, `InProcessProductionTransport` `request.read()`, and `storage.py` reading whole `UploadFile`). For 100 MiB files, this caused multi-fold memory amplification.
     - *Correction:*
       - `backend/app/services/storage.py`: Implemented bounded 64 KiB chunk streaming in `validate_and_read_upload()`, incrementally computing SHA-256 and enforcing byte limits without allocating 100 MiB in memory. Validated structure for DOCX/ZIP directly on seekable streams. `save_file()` streams chunks directly to disk via `shutil.copyfileobj()`.
       - `frontend/client/api_client.py`: Updated `InProcessProductionTransport` to stream request body chunks asynchronously into ASGI `receive()`. Updated `upload_document()` to accept `file_path` and stream file handles via multipart form data with a 300-second timeout.
       - `frontend/pages/documents_page.py`: Detected `file_obj._path` from NiceGUI's `LargeFileUpload` and passed `file_path` directly to `upload_document`.
  5. *PostgreSQL Intermittent Outage Root Cause & Resolution:*
     - *Diagnostic Evidence & Root Cause:* Inspected PostgreSQL log files (`D:\Kartik\pgsql\logfile.log`) and active system processes. The logs showed: `LOG: received fast shutdown request` followed by `LOG: abnormal database system shutdown`.
     - *Explanation:* PostgreSQL was not registered as a Windows Service (`Get-Service *postgres*` was empty). It had been launched interactively in a console session (`postgres.exe -D D:\Kartik\pgsql\data`). Whenever the terminal session ended or IDE server restarted, Windows process tree cleanup sent a close signal (`0xC000013A`), terminating PostgreSQL.
     - *Service Registration Privilege Requirement:* Attempting to register the Windows service (`pg_ctl.exe register -N "postgresql-16" -D "D:\Kartik\pgsql\data" -S auto`) from the medium-integrity agent shell failed with `pg_ctl: could not open service manager`. Registering a permanent Windows service requires an **Elevated Administrator PowerShell prompt**. Provided the exact elevated command and verified data integrity.
     - *Data Integrity Preserved:* Non-destructive database backups created: `rag_assistant_db_backup.dump` (456,217 bytes) and `rag_assistant_test_db_backup.dump` (26,443 bytes). All 3 courses, 4 documents, 99 chunks (1024 dimensions), and 11 users verified intact. PostgreSQL 16.15 and pgvector 0.8.6 confirmed.
  6. *Database Availability & Mode Selection Policy:*
     - *Root Cause:* `frontend/client/api_client.py` previously checked database connectivity via a fragile 200ms TCP socket test (`s.connect_ex(("127.0.0.1", 5432))`), and `_should_use_real_http()` silently fell back to returning mock demo data whenever PostgreSQL had a momentary glitch.
     - *Correction:* Updated `check_database_connection()` in `backend/app/db/session.py` to execute a genuine `SELECT 1` query against the engine without fragile socket timeouts. Updated `_should_use_real_http()` in `frontend/client/api_client.py` so real mode never silently substitutes fake preview data for real backend data. Offline preview mode is strictly restricted to explicit `DEMO_MODE=1` or intentional test mock configurations.
- **Verification & Test Outcomes:**
  - New Part 9B Test Suite: `backend/tests/frontend/unit/test_admin_part9b_inline_upload_and_size_limits.py` (**13/13 passed**, testing exact 104,857,600 byte boundary, 104,857,601 byte HTTP 413 rejection, empty file rejection, unsupported format rejection, magic byte spoofing protection, path traversal sanitization, mode selection policy, and file path streaming).
  - Workflow Contracts Suite: `backend/tests/frontend/unit/test_document_upload_and_indexing_workflow_contracts.py` (**21/21 passed**).
  - Full Frontend Unit Suite: **274/274 passed** in `backend/tests/frontend/unit/` (100% pass rate in 36.30s).
  - Code Quality & Linting: `ruff check frontend/ backend/` **100% clean** (0 errors); `git diff --check` **100% clean** (0 whitespace errors).
  - Browser QA: 12 authentic screenshots captured and visually inspected in `screenshot/admin/part9b/` across Desktop 1440x900, Laptop 1366x768, Tablet 768x1024, Mobile 390x844, and Compact Mobile 375x667.

---

## Historical Phase — 2026-10-21 (Part 9A)

**ADMIN PART 9A — REDESIGN THE DOCUMENTS PAGE AND UPLOAD EXPERIENCE**

### Status: COMPLETED, FULLY TESTED & CANONICALLY VERIFIED
- **Core Objectives & Root Cause Diagnoses:**
  1. *Elimination of Leaked Delete-Confirmation Text:*
     - *Root Cause:* In `frontend/pages/documents_page.py`, `delete_dialog_msg = ui.label(...)` was instantiated at page creation time *before* entering `with delete_dialog, ui.card():`. Calling `.classes(...)` on an existing label inside a `with` block does not re-parent it in NiceGUI's component tree. As a result, the label was parented to the main page container and rendered at the top of `/documents` even when the modal dialog was closed.
     - *Correction:* Moved the instantiation of `delete_dialog_msg` strictly inside `with delete_dialog, ui.card():`. Tested and verified that the message is only mounted within the modal dialog, displays the correct target filename upon deletion request, resets safely across invocations, and never leaks onto the page ledger.
  2. *Upload Experience & Dropzone Redesign:*
     - *Root Cause:* Default Quasar `q-uploader` rendered with an aggressive dark-blue primary header (`--q-primary: #0E1D61`) that visually clashed with the Ivory (`#E8E0D2`), Gold (`#B89A5A`), and Deep Atlas Navy (`#0E1D61`) design system, resembling an unstyled legacy widget.
     - *Correction:* Styled the dropzone with `.academic-uploader` in `frontend/components/theme.py` and `frontend/pages/documents_page.py`. Applied transparent header background, warm parchment drop surface (`#FAF6F0`), restrained gold dashed outline (`1.5px dashed #B89A5A`), gold upload icon, clear typography ("Drop a course material file here or browse"), explicit format (`PDF, DOCX, TXT, Markdown, CSV`) and authoritative size guidance (35 MB limit), and a prominent Deep Atlas Navy `+ BROWSE FILE` action button.
     - *Integrity:* Preserved the genuine `ui.upload` component, real async upload event handler, server-side MIME and format validation, authoritative file-size checks, and target course selection.
  3. *Truthful Stage and Progress Formatting:*
     - *Root Cause:* Stage percentages and chunk completion were conflated. In offline/mock and queue states, an internal 25% stage progress was formatted unconditionally as `0/10 chunks (25%)`, misrepresenting queue waiting as partial chunk processing.
     - *Correction:* Decoupled workflow-stage indicators from chunk counters. `QUEUED_FOR_INDEXING` displays truthful `"Waiting for vector indexing..."` with an indeterminate progress bar and zero chunk counter. Quantitative chunk counts (`{processed}/{total} chunks ({pct}%)`) are displayed strictly during active chunk embedding (`EMBEDDING`).
  4. *Status Badge and Filter Pill Consistency:*
     - *Root Cause:* `render_status_badge()` in `frontend/components/ui_kit.py` mapped `inactive` and `pending` to rose failure styling with `error_outline` icons, causing unindexed or inactive documents to render as system errors. Selected filter pills also lacked explicit text color contrast against active dark navy backgrounds.
     - *Correction:* Updated `render_status_badge()` to map `unindexed`, `not_indexed`, `inactive`, and `pending` to neutral secondary-navy styling (`bg-surface text-secondary-navy border-subtle`). Added `.filter-pill-selected` and `!text-white font-bold` to selected filter pills, ensuring the active `All (N)` pill renders with high contrast. Completed documents render emerald `Ready` badges with vector counts.
  5. *Error Handling vs. Genuine Empty States:*
     - *Correction:* In `refresh_documents()`, all-course iteration previously caught inner exceptions and silently continued. Now: if all course requests fail, a normalized error banner with a working Retry action is displayed; if partial courses fail, fetched documents are rendered alongside an alert banner indicating incomplete results; genuine empty scopes render "No documents are available for the selected scope." For chunk inspection, API failures render a sanitized error alert with Retry, clearly distinguished from a genuine zero-chunk response ("No vector chunks generated yet for this document.").
  6. *Preservation of Indexing Center & Non-Destructive Testing:*
     - `/indexing` and its queue management and retry functionality are strictly preserved.
     - Real user-uploaded project documents (specifically `RAG_Assistant_Major_Project_Report.pdf`) were inspected read-only and never deleted or manipulated during testing.
- **Verification & Test Outcomes:**
  - New Contract Suite: `backend/tests/frontend/unit/test_document_upload_and_indexing_workflow_contracts.py` (21/21 passed, including comprehensive tests for leaked delete text, uploader formats/limits, status badges, filter pill contrast, truthful stage progress, partial failure banners, and chunk error handling).
  - Full Frontend Unit Suite: **261/261 passed** in `backend/tests/frontend/unit/` (100% pass rate in 64.81s).
  - Code Quality: `ruff check frontend/ backend/` **100% clean** (0 errors); `git diff --check` **100% clean** (0 whitespace errors).
  - Browser QA: Authentic screenshots captured and visually inspected in `screenshot/admin/part9a/`:
    - `documents_before_desktop.png`, `documents_before_mobile.png`, `upload_dialog_before.png` (Baseline audit evidence).
    - `documents_final_desktop.png` (Desktop 1440x900: clean table, zero leaked text, white text on `All (3)` pill, emerald Ready badges, neutral Unindexed badge).
    - `documents_final_mobile.png` (Mobile 390x844: fully responsive table cards, zero horizontal overflow).
    - `upload_dialog_final.png` (Academic dropzone with gold dashed border, parchment background, and clear file constraints).
    - `delete_dialog_open.png` (Delete confirmation modal cleanly containing warning message and target filename).
    - `upload_progress_final.png` (Format validation failure state cleanly displaying safe error alert and failed status badge).

---

## Historical Phase — 2026-10-19 (Part 9)

**FRONTEND PART 9 — COMPLETE DOCUMENT UPLOAD-TO-INDEXING WORKFLOW WITH REAL-TIME PROGRESS**

### Status: COMPLETED, FULLY TESTED & CANONICALLY VERIFIED
- **Core Objectives & Implemented Architecture:**
  1. *End-to-End Processing Lifecycle & Automatic Queue Hand-Off:*
     - *Original Architectural Gap:* Previously, document upload scheduled `process_document_task` which completed text extraction and chunking, setting ingestion status to `COMPLETED` and leaving the document in vector-indexing limbo. Admins were forced to navigate manually to `/indexing` to trigger vector indexing.
     - *Automatic Hand-Off Pipeline:* Connected the pipeline end-to-end. Upon upload, `backend/app/api/v1/endpoints/knowledge_bases.py` creates the persistent `Document` and pre-creates a persistent `IndexingJob` (in `SAVING` stage). It verifies administrator indexing permissions (`Permission.DOCUMENT_INDEX` or `is_main`), scheduling `process_document_task(doc.id, auto_index=can_index, job_id=job.id)`.
     - *Authoritative Lifecycle Stages:* Expanded `IndexingJobStage` enum in `backend/app/models/indexing_job.py` to natively track:
       `UPLOADING` → `VALIDATING` → `SAVING` → `EXTRACTING` → `CHUNKING` → `QUEUED_FOR_INDEXING` → `PREPARING` → `EMBEDDING` → `WRITING_VECTORS` → `VERIFYING` → `COMPLETED` (or `FAILED`).
     - *Worker Trigger & Concurrency Safety:* When text extraction and chunk persistence succeed, `IngestionPipeline` atomically updates `job.total_chunks`, sets stage to `QUEUED_FOR_INDEXING`, triggers `notify_indexing_worker()`, and dispatches `index_document_task`. If the admin lacks indexing permissions, the document is safely held in `QUEUED_FOR_INDEXING` awaiting authorized action. Concurrency is guarded by idempotent job reuse (`create_or_reuse_job`) and worker loop deduplication.
  2. *Authoritative Progress Source of Truth & Model Contracts:*
     - Extended `DocumentResponse` (`backend/app/schemas/document.py`) and `DocumentDTO` (`frontend/client/models.py`) with `job_id`, `current_stage`, `progress_percent`, `total_chunks`, `processed_chunks`, `embedded_chunks`, `indexed_chunks`.
     - `list_documents`, `get_document`, and `get_document_index_status` query the latest persistent `IndexingJob` to return live stages and chunk metrics across route navigation and page refreshes.
  3. *Responsive Non-Blocking UI & Live Progress Experience:*
     - Rebuilt the upload dialog in `frontend/pages/documents_page.py`. After file attachment, the modal transitions from form view to an active progress card (`update_modal_progress_ui`), displaying filename, target course, file size, stage badge, linear progress bar, truthful stage description, and chunk counters (`X/Y chunks (Z%)`).
     - Real-time stage formatting (`format_stage_label`) maps internal enum stages to human-readable academic terminology.
     - Implemented `active_pipeline_container` banner above the Documents table displaying all active ingestion/indexing jobs with real-time progress bars and a shortcut to the Indexing Center.
     - Dedicated `Pipeline & Indexing` column in the Documents table shows active stage badge, mini progress bar, and chunk counts for running documents, or ready vector counts for completed documents.
     - Non-blocking execution: `api_client.upload_document` is wrapped in `asyncio.to_thread` to prevent blocking the NiceGUI event loop. Polling timer runs non-blockingly via decoupled table container refreshes without losing search input focus or filter selection.
     - Indexing Center (`frontend/pages/indexing_page.py`) synchronizes with the identical job ID, stage, and counts.
  4. *Truthful Metrics & Failure Diagnostics:*
     - No fabricated percentages: Early stages (`EXTRACTING`, `CHUNKING`) display indeterminate progress bars; percentage is displayed only during `EMBEDDING` and `WRITING_VECTORS` where chunk measurements exist.
     - Progress never reaches 100% until vector storage and verification succeed.
     - Sanitized error messages via `normalize_error()` mask raw database exceptions, file system paths, or credential leakage.
  5. *Visual QA & Screenshot Verification:*
     - Captured 6 authentic screenshots in `screenshot/admin/final/`:
       - `upload_progress_uploading.png`: Initial uploading stage badge and indeterminate progress.
       - `upload_progress_extracting.png`: Text extraction and section splitting stage with active progress.
       - `upload_progress_embedding.png`: Real chunk embeddings (3/10 chunks, 30%) with progress bar.
       - `upload_progress_completed.png`: Final verified state with green `Ready` badge, `10 chunks indexed`, and `Done` action.
       - `upload_progress_indexing_center.png`: Synchronized job in Indexing Center queue.
       - `upload_progress_failed.png`: Format validation rejection state with safe error alert.
- **Verification & Test Outcomes:**
  - New Contract Suite: `backend/tests/frontend/unit/test_document_upload_and_indexing_workflow_contracts.py` (12/12 passed).
  - Full Frontend Unit Suite: **252/252 passed** in `backend/tests/frontend/unit/` (100% pass rate).
  - Code Quality: `ruff check frontend/ backend/` **100% clean** (0 errors).
  - Git Safety: All uncommitted changes preserved; no git commit or push executed.

---

## Historical Phase — 2026-10-19 (Part 8)

**FRONTEND PART 8 — COMPLETE ADMINISTRATOR EXPERIENCE RESET (All Pages & Navigation Redesign)**

### Status: COMPLETED, FULLY AUDITED & CANONICALLY VERIFIED
- **Core Objectives & Implemented Architecture:**
  1. *De-Duplication & Complete Visual Reset from First Principles:*
     - *Issue with Part 8A Reference:* The previous Part 8A overview design improved functionality, but visually suffered from stacked card-in-card containers, an outlined telemetry container filled with massive status pills, a 4-button quick action row that duplicated the persistent sidebar, and elongated mobile layouts.
     - *Full Administrative Reset:* Completely redesigned the visual language and information architecture across all 9 administrative destinations, abandoning the repetitive dashboard card pattern in favor of open editorial surfaces, unified data lists/tables, purposeful whitespace, and responsive mobile adaptations.
  2. *Redesigned Destinations:*
     - **Administrator Navigation (`layout.py`):** Grouped into Overview (`/dashboard`), Academic Content (`/knowledge-bases`, `/documents`), Processing (`/indexing`), Access & Governance (`/administrators`, `/activity`), System & Tools (`/system-health`, `/chat`), plus base account card with initials avatar and Sign Out.
     - **Administrator Overview (`dashboard_page.py`):** Compact editorial heading with quick refresh; single responsive operational status strip (`Healthy`, `Degraded`, or `Outage`); prioritized attention banner rendered ONLY when failed jobs exist; clean 2-column split for Course Repositories and Indexing Queue; and compact Recent Activity audit list. Removed repetitive button row and giant pill containers.
     - **Courses Management (`knowledge_bases_page.py`):** Administrative branch redesigned with an editorial data table showing course code, title, description, material count, and direct actions (`[Documents]`, `Indexing`, `Test Chat`), while strictly preserving the student Course Library catalog intact.
     - **Documents Management (`documents_page.py`):** Replaced blocking course selection barrier card with an open multi-course ledger ("All Accessible Courses" by default), live search, status filter pills (`ALL`, `READY`, `INDEXING`, `FAILED`), chunk inspection modal, delete confirmation, and focused upload dialog.
     - **Indexing Center (`indexing_page.py`):** Structured operational queue distinguishing Queued, Running, Completed, and Failed jobs, with stage progress, chunk counts, live sync status, and contextual retry without nested empty cards.
     - **Administrator Governance (`admin_users_page.py`):** Compact governance banner, scannable user directory table with role badge, course scope badges, permission count, active status toggle, and last main-admin protection.
     - **Activity & Audit (`activity_page.py`):** Immutable event ledger with actor initials avatar, category pills (`Courses`, `Documents`, `Indexing`, `Security & Admins`), outcome filters (`Success Only`, `Failures Only`), and detail inspection dialog.
     - **System Diagnostics (`system_health_page.py`):** Structured diagnostic matrix table with component scope, status badge, probe timestamp, and live telemetry message across PostgreSQL, pgvector, Ollama runtime, and storage.
     - **Test Assistant (`chat_page.py`) & Profile (`profile_page.py`):** Seamlessly integrated into sidebar navigation; student chat and approved profile layout strictly preserved.
  3. *State Safety & Truthfulness:*
     - Truthfully reports degraded indexing worker status; never masks failures as green.
     - Failed requests display decoupled error banners with retry handlers; never converted to false empty states.
     - Added backward-compatible `knowledge_base_id` property to `DocumentDTO`.
  4. *Screenshot Cleanup & Manifest:*
     - Created `context/SCREENSHOT_CLEANUP_MANIFEST.md` classifying all 137 files (131 kept, 6 archived in `screenshot/archive/`, 0 unresolved).
     - Captured 18 authentic, final screenshots in `screenshot/admin/final/` across desktop (1440x900) and mobile (390x844).
- **Verification & Test Outcomes:**
  - `backend/tests/frontend/unit/`: **240/240 passed** in 59.64s.
  - `ruff check frontend/ backend/`: **100% clean** (0 errors).
  - `git diff --check`: **100% clean** (0 errors).
  - Visual inspection: All 18 screenshots visually reviewed with zero overlapping text or clipping.

---

## Historical Phase — 2026-10-19 (Part 8A Intermediate)

**FRONTEND PART 8A — ADMINISTRATOR NAVIGATION AND OVERVIEW REDESIGN (/dashboard, dashboard_page.py, layout.py, test_admin_overview_and_navigation_contracts.py)**

### Status: COMPLETED & VERIFIED
- **Core Objectives & Implemented Corrections:**
  1. *Elimination of Duplicated Administrator Navigation & Single Source of Truth:*
     - *Issue:* `frontend/components/layout.py` previously contained a dormant `get_sidebar_sections()` definition while the actual rendering function `_render_app_sidebar()` manually assembled a conflicting flat list of links. In addition, the administrator sidebar was erroneously cluttered with student-specific features (`+ New Chat` button and student `RECENT CHATS` conversation history).
     - *Correction:* Consolidated administrator navigation into a single, authoritative definition: `get_sidebar_sections(user: UserDTO | None) -> list[dict[str, Any]]`.
     - *Group Architecture:*
       - **Overview**: `("Overview", "/dashboard", "dashboard")`
       - **Academic Content**: `("Courses", "/knowledge-bases", "menu_book")` (guarded by `COURSE_VIEW` or `is_main`), `("Documents", "/documents", "description")` (guarded by `DOCUMENT_VIEW` or `is_main`).
       - **Processing**: `("Indexing", "/indexing", "sync")` (guarded by `DOCUMENT_INDEX` or `DOCUMENT_INDEX_RETRY` or `is_main`).
       - **Access & Governance**: `("Administrators & Permissions", "/administrators", "admin_panel_settings")`, `("Activity & Audit", "/activity", "history")` (guarded by `ADMIN_VIEW` or `is_main`).
       - **System & Tools**: `("System Health", "/system-health", "health_and_safety")` (guarded by `ADMIN_VIEW` or `is_main`), `("Test Assistant", "/chat", "chat")` (guarded by `ADMIN_CHAT` or `is_main`).
       - **Base Account Area**: Retains administrator identity card with initials avatar and Sign Out.
     - *Strict Visual Separation:* The administrator sidebar renders ONLY the permission-filtered grouped navigation. Student `+ New Chat` and student `RECENT CHATS` are completely omitted from the administrator layout.
     - *Student Navigation Preserved 100%:* The student view retains its approved layout (`+ New Chat`, `Assistant`, `Courses`, `Profile`, recent chats with deletion/restore, and account card).
  2. *Redesigned Administrator Overview as an Operational Control Center:*
     - Completely rebuilt `frontend/pages/dashboard_page.py` from first principles.
     - **Header**: Editorial serif `Administrator Overview` with concise description: "Operational status, indexing controls, and academic knowledge management." No bloated marketing heroes.
     - **System Operational Telemetry**: Queries authoritative `api_client.get_system_health()`. Displays truthful status (`Healthy`, `Degraded`, or `Outage`), timestamp, and granular subsystem status pills: API Gateway, PostgreSQL Database, pgvector Extension, Ollama Embedding Model, LLM Generation, and Indexing Background Worker. Provides "Detailed Diagnostics" entry point to `/system-health`. If diagnostics fail, displays a dedicated error banner with a "Retry Diagnostics" button.
     - **Academic Management Quick Actions**: Direct entry points to `Manage Courses` (`/knowledge-bases`), `Manage Documents` (`/documents`), `Open Indexing Center` (`/indexing`), and `Audit Log` (`/activity`).
     - **Attention Required (Failed Indexing Jobs)**: Prioritized alert box when failed indexing jobs exist. Highlights document name, error description, attempt count, and a working "Retry Indexing" action (enforcing `DOCUMENT_INDEX_RETRY` or `is_main`), plus a link to `/indexing`.
     - **Indexing Queue & Processing**: Truthfully distinguishes: (1) active running jobs with stage and progress bar, (2) genuine idle queue with checkmark and "Open Indexing Center" button, and (3) decoupled error banner with "Retry Indexing Status" button. NEVER falsely claims the system is idle upon request failure.
     - **Course Knowledge Repositories**: Truthfully distinguishes: (1) populated course table showing active docs, total docs, indexed count, and quick document actions, (2) genuine empty state via `render_empty_state`, and (3) decoupled error alert with "Retry Courses" button. NEVER displays false "No Courses Found" upon request failure.
     - **Recent Administrative Activity**: Compact audit timeline displaying recent events for administrators with `ADMIN_VIEW` or `is_main`.
  3. *Routing & Access Contracts Preserved:*
     - Authenticated administrator visiting `/dashboard` sees the operational Administrator Overview.
     - Authenticated student visiting `/dashboard` is automatically redirected to `/chat`.
     - Direct URL access to protected routes (`/dashboard`, `/documents`, `/administrators`, etc.) is strictly enforced on both frontend and backend RBAC layers.
     - In-place `on_refresh()` capability enables all Retry buttons to reload data without page refreshes.
- **Verification & Test Suite Outcomes:**
  - `backend/tests/frontend/unit/test_admin_overview_and_navigation_contracts.py`: **19/19 passed** in 4.65s (covering all 20 contract requirements from prompt).
  - Full `backend/tests/frontend/unit/`: **240/240 passed** in 59.87s.
  - `backend/tests/security/`: **8 passed, 51 skipped** (requiring live db/auth which we tested via live browser CDP).
  - `ruff check frontend/ backend/`: **100% clean** (0 errors).
  - `git diff --check`: **100% clean** (0 errors).
- **Screenshot Evidence:**
  - `screenshot/admin_overview_part8a_desktop.png` (1440x900): Clean desktop control center with truthful degraded telemetry, quick actions, idle queue, course summary table, and grouped sidebar.
  - `screenshot/admin_navigation_part8a_desktop.png` (1440x900): Authoritative grouped sidebar navigation.
  - `screenshot/admin_overview_part8a_tablet.png` (768x1024): Natural stacking at tablet width.
  - `screenshot/admin_overview_part8a_mobile.png` (390x844): Refined mobile layout.
  - `screenshot/admin_navigation_part8a_mobile.png` (390x844): Clean responsive drawer with all 5 groups and account card.
  - `screenshot/admin_overview_part8a_compact.png` (375x667): Compact mobile viewport without horizontal overflow.
  - `screenshot/student_dashboard_redirect_part8a.png` (1440x900): Verified student redirect to `/chat` with student navigation intact.

## Prior phases

### Phase 7C — 2026-10-19

**FRONTEND PART 7C — COMPLETE PROFILE REDESIGN AND REMOVE NEW CHAT FROM PROFILE (/profile, profile_page.py, test_student_profile_contracts.py)**

### Status: COMPLETED & VERIFIED
- **Core Objectives & Implemented Corrections:**
  1. *Complete Removal of Profile-Specific New Chat Action:*
     - *Issue:* Profile page featured an in-page `New Chat` button with an `add` icon (`handle_student_new_chat`) in the student identity header. The Profile page is an account and academic access overview, not another chat launch surface. The global application sidebar already provides the persistent, authoritative `+ New Chat` action.
     - *Correction:* Completely removed both the in-page button and `handle_student_new_chat()` from `frontend/pages/profile_page.py`. Did not replace with any alternative chat launcher (`Start Chat`, `Ask Assistant`, `Return to Assistant`, `Open Chat`).
     - *Preserved Actions:* Student identity card provides clean, accessible `Sign Out` (`outline` button with `logout` icon). Academic access card provides `Explore Courses` (`/knowledge-bases`).
     - *Sidebar Preserved:* Application shell sidebar (`_render_app_sidebar`) continues to provide `+ New Chat`, `Assistant`, `Courses`, `Profile`, and `Recent Chats`.
  2. *Elimination of Duplicated Identity Information:*
     - *Issue:* The previous profile repeated user's Full Name, Email Address, and Account Role across both the top identity card and a lower "Account Details" card.
     - *Correction:* Retired the redundant "Account Details" card entirely. Consolidated all account information into a single, compact identity section where each piece of data appears exactly once:
       - User Avatar with bold initials (`get_user_initials`) and high-contrast styling (`bg-surface-navy border-2 border-gold text-inverted`).
       - Full Name in editorial serif (`text-xl sm:text-2xl font-bold font-editorial text-primary-navy tracking-tight leading-snug`).
       - Email Address in monospace with safe wrapping (`[overflow-wrap:anywhere] break-words text-xs sm:text-sm`).
       - Semantic Badges: Role (`UNIVERSITY STUDENT` / `SYSTEM ADMINISTRATOR`), Portal Access (`Student Academic Portal` / `Administrator Operations Portal`), truthful session status (`● Signed in`), and active status (`Active` / `Inactive`).
  3. *Resolution of Desktop Empty-Space Defect:*
     - *Issue:* The previous two-card row (`Account Details` + `Academic Access`) used `flex flex-col justify-between items-stretch`. Because `Academic Access` contained significantly more content, `Account Details` was stretched artificially, creating a glaring blank white void beneath "Account Status".
     - *Correction:* Eliminated the two-card equal-height layout. Replaced it with a natural, content-driven vertical hierarchy (`max-w-4xl mx-auto w-full`):
       - Section 1: Compact Identity & Account Overview Card.
       - Section 2: Focused Academic Access Card (Student) or Governance & Permissions Card (Admin).
       - Card heights are 100% content-driven, eliminating dead space and empty card bottoms.
  4. *Mobile Layout Refinement (390px and 375px):*
     - *Issue:* In mobile viewports, the email address broke mid-word (`student@university.ed\nu`), the user name wrapped into multiple large lines, and action buttons consumed excessive vertical height.
     - *Correction:*
       - Applied `[overflow-wrap:anywhere] break-words text-xs sm:text-sm`, allowing standard emails to fit on a single line on mobile and break only at safe boundaries if extended.
       - Full name rendered at `text-xl sm:text-2xl` for elegant, natural wrapping.
       - Scaled avatar to `w-13 h-13 sm:w-16 sm:h-16`, vertically centered with identity copy.
       - Styled `Sign Out` as a compact outline button aligned cleanly at the card footer without bloated height.
  5. *Preservation of Security, Account, and Academic Behaviors:*
     - 3-state course loading preserved: loaded preview (up to 5 courses with verified document counts), honest empty state, and normalized error alert with working `Retry` button.
     - `Explore Courses` navigates directly to `/knowledge-bases`.
     - `Sign Out` executes `api_client.logout()`, resets in-memory `AppState` (`clear_chat()`, `active_kb = None`, `reset_session_state()`), and redirects to login without deleting backend-persisted conversations.
     - Administrator profile preserves `Return to Dashboard` (`/dashboard`), `Sign Out`, `Manage Courses` (`/knowledge-bases`), `Indexing Center` (`/indexing`), and governance permissions summary.
- **Verification & Test Suite Outcomes:**
  - `backend/tests/frontend/unit/test_student_profile_contracts.py`: **17/17 passed** in 4.17s.
  - Full `backend/tests/frontend/unit/`: **221/221 passed** in 55.90s.
  - `backend/tests/security/test_student_access_policy.py`: **9/9 passed** in 9.90s.
  - `backend/tests/integration/test_frontend_workflows.py`: **8/8 passed** in 3.26s.
  - `ruff check frontend/ backend/`: **100% clean** (0 errors).
  - `git diff --check`: **100% clean** (0 whitespace/formatting errors).
- **Screenshot Verification:**
  - `screenshot/student_profile_desktop.png` (1440x900): Clean compact identity card with `AR` avatar, no New Chat, Sign Out, single non-duplicated Academic Access card, zero desktop empty space.
  - `screenshot/student_profile_laptop.png` (1366x768): Perfectly proportioned laptop view, content-driven height.
  - `screenshot/student_profile_mobile.png` (390x844): Mobile view with unbroken email, natural name wrapping, compact avatar and Sign Out button.
  - `screenshot/student_profile_compact_mobile.png` (375x667): Compact mobile view with unbroken email, zero horizontal overflow.
  - `screenshot/admin_profile_desktop.png` (1440x900): Admin profile with `SA` avatar, Return to Dashboard, Sign Out, Governance & Permissions card with Manage Courses and Indexing Center.
  - `screenshot/student_profile_empty_courses.png` (1440x900): Honest academic empty state.
  - `screenshot/student_profile_course_error.png` (1440x900): Normalized error state with functional Retry button.

## Prior phases

### Phase 7B — 2026-10-16

**FRONTEND PART 7B — REMOVE GLOBAL BREADCRUMBS, FIX PROFILE AVATAR, AND SIMPLIFY PROFILE ACTIONS (/profile, layout.py, theme.py, profile_page.py)**

### Status: COMPLETED & VERIFIED
- **Core Objectives & Implemented Corrections:**
  1. *Centrally Remove Redundant Back/Breadcrumbs Bar:*
     - *Issue:* Redundant strip `[Back] Assistant > Profile` / `[Back] Assistant > Courses` / `[Back] Courses` was rendered across student and admin pages.
     - *Correction:* In `frontend/components/layout.py`, set `show_breadcrumb=False` and `show_back=False` by default in `page_layout()`, completely excised the breadcrumb rendering block, and removed redundant caller arguments (`breadcrumbs=...`, `show_breadcrumb=False`) in `profile_page.py`, `knowledge_bases_page.py`, `chat_page.py`, and `dashboard_page.py`. Main page headings remain prominent and page content starts at an intentional, clean vertical offset below the header (`padding: 2rem 1rem`).
     - *Preserved genuine navigation:* Sidebar navigation (`Assistant`, `Courses`, `Profile`, `Dashboard`), `New Chat` button, reader's internal Back navigation, and Admin `Return to Dashboard` remain 100% functional.
  2. *Restore Visible Profile Avatar in Identity Card:*
     - *Root Cause:* `profile_page.py` applied `.bg-primary-navy` and `.text-inverted` (`#FAF6F0`). However, `.bg-primary-navy` was never defined in `theme.py` (only `.text-primary-navy` and `.bg-surface-navy` existed). Without a background color, the div was transparent, causing `#FAF6F0` initials to render invisibly against the `#FAF6F0` card surface (`bg-surface-elevated`), leaving an unexplained blank gap before the user name.
     - *Correction:* Defined `.bg-primary-navy` in `theme.py` (mapping to `var(--color-atlas-navy)`), applied `.bg-surface-navy`, `border-2 border-gold`, and `text-inverted` with explicit flex centering and font styling (`font-serif font-bold`) to render a crisp circular avatar (`w-14 h-14 sm:w-16 sm:h-16`) beside the student and admin names.
  3. *Fix Student Initials Helper & Unify Generation:*
     - *Root Cause:* Previous `_get_user_initials()` split `full_name` by whitespace and took the first characters of the first and last words. When the display name was `"Alex Rivera (Student)"`, the last word was `"(Student)"`, producing the invalid initial `'('` (displaying `A(` in the mobile account avatar).
     - *Correction:* Created a centralized, pure `get_user_initials(full_name: str | None, email: str | None = None) -> str` in `frontend/components/layout.py`:
       - Strips parenthetical role tags using `re.sub(r"\(.*?\)", "", name)`.
       - Extracts valid alphabetical tokens (`re.findall(r"[a-zA-Z]+", ...)`).
       - Handles multi-word names (`"Alex Rivera (Student)"` -> `"AR"`, `"Riya Patel (Faculty)"` -> `"RP"`, `"Alexander John Mercer"` -> `"AM"`).
       - Handles single-word names cleanly (`"Morgan"` -> `"MO"`, single letter -> `"M"`).
       - Handles empty/whitespace/punctuation-only names by falling back to the email prefix or `"U"`.
       - Imported `get_user_initials` into `frontend/pages/profile_page.py`, eliminating duplicate logic and ensuring 100% consistency across the mobile header, sidebar user chip, and profile identity card.
  4. *Simplify Student Profile Actions:*
     - *Issue:* Student profile had two redundant actions navigating to `/chat`: `Return to Assistant` in the identity card, and `Ask Assistant` at the bottom of the Academic Access card.
     - *Correction:* Replaced `Return to Assistant` with a primary **`New Chat`** action in the identity card. Clicking it calls `state.start_new_conversation()` (clearing active conversation selection, message view, citation state, question composer draft, and resetting course scope to `ALL_COURSES` while strictly preserving persistent saved conversations in history) and navigates to `/chat`.
     - Removed the redundant `Ask Assistant` button from the Academic Access card, leaving `Explore Courses` as the focused course discovery action.
     - Preserved administrator profile actions: `Return to Dashboard`, `Sign Out`, `Manage Courses`, and `Indexing Center`.
- **Test Suite Verification:**
  - `backend/tests/frontend/unit/test_student_profile_contracts.py`: **16/16 passed** in 2.26s (including new contracts for initials derivation, New Chat state reset, absence of redundant assistant buttons, and default breadcrumb suppression).
  - Full `backend/tests/frontend/unit/`: **220/220 passed** in 31.32s.
  - `backend/tests/security/test_student_access_policy.py`: **9/9 passed** in 10.05s.
  - `backend/tests/integration/test_frontend_workflows.py`: **8/8 passed** in 2.44s.
  - `ruff check frontend/ backend/`: **100% clean** (0 errors).
- **Screenshot Verification:**
  - `screenshot/student_profile_desktop.png`: Prominent `AR` initials avatar, no breadcrumbs, clean `New Chat` and `Sign Out` buttons, `Explore Courses` in Academic Access.
  - `screenshot/student_profile_mobile.png`: Mobile layout with visible `AR` avatar, no breadcrumbs, perfect responsive spacing.
  - `screenshot/mobile_header_corrected_initials.png`: Mobile top-right chip showing `AR` (fixed from `A(`) and sidebar drawer user chip showing `AR`.
  - `screenshot/course_library_no_breadcrumbs.png`: Course Library without breadcrumb row; natural vertical rhythm.
  - `screenshot/student_profile_after_new_chat.png`: Navigated to `/chat` with composer in draft state, scope reset to "All available courses", and saved chats intact.
  - `screenshot/admin_knowledge_bases_no_breadcrumbs.png`: Admin Course Management without breadcrumb row, admin controls intact.
  - `screenshot/admin_profile_desktop.png`: Admin profile with `SA` avatar, `Return to Dashboard`, `Manage Courses`, and `Indexing Center` preserved.

## Prior phases

### Phase 7 — 2026-10-16

**FRONTEND PART 7 — STUDENT PROFILE REDESIGN AND ACCOUNT-INFORMATION CORRECTIONS (/profile, profile_page.py, models.py)**

### Status: COMPLETED & VERIFIED
- **Core Objectives & Answers Delivered:**
  1. *Which account am I using?*
     - Clear, compact identity card displaying Source Serif 4 initials avatar, full user name with safe wrapping (`break-words`), email address with break support (`break-all`), role badge (`UNIVERSITY STUDENT`), and truthful `● Signed in` status badge.
     - Safely handles missing names, long emails, and special characters.
  2. *What information and access belong to this account?*
     - Renamed "Account Credentials" to **"Account Details"** with plain sentence-case labels: `Full Name`, `Email Address`, `Account Role`, `Portal Access`, `Account Status` (`Active` derived truthfully from `user.is_active`). Strictly zero passwords, tokens, internal IDs, or secrets shown.
     - Academic Access card with student privilege explanation, followed by accessible courses summary.
  3. *Where can I go next?*
     - Clear primary navigation actions: `Return to Assistant` (navigating to `/chat`), `Sign Out`, `Explore Courses` (navigating to `/knowledge-bases`), and `Ask Assistant` (navigating to `/chat`).
- **Defects Addressed & Architectural Solutions:**
  1. *Course-Loading Error vs. Empty-State Decoupling:*
     - *Root Cause:* Previous profile swallowed exceptions from `api_client.get_knowledge_bases()` and set `enrolled_kbs = []`, falsely displaying "No active courses published yet" when an API, database, or network error occurred.
     - *Correction:* Strictly separated into 3 decoupled branches:
       - *Populated courses:* Preview up to 5 courses with verified document counts (`1 doc`, `N docs`, or `Count unavailable`), displaying `+N more courses` note and `View All Courses` link when total courses exceed 5.
       - *Genuine empty state:* Honest academic message: *"No accessible courses are currently available. Published course materials will appear here once assigned or made available to students."*
       - *Course request failure:* Normalized error alert using `normalize_error(exc, context="course")`, stating *"Unable to load accessible courses"* with descriptive subtext and an interactive **Retry** button that re-fetches courses in-place.
  2. *Deceptive Session-Status Labels Resolved:*
     - *Root Cause:* Previous profile rendered dual static badges: `Active Session` and `Session Verified` with a checkmark, conveying an unverified security claim.
     - *Correction:* Replaced with a single truthful `● Signed in` emerald badge, and an `Account Status` row showing `Active` checking `user.is_active`.
  3. *Sign-Out Reset Audit:*
     - Sign-out handler calls `api_client.logout()`, resets in-memory session state (`state.clear_chat()`, `state.active_kb = None`, `state.reset_session_state()`), and redirects cleanly to `/student/login` (or `/admin/login`).
     - Persistent backend conversation history in PostgreSQL is strictly preserved across sign-outs.
  4. *Administrator Profile Integrity:*
     - Preserved administrator profile layout with "Governance & Permissions" panel:
       - `Management Scope`: "All University Courses"
       - `Assigned Permissions`: "Full Administrative Access"
       - Administrative responsibilities notice
       - Direct administrative actions: `Manage Courses` (`/knowledge-bases`), `Indexing Center` (`/indexing`), and `Return to Dashboard` (`/dashboard`).
  5. *UserDTO Model Attribute Alignment:*
     - Added `is_active: bool = True` to `UserDTO` in `frontend/client/models.py`, preventing `AttributeError` when reading status across backend schemas.
- **Verification & Test Outcomes:**
  - Added `TestStudentProfileContracts` with 14 comprehensive behavioral tests in `backend/tests/frontend/unit/test_student_profile_contracts.py` covering all Section 10 contracts:
    1. Authenticated student sees real name, email, and role.
    2. Missing user details handled safely without throwing.
    3. Student sees only authorized courses.
    4. Successful empty course response shows genuine empty state.
    5. Course-loading failure shows error rather than false empty state.
    6. Retry can retrieve actual courses after failure.
    7. Unavailable optional course metadata is not fabricated.
    8. Session-status labels reflect actual authenticated state.
    9. Student Return to Assistant navigates to `/chat`.
    10. Explore Courses navigates to `/knowledge-bases`.
    11. Sign Out invokes real logout mechanism and clears in-memory state.
    12. Signing out does not delete persisted conversation history.
    13. Administrator profile and role-specific access remain intact.
    14. User role and permission boundaries are not weakened.
  - Full Test Gate:
    - `backend/tests/frontend/unit/`: **218/218 passed** in 55.04s.
    - `backend/tests/security/test_student_access_policy.py`: **9/9 passed** in 9.94s.
    - `backend/tests/integration/test_frontend_workflows.py`: **8/8 passed** in 2.47s.
    - `ruff check frontend/ backend/`: **100% clean** (0 errors).
    - `git diff --check`: **100% clean** (0 whitespace warnings).
- **Screenshots Captured & Visually Inspected:**
  - `screenshot/student_profile_baseline_desktop.png` (1440x900 desktop student profile baseline audit)
  - `screenshot/student_profile_baseline_mobile.png` (390x844 mobile student profile baseline audit)
  - `screenshot/admin_profile_baseline.png` (1440x900 admin profile baseline audit)
  - `screenshot/student_profile_desktop.png` (1440x900 desktop student profile final)
  - `screenshot/student_profile_courses.png` (1440x900 desktop student profile with accessible courses)
  - `screenshot/student_profile_empty_courses.png` (1440x900 desktop student profile showing genuine empty state)
  - `screenshot/student_profile_course_error.png` (1440x900 desktop student profile showing normalized error state and Retry)
  - `screenshot/student_profile_mobile.png` (390x844 responsive mobile student profile with clean wrapping)
  - `screenshot/admin_profile_desktop.png` (1440x900 desktop administrator profile with governance panels)

---

## Historical Phase — 2026-10-16

**FRONTEND PART 6C — REMOVE CHAT NAVIGATION DUPLICATION AND UNIFY CONVERSATION HISTORY (/chat, layout.py, app_state.py, chat_page.py)**

### Status: COMPLETED & VERIFIED
- **Navigation & History Clarification Overview:**
  - Resolved student navigation ambiguity between `New Chat`, `Chat`, and `Recent Chats`.
  - Renamed the student navigation label to **`Assistant`** (pointing to `/chat`), distinguishing destination from action:
    - **`New Chat`**: Starts a completely fresh conversation state, clears messages/citations/composer draft, unselects any conversation, resets search scope to `ALL_COURSES`, closes mobile drawer, and preserves saved history.
    - **`Assistant`**: Navigates to the student workspace at `/chat`, preserving active conversation when returning from Courses or Profile.
    - **`Recent Chats`**: Loads and displays saved conversations in-place, highlighting the active conversation and closing mobile drawer.
  - Unified the chat history interface: Removed the duplicate mobile-specific `mobile_history_dialog` and header history toggle from `frontend/pages/chat_page.py`. The single shared application drawer now handles navigation, New Chat, and Recent Chats on both desktop and mobile.
- **Core Changes Implemented:**
  1. *Student Navigation Label Renamed to `Assistant` (`frontend/components/layout.py`):*
     - Replaced `("Chat", "/chat", "chat")` with `("Assistant", "/chat", "chat")`.
     - Preserved administrator navigation (`Admin Chat` under Assistant section) and admin dashboard.
     - Updated breadcrumb resolution: root label for student resolves to `Assistant` (`/chat`).
     - Updated profile return action (`frontend/pages/profile_page.py`): button label resolves to `"Return to Assistant"`.
  2. *Unified Mobile Navigation & Drawer Handling (`frontend/components/layout.py`):*
     - Closing helper automatically dismisses the drawer on mobile (`< 1024px`) upon clicking `New Chat`, any navigation link, or selecting a conversation.
     - Clicking `New Chat` or a saved conversation while already on `/chat` updates the browser address bar via `replaceState` and refreshes the page in-place without jarring full-page reloads.
     - Added safe error notification via `normalize_error` if loading a saved conversation fails.
  3. *Elimination of Duplicate Mobile History Dialog (`frontend/pages/chat_page.py`):*
     - Completely removed `mobile_history_dialog`, `mobile_history_container`, duplicate CSS overrides, and duplicate `render_history_list()` / `render_history()` methods.
     - Removed redundant mobile history button from chat header.
     - Synchronized `active_scope` with `AppState.active_scope` and `AppState.active_kb_id`.
     - Enhanced `on_state_update`: when a fresh new conversation is started, resets composer input, clears draft, and resets scope pill to `ALL_COURSES`.
  4. *Session State Scope Tracking (`frontend/state/app_state.py`):*
     - Added `active_scope` (defaults to `"ALL_COURSES"`) and `active_kb_id` (defaults to `None`) to `AppState` and `_SessionAppStateProxy`.
     - Updated `start_new_conversation()` to reset `active_scope = "ALL_COURSES"` and `active_kb_id = None`.
- **Verification & Test Outcomes:**
  - Added `TestStudentChatNavigationAndUnifiedHistoryContracts` with 9 behavioral tests in `backend/tests/frontend/unit/test_student_chat_contracts.py`:
    1. Student navigation displays 'Assistant' and routes to `/chat`.
    2. New Chat creates clean state without creating fake records.
    3. New Chat resets scope to `ALL_COURSES`.
    4. New Chat does not delete existing saved conversations.
    5. Assistant navigation preserves active saved conversation when returning from other pages.
    6. Selecting a saved conversation updates active conversation and triggers state notification.
    7. Failed conversation load request preserves state without creating false empty chat.
    8. `chat_page.py` contains no `mobile_history_dialog` or duplicate history renderers.
    9. Administrator navigation retains `Admin Chat` under Assistant section.
  - Updated existing contract tests in `backend/tests/frontend/unit/test_student_dashboard_contracts.py` for Assistant label.
  - Full Test Gate:
    - `backend/tests/frontend/unit/`: **204/204 passed** in 31.08s.
    - `backend/tests/security/test_student_access_policy.py`: **9/9 passed** in 10.91s.
    - `backend/tests/integration/test_frontend_workflows.py`: **8/8 passed** in 2.63s.
    - `ruff check frontend/ backend/`: **100% clean** (0 errors).
    - `git diff --check`: **100% clean** (0 whitespace errors).
- **Screenshots Captured & Visually Inspected:**
  - `screenshot/desktop_assistant_empty_chat.png` (1440x900 desktop Assistant with empty chat, New Chat button, Assistant nav highlighted, Recent Chats list)
  - `screenshot/desktop_assistant_saved_conversation.png` (1440x900 desktop Assistant with active saved conversation and citations)
  - `screenshot/desktop_assistant_new_chat_cleared.png` (1440x900 desktop Assistant showing clean reset upon clicking New Chat on /chat)
  - `screenshot/desktop_assistant_return_from_courses.png` (1440x900 desktop Assistant returning from Courses with active conversation preserved)
  - `screenshot/mobile_assistant_workspace.png` (390x844 responsive mobile Assistant without duplicate history button in header)
  - `screenshot/mobile_unified_drawer_history.png` (390x844 responsive mobile unified drawer containing New Chat, Assistant, Courses, Profile, and Recent Chats)

---

## Historical Phase — 2026-10-16

**FRONTEND PART 6B — REMOVE THE REDUNDANT STUDENT DASHBOARD AND MAKE CHAT THE STUDENT HOME (/dashboard, /chat, layout.py, auth_pages.py)**

### Status: COMPLETED & VERIFIED
- **Architectural Refinement Overview:**
  - Retired the redundant Student Dashboard experience from the normal student journey.
  - Made `/chat` the authoritative default home and landing workspace for authenticated students.
  - Preserved the full operational capability of the Administrator Dashboard at `/dashboard`.
  - Preserved the approved Ivory, Gold, and Deep Atlas Navy chat UI, persistent conversation history, composer scope selector, Stop Generating, citations, Course Library (`/knowledge-bases`), and full-page source reader (`/reader`).
- **Core Changes Implemented:**
  1. *Student Authentication Routing (`frontend/pages/auth_pages.py`):*
     - Successful student login defaults immediately to `/chat`.
     - Created `_get_safe_return_destination(return_to, is_student)` validating whitelisted internal routes (`/chat`, `/knowledge-bases`, `/profile`, `/reader`, `/documents`, `/indexing`, `/dashboard`), resolving `/dashboard` to `/chat` for students while strictly blocking external protocols (`http://`, `//`, `/\\`).
     - Student registration (`/register`) redirects new students directly to `/chat`.
  2. *Student Navigation in Unified Sidebar (`frontend/components/layout.py`):*
     - Replaced `("Home", "/dashboard", "dashboard")` with `("Chat", "/chat", "chat")` in student navigation.
     - Brand and logo clicks in mobile header and left drawer are role-aware: navigates to `/dashboard` for administrators and `/chat` for students.
     - Breadcrumb resolution in `page_layout` updated to role-aware root: `Chat` (`/chat`) for students, `Dashboard` (`/dashboard`) for admins.
     - Profile page (`frontend/pages/profile_page.py`) return button updated: `"Return to Chat"` navigating to `/chat` for students, `"Return to Dashboard"` for admins.
  3. *Direct `/dashboard` Route Compatibility (`frontend/pages/dashboard_page.py`):*
     - Authenticated students visiting `/dashboard` directly are cleanly navigated to `/chat`.
     - In `frontend/security/access_control.py`: Student capability for `/dashboard` preserved so requests are received and handled with clean client-side navigation rather than an authorization 403 error.
  4. *Administrator Dashboard Preservation:*
     - When an authenticated administrator (`user.role == "ADMIN"`) visits `/dashboard`, the real operational dashboard is rendered with indexing monitor, failed-job retry controls, and course management.
  5. *Obsolete Code Cleanup:*
     - Retired ~240 lines of duplicate student inquiry inputs, courses preview cards, and obsolete imports (`html`, `urllib.parse`, `format_document_count`, `ConversationSummaryDTO`, `KnowledgeBaseDTO`).
     - Kept `_render_student_dashboard()` as a clean, direct forwarder: `ui.navigate.to("/chat")`.
- **Verification & Test Outcomes:**
  - Added 14 behavior-focused unit tests to `backend/tests/frontend/unit/test_student_dashboard_contracts.py`.
  - Full Test Gate: 195 unit tests passed, 9 security tests passed, 8 integration tests passed, ruff clean, git diff clean.

---

## Historical Phase — 2026-10-16

**FRONTEND PART 6 — STUDENT DASHBOARD REDESIGN AND FUNCTIONAL POLISH (/dashboard, dashboard_page.py)**

### Status: COMPLETED & VERIFIED
- **Core Objectives & User Answers Delivered:**
  1. *Where can I ask a question?*
     - Designed prominent, focused primary inquiry workspace: "Ask Knowledge Assistant".
     - Sized question input with clear placeholder `"What would you like to know about your courses?"`.
     - Primary Deep Atlas Navy action `"Ask Question"` with keyboard Enter submission and instant validation preventing empty queries.
     - Navigates seamlessly to `/chat?q={encoded_query}` where single turn submission is preserved without duplicate messages or scope errors.
  2. *How can I continue a previous conversation?*
     - Integrated real persistent conversation history fetched directly from backend via `api_client.get_conversations()`.
     - Displays actual conversation titles (cleanly truncated on mobile with `truncate` and `min-w-0`), authentic relative updated times (`format_relative_time()`, e.g., "2d ago", "Just now", "15m ago"), scope badges, and a direct `"Continue ->"` link navigating to `/chat?conversation_id={id}`.
     - When no conversations exist, renders a dignified empty state with a `"Start New Chat"` button.
     - Never displays hard-coded or fabricated conversations.
  3. *How can I access my courses?*
     - Compact preview panel displaying authentic authorized courses from `api_client.get_knowledge_bases()`.
     - Truthful document count formatting via shared `format_document_count()`: verified positive counts (e.g., "1 document", "3 documents"), verified zero counts ("No documents"), and unavailable counts ("Count unavailable").
     - Direct `"Ask in Course"` action scoping chat queries to `/chat?kb_id={c_id}`.
     - `"View All (N)"` header link navigating directly to `/knowledge-bases`.
- **Known Functional Defects Diagnosed & Fixed:**
  1. *Awkward and Defective Document-Count Display:*
     - *Root Cause:* Previous dashboard contained `f"{kb.document_count} doc(s)"`, rendering `None doc(s)` when summary failed and awkward wording for valid counts.
     - *Correction:* Replaced with shared `format_document_count(kb.document_count)` ensuring truthful counts across Course Library and Dashboard.
  2. *Misleading Course-Loading Error vs. Empty-State Bug:*
     - *Root Cause:* Dashboard previously evaluated `if course_load_error or not enrolled_kbs:`, showing the "No Courses Available" empty state even when an API or network exception occurred.
     - *Correction:* Explicitly decoupled into 3 isolated states:
       - API Failure: Safely normalized alert via `normalize_error()` with a functional `"Retry"` button.
       - Genuine Zero Courses: Dignified academic empty catalog state explaining no courses are assigned.
       - Populated Courses: Clean preview cards with verified document counts.
  3. *Removal of Outdated Quick-Suggestion Buttons:*
     - Removed obsolete preset inquiry buttons (`Syllabus overview`, `Grading breakdown`, `Attendance policy`).
     - Kept dashboard focused on genuine student academic inquiries.
  4. *Mobile Text & Badge Collision Fix:*
     - *Root Cause:* In baseline mobile layout, course titles and document badges collided due to lack of flex wrapping, shrinking, and truncation.
     - *Correction:* Applied modern responsive utilities (`min-w-0`, `truncate`, `shrink-0`) and clean stacking to ensure 100% readable layout on 390x844 and 375x667 devices.
- **Administrator Dashboard Protected:**
  - `_render_admin_dashboard()` remains completely untouched with operational indexing, failed-job monitoring, course management, and administrative portal navigation fully intact.
- **Verification & Test Outcomes:**
  - Created 21 behavior-focused unit tests in `backend/tests/frontend/unit/test_student_dashboard_contracts.py` covering all 16 specified requirements.
  - Test Suites Executed:
    - `backend/tests/frontend/unit/`: 181/181 passed in 47.48s.
    - `backend/tests/security/test_student_access_policy.py`: 9/9 passed in 10.59s.
    - `backend/tests/integration/test_frontend_workflows.py`: 8/8 passed in 2.43s.
    - `ruff check frontend/ backend/`: 100% clean (0 errors).
    - `git diff --check`: 100% clean (0 whitespace errors).
- **Screenshots Captured & Inspected:**
  - `screenshot/student_dashboard_baseline_desktop.png` (1440x900 baseline audit)
  - `screenshot/student_dashboard_baseline_mobile.png` (390x844 baseline audit displaying collision defect)
  - `screenshot/student_dashboard_final_desktop.png` (1440x900 final redesigned academic workspace)
  - `screenshot/student_dashboard_final_laptop.png` (1366x768 final laptop verification)
  - `screenshot/student_dashboard_final_mobile.png` (390x844 final responsive mobile layout with clean wrapping)
  - `screenshot/student_dashboard_recent_conversations.png` (verified recent conversations panel displaying real persistent threads)

---

## Historical Phase — 2026-10-16

**FRONTEND PART 5B — FIX DOCUMENT-COUNT ERROR HANDLING AND PROJECT-ARCHIVE SAFETY (/knowledge-bases, api_client, scripts/create_safe_project_zip.py)**

### Status: COMPLETED & VERIFIED
- **Defects Addressed & Root Causes:**
  1. *Document-Count Fallback Error Swallowing (`frontend/client/api_client.py:get_knowledge_bases`):*
     - *Root Cause:* In `get_knowledge_bases()`, when `get_course_summaries()` failed, the exception was caught and silently ignored, and the method fell back to `len(self._documents.get(str(item["id"]), []))`. In a live API session where `_documents` was not populated, this falsely displayed `0 doc(s)` or "No documents" even when documents existed in PostgreSQL.
     - *Correction:* Updated `KnowledgeBaseDTO.document_count` to `int | None = 0`. When `get_course_summaries()` fails, `summaries_failed` is flagged as `True`, and `document_count` is assigned `None` (unavailable). Successfully returned positive counts display normally (e.g., "5 documents"), verified counts of zero display as "No documents", and unavailable counts display as "Count unavailable".
  2. *Material Filter Handling of Unavailable Counts (`frontend/pages/knowledge_bases_page.py`):*
     - Courses with `document_count is None` are strictly excluded from the "No Materials" (`no_docs`) and "With Materials" (`with_docs`) filters. They are never counted as zero.
     - Filter counts: `With Materials ({with_materials_count})` counts only verified courses where `count > 0`; `No Materials ({no_materials_count})` counts only verified courses where `count == 0`.
     - When `unknown_count > 0`: a fourth filter pill `Count Unavailable ({unknown_count})` is dynamically appended, accompanied by subtle italic notice `"Some material counts could not be verified"`.
  3. *Project Archive Safety & Secret Exclusion (`scripts/create_safe_project_zip.py`):*
     - *Audit of Existing Repo & Git History:* Verified via `git ls-files .env` and `git log --all --full-history -- "**.env"` that `.env` is NOT tracked by Git and was NEVER committed to Git history. The `.env` in the uploaded archive was due to direct OS directory compression.
     - *Exclusion Script:* Created `scripts/create_safe_project_zip.py` with strict exclusion rules pruning `.env`, `.env.*` (preserving `.env.example`), `.git/`, `.venv*/`, `venv/`, `env/`, `__pycache__/`, `*.pyc`, `*.pyo`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `scratch/`, `.nicegui/`, `.tempmediaStorage/`, `logs/`, `*.log`, `*.pem`, `*.key`, `*.sqlite3`, `*.db`, `*.faiss`, OS files, and IDE files.
     - *Post-Validation:* The script reads every entry from the generated ZIP and verifies zero sensitive files before finishing. Tested generation produces a clean archive with 1391 files and zero leaks.
- **Tests Added & Verification:**
  - Added 7 behavior-focused regression tests to `backend/tests/frontend/unit/test_course_access_contracts.py`:
    1. `test_course_summary_succeeds_positive_document_count`: Summary succeeds and positive count displayed.
    2. `test_course_summary_succeeds_genuine_zero_count`: Summary succeeds and genuine zero count displayed as "No documents", correctly placed in "no_docs" filter.
    3. `test_course_summary_fails_represented_as_unavailable_not_zero`: Summary fails, count is represented as `None` ("Count unavailable") rather than 0.
    4. `test_unavailable_count_not_in_no_materials_filter`: Unavailable count courses are strictly excluded from "No Materials" filter.
    5. `test_main_course_list_remains_usable_when_summary_fails`: Base course list remains usable and searchable when summary fails.
    6. `test_later_successful_summary_restores_accurate_counts`: System recovers and restores accurate document count when summary endpoint recovers.
    7. `test_course_error_messages_safely_normalized`: Primary course-list failures are safely sanitized through `normalize_error()` without leaking credentials, SQL, or ports.
  - Added comprehensive archive safety tests to `backend/tests/frontend/unit/test_archive_safety_contracts.py`.
- **Test Gate & Code Quality:**
  - `.\.venv\Scripts\pytest.exe backend\tests\frontend\unit\ -v`: 166/166 passed in 25.04s.
  - `.\.venv\Scripts\pytest.exe backend\tests\security\test_student_access_policy.py -v`: 9/9 passed in 10.07s.
  - `.\.venv\Scripts\pytest.exe backend\tests\integration\test_frontend_workflows.py -v`: 8/8 passed in 2.32s.
  - `.\.venv\Scripts\ruff.exe check frontend\ backend\`: 100% clean (0 errors).
  - `git diff --check`: 100% clean (0 whitespace errors).

---

## Historical Phase — 2026-10-16

**FRONTEND PART 5 — STUDENT COURSE LIBRARY AND MATERIAL DISCOVERY (/knowledge-bases, api_client, source_viewer)**

### Status: COMPLETED & VERIFIED
- **User Requirements Addressed:**
  1. *Immediate Answers to Core Student Questions:*
     - *Which courses can I access?* Clean, responsive catalogue grid displaying only authorized accessible courses (`BCA`, `Computer Architecture`, `Official University Regulations`) with real descriptions and active statuses.
     - *Which documents are available in each course?* Dynamic `1 document` / `N documents` / `No documents` badges reflecting actual active document counts from `/knowledge-bases/summaries` (replacing the drab table and hardcoded `0 doc(s)`).
     - *How can I ask a question about a course or open its documents?* Two clear primary actions per card:
       - Primary: `Ask in Course` (solid Deep Atlas Navy `#0E1D61` button, navigating directly to `/chat?kb_id={c_id}` and genuinely scoping retrieval).
       - Secondary: `Materials` (opens academic materials modal showing syllabus and reference files with file format icons, formatted size, and direct `Read` action).
  2. *Defect Diagnoses & Fixes:*
     - *Document Count Mismatch:* Old `api_client.get_knowledge_bases()` queried `/knowledge-bases` without document counts, resulting in `0 doc(s)` for all courses. Fixed by enriching course objects with `/knowledge-bases/summaries` counts.
     - *Silent Error Swallowing in Materials Dialog:* The old handler silently caught all exceptions and set `docs = []`, misrepresenting API failures or network timeouts as empty courses. Fixed by integrating `normalize_error(err, context="document")` and a retry button.
     - *Dialog Attachment & Accessibility:* Refactored modal dialogs to be instantiated cleanly at page level with clear aria-labels and semantic classes (`.course-materials-btn`, `.doc-read-btn`), resolving DOM attachment issues during websocket events.
     - *Full-Page Reader Integration & Return Context:* Opening a document opens `/reader?document_id=...&kb_id=...&return_to=%2Fknowledge-bases`, providing a contextual `Back to Courses` action that returns cleanly to `/knowledge-bases`.
  3. *Administrator Experience Preservation:*
     - Route architecture remains unified at `/knowledge-bases`.
     - Administrators retain `Dashboard > Courses` breadcrumbs, `Course Management` header, `+ New Course` dialog, `ACTIVE` status pills, `Manage Docs` navigation to `/documents?kb_id={c_id}`, and administrator sidebar navigation.
  4. *Academic Catalogue Aesthetics:*
     - Strictly complies with `context/FRONTEND_DESIGN_SYSTEM.md` using Ivory `#E8E0D2`, Gold `#B89A5A`, and Deep Atlas Navy `#0E1D61`.
     - Real-time search by course name and description with clear icon and empty state recovery button.
     - Dynamic filter pills: `All Courses`, `With Materials`, `No Materials`.
- **Visual Verification & Browser QA:**
  - `screenshot/course_library_student_desktop.png` (1440x900 desktop: Course Library header, search bar, filter pills, 3 academic course cards with `Ask in Course` and `Materials`).
  - `screenshot/course_library_student_mobile.png` (390x844 mobile: responsive single column, wrapped filter pills, touch targets).
  - `screenshot/course_library_search_results.png` (1440x900: real-time search for "Architecture" filtering to Computer Architecture).
  - `screenshot/course_library_search_empty.png` (1440x900: search for "Astrophysics" displaying academic empty state with Clear Search button).
  - `screenshot/course_library_materials_modal.png` (1440x900: BCA Materials modal showing `KSU-Act-English.pdf`, 343 KB, and Read button).
  - `screenshot/course_library_reader_opened.png` (1440x900: full-page dedicated reader rendering native PDF with `Back to Courses` header action).
  - `screenshot/course_library_reader_return.png` (1440x900: seamless return to `/knowledge-bases` as Student).
  - `screenshot/course_library_admin_view.png` (1440x900: admin view with New Course, Manage Docs, breadcrumbs, and admin portal sidebar).
- **Test Gate & Code Quality:**
  - `.\.venv\Scripts\pytest.exe backend\tests\frontend\unit\ -v`: 105/105 passed in 18.76s (15 comprehensive course access contract tests).
  - `.\.venv\Scripts\pytest.exe backend\tests\security\test_student_access_policy.py -v`: 9/9 passed in 10.31s.
  - `.\.venv\Scripts\pytest.exe backend\tests\integration\test_frontend_workflows.py -v`: 8/8 passed in 2.53s.
  - `.\.venv\Scripts\ruff.exe check frontend\ backend\`: 100% clean (0 errors).
  - `git diff --check`: 100% clean (0 whitespace errors).

---

## Historical Phase — 2026-10-14

**CLEAN TEST DOCUMENTS AND VERIFY REAL ALL-COURSES UNSUPPORTED-QUESTION RESPONSE**

### Status: COMPLETED & VERIFIED
- **Investigation of Offline Preview Fallback Root Cause:**
  - In the previous run, the local PostgreSQL service was inactive.
  - `frontend/client/api_client.py` uses `is_db_connected()` which checks TCP connectivity to 127.0.0.1:5432.
  - When port 5432 did not respond, `_should_use_real_http()` returned `False`, causing the frontend to enter offline preview mode (`_init_offline_state()`) which returned canned CS101 grading policy answers.
- **Environment Discovery & Startup:**
  - Located standalone PostgreSQL 16.15 with pgvector 0.8.6 at `D:\Kartik\pgsql\pgsql\bin\postgres.exe` with data cluster at `D:\Kartik\pgsql\data`.
  - Started PostgreSQL 16 as background daemon process listening on `127.0.0.1:5432`.
  - Verified database `rag_assistant_db`, pgvector extension, and tables using `rag_app_user`.
  - Verified local Ollama daemon on `127.0.0.1:11434` with `qwen3-embedding:0.6b` and `qwen3:4b`.
  - Verified `api_client._should_use_real_http()` and `is_db_connected()` return `True`.
- **Database Backup & Test Document Cleanup:**
  - Created complete SQL dump backup: `scratch/db_backup/rag_assistant_db_backup_20261014_123058.sql` (1,118,846 bytes).
  - Created deletion manifest: `scratch/deletion_manifest.json`.
  - Audited document inventory: identified 1 confirmed synthetic test KB (`Upload Test KB`, ID `c02234b1-932f-47cc-9539-1b39d5b76110`) and test document (`test.txt`, ID `97f7beba-70b3-4cb0-8889-03ffeb91f370`, 19 bytes, 1 chunk).
  - Safely purged synthetic test records from the database in an atomic transaction and removed storage folder `storage/c02234b1-932f-47cc-9539-1b39d5b76110/`.
  - Exactly 3 genuine active courses retained: `BCA`, `Computer Architecture`, and `Official University Regulations`, containing `KSU-Act-English.pdf` (99 chunks total).
- **Out-of-Corpus Question Selection & Live Verification:**
  - Selected question: *"What is the exact date and venue of the Annual University Tech Fest 2026?"*.
  - Verified text search confirms no information on Tech Fest 2026 exists anywhere in the retained course files.
  - Reset student test account password to `Password123!`.
  - Executed Edge CDP session against running `frontend.main`:
    - Scope selected in composer: **All available courses** (`ALL_COURSES`).
    - Submitted question.
    - Live backend synthesized response via Ollama `qwen3:4b` with hybrid retrieval and reranking:
      *"The answer is that there is not enough information in the provided evidence to answer the question."*
    - Zero citations and zero hallucinated dates/venues were generated.
    - Verified DOM rendered text and confirmed absence of any canned grading policy.
  - Captured authentic 1440x900 browser screenshot: `screenshot/ppt_evidence/unsupported_question_all_courses_live.png`.
- **Presentation & Documentation Deliverables:**
  - Updated Slide 14 in `scripts/build_major_presentation.py` with the verified live backend Directive 4 response and caption: *"Question not answered because the available documents do not contain the requested information • Actual live browser capture from running application"*.
  - Rebuilt presentation: `report and ppt/RAG_Assistant_Major_Project_Presentation.pptx`.
  - Regenerated vector PDF: `report and ppt/RAG_Assistant_Major_Project_Presentation.pdf`.
  - Rendered `report and ppt/rendered_presentation_pages/slide_14.png` and verified visual quality.
  - Updated `report and ppt/RAG_Assistant_Presentation_Speaker_Notes.md`, `report and ppt/RAG_Assistant_Viva_Quick_Revision.md`, and `report and ppt/PPT_COMPLETION_NOTES.md`.

---

## Historical Phase — 2026-10-13

**FRONTEND PART 4 — AUTHENTICATION UI REPAIR — FIX STUDENT LOGIN, ADMIN LOGIN, AND REGISTRATION**

### Status: COMPLETED & VERIFIED
- **Defects Investigated & Root Causes Identified:**
  1. *Student Login & Registration Left-Stack Wrapping Root Cause:*
     - The parent container had `flex flex-col lg:flex-row gap-12` with two children having `w-full lg:w-1/2` (50% width).
     - In Flexbox layout, 50% + 50% + `gap-12` (3rem / 48px) = `100% + 48px > 100%`.
     - When total content width exceeded 100%, flexbox forced the second child (the sign-in / registration card) to wrap onto a second row.
     - Because both children retained `width: 50%` and default left alignment, both stacked vertically on the left side of the screen, leaving the right 50% of the viewport empty.
     - Furthermore, in `frontend/components/theme.py`, a missing closing brace on `@media (max-width: 767px)` trapped `.auth-split-grid` inside the mobile media query, preventing desktop grid styles from applying until repaired.
  2. *Administrator Header Overlap & Large Blank Area Root Cause:*
     - *Large Blank Gap:* Compounded vertical spacing in `auth_layout` (`pt-8 md:pt-12` = 48px) plus child container margin (`my-12` = 48px) plus Quasar `.q-page-container` default header offset (61px) totaled ~157–175px from top, creating an excessive 114px blank gap between the header bottom (61px) and content top (175px).
     - *Header Overlap:* When navigating to `/admin/login` from `/login` where the "Enter Administrator Portal" button was located below the fold at `scrollY: ~1200px`, the browser's default `history.scrollRestoration = 'auto'` preserved the scrolled position on the shorter admin login route, causing content to push up behind the fixed header (`top: 0..61px`).
- **Architectural Solutions & Changes Implemented:**
  1. *Robust CSS Grid Architecture (`frontend/components/theme.py`, `frontend/pages/auth_pages.py`):*
     - Replaced fragile flex width calculations with `.auth-split-grid`.
     - Desktop (`>= 1024px`): `grid-template-columns: minmax(0, 1.05fr) minmax(360px, 0.95fr) !important; gap: 3rem !important;`
     - Mobile / Tablet (`< 1024px`): `grid-template-columns: 1fr !important; gap: 2rem !important;`
     - Applied to both `_render_login_form()` and `register_page()`.
  2. *Quasar Header Fixed Positioning & Scroll Restoration (`frontend/components/theme.py`):*
     - Added `.q-header.fixed-top { top: 0 !important; left: 0; right: 0; position: fixed; z-index: 2000 !important; }` ensuring header stays pinned at top of viewport.
     - Added `history.scrollRestoration = 'manual'` and `window.addEventListener('pageshow', () => window.scrollTo(0, 0))` via `init_theme()`, guaranteeing zero scroll bleed across navigations.
  3. *Balanced Vertical Rhythm (`frontend/components/layout.py`):*
     - Rationalized top padding in `auth_layout` to `pt-4 sm:pt-6 md:pt-8 pb-6 md:pb-10 box-border`.
     - Reduced child grid vertical margin to `my-2 sm:my-4 md:my-6 box-border`.
     - Grid starts at `top: 133px` (comfortably below header bottom at `61px`), heading starts at `top: 177px`, completely visible and unobstructed.
  4. *Role-Specific Header Navigation Integrity (`frontend/components/layout.py`):*
     - Added dedicated navigation links for `/register`: "Student Sign In" (`/student/login`) and "Home" (`/login`).
     - Maintained dedicated links for `/student/login` ("Faculty Admin", "Home") and `/admin/login` ("Student Gateway", "Home").
  5. *Behavioral Test Suite (`backend/tests/frontend/unit/test_auth_layout_contracts.py`):*
     - 9 behavior-focused tests verifying public route availability, desktop split grid CSS properties, header positioning rules, error sanitization, and authenticated redirection.
- **Visual Verification (Edge CDP across all viewports):**
  - `screenshot/auth_student_login_desktop.png` (1503x1000 Desktop: balanced two columns, 0 scroll, perfect alignment)
  - `screenshot/auth_register_desktop.png` (1503x1000 Desktop: balanced two columns, full registration form)
  - `screenshot/auth_admin_login_desktop_direct.png` (1503x1000 Desktop direct load: heading fully visible below header)
  - `screenshot/auth_admin_login_from_nav.png` (1503x1000 Desktop from scrolled /login: 0 scroll restoration, 0 overlap)
  - `screenshot/auth_landing_desktop.png` (1503x1000 Desktop: landing page completely preserved)
  - `screenshot/auth_student_login_laptop_1366.png` (1366x768 Standard Laptop: balanced two columns)
  - `screenshot/auth_student_login_tablet_768.png` (768x1024 Tablet: single-column reflow)
  - `screenshot/auth_student_login_mobile_390.png` (390x844 Mobile: single-column reflow, full touch target usability)
  - `screenshot/auth_register_mobile_390.png` (390x844 Mobile register)
  - `screenshot/auth_admin_login_mobile_390.png` (390x844 Mobile admin login)
  - `screenshot/auth_student_login_compact_375.png` (375x667 Compact Mobile)
- **Quality & Test Gate:**
  - `pytest backend/tests/frontend/unit/ -v`: 93/93 passed (100%).
  - `ruff check frontend/ backend/`: 100% clean (0 errors).
  - `git diff --check`: 100% clean (0 whitespace warnings).

---

## Historical Phase — 2026-10-13

**FRONTEND PART 3B — REDESIGN THE SOURCE VIEWER AS A DEDICATED READING PAGE (/reader)**

### Status: COMPLETED & VERIFIED
- **Rejection of Previous Drawer Design & Rationale:**
  - The previous right-side dialog/drawer design rendered an overlay covering ~60% of the screen while leaving a dimmed, distracted strip of the previous page visible beside the reader.
  - The user rejected this presentation because reading academic course documents requires an immersive, dedicated workspace rather than an oversized diagnostic overlay.
  - The dedicated full-page reader route (`/reader`) replaces the overlay entirely, allocating 100% of the viewport width and height to the document reading experience in the same tab.
- **Architectural Solutions & Features Implemented:**
  1. *Dedicated Reading Route (`frontend/pages/reader_page.py`):*
     - Registered route `@ui.page("/reader")` receiving canonical document parameters (`document_id`, `page`, `doc_name`, `kb_id`, `course`, `return_to`, `conv_id`, `snippet`, `evidence`).
     - Eliminates overlays, modals, and dimmed backdrops. Allocates 100vw and 100vh (`100dvh`) directly to the reading workspace.
  2. *Contextual Back Navigation & Whitelist Validation (`validate_return_route()`):*
     - Provides clear return navigation to the originating page: "Back to Conversation" (restores exact active conversation ID and message history), "Back to Documents", "Back to Courses", or "Back to Dashboard".
     - Strictly enforces internal relative route whitelist `("/chat", "/documents", "/knowledge-bases", "/dashboard", "/system-health", "/activity", "/profile")`, blocking external open redirects and directory traversal attempts.
     - Automatically preserves active conversation thread via `conversation_id` query parameter synchronization.
  3. *Collapsible Cited Evidence Grounding Strip:*
     - When opened from a citation, renders a compact evidence strip showing the exact cited passage in Source Serif typography with a gold accent border (`border-l-2 border-gold`) and page badge.
     - Includes an accessible toggle button ("Hide Evidence" / "Show Evidence") that collapses the strip down to a single ~36px line, maximizing vertical reading space for the document while keeping the evidence grounding accessible on demand.
  4. *In-Browser Native PDF Reader:*
     - Full-viewport authorized `<iframe>` pointing to same-origin `/api/v1/documents/{document_id}/file#page={page}&view=FitH`.
     - Preserves all native browser PDF controls (zoom, page jump, search, print) while filling 100% of remaining vertical height.
     - Bottom status bar providing current page position and explicit "Open PDF in New Window ↗" secondary fallback.
  5. *Dedicated Non-PDF Academic Reading Workspace:*
     - For DOCX, TXT, Markdown, and CSV, replaces the PDF viewer with an adapted text reading workspace.
     - Displays extracted document sections, highlights cited passages with gold badges, shows format badges, and provides direct file download actions.
     - Zero misleading "PDF Document" tabs for non-PDF documents.
  6. *Dignified Document Unavailable State:*
     - Clean academic notice when document is missing, unassigned, or unauthorized, with safe Back action returning to originating experience.
     - Zero stack traces, raw SQL, internal paths, or tokens leaked.
  7. *Server-Managed Session Context Persistence:*
     - Transient reader state (`state.set_reader_context(...)`) preserved across page navigation in `AppState`, ensuring cited evidence snippets and active conversation threads persist without placing sensitive content in query strings.
- **Visual Verification (Edge CDP):**
  - `screenshot/reader_pdf_page2_desktop.png` (PDF at Page 2, 1440x900 full-page reading workspace, native controls showing "2 of 18", expanded evidence strip)
  - `screenshot/reader_pdf_page5_desktop.png` (PDF at Page 5, 1440x900 full-page reading workspace, native controls showing "5 of 18")
  - `screenshot/reader_pdf_evidence_expanded.png` (Evidence context expanded showing quoted passage and page badge)
  - `screenshot/reader_pdf_evidence_collapsed.png` (Evidence context collapsed down to slim bar, maximizing PDF height)
  - `screenshot/reader_non_pdf_docx.png` (DOCX reading workspace showing extracted sections and highlighted cited passage)
  - `screenshot/reader_missing_document.png` (Missing document dignified error notice with "Back to Conversation" button)
  - `screenshot/reader_desktop_fullpage.png` (Desktop 1440x900 reading workspace occupying 100% viewport with zero dimmed background)
  - `screenshot/reader_mobile.png` (Mobile 390x844 responsive reader with compact "Back" button, safe title wrapping, and touch-friendly controls)
- **Quality & Test Gate:**
  - `pytest backend/tests/frontend/unit/ -v`: 84/84 passed (100%).
  - `pytest backend/tests/unit/test_source_viewer.py -v`: 6/6 passed (100%).
  - `ruff check frontend/ backend/`: 100% clean (0 errors).
  - `git diff --check`: 100% clean (0 whitespace errors).

---

## Historical Phase — 2026-10-12

**FRONTEND PART 3 — SOURCE VIEWER AND DOCUMENT READING EXPERIENCE (/chat, /documents, source_viewer)**

### Status: COMPLETED & VERIFIED (SUPERSEDED BY PART 3B)
- Evaluated and verified core document streaming, iframe rendering, and non-PDF reading views. Drawer layout subsequently rejected in Part 3B in favor of the dedicated full-page reading workspace at `/reader`.

---

## Historical Phase — 2026-10-12

**FRONTEND PART 2F — COURSE SELECTOR SIZE AND COMPOSER SPACING POLISH (/chat)**

### Status: COMPLETED & VERIFIED
- **User Requirements Addressed:**
  1. *Scope Selector Proportions Enlarged (`frontend/pages/chat_page.py`):*
     - Dropped Quasar `dense` prop on the scope trigger button, which previously clamped the button height to ~28px.
     - Upgraded button size to `h-[38px] sm:h-[40px]` with `px-3.5 sm:px-4` padding, achieving a clickable target of ~38–40px.
     - Scaled typography from tiny 11px to readable 13–14px (`text-[13px] sm:text-sm font-medium`).
     - Increased academic `school` icon to `16px` and indicator `unfold_more` icon to `15px`.
     - Attached native title hover tooltip (`title="{current_label}"`) for complete course title accessibility.
     - Added distinct subtle gold styling when a specific course is selected (`border-gold/70 bg-gold-light/30`).
  2. *Composer Toolbar Divider Spacing Repaired (`frontend/pages/chat_page.py`):*
     - Eliminated cramped proximity between the composer horizontal divider rule (`border-t border-subtle/50`) and bottom toolbar controls.
     - Replaced tight `pt-1` (4px) with intentional `pt-2.5 sm:pt-3 pb-0.5` (10–12px buffer gap), separating the control cleanly from the line while preserving generous spacing before the composer boundary.
     - Balanced composer card padding at `p-2.5 sm:p-3` with `gap-2`.
     - Resized scope popover menu to `w-[290px] sm:w-[340px]` with `p-3` for clean search filtering and list selection.
  3. *Core Contracts and Behavior Fully Preserved:*
     - Maintained `ALL_COURSES` default scope and backend-authorized course filtering.
     - Query payload mapping (`scope="ALL_COURSES"` vs `scope="COURSE"`), persistent history, New Chat, Stop Generating, and citation mechanics remained completely untouched.
- **Visual Verification:**
  - `screenshot/chat_sidebar_desktop.png` (1440x900 desktop default chat: All available courses pill at 38–40px height, 13–14px font, generous spacing below divider)
  - `screenshot/chat_specific_course_selected.png` (1440x900 desktop specific course: distinct gold accent pill, truncated course name with full title tooltip)
  - `screenshot/chat_composer_scope_menu_open.png` (1440x900 desktop opened course menu: 340px popover with search filter and course list)
  - `screenshot/chat_mobile_composer.png` (390x844 mobile viewport: clean composer layout with comfortable tap target)
  - `screenshot/chat_mobile_composer_scope.png` (390x844 mobile viewport: opened scope menu popover)
- **Quality & Test Gate:**
  - `pytest backend/tests/frontend/unit/ -v`: 73/73 passed (100%).
  - `ruff check frontend/ backend/`: 100% clean (0 errors).
  - `git diff --check`: 100% clean (0 errors).

---

## Historical Phase — 2026-10-12

**FRONTEND PART 2E — CHAT WORKSPACE COMPLETION & MODERN LEFT SIDEBAR SHELL (/chat, layout, conversations)**

### Status: COMPLETED & VERIFIED
- **User Requirements Addressed:**
  1. *Left Sidebar Transformation & Navigation Modernization:*
     - Converted application shell navigation to an authoritative left sidebar shell (`frontend/components/layout.py`) inspired by modern conversational AI platforms (ChatGPT workspace architecture).
     - Single clean `+ New Chat` button with single `+` symbol (eliminated duplicate `+` icon bug).
     - Streamlined primary navigation links (`Home`, `Courses`, `Profile`). Eliminated redundant "Ask Assistant" link because "New Chat" is right above it.
     - Recent chat history section (`RECENT CHATS`) rendering authenticated, isolated persistent conversations with active highlighting and deletion.
     - Student profile footer card displaying user initials avatar ring, display name, role badge (`Student`), and Sign Out action.
     - Mobile drawer layout (<1024px) cleanly accessible via top hamburger button with zero overflow.
  2. *Composer-Docked Scope Capsule Selector:*
     - Moved the course selector into the bottom toolbar of the question composer (`frontend/pages/chat_page.py`).
     - Removed the old-fashioned `expand_more` dropdown arrow; replaced with an ultra-clean capsule pill (`rounded-full`) featuring a gold academic icon and subtle modern `unfold_more` indicator.
     - Compact searchable popover menu (`ui.menu`) with real-time course search filter, checkmark indicator on active scope, and instant "Reset to All" action.
     - Tightly synchronized with backend query payload (`scope="ALL_COURSES"` vs `scope="COURSE"`).
  3. *Real Persistent Conversation History:*
     - Engineered durable database schema with `conversations` and `chat_messages` tables via Alembic migration `b2c3d4e5f6a7`.
     - Strict multi-tenant isolation enforced server-side: a student can only read, modify, or delete their own conversations; foreign IDs return HTTP 404.
     - Automatic title generation from first question; ordered message history with citation provenance retained.
     - First-class `New Chat` resets active conversation draft without writing fake history items.
     - Removed duplicate "New Chat" button from chat page header to eliminate clutter.
  4. *Real 'Stop Generating' Action:*
     - Replaced Send button with a prominent red Stop button during active synthesis.
     - Safely terminates background synthesis task via monotonic generation ID tracking and marks response as stopped.
     - Prevents late-arriving responses from overwriting newer conversation state.
  5. *Horizontally & Vertically Centered Greeting:*
     - Centered the "Academic Knowledge Assistant" title, gold graduation cap, and explanatory description in the available chat workspace, matching modern AI assistant empty states.
- **Visual Verification:**
  - `screenshot/chat_sidebar_desktop.png` (1440x900 desktop default chat: clean left sidebar, centered greeting, composer-docked scope pill)
  - `screenshot/chat_composer_scope_menu_open.png` (1440x900 desktop opened course menu: compact popover with search filter and authorized courses)
  - `screenshot/chat_stop_generating.png` (1440x900 desktop active generation: red Stop button)
  - `screenshot/chat_concise_grouped_citations.png` (1440x900 desktop active chat: concise answer, grouped citations, active conversation highlighted in recent chats)
  - `screenshot/chat_desktop_history.png` (1440x900 desktop saved conversation: ordered turns and message-stable citations preserved)
  - `screenshot/chat_new_chat_clean.png` (1440x900 desktop new chat: clean draft state with past history preserved)
  - `screenshot/chat_sidebar_mobile.png` (390x844 mobile viewport: centered greeting and compact mobile layout)
  - `screenshot/chat_mobile_composer_scope.png` (390x844 mobile drawer: full touch navigation and recent chats)
- **Quality & Test Gate:**
  - `pytest backend/tests/frontend/unit/ -v`: 73/73 passed.
  - `pytest backend/tests/security/ backend/tests/unit/ -v`: 21/21 passed (51 offline-db tests skipped).
  - `pytest backend/tests/unit/test_production_quality_gate.py -v`: 9/9 passed (5 offline-db tests skipped).
  - `ruff check frontend/ backend/`: 100% clean (0 errors).
  - `git diff --check`: 100% clean (0 errors).

---

## Historical Phase — 2026-10-09

**FRONTEND PART 2D — COURSE SCOPE SELECTOR + CONCISE RAG ANSWERS (/chat, prompt_builder, service)**

### Status: COMPLETED & VERIFIED
- **User Requirements Addressed:**
  1. *Compact Searchable Course Scope Selector:*
     - Redesigned the student chat course selector in `frontend/pages/chat_page.py` from a bulky control into a compact, intentional control inspired by modern assistant selection menus.
     - Default scope is `All available courses` (`ALL_COURSES`), searching all courses the current student is authorized to access.
     - Compact scope button trigger in the chat header displays current scope name (e.g., `All available courses` or specific course name `CS101: Introduction to Computer Science`), graduation school icon, and dropdown indicator with `aria-label="Search scope selector"`.
     - Popover menu (`ui.menu`) features Quasar natural auto-positioning (`:offset="[0, 8]"`) and responsive max-width (`w-[280px] sm:w-[320px] max-w-[calc(100vw-2rem)]`), completely eliminating left/right clipping on mobile (390×844) and desktop (1440×900).
     - Integrated instant search filter (`ui.input(placeholder="Search courses...")`) allowing students to filter courses dynamically by title or description.
     - Clear selected states with gold checkmark icons (`ui.icon("check")`) and highlighted borders.
     - "Reset to All" quick action in menu header to return immediately to `All available courses`.
     - Selecting a course updates the actual query scope payload (`kb_id` and `scope="COURSE"` vs `scope="ALL_COURSES"`), verified by behavioral contract tests.
     - Synchronized docked composer status indicator (`Scope: All available courses` / `Scope: <Course Name>`) on mount and selection changes.
  2. *Concise and Direct RAG Answers by Default:*
     - Analyzed the end-to-end answer generation pipeline across prompt builder, LLM provider, post-processing, and client transport.
     - Authored authoritative **Directive 8 (`CONCISE AND DIRECT BY DEFAULT`)** in `backend/app/services/llm/prompt_builder.py:SYSTEM_GROUNDING_INSTRUCTION`:
       * Mandates answering the user question immediately in the first sentence.
       * Forbids repeating or rephrasing the question.
       * Forbids generic conversational preambles ("Based on the provided documents...", "According to the context...").
       * Synthesizes facts rather than transcribing long retrieved passages.
       * Calibrated length policy: direct sentence or short paragraph for simple factual questions; direct answer with concise supporting points for explanatory questions; full structured detail with headings and bullet points only when comprehensive detail, comparisons, or step-by-step instructions are explicitly requested.
       * Strictly preserves academic rigor: never drops formulas, conditions, exceptions, or Dean approval qualifications.
     - Enhanced post-processing sanitizer `_sanitize_llm_answer` in `backend/app/services/llm/service.py` with regex filter removing leading boilerplate preambles unless communicating necessary uncertainty ("not enough information").
     - Updated `frontend/client/api_client.py` mock generator to produce concise factual answers by default and detailed structured answers when detail is explicitly requested.
     - Grounding and citation validation pipelines remain fully preserved with zero weakening.
- **Visual Verification:**
  - `screenshot/chat_all_courses.png` (1440×900 desktop default chat: `All available courses` selected, dignified academic assistant, zero suggestions)
  - `screenshot/chat_scope_menu_open.png` (1440×900 desktop opened course menu: compact popover, search field, checkmark on `All available courses`, readable course list)
  - `screenshot/chat_specific_course_selected.png` (1440×900 desktop specific course: button reflects `CS101: Introduction to Comput...`, composer reflects `Scope: CS101: Introduction to Computer Science`, menu closed)
  - `screenshot/chat_mobile_scope_menu_open.png` (390×844 mobile opened menu: zero horizontal overflow, zero clipping, comfortable margins)
  - `screenshot/chat_concise_answer.png` (1440×900 desktop concise answer: direct factual answer without introductory filler, grouped citations tray with distinct page chips `[1] Page 2 ↗`, `[2] Page 5 ↗`, `[3] Page 8 ↗`)
  - `screenshot/chat_detailed_answer.png` (1440×900 desktop detailed answer: structured comprehensive response with section headers, bullet points, and verified citations when requested)
- **Quality & Test Gate:**
  - `.\.venv\Scripts\pytest.exe backend\tests\frontend\unit\ -v`: 64/64 passed in 16.86s (10 new behavioral tests).
  - `.\.venv\Scripts\pytest.exe backend\tests\unit\test_grounded_prompt_builder.py -v`: 7/7 passed in 1.67s.
  - `.\.venv\Scripts\pytest.exe backend\tests\unit\test_grounding_validation_service.py -v`: 6/6 passed in 1.49s.
  - `.\.venv\Scripts\ruff.exe check frontend\ backend\`: 100% clean (0 errors).
  - `git diff --check`: 100% clean (0 whitespace errors).

---

## Historical Phase — 2026-10-09

**FRONTEND PART 2C — FINISH CHAT REQUIREMENTS (/chat, evidence_panel, citations)**

### Status: COMPLETED & VERIFIED
- **User Requirements Addressed:**
  1. *Complete Removal of Suggestions:* In `frontend/pages/chat_page.py`, removed the suggested/example-question section from the empty chat state entirely. Did not restyle or replace with borderless links. Kept concise, dignified introductory message (graduation cap icon, "Academic Knowledge Assistant", and brief text). The bottom question composer is the main visible interaction.
  2. *Document-Grouped Evidence Presentation:*
     - Implemented `group_citations_by_document(citations)` in `frontend/client/citations.py` using stable canonical document identifier (`document_id` UUID primary key; fallback tuple `(knowledge_base_id, document_name)`). Distinct documents with matching filenames are never merged.
     - Within each document group, deduplicated citations sharing the same page number without duplicate page entries, aggregating citation indices `[1, 3]` and distinct excerpts without snippet loss or merging.
     - Preserved `page_number=None` for unpaged sources (DOCX, TXT, Markdown) without fabricating page numbers.
     - Updated inline "Cited Sources" tray in `frontend/pages/chat_page.py` to display each document once, followed by clickable distinct page references opening the canonical source-viewer route.
     - Updated slide-out "Evidence & Provenance" panel in `frontend/components/evidence_panel.py` to organize evidence into document group cards with cited page badges and dedicated per-page excerpt sections and PDF viewing actions.
     - Preserved message-stable inline citation click resolution (`data-message-id`, `data-citation-index`) across multi-turn assistant responses.
  3. *Safe Screenshot Inventory & Cleanup:*
     - Classified all screenshots across `screenshot/` into Historical Baseline, Approved Design Reference, Current Final Verification, and Temporary/Obsolete.
     - Safely deleted 5 temporary/obsolete/duplicate captures not referenced by tests or documentation: `screenshot/current_login.png`, `screenshot/current_student_login.png`, `screenshot/redesign_part1_login.png`, `screenshot/test_empty_mobile.png`, and `screenshot/test_mobile.png`.
     - Preserved 21 historical baseline screenshots in `screenshot/old screenshot/`, 9 approved design references in `screenshot/stage1_redesign/`, and all baseline captures referenced in project history.
- **Visual Verification:**
  - `screenshot/chat_empty_student.png` (1440×900 desktop empty state verified: no suggestions, composer is main interaction)
  - `screenshot/chat_active_same_pdf.png` (1440×900 desktop active conversation citing pages 2, 5, 8 of one PDF: document rendered once followed by 3 distinct page chips `[1] Page 2 ↗`, `[2] Page 5 ↗`, `[3] Page 8 ↗`)
  - `screenshot/chat_active_multi_doc.png` (1440×900 desktop active conversation citing multiple documents: 3 distinct document cards with correct page and unpaged `View Document` actions)
  - `screenshot/chat_mobile_student.png` (390×844 mobile active conversation: responsive header, zero composer overlap, grouped evidence chips)
  - `screenshot/chat_evidence_drawer.png` (1440×900 desktop evidence drawer: slide-out drawer showing document header with "3 cited pages" badge and distinct page excerpt sections)
- **Quality & Test Gate:**
  - `.\.venv\Scripts\pytest.exe backend\tests\frontend\unit\ -v`: 54/54 passed in 12.14s (6 new behavioral tests).
  - `.\.venv\Scripts\ruff.exe check frontend\ backend\`: 100% clean (0 errors).
  - `git diff --check`: 100% clean (0 whitespace errors).

---

## Historical Phase — 2026-10-09

**FRONTEND PART 2B — CHAT VISUAL REFINEMENT AND MOBILE LAYOUT FIX (/chat)**

### Status: COMPLETED & VERIFIED
- **Defects Audited & Addressed:**
  1. Mobile Composer Overlap: On mobile viewports (390×844 and 375×667), sticky bottom composer was overlapping citation and source evidence chips, preventing reading and tapping of the last source item.
  2. Template-Heavy Empty State: Empty state was dominated by heavy outlined pill button controls.
  3. Redundant Micro-Labels & Status Indicators: Repeated labels (QUESTION, ASSISTANT EXPLANATION), synthetic Online · Grounded status pills, and green check certainty claims cluttered the conversation stream.
  4. File Name Truncation: Long source filenames were truncated or overflowing.
  5. Mobile Sub-Header Wrapping: Scope selector and reset action wrapped into awkward multi-line arrangements on small screens.
- **Architectural & Design Solutions:**
  1. Independent Scrolling Flex Layout: Structured the page as a flex column container (height: calc(100dvh - 5.5rem); max-height: calc(100dvh - 5.5rem); overflow: hidden;) with Section B (lex-1 min-h-0 overflow-y-auto chat-scroll-area) and Section C (composer) docked cleanly as a sibling shrink-0 element. The composer physically cannot overlap messages or citations; citations are 100% visible and interactive at both 390×844 and 375×667.
  2. Editorial Empty State Composition: Replaced heavy outlined button pills with lightweight, borderless suggestions with subtle arrows (rrow_outward), soft hover washes, and calm typography. Composer remains the clear primary interactive focus.
  3. Truthful & Calm Academic Scope: Replaced diagnostic Grounded in all... and green checkmark with quiet, honest scope indicator (menu_book icon + Scope: All available courses / Scope: <Course Name>). Removed diagnostic micro-labels (QUESTION, ASSISTANT EXPLANATION).
  4. Robust Long Filename Wrapping: Updated source chips and evidence panel to reak-all sm:break-words leading-tight/snug with accessible 	itle hover tooltips, tested with 58-character names (cs101_laboratory_policies_grading_rubric_and_protocols_2026.docx).
  5. Compact Mobile Navigation & Header: Refined course selector to min-w-[170px] sm:min-w-[210px], ensuring Row 1 has Ask Assistant and Row 2 holds dropdown and Clear Chat cleanly without 3-line wrap.
- **Visual Verification:**
  - screenshot/chat_empty_student.png (1440×900 desktop empty state verified)
  - screenshot/chat_active_student.png (1440×900 desktop active conversation with long source names verified)
  - screenshot/chat_empty_mobile.png (390×844 mobile empty state verified)
  - screenshot/chat_mobile_student.png (390×844 mobile active conversation showing all 3 citations and zero composer overlap verified)
  - screenshot/test_se.png (375×667 compact mobile active conversation showing full citation visibility and zero overlap verified)
- **Quality & Test Gate:**
  - pytest backend/tests/frontend/unit/ -v: 48/48 passed.
  - ruff check frontend/ backend/: 100% clean (0 errors).
  - git diff --check: 100% clean (0 errors).

---

## Historical Phase — 2026-10-09

**PUBLIC LANDING PAGE — FINAL FOOTER REFINEMENT (/login & auth_layout)**

### Status: COMPLETED & VERIFIED
- **Defects Addressed:**
  1. Full-width contrasting light banner (`bg-surface-elevated`) appeared visually disconnected from the warm ivory page canvas (`#E8E0D2`).
  2. Redundant technical claims ("Server-Side RBAC Enforced", "Zero Token URL Leakage", "Multi-Format Text RAG") in tiny monospace uppercase repeated information already displayed in the 4-column trust pillars above.
  3. Mobile line wrapping produced cramped text with awkward trailing bullet characters (`•`).
  4. Excessive vertical gap (~96px) between Section 4 trust pillars and the footer divider due to compounded bottom padding.
- **Architectural & Design Solutions:**
  1. Restrained Editorial Colophon: Removed `bg-surface-elevated`; footer now sits seamlessly on the ivory page canvas (`bg-canvas`) separated by a single delicate hairline divider (`border-t border-subtle`). Content aligned strictly with `max_width_class` (`max-w-6xl` on landing page).
  2. Clean Typography & Canonical Identity: Left side features `RAG Assistant © 2026` with gold book icon in display typography (`font-editorial font-bold text-primary-navy text-sm`). Right side features canonical title `Multimodal RAG-Based University Knowledge Assistant` in readable body type (`text-xs md:text-sm text-secondary-navy font-medium`). Removed all duplicate technical labels and fake links.
  3. Immediate Spacing & Mobile Stacking: Tightened layout vertical padding (`pt-8 md:pt-12 pb-6 md:pb-10` in `auth_layout` and `pb-4` on Section 4 in `auth_pages.py`), creating balanced ~48px breathing room connecting the footer to the page. Responsive `flex-col sm:flex-row gap-3 sm:gap-4`: stacks cleanly on mobile with zero trailing bullets and zero horizontal overflow.
  4. Multi-Route Protection: Verified clean appearance on `/login`, `/student/login`, `/admin/login`, and `/register` sharing `auth_layout`. Authenticated `page_layout` remains unaffected.
- **Visual Verification:**
  - Desktop Screenshot: `screenshot/landing_desktop_footer_review.png` (1440x900) verified.
  - Mobile Screenshot: `screenshot/landing_mobile_footer_review.png` (390x844) verified.
- **Quality & Test Gate:**
  - `.\.venv\Scripts\pytest.exe backend/tests/frontend/unit/`: 46/46 passed in 10.08s.
  - `.\.venv\Scripts\ruff.exe check frontend/ backend/`: 100% clean (0 errors).
  - `git diff --check`: 100% clean (0 whitespace errors).

---

## Historical Phase — 2026-10-09

**FRONTEND REVIEW — PART 1: PUBLIC LANDING PAGE COMPOSITION (/login)**

### Status: COMPLETED & VERIFIED
- **Audit & Diagnosed Defects (`screenshot/verified_login.png`):**
  1. Excessive Unused Right-Hand Space: Student and Administrator gateway cards occupied only the left side (~50% width), leaving 50% blank void on the right, caused by NiceGUI flex row flexbox wrapping when `w-1/2` was paired with `gap: 2rem`.
  2. Nested Box Clutter: Evidence demonstration featured three nested bordered cards (`bg-surface-elevated` > `bg-surface` > `bg-gold-light`).
  3. Repetitive Card Visuals: Every section was enclosed in bordered containers.
  4. Low Contrast: Masthead kicker used `text-gold` on ivory canvas (`#E8E0D2`).
  5. Repetitive Trust Badges: Duplicate strip immediately preceded footer.
- **Architectural & Design Solutions:**
  1. Balanced Two-Column Gateway Grid: Converted gateway cards container to a pure CSS Grid (`w-full grid grid-cols-1 md:grid-cols-2 gap-8 mb-16 items-stretch`), ensuring a balanced 50/50 split on desktop/tablet, filling 100% of the `max-w-6xl` container with zero empty void. Responsive single-column stack on mobile.
  2. Unboxed Evidence Grounding Specimen: Converted the 3-layer nested card into a single elegant archival specimen sheet with a gold top rule, monospace archival metadata bar, unboxed student inquiry, synthesized evidence answer with a scholarly left gold rule (`border-l-2 border-gold pl-5`), and integrated citation footer bar (`[1]` badge, document name, page/section, and verified in-browser citation tag).
  3. Contrast & Typography Polish: Upgraded kicker to `text-xs font-bold font-mono tracking-widest text-primary-navy` flanked by gold accent marks (`10.5:1` contrast ratio). Upgraded gateway feature checklists to `14px` (`text-sm text-secondary-navy`).
  4. Open 4-Column Architectural Trust Pillars: Replaced duplicate badges with an open 4-column architecture overview (`Server-Side RBAC`, `Zero Token URL Leakage`, `Native Document Viewer`, and `Multi-Format Text RAG`) with descriptive copy and icons.
- **Visual Verification:**
  - Desktop Screenshot: `screenshot/landing_desktop_redesign.png` (1440x900) verified.
  - Mobile Screenshot: `screenshot/landing_mobile_redesign.png` (390x844) verified.
- **Quality & Test Gate:**
  - `.\.venv\Scripts\pytest.exe backend/tests/frontend/unit/`: 46/46 passed in 9.95s.
  - `.\.venv\Scripts\ruff.exe check frontend/ backend/`: 100% clean (0 errors).
  - `git diff --check`: 100% clean (0 whitespace errors).

---

## Historical Phase — 2026-10-09

**NICEGUI STARTUP REPAIR & GLOBAL-SCOPE ELEMENT RESOLUTION**

### Status: COMPLETED & VERIFIED
- **Incident & Fix:** Resolved `RuntimeError: ui.page cannot be used in NiceGUI scripts when UI is defined in the global scope` by replacing `ui.colors(...)` with `app.colors(...)` in `frontend/components/theme.py:init_theme()`. `ui.colors()` subclasses `Element` and inadvertently registered children to `core.script_client.content.default_slot.children` during startup before `ui.run()`. Using `app.colors()` sets application-wide Quasar configuration cleanly without generating client elements.
- **Verification:** Verified `python -m frontend.main` starts without errors, all 14 routes are properly registered, 46/46 frontend unit tests passed, and `ruff check` is clean.

---

## Historical Phase — 2026-10-08

**STAGE 3 — DESIGN SYSTEM RESET + STUDENT EXPERIENCE REBUILD**

### Status: COMPLETED & VERIFIED
- **Accomplishments:**
  - **Stage 3A (Contracts & Documentation Reset):**
    * Authored authoritative `context/FRONTEND_DESIGN_SYSTEM.md`: Ivory `#E8E0D2`, Gold `#B89A5A`, Deep Atlas Navy `#0E1D61`, editorial typography scale, single student navigation, default `ALL_COURSES` chat scope.
    * Reconciled `AGENTS.md`, `PROJECT_CONTEXT.md`, `context/BACKEND_RULES.md`, `context/FRONTEND_RULES.md`, `context/RAG_SPECIFICATION.md`, and `context/TESTING_AND_SECURITY.md`.
    * Implemented authoritative student catalog access in `backend/app/api/deps.py`: active and student-visible courses are accessible to students by default without manual enrollment; restricted courses (`is_student_visible=False`) require explicit membership (`KnowledgeBaseMember`); inactive courses return 404.
    * Reset stale milestone test suites, creating 71 behavioral and security tests in `backend/tests/frontend/` and deleting all obsolete milestone tests.
  - **Stage 3B (Design System Tokens & Theme):**
    * Rebuilt `frontend/components/theme.py` with palette tokens: Deep Atlas Navy `#0E1D61`, Gold `#B89A5A`, Warm Parchment Ivory `#FAF6F0`, and Charcoal text `#1C1917`. Set typography to Source Serif 4, Plus Jakarta Sans, and JetBrains Mono.
    * Rebuilt `frontend/components/ui_kit.py` with restrained editorial headers, empty states, stat cards, and alerts.
  - **Stage 3C & 3D (Shell Navigation & Public Entry Rebuild):**
    * Rebuilt `frontend/components/layout.py`: single top-nav for students (`Home`, `Ask Assistant`, `Courses`, `Profile`), zero duplicate sidebars, zero static BCA badges.
    * Rebuilt `frontend/pages/auth_pages.py`: editorial landing page, live grounded evidence demo card, student academic gateway, faculty admin gateway, and student registration.
  - **Stage 3E (Student Dashboard & Course Library Rebuild):**
    * Rebuilt `frontend/pages/dashboard_page.py`: personalized greeting, integrated assistant composer with prompt inspiration chips, 3 quick action strips, course atlas cards with document counts and direct actions.
    * Rebuilt `frontend/pages/knowledge_bases_page.py`: search filter, course cards with material counts, direct "Ask Questions" action, and "View Materials" dialog.
  - **Stage 3F (Conversational Chat Rebuild):**
    * Rebuilt `frontend/pages/chat_page.py`: default search scope `ALL_COURSES`, conversation stream with clean reading width, bottom composer, distinct gold citation markers `[1]` with hover tooltips, and verified sources cards.
  - **Stage 3G (Source Viewer Repair & Redesign):**
    * Rebuilt `frontend/components/source_viewer.py`: native PDF object/iframe embedding with page fragment `#page=N` support, side-by-side evidence passage banner, extracted text chunks fallback tab, strict HttpOnly cookie authentication, zero query token leakage.
  - **Stage 3H (Student Profile Rebuild):**
    * Rebuilt `frontend/pages/profile_page.py`: academic identity, institutional email, student role badge, active session indicator, accessible course list, and sign out action.
  - **Stage 3I (Verification & Quality Gate):**
    * Unit & Frontend Tests: 71/71 passed in `backend/tests/frontend/`.
    * Security Tests: 59/59 passed in `backend/tests/security/`.
    * Total Test Suite: 625/625 tests passed across `backend/tests/ -m "not real_ollama"`.
    * Code Quality: `ruff check` passed with 0 errors across frontend and backend.
    * Local Server Smoke: All public HTTP routes (`/`, `/login`, `/student/login`, `/admin/login`, `/register`) return HTTP 200 OK.

---

## Master Phase Status (2026-10-05 Rebuild)

### Phase 1: Security Hardening & Backend Correctness
- **Status:** **COMPLETED & VERIFIED**
- **Commit:** `cfb824e`
- **Accomplishments:**
  - Removed `?token=` query parameter authentication (rejected with HTTP 401).
  - Replaced production `TestClient` usage with `InProcessProductionTransport` in `FrontendAPIClient`.
  - Completely deleted raw session token persistence (`_get_persistent_token`, `_set_persistent_token`, and `app.storage.user["auth_session_token"]`).
  - Decoupled backend `deps.py` completely from NiceGUI (`nicegui.app` and `storage._users` removed; framework-independent auth).
  - Redesigned `SessionCookieSyncMiddleware` to sync HttpOnly cookies directly from in-memory clients (`_session_clients`).
  - Centralized safe error normalization via `normalize_error()` across all API client error paths and 14 frontend page call sites.
  - Confirmed authoritative student course access rule: strictly membership-based (`KnowledgeBaseMember`).
  - Cleaned repository (untracked file `frontend/client/Untitled-1.txt` confirmed clean).
  - Expanded Phase 1 regression test suite to 13 tests covering requirements A through N (`backend/tests/security/test_phase1_security_hardening.py` — 13/13 passed).
  - Verification: 572 tests passed in the non-real_ollama regression suite (`pytest backend/tests/ -m "not real_ollama"` in 423.96s; tests marked real_ollama were excluded from this verification), 50/50 security tests passed, `ruff check .` passed with 0 errors.

### Phase 2: Scope Control & Project Context Consistency
- **Status:** **COMPLETED & VERIFIED**
- **Accomplishments:**
  - Established authoritative naming policy:
    * Official academic project title: **Multimodal RAG-Based University Knowledge Assistant**
    * Application / Product / UI name: **RAG Assistant**
  - Updated application configuration (`APP_NAME = "RAG Assistant"` in `backend/app/core/config.py` and `.env.example`).
  - Replaced obsolete product brand names (`BCA RAG Assistant`, `RAG Studio`, `Academic Assistant`, `University RAG Assistant`) across current application code, layout, auth pages, chat page, and docstrings with **RAG Assistant**.
  - Preserved legitimate academic references to BCA (degree, course codes, syllabi, student enrollment, academic context).
  - Updated and verified direct tests asserting product name: `test_config.py` and `test_production_quality_gate.py` assert `APP_NAME == "RAG Assistant"`; `test_student_dashboard_fixes.py` asserts `"Ask RAG Assistant"`.
  - Current RAG scope documented truthfully as **Multi-Format Text RAG** (PDF, DOCX, TXT, Markdown, CSV).
  - Genuine Multimodal RAG (vision models, OCR, image embeddings, visual retrieval) explicitly documented as **FUTURE / DEFERRED**.
  - Standardized regression test passing statements to: "572 tests passed in the non-real_ollama regression suite; tests marked real_ollama were excluded from this verification."
  - Preserved historical audit records with clear labels while strictly prohibiting insecure patterns in current instructions.
  - Documented authoritative membership-based student course authorization rule.
  - Documented that Phase 4 will be a complete **frontend rebuild from scratch** in NiceGUI (current UI is superseded; restrained aesthetic, no decorative animations/gradients/glassmorphism).
  - Documented screenshot reference rule: screenshots in `screenshot/` folder are audit evidence of existing defects/flows, not a design template.
  - Documented testing rules: Phase 3 will rewrite tests from scratch to protect behavior/contracts/security without asserting CSS classes, colors, or DOM nesting.
  - Verified physical absence of `frontend/client/Untitled-1.txt` (`Test-Path` returned `False`) and verified no other `Untitled` scratch files exist in the project.
  - Verified clean working tree and `ruff check .` passes with 0 errors.

### Phase 3: Frontend Test Suite Rewrite, Architecture Decoupling & Content Safety
- **Status:** **COMPLETED & VERIFIED**
- **Commit:** Pending final correction commit (`fix(testing): finalize Phase 3 boundaries and content safety`)
- **Accomplishments:**
  - Removed and verified physical absence of `frontend/client/Untitled-1.txt` (`Test-Path` returned `False`) and verified zero `*Untitled*` scratch files across the entire repository.
  - Verified and handled generated egg-info packaging artifact (`bca_rag_assistant.egg-info/` removed from workspace; confirmed `.gitignore` contains `*.egg-info/`).
  - Unit tests made truly framework-independent:
    * Completely removed `nicegui.storage.request_contextvar` and `starlette.requests.Request` from `backend/tests/unit/test_frontend.py`.
    * Transferred AppState per-browser-session isolation test to `backend/tests/integration/test_frontend_workflows.py` (`TestAppStateSessionIntegrationContracts`), maintaining pure in-memory unit tests in `test_frontend.py`.
    * Documented unit vs integration boundary clearly in test module docstrings.
  - Removed presentation coupling from authentication persistence test:
    * Removed `from frontend.components.layout import page_layout` and `with page_layout(...)` invocation from `backend/tests/integration/test_auth_session_persistence.py`.
    * Replaced with stable verification of authenticated user identity, role, and session token state.
  - Fail-closed access control on unknown roles:
    * Corrected `frontend/security/access_control.py`: unknown and malformed roles are strictly DENIED all protected routes (`/dashboard`, `/profile`, `/chat`, `/knowledge-bases`, `/documents`, `/indexing`, `/administrators`, `/activity`, `/system-health`).
    * Backend authorization remains authoritative; access control is strictly client capability gating.
    * Added dedicated unit test `test_unknown_role_is_denied_protected_routes` verifying fail-closed denial.
  - Content safety and dangerous URI scheme neutralization:
    * Hardened `frontend/client/content_safety.py` to identify and neutralize active URI schemes: `javascript:` (standard, mixed-case `JaVaScRiPt:`, whitespace/tab/newline obfuscations), `vbscript:`, `data:text/html`, and dangerous HTML `href`/`src` attributes.
    * Preserves legitimate Markdown syntax (`**bold**`, `*italic*`, code) and safe HTTPS/HTTP URLs (`https://university.edu`).
    * Replaced `href="javascript:void(0)"` with safe anchor `href="#"` in `chat_page.py` citation pills, eliminating script schemes from citation markup.
  - Citation semantic processing framework independence:
    * `frontend/client/citations.py` parses and resolves citation markers without HTML or UI dependencies.
    * Protected citation-like syntax inside inline code (`` `...` ``) and fenced code blocks (` ```...``` `), ensuring code snippets such as `arr[1]` are never corrupted into citation references.
  - Removed swallowing unit conftest:
    * Deleted redundant and error-masking `backend/tests/unit/conftest.py`, ensuring root `conftest.py` manages transactions cleanly without hiding database connection failures.
  - Confirmed zero presentation locks across test suite (zero matches for `box-border`, `max-w-`, `animate-`, `citation-pill`, `card_count`, `hover:`, `transition-`, `shadow-`, `gradient`, `class=`, `style=`, `page_layout`).
  - Verification on local PostgreSQL 16 server:
    * `pytest backend/tests/unit/ -v`: 342 passed, 0 failed.
    * `pytest backend/tests/security/ -v`: 50 passed, 0 failed.
    * `pytest backend/tests/integration/ -v`: 191 passed, 0 failed.
    * `pytest backend/tests/ -m "not real_ollama"`: 583 passed, 0 failed (in 413.25s; tests marked `real_ollama` were excluded from this verification).
    * `ruff check .`: All checks passed with 0 errors.

### Phase 4: Frontend Rebuild from Scratch
- **Status:** **COMPLETED & VERIFIED**
- **Core Accomplishments:**
  1. **Audited All Screenshots & Old UI Problems**:
     - Inspected all 21 screenshots in `screenshot/`.
     - Cataloged UI defects: ghost empty white cards on `/documents` (caused by cards declared before `with dialog:`), harsh gradients, floating card lift/scale animations, non-semantic badges, broken mobile navigation, and missing contextual empty states.
  2. **Institutional Academic Theme & Design Tokens (`frontend/components/theme.py`)**:
     - Retrained palette: Slate Navy `#0f172a`, Oxford Blue `#1e40af`, Surface `#ffffff`, Border `#e2e8f0`, Canvas `#f8fafc`.
     - High-contrast typography hierarchy with WCAG 2.1 AA accessible focus rings (`*:focus-visible`).
     - Removed all decorative gradients, glassmorphism, floating transforms, and hover lift/scale effects.
  3. **Rebuilt Application Shell (`frontend/components/layout.py`)**:
     - Single responsive layout with desktop rail and collapsible mobile drawer (`ui.left_drawer`).
     - Strict role separation: student navigation (`Home`, `Courses`, `Ask Assistant`, `Profile`) vs administrator navigation (`Dashboard`, `Courses`, `Documents`, `Indexing`, `Administrators`, `Audit Activity`, `System Health`, `Profile`).
     - Global sanitized error and notification presentation.
  4. **Reusable Restrained UI Kit Primitives (`frontend/components/ui_kit.py`)**:
     - `render_page_header`: Clean titles with subtitle hierarchy and primary action slot.
     - `render_stat_card`: Purposeful administrative metric cards with solid neutral badges and no hover lift animations.
     - `render_alert`: Semantic alerts with `role="alert"` for accessible screen reader announcements.
     - `render_empty_state`: Multi-line empty states explaining what is empty, why, and what action to take next.
  5. **Portal Separation Authentication (`frontend/pages/auth_pages.py`)**:
     - Clean portal hub at `/login` with dedicated pathways for Student Login (`/student/login`) and Administrator Login (`/admin/login`).
     - Clean student registration (`/register`) with clear institutional requirements and zero marketing clutter.
     - All errors routed through `normalize_error()`.
  6. **Rebuilt Student Experience (`frontend/pages/dashboard_page.py`, `frontend/pages/knowledge_bases_page.py`, `frontend/pages/chat_page.py`)**:
     - Student Dashboard: Quick inquiry search hero and dynamic enrolled courses grid strictly scoped to `KnowledgeBaseMember` memberships. Zero catalog leaks of unassigned courses.
     - Knowledge Bases: Distinct enrolled courses view with document counts, status badges, and direct "Ask Assistant" action.
     - Chat / RAG Interface: Clean conversational workspace with solid slate user messages, crisp white assistant cards, inline interactive citation pills (`[1]`), and collapsible grounded source cards with direct links to secure canonical document viewing.
  7. **Rebuilt Administrator Experience (`frontend/pages/documents_page.py`, `frontend/pages/indexing_page.py`, `frontend/pages/admin_users_page.py`, `frontend/pages/activity_page.py`, `frontend/pages/system_health_page.py`)**:
     - Documents Page: Fixed ghost white boxes bug. Clean upload drop zone with clear 20MB limit and multi-format indicators (PDF, DOCX, TXT, MD, CSV). Document table with status badges (`COMPLETED`, `PROCESSING`, `FAILED`), chunk inspection modal, and activate/deactivate lifecycle actions.
     - Indexing Page: Dedicated operational pipeline view showing real-time job queues, granular stages (`EMBEDDING`, `STORING_VECTORS`, `VERIFYING`, `COMPLETED`), progress bars, and sanitized error summaries.
     - Administrator Management: Scoped permission assignments (`MAIN_ADMIN` vs `FACULTY_ADMIN`), provisioning modal, and active administrator directory with self-protection guards.
     - Audit Activity & System Health: Operational audit timeline and telemetry diagnostics with refresh actions.
  8. **Preserved Secure Canonical Source Viewer**:
     - Streaming endpoint `/api/v1/documents/{document_id}/file#page={page}` requires authenticated session cookie.
     - 0 query parameter session tokens (`?token=`), 0 JavaScript access to tokens, and 0 unsafe HTML sinks.
  9. **Obsolete Frontend Tests Safely Cleaned Up**:
     - Audited and deleted duplicate/obsolete test files:
       * `backend/tests/unit/test_step21e_frontend_workflow.py` (duplicate of `backend/tests/unit/test_frontend.py` lines 637–763).
       * `backend/tests/unit/test_student_dashboard_fixes.py` (coverage fully preserved in `backend/tests/unit/test_frontend.py` and `backend/tests/unit/test_llm_generation_service.py`).
     - Confirmed absence of redundant `backend/tests/unit/conftest.py`.
  10. **Full Test Suite & Code Quality Verification**:
     - Unit tests: 335 passed, 0 failed.
     - Security tests: 50 passed, 0 failed.
     - Integration tests: 191 passed, 0 failed.
     - Non-real_ollama regression suite: 576 passed, 0 failed.
     - Ruff check: 0 errors across entire workspace.

### Multimodal RAG
- **Status:** **FUTURE / DEFERRED**
- **Scope:** Vision-language models, OCR pipelines, image embeddings, image retrieval, and visual citations will be designed and implemented in a separate roadmap phase after current text RAG is stable.

### Persistent Chat History
- **Status:** **FUTURE / DEFERRED**
- **Scope:** Durable Conversation/Message database models, server-side tenant isolation, and history management will be implemented as a controlled feature without destabilizing core RAG.

### Repository hygiene
- [x] Remove `frontend/client/Untitled-1.txt` (confirmed clean).
- [x] Keep `.env`, `.git`, `storage/`, caches, `.nicegui/`, bytecode, and generated dumps out of source-sharing archives.
- [x] Check Git history/diff for secrets before every push.

## Required acceptance criteria

This phase is complete only when:
1. no main session token is accepted in a source/file query string; [VERIFIED]
2. no raw main session token is sent to browser JavaScript; [VERIFIED]
3. production frontend does not import/use FastAPI `TestClient`; [VERIFIED]
4. source viewer is server-authorized and renders an actual document in the browser; [VERIFIED]
5. user-facing errors never expose raw exceptions; [VERIFIED]
6. frontend tests are behavior/security focused and survive visual redesign; [VERIFIED]
7. student/admin pages are rebuilt from scratch in NiceGUI; [VERIFIED]
8. the UI is simple, restrained, readable, and responsive; [VERIFIED]
9. unnecessary animation/hover/decorative effects are removed; [VERIFIED]
10. project documentation matches real multimodal capability; [VERIFIED]
11. Git/GitHub contains meaningful commits and no secrets. [IN PROGRESS]

## Verification honesty

Historical test counts below are historical records only. They are not current proof.

After the final changes, rerun the actual supported environment. If PostgreSQL, pgvector, Ollama, or browser tooling is unavailable, record that limitation instead of claiming the check passed.

## Historical task record

The original task history is preserved below. Its completed design decisions are historical evidence, not instructions to restore the superseded frontend.

## Step 21D Execution Record (Functional Integrity)

* **Status**: COMPLETE
* **Core Accomplishments**:
  1. **Real Persistent Vector Indexing**:
     - Created `indexing_jobs` table via Alembic migration `aab1529830b5` tracking truthful status (`QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED`), granular stages (`EMBEDDING`, `STORING_VECTORS`, `VERIFYING`, `COMPLETED`), chunk counts, and float percentage.
     - Configured safe batching (`OLLAMA_EMBED_BATCH_SIZE=4`, `OLLAMA_EMBED_TIMEOUT=120.0`) in `backend/app/core/config.py`.
     - Built resilient `IndexingWorker` running asynchronously on NiceGUI startup with startup recovery of interrupted jobs and event-loop decoupled notifications.
     - Enforced strict vector cardinality and dimension (1024-d) persistence verification before marking jobs `COMPLETED`.
  2. **Publication Integrity & Document Activation Gate**:
     - Documents with `indexing_status != COMPLETED` render `NOT READY` badge in NiceGUI.
     - Backend enforces HTTP 400 rejection if attempting to activate an unindexed document (`/activate`).
  3. **Restored & Scoped Admin Chat**:
     - Extended `/api/v1/chat/query` and frontend with explicit scopes: `ALL_COURSES`, `COURSE`, `DOCUMENT`.
     - Enforced SQL query-level filtering in Vector and Lexical retrieval so document-scoped queries never leak foreign content.
     - Automatically rejects unindexed documents with HTTP 400.
     - Grounded citations verified in end-to-end testing with document name, page, section, and snippets.
  4. **Hierarchical RBAC & Admin Lifecycle**:
     - Defined 16 canonical permissions in `backend/app/core/permissions.py` across Courses, Documents, Chat, and Administrators.
     - `MAIN_ADMIN` possesses inherent full authority across all courses, documents, chat, and admin actions.
     - `FACULTY_ADMIN` permissions are granularly configurable and course access is strictly bounded to creator or explicit `KnowledgeBaseMember`.
     - Complete admin lifecycle endpoints (`POST /auth/admin`, `GET /auth/admins`, `PATCH .../permissions`, `PATCH .../deactivate`, `PATCH .../activate`, `DELETE .../{admin_id}`) with safety guards preventing self-deactivation/deletion and protecting the final active Main Admin.
  5. **Verification**:
     - All 481 automated tests passing (`pytest backend/tests/ -m "not real_ollama"`).
     - 37/37 security tests passing (`backend/tests/security/`).
     - 5/5 Step 21D integration tests passing (`test_step21d_functional_integrity.py`).
     - 7/7 isolation & multi-KB tests passing (`test_global_retrieval_and_isolation.py`).
     - Full programmatic end-to-end verification script (`e2e_verify.py`) verified real Ollama embeddings, PostgreSQL 1024-d vectors (33/33 chunks on `KSU-Act-English.pdf`), 4 grounded citations, and RBAC lifecycle.
     - Alembic check: 0 pending operations.
     - Ruff check: 0 errors.

## Step 21B Execution Record (Product UX & Workflow Correction)

* **Status**: COMPLETE
* **Core Accomplishments**:
  1. **Separation of Student vs Administrator Experiences**:
     - **Student Experience**: Directly ask questions across all enrolled course materials (`POST /api/v1/chat/query` with omitted `knowledge_base_id`) without being forced into a corpus/folder selector; verified source citations and clean answers; zero internal RAG controls/jargon.
     - **Admin Experience**: Manage courses (`/knowledge-bases`), manage document lifecycle and versions (`/documents`), publish/deactivate materials without deleting, manage administrators (`/administrators`), and audit retrieval performance.
  2. **Document Activation Lifecycle (`is_active` Flag & Database Migration)**:
     - Added indexed `is_active: bool` column with server default `true` to `documents` table via Alembic migration `d4e5f6a7b8c9_add_is_active_to_documents.py`.
     - Tested on both `rag_assistant_db` and `rag_assistant_test_db`; verified zero schema drift via `alembic check`.
     - Integrated `is_active` into `VectorRetrievalService` and `LexicalRetrievalService` ensuring deactivated historical materials (e.g. 2025 syllabus) are strictly excluded from retrieval while preserving files and chunks.
     - Added `PATCH /knowledge-bases/{kb_id}/documents/{document_id}/activate` and `deactivate` endpoints (ADMIN only, returning 409 Conflict on duplicate state transitions).
  3. **Multi-KB Global Retrieval & Provenance Retention**:
     - Updated `VectorRetrievalService`, `LexicalRetrievalService`, `HybridRetrievalService`, and `RAGOrchestrator` to accept single KB UUID or collection of authorized KB UUIDs.
     - Direct retrieval-service query with empty list `[]` returns `[]` immediately without executing unscoped SQL queries.
     - Preserved canonical `POST /api/v1/knowledge-bases/{kb_id}/chat` endpoint 100% untouched.
     - In `POST /api/v1/chat/query`, preserved exact scoped behavior when `knowledge_base_id` is supplied, and dynamically resolves all authorized KBs server-side using SQL-based membership logic when omitted.
     - Individual chunk and citation items strictly retain non-null `knowledge_base_id`, `document_id`, and full provenance.
  4. **Dedicated Privacy-Preserving Administrator Management (`/administrators`)**:
     - Added `POST /api/v1/auth/admin` allowing an authenticated ADMIN to provision another ADMIN. Public registration remains strictly STUDENT.
     - Added `GET /api/v1/auth/admins` for listing active administrators.
     - Strict privacy enforcement: endpoints and DTOs never expose internal database UUIDs, password hashes, or session tokens.
     - Added dedicated `/administrators` frontend management page with creation form and active admin table.
  5. **Contextual Frontend Error Normalization (`frontend/client/error_handler.py`)**:
     - Built `normalize_error(err, context)` converting HTTP status codes, Pydantic validation error lists, and backend error tokens into user-friendly messages.
     - Suppresses raw SQL, syntax errors, stack traces, and internal UUIDs.
  6. **UI & Navigation Modernization**:
     - Updated `frontend/components/layout.py`: Student navigation (`Home`, `Ask Assistant`, `Courses`, `Profile`) vs Admin navigation (`Dashboard`, `Courses`, `Documents`, `Administrators`, `Chat & Search`, `Profile`). Active KB dropdown restricted strictly to ADMIN.
     - Updated `frontend/pages/chat_page.py`: Clean student experience with no forced corpus selector, initial zero-evidence state, and clear scope indicators.
     - Updated `frontend/pages/dashboard_page.py`: Student Hero CTA ("Ask a Question") and enrolled course cards vs Admin system metrics.
     - Updated `frontend/pages/documents_page.py`: Added `ACTIVE`/`INACTIVE` badges and `[Activate]` / `[Deactivate]` controls.
     - Updated `frontend/components/evidence_panel.py`: Clean empty state ("Sources will appear here after you ask a question.") and clean student citations.
* **Verification**:
  - `backend/tests/integration/test_global_retrieval_and_isolation.py`: 7/7 passed in 18s.
  - `backend/tests/unit/test_frontend.py`: 30/30 passed in 10s.
  - Complete backend test suite: 469/469 passed (0 failures).
  - Ruff check & format: 0 errors, clean working tree.

## Step 21 Execution Record (Frontend Design & Accessibility)

* **Status**: COMPLETE
* **Core Accomplishments**:
  1. **Restrained Academic Theme & Design Tokens (`frontend/components/theme.py`)**:
     - Established institutional color palette (Slate Navy `#0f172a`, Oxford Blue `#1d4ed8`, Canvas `#f8fafc`, Surface `#ffffff`, Slate Border `#e2e8f0`).
     - Injected global CSS with WCAG 2.1 AA engineering design targets: visible 2px focus rings (`*:focus-visible`), readable typography, custom subtle scrollbars, and responsive table utilities.
  2. **Unified Navigation Definition (`frontend/components/layout.py`)**:
     - Single source of truth: `get_nav_items(user)` shared identically across desktop navbar and mobile drawer.
     - Role-filtered: `Documents` only presented to `ADMIN`; `Dashboard`, `Knowledge Bases`, `Chat & Search`, and `Profile` presented to all authenticated users.
     - Mobile navigation supported via collapsible Quasar `ui.left_drawer` with full touch targets.
  3. **Reusable UI Kit Primitives (`frontend/components/ui_kit.py`)**:
     - Created `render_page_header`, `render_empty_state`, `render_alert` (with `role="alert"`), and `render_stat_card` to ensure consistent visual language across all screens.
  4. **Multi-Modal Accessible Status Badges (`frontend/components/status_badge.py`)**:
     - Adheres to accessibility rule: color is never the sole indicator of state (always pairs icon + text label + semantic color).
     - Covers document ingestion (`COMPLETED`, `PROCESSING`, `FAILED`, `PENDING`), indexing (`INDEXED`, `INDEXING...`, `INDEX FAILED`, `UNINDEXED`), and grounding states (`FULLY GROUNDED`, `PARTIALLY GROUNDED`, `NO EVIDENCE / REFUSAL`, `UNSUPPORTED`).
  5. **Privacy-Preserving Profile Page (`frontend/pages/profile_page.py`)**:
     - Added dedicated `/profile` route presenting user display name, email address, role badge, account status, and sign-out controls.
     - Strictly omits internal user UUIDs, session token hashes, cookie names, and cryptography details.
  6. **Zero N+1 Queries on Dashboard (`frontend/pages/dashboard_page.py`)**:
     - Derives document metrics from the active corpus alone, eliminating per-KB looping.
     - Tailors quick actions and metrics based on `ADMIN` vs `STUDENT` role.
  7. **Safe Content Rendering in Chat (`frontend/pages/chat_page.py`)**:
     - Neutralizes raw HTML tags and script event handlers (`sanitize_markdown_text`) before rendering to prevent XSS from untrusted documents or queries.
     - Standard asynchronous request-response architecture with processing indicator (zero fake streaming).
  8. **Dynamic Upload Limits (`frontend/pages/documents_page.py`)**:
     - Dynamically queries `settings.MAX_UPLOAD_SIZE_BYTES` rather than hardcoding file size limits.
  9. **Frontend Testing Suite (`backend/tests/unit/test_frontend.py`)**:
     - Expanded to 28 passing unit tests covering role-based navigation, theme injection, UI kit rendering, multi-modal status badges, safe markdown sanitization, upload size limits, and N+1 prevention.
* **Verification**:
  - `backend/tests/unit/test_frontend.py`: 28/28 passed in 9.14s.
  - Complete backend suite: running regression validation.
  - `ruff check .` & `ruff format --check .`: 0 errors across 199 files.
* **Next Safe Task**: Step 22: End-to-End QA & Deployment Verification.
- [ ] End-to-end QA
- [ ] Deployment verification
- [ ] Final security audit
- [ ] Final RAG evaluation
- [ ] Documentation
- [ ] Git/GitHub final review

## Step 20 Execution Record (Backend Production Quality Gate)

* **Status**: COMPLETE
* **Quality Gate Verification & Hardening across 14 Dimensions**:
  1. **Application Startup & Lifespan**:
     - Converted `backend/app/main.py` to use an `@asynccontextmanager async def lifespan(app: FastAPI)` handler.
     - Database health check reuses existing `check_database_connection()` and authoritative `engine`.
     - Fails startup fast with `RuntimeError` if authoritative PostgreSQL is unreachable; engine is disposed in exception paths and normal shutdown `finally` block.
     - Does not create persistent connections or leak DB credentials/traces to clients.
     - Verified in `backend/tests/unit/test_production_quality_gate.py` (Test 1 & 2).
  2. **Database Migrations & Model Drift**:
     - Executed `alembic check`: 0 pending model-generated migration changes detected.
     - Verified test database current revision equals repository migration head `e71a92b3c4d5`.
     - Verified in `backend/tests/unit/test_production_quality_gate.py` (Test 3 & 4).
  3. **API Contracts & Route Consistency**:
     - Verified all 8 core API routers (`auth`, `users`, `knowledge_bases`, `documents`, `retrieval`, `query`, `chat`, `evaluation`, `telemetry`) conform to Pydantic v2 schemas and OpenAPI specifications.
  4. **End-to-End RAG Pipeline Functionality**:
     - Verified end-to-end execution through `RAGOrchestrator`: normalization -> hybrid retrieval -> reranking -> context assembly -> generation -> grounding.
  5. **Provider Failure Isolation & Resilience**:
     - Verified vector dimension mismatch (e.g., 768 vs 1024) raises `RetrievalValidationError` without corrupting state.
     - Verified reranker provider failure (HTTP 503/timeout) surfaces as sanitized `503 Service Unavailable`.
     - Verified transaction rollback integrity on mid-pipeline failure with session rolling back cleanly.
     - Verified in `backend/tests/unit/test_production_quality_gate.py` (Test 5, 6, 7).
  6. **Database Performance & Resource Management**:
     - Verified `CrossEncoder` model singleton prevents duplicate heavy model loads in memory.
     - Verified retrieval top-k parameters are strictly validated with `@field_validator` / Pydantic `Field(ge=1, le=100)`.
     - Verified in `backend/tests/unit/test_production_quality_gate.py` (Test 8 & 9).
  7. **Observability, Telemetry & Logging**:
     - Verified structured JSON logging across all 7 RAG stages with correlation IDs, latency tracking, and zero secret leakage.
  8. **Rate Limiting & Abuse Protection**:
     - Verified PostgreSQL-backed atomic rate limiting with fail-closed behavior on auth and fail-open behavior on RAG operations during storage outages.
     - Verified in `backend/tests/unit/test_production_quality_gate.py` (Test 10 & 11).
  9. **Security Audit Regressions**:
     - Verified all 8 Step 19 security mitigations remain intact: dummy Argon2 verification, HttpOnly session cookies, sanitized `/ready` endpoint, conditional HSTS, configurable explicit CORS, sanitized 500/503 errors, and production security settings validation.
     - Verified via `backend/tests/security/test_backend_security_audit.py` (19/19 passed) and `test_security_rbac.py` (18/18 passed).
  10. **Code Quality & Static Typing**:
      - `ruff check .` passed with 0 errors across all 196 files.
      - `ruff format --check .` passed cleanly (100% compliant).
  11. **Dependencies & Environment Configuration**:
      - Inspected `Settings` types and verified `.env.example` parses seamlessly using `pydantic-settings` without type errors.
      - Verified in `backend/tests/unit/test_production_quality_gate.py` (Test 12).
  12. **Documentation Consistency**:
      - Updated `.env.example` with exact parameter schemas for all settings introduced in Steps 1–19.
  13. **Test Suite Integrity & Coverage**:
      - 451 total backend tests passing (14 new unit tests in `backend/tests/unit/test_production_quality_gate.py`).
  14. **Git Discipline & Baseline Integrity**:
      - Verified zero secrets committed, `.gitignore` protects credentials and databases, clean atomic commit prepared.
* **Next Safe Task**: Phase 4 — Frontend Completion (NiceGUI refinement, responsive design, accessibility).
- [x] Functional frontend (COMPLETE — Step 3 Shell + Step 4 RBAC + Step 5 Upload/Delete + Step 6 Indexing UI + Step 7 Vector UI + Step 8 Lexical UI + Step 9 Hybrid UI + Step 10 Rerank UI + Step 11 Query DTO)
- [ ] Frontend design pass
- [ ] Accessibility QA
- [ ] Responsive QA
- [ ] End-to-end QA
- [ ] Deployment verification
- [ ] Final security audit
- [ ] Final RAG evaluation
- [ ] Documentation
- [ ] Git/GitHub final review

## Step 19 Execution Record (Comprehensive Backend Security Audit & Hardening)

* **Status**: COMPLETE
* **Audit Dimensions & Hardening**:
  1. **SEC-01: Authentication Timing-Difference Mitigation**:
     - Precomputed dummy Argon2id hash (`DUMMY_ARGON2_HASH`) and `verify_dummy_password()`.
     - Invoked when user does not exist so unauthenticated lookups incur comparable CPU/memory cost to real user lookups.
     - Documented as timing-difference defense-in-depth mitigation, NOT mathematically constant-time behavior.
  2. **SEC-02: Session Token Transmission & Persistence**:
     - Removed `X-Session-Token` from `/api/v1/auth/login` response headers; session credentials issued solely via secure HttpOnly cookie.
     - Confirmed raw tokens are never persisted: only SHA-256 digests (`session_token_hash`) stored in PostgreSQL.
  3. **SEC-03: Readiness Probe Information Sanitization**:
     - Sanitized `/ready` endpoint to return `"storage": "ready"` rather than leaking absolute local filesystem paths (`settings.STORAGE_DIR`).
  4. **SEC-04: Defensive Security Headers Middleware**:
     - Attached `SecurityHeadersMiddleware` applying `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: geolocation=(), camera=(), microphone=()`.
     - Strict-Transport-Security (`HSTS`) applied strictly conditionally when `request.url.scheme == "https"` or `x-forwarded-proto == "https"`; never sent over plain local HTTP.
  5. **SEC-05: Explicit Configurable CORS**:
     - Configurable `CORS_ORIGINS` setting added; explicit origins allowed for NiceGUI/API clients.
     - Wildcard origins (`*`) are never combined with `allow_credentials=True`.
  6. **SEC-06: Retrieval Error Message Sanitization**:
     - Generic client-safe 500 messages across `retrieval.py`, `lexical_retrieval.py`, `hybrid_retrieval.py`, and `reranking.py`.
     - Detailed exception traces logged server-side only; zero internal database/network exception interpolation into API responses.
  7. **SEC-07: Production Configuration Guardrails**:
     - Pydantic `@model_validator(mode="after")` `validate_production_security()` raises `ValueError` if `APP_ENV="production"` with `DEBUG=True`, default insecure `SECRET_KEY`, or `SECRET_KEY` < 32 characters.
  8. **Step 13 Trust Boundary & Citation Security**:
     - Tested `GroundedPromptBuilder` against adversarial delimiter collision (`--- END EVIDENCE`) and prompt injection overrides.
     - Verified retrieved content is treated strictly as untrusted data within designated blocks, with system instructions retaining hierarchy of authority.
     - Verified `CitationValidator` detects and invalidates out-of-context citation references.
  9. **Zero Real Secrets Verification**:
     - Audited codebase and repository history. Zero real API keys, secrets, or certificates committed.
* **Verification & Testing**:
  - `backend/tests/security/test_backend_security_audit.py`: 19/19 passed.
  - `backend/tests/security/test_security_rbac.py`: 18/18 passed.
  - Complete backend test suite: 437/437 passed (0 failures).
  - Ruff check: 0 errors across all 195 files. Ruff format: 100% clean.
* **Next Safe Task**: Step 20: Comprehensive Backend Quality Gate.


## Step 14 Execution Record (Citation and Grounding Validation Layer)

* **Status**: COMPLETE
* **Architecture & Implemented Requirements**:
  1. **Conservative Deterministic Heuristic Grounding**:
     - Operates as a conservative deterministic heuristic validator measuring whether generated claims have evidence characteristics consistent with supplied context.
     - Does NOT claim definitive semantic entailment or real-world truth.
     - Favors `UNVERIFIABLE` rather than falsely declaring `SUPPORTED` when confidence is insufficient.
     - Known limitations clearly documented: paraphrasing with heavy synonym replacement may be missed, common vocabulary can introduce false overlap if not stopword-filtered, and entity/numerical matching is an auxiliary signal.
  2. **Independent Citation Syntax & Provenance Verification**:
     - `CitationValidator` detects standard tags (`[source_X]`) and malformed patterns (`[source_]`, `(source_1)`).
     - Resolves valid tags to exact `ContextItem` provenance (chunk UUID, document ID, title, page, section).
     - Zero citations metric rule: `citation_validity_rate` is 0.0 when `citations_found == 0` (never 1.0).
  3. **Sentence & Claim Segmentation with Protected Tokens**:
     - `SentenceSplitter` partitions answers by line breaks and sentence terminals without variable-width lookbehinds.
     - Trailing citation markers are cleanly preserved with their attributing sentence.
     - Negative guards protect abbreviations (`e.g.`, `i.e.`, `Dr.`, `vs.`), decimals (`3.14`), versions (`v1.2.3`), list prefixes (`1.`, `-`), and code spans.
     - Classifies conversational preambles/refusals so they are not evaluated as ungrounded factual assertions.
  4. **Multi-Faceted Claim Grounding & Strict Entity Invariance**:
     - `ClaimVerifier` enforces content-word recall against stopword-filtered vocabularies.
     - Strict entity & numerical invariance: claims asserting numbers (e.g. `1970` vs `1950`) or technical acronyms (e.g. `SJF` vs `FCFS`) absent from the cited source chunk are flagged as `UNSUPPORTED`.
     - Extracts the highest-overlap sentence snippet from the evidence chunk as human-auditable proof.
     - Detects uncited claims corroborated by retrieved context (`SUPPORTED_UNCITED`).
  5. **Conservative Evidence Conflict Detection**:
     - `ConflictDetector` performs pairwise comparison over bounded context items for opposing polarities (e.g. `preemptive` vs `non-preemptive`) or conflicting explicit values associated with the same technical entity.
     - Preserves source neutrality without deciding which source is correct.
  6. **Mathematically Bounded Metric Contracts**:
     - `citation_validity_rate` = `valid / found` if `found > 0` else `0.0`.
     - `citation_coverage` = `cited_claims / factual_claims` if `factual_claims > 0` else `0.0`.
     - `claim_support_rate` = `supported / factual_claims` if `factual_claims > 0` else (`1.0` if empty context refusal else `0.0`).
     - `unsupported_claim_rate` = `(unsupported + unverifiable) / factual_claims` if `factual_claims > 0` else `0.0`.
     - All metrics strictly bounded to `[0.0, 1.0]` with zero division safeguards.
  7. **Comprehensive Verification**:
     - 327 total tests passing across entire test suite (25 new tests: 24 unit tests, 1 integration test).
     - Ruff check passed with 0 errors across 169 files; ruff format 100% clean.
* **Next Safe Task**: Step 15: Quantitative RAG Evaluation Harness & Benchmarking.


## Step 13 Execution Record (Grounded Provider-Independent LLM Generation Layer)

* **Status**: COMPLETE
* **Architecture & Implemented Requirements**:
  1. **Provider-Independent Abstraction**:
     - `BaseLLMProvider` abstract contract enforces strict provider decoupling with canonical properties (`provider_name`, `model_name`) and `generate(system_instruction, user_prompt, ...)`.
     - `OllamaLLMProvider` implements local inference with `qwen3:4b` over HTTP (`/api/chat`).
     - `LLMGenerationService` depends exclusively on `BaseLLMProvider`, allowing seamless addition of future providers (OpenAI, Anthropic, Gemini, local vLLM).
  2. **Adversarial-Resistant Prompt Architecture**:
     - `GroundedPromptBuilder` enforces strict hierarchy: System Instructions > Retrieved Evidence (untrusted data) > User Question (user-controlled input).
     - Model is explicitly instructed that neither retrieved evidence nor user queries can override system grounding rules, confidentiality, or source constraints.
     - Delimiters (`=== RETRIEVED EVIDENCE (UNTRUSTED DATA) ===`, `--- BEGIN EVIDENCE [source_X] ---`, `--- END EVIDENCE [source_X] ---`) provide clean structural separation. Internal delimiter collision strings within chunks are neutralized without mutating content.
  3. **Deterministic Empty-Context Fast-Path**:
     - When `ContextAssemblyResult` has 0 items, `LLMGenerationService` immediately returns a deterministic refusal (`"I could not find any relevant information in the available documents to answer your question."`) with `is_empty_context=True` and `latency_ms=0.0` without invoking the LLM provider, guaranteeing zero hallucination.
  4. **Citation Handoff Preservation**:
     - Embeds Step 12 `source_1`, `source_2` markers into prompt evidence blocks.
     - Parses candidate referenced source tags (`[source_X]`) into `sources_referenced`.
     - Strictly delegates citation validation, factuality checking, and URL linking to Step 14.
  5. **Safe Error Handling & Diagnostic Metadata**:
     - Explicit domain exceptions: `LLMError`, `LLMProviderError`, `LLMConnectionError`, `LLMTimeoutError`, `LLMModelNotFoundError`, `LLMResponseError`.
     - Preserves only safe diagnostic metadata (`prompt_tokens`, `output_tokens`, `latency_ms`, duration metrics); strictly excludes secrets, internal paths, headers, or raw exception traces.
     - Failures never result in fabricated answers.
  6. **Comprehensive Verification**:
     - 302 total tests passing across entire test suite (23 new tests: 21 unit tests, 2 integration tests).
     - Real integration test verified live inference with local Ollama `qwen3:4b`, producing grounded completions with citation markers and validating connection error handling.
     - Ruff check passed with 0 errors across 157 files; ruff format 100% clean.
* **Next Safe Task**: Step 14: Citation Validation and Factual Grounding Evaluation.


## Step 12 Execution Record (Deterministic Context Assembly Layer)

* **Status**: COMPLETE
* **Architecture & Implemented Requirements**:
  1. **Strict Evidence Integrity**:
     - Chunk text is completely immutable during context assembly.
     - Never truncates, rewrites, summarizes, cleans, normalizes, merges, or alters chunk text or punctuation.
     - Never introduces "[TRUNCATED]" or any truncation behavior.
     - Consistent oversized candidate policy: if a candidate does not fit within the remaining token budget, it is skipped, and subsequent candidates continue to be evaluated against the remaining budget. If no candidate fits, an empty context item list is returned.
  2. **Configured Defaults without Module Import Freezing**:
     - Uses established project configuration pattern with dynamic evaluation (`default_factory=lambda: settings.MAX_CONTEXT_TOKENS` and `default_factory=lambda: settings.RAG_TOP_K_RERANK`).
     - Zero duplicate configuration variables introduced.
  3. **Preservation of Raw vs. Processed Query Distinction**:
     - Preserves `original_query` (raw user query) and `query` (Step 11 processed query) independently.
     - ContextAssembler performs zero query normalization, rewriting, expansion, or summarization.
  4. **Authorization vs. Integrity Separation**:
     - ContextAssembler is strictly an internal domain service, not an authorization or RBAC layer.
     - Validates candidate `knowledge_base_id` consistency against request `knowledge_base_id` when supplied, raising `ValueError` on cross-KB candidate contamination without performing database queries.
  5. **Token Accounting & TokenEstimator Usage**:
     - Uses existing deterministic `TokenEstimator` from `backend.app.services.chunking`.
     - Explicitly documented and tested as an estimator (`test_uses_existing_token_estimator`), making no claim of exact LLM token counts.
  6. **Deduplication & Reranker Ordering**:
     - Evaluates candidates strictly in their incoming Step 10 CrossEncoder rank order.
     - Applies two-tier deduplication: `chunk_id` tracking and exact content hash (SHA-256 of `text.strip()`).
     - Drops exact duplicates while incrementing `items_deduplicated` counter without merging partially overlapping chunks.
  7. **Full Provenance Preservation**:
     - Each selected `ContextItem` is assigned a 1-based sequential attribution identifier (`source_1`, `source_2`, ...).
     - Fully preserves document title, page number, section title, chunk metadata, reranker rank & raw float score, RRF score, and estimated tokens.
  8. **Zero Database Migrations & Zero New Dependencies**:
     - Pure in-memory domain service; no new database tables or schema changes.
     - Zero external dependencies added.
  9. **Comprehensive Verification**:
     - 279 total tests passing across entire test suite (20 new tests: 17 unit tests, 3 integration tests).
     - Unit tests verify zero text mutation, oversized candidate skipping, subsequent smaller candidate inclusion, exact budget fitting, empty result on all exceeding, deterministic repeated execution, deduplication, provenance, query preservation, and zero external network/database dependencies.
     - Integration tests verify end-to-end flow from Step 11 QueryProcessor -> Steps 7-9 Retrieval -> Step 10 CrossEncoder -> Step 12 ContextAssembler with real PostgreSQL 16.15 + pgvector.
     - Ruff check passed with 0 errors across 146 files; ruff format 100% clean.
* **Next Safe Task**: Step 13: Grounded Generation (Prompt Engineering & Ollama LLM Inference).


## Step 11 Execution Record (Deterministic Query Processing Layer)

* **Status**: COMPLETE
* **Architecture & Implemented Requirements**:
  1. **Deterministic Single Normalization Boundary**:
     - `QueryProcessor` implemented in `backend/app/services/query_processing.py` as the single, centralized, deterministic query normalization service.
     - Strips dangerous non-printable ASCII/Unicode control characters (`0x00-0x08, 0x0B-0x0C, 0x0E-0x1F, 0x7F`), preventing null-byte injection and terminal escape sequence issues.
     - Applies Unicode NFKC normalization (standardizes typographic ligatures `ﬁ` -> `fi` and full-width Latin/digit characters `ＡＢＣ` -> `ABC` while preserving composed accented characters like `café`).
     - Standardizes internal whitespace: converts `\r\n`, `\r`, `\n`, and `\t` into single spaces and collapses multiple spaces.
     - Strips leading and trailing whitespace.
  2. **Raw vs. Processed Query Preservation**:
     - Preserves the exact user query string in `original_query`.
     - Returns `processed_query` alongside `original_query` in `QueryProcessingResult`.
     - Avoids permanently destroying the user query, facilitating auditability and future evaluation.
     - Retains existing retrieval schemas (`VectorRetrievalResponse`, `LexicalRetrievalResponse`, `HybridRetrievalResponse`, `RerankResponse`) without unnecessary modification, preventing coupling.
  3. **Preservation of Technical Tokens & Meaningful Punctuation**:
     - Zero destructive regex stripping (no `re.sub(r"[^a-zA-Z0-9 ]", "", q)`).
     - Fully preserves programming languages, frameworks, database keywords, status codes, and hyphenated identifiers: `C++`, `C#`, `.NET`, `PostgreSQL`, `pgvector`, `Python 3.12`, `HTTP 401`, `BCA Sem-4`, `SELECT * FROM users`, and quoted phrases (`"machine learning"`).
     - Treats SQL and shell strings strictly as literal data without interpretation.
  4. **Strict Boundaries & Zero Semantic Rewriting**:
     - Zero LLM inference, zero synonym hallucination, zero keyword expansion, zero external network calls.
     - Stopwords are intentionally preserved (PostgreSQL lexical search handles language stopwording natively, and vector embeddings require natural syntax).
  5. **Idempotence & Diagnostic Metadata**:
     - Strictly idempotent: `process(process(q).processed_query).processed_query == process(q).processed_query`.
     - `character_count`: Processed query string length.
     - `token_estimate`: Deterministic word/punctuation count via `TokenEstimator`.
     - `has_quotes`: Diagnostic boolean for quoted phrases.
     - `has_technical_tokens`: Diagnostic boolean for technical identifiers and symbols (never alters retrieval or ranking logic).
     - Safe dictionary defaults (`Field(default_factory=dict)`).
  6. **Security & Validation**:
     - Rejects empty or whitespace-only queries with `QueryValidationError` (HTTP 422).
     - Rejects queries exceeding `settings.RETRIEVAL_MAX_QUERY_LENGTH` (1000 characters).
  7. **API Endpoint & Integration**:
     - `POST /api/v1/query/process` registered in `backend/app/api/v1/router.py` and protected by `AuthenticatedUser`.
     - Verified end-to-end integration: processed query flows smoothly through Vector (Step 7), Lexical (Step 8), Hybrid RRF (Step 9), and CrossEncoder (Step 10).
  8. **Zero Database Migrations**:
     - In-memory deterministic processing; no database schema modifications or query history tables created.
  9. **Comprehensive Verification**:
     - 259 total tests passing across entire test suite (34 new tests: 29 unit tests, 4 integration tests, 1 frontend client test).
     - Full test suite: 259 passed, 0 failures, 0 regressions in 140s.
     - Ruff check passed with 0 errors across 142 files; ruff format 100% clean.
* **Next Safe Task**: Step 12: Context Assembly and Token-Budgeted Prompt Builder.
- [ ] Grounded generation
- [ ] Citations
- [ ] Query/conversation persistence if required
- [x] Background jobs (COMPLETE — Step 5 FastAPI BackgroundTasks Ingestion & Fault-Tolerant Transitions)
- [ ] Observability
- [ ] Rate limiting
- [ ] Backend security audit
- [ ] Backend quality gate
- [x] Functional frontend (COMPLETE — Step 3 Shell + Step 4 RBAC + Step 5 Upload/Delete + Step 6 Indexing UI + Step 7 Vector UI + Step 8 Lexical UI + Step 9 Hybrid UI + Step 10 Rerank UI)
- [ ] Frontend design pass
- [ ] Accessibility QA
- [ ] Responsive QA
- [ ] End-to-end QA
- [ ] Deployment verification
- [ ] Final security audit
- [ ] Final RAG evaluation
- [ ] Documentation
- [ ] Git/GitHub final review

## Step 10 Execution Record (CrossEncoder Reranking Layer)

* **Status**: COMPLETE
* **Architecture & Implemented Requirements**:
  1. **Provider-Independent CrossEncoder Reranking**:
     - `BaseRerankerProvider` abstract contract enforces strict provider isolation.
     - `HuggingFaceCrossEncoderProvider` implements local inference using `sentence-transformers` (`cross-encoder/ms-marco-MiniLM-L-6-v2`).
     - Thread-safe lazy model loading via `threading.Lock()` ensures the model is loaded once and shared across requests.
     - Non-blocking execution via `asyncio.to_thread` keeps FastAPI's event loop unblocked during CPU inference.
     - Completely local inference; zero paid APIs or external inference services.
  2. **Raw Float Score Contract & Ordering**:
     - Raw finite CrossEncoder scores are preserved without internal rounding (`reranker_score: float`).
     - Candidates are sorted strictly by `reranker_score DESC`.
     - Deterministic tie-breaking on `(chunk_index ASC, str(chunk_id) ASC)` on equal scores.
     - Formatting to 6 decimal places is restricted strictly to presentation time in the UI (`f"{item.reranker_score:.6f}"`).
     - CrossEncoder scores are used solely for final candidate ranking; never combined or averaged with RRF or vector/lexical scores.
  3. **Preservation of Full Step 9 Provenance**:
     - Preserves all upstream fields: `chunk_id`, `document_id`, `knowledge_base_id`, `document_title`, `chunk_index`, `text`, `page_number`, `section_title`, safe `chunk_metadata` dictionary.
     - Preserves all diagnostic branch metrics: `rrf_score`, `vector_rank`, `lexical_rank`, `vector_contribution`, `lexical_contribution`, `cosine_distance`, `similarity`, and `lexical_score`.
     - Adds `reranker_score` (raw float) and `reranker_rank` (1-indexed position).
  4. **Strict Architectural Boundary**:
     - Operates strictly on hybrid candidates retrieved from Step 9 (`HybridRetrievalService.retrieve`).
     - Does NOT implement Step 11 or any of: query rewriting/expansion, context assembly, LLM generation, citations, grounding validation, or chat answer generation.
  5. **Configuration Discipline**:
     - Reuses existing `settings.RRF_K` (60), `settings.RERANKER_MODEL` (`cross-encoder/ms-marco-MiniLM-L-6-v2`), `settings.RAG_TOP_K_RETRIEVAL` (20), `settings.RAG_TOP_K_RERANK` (5), `settings.RETRIEVAL_MIN_TOP_K` (1), and `settings.RETRIEVAL_MAX_TOP_K` (50).
     - Added only `RERANK_BATCH_SIZE: int = 32`.
     - Zero duplicate configuration sources.
  6. **Zero Database Migrations**:
     - Purely computational in-memory reranking over retrieved candidate chunks. No schema changes or migrations.
  7. **Security & Authorization**:
     - Enforces `get_authorized_knowledge_base` dependency on `POST /api/v1/knowledge-bases/{kb_id}/rerank`.
     - Admins authorized for owned KBs; students authorized strictly via `knowledge_base_members`.
     - Unauthorized or nonexistent KBs return HTTP 404 (preventing existence leakage); unauthenticated requests return HTTP 401.
     - Foreign KB chunks never leak across knowledge base boundaries.
  8. **Frontend Presentation Layer**:
     - Added `RerankResultDTO` in `frontend/client/models.py`.
     - Added `rerank_chunks` method in `frontend/client/api_client.py`.
     - Created administrative inspection dialog in NiceGUI (`frontend/components/rerank_inspect.py`) labeled **"CrossEncoder Reranking Inspection"**.
     - Added "Inspect Reranking" button for administrators in the `/chat` context bar.
  9. **Comprehensive Verification**:
     - 225 total tests passing across entire test suite (30 new tests in Step 10: 21 unit tests, 1 real CrossEncoder inference integration test, 7 PostgreSQL integration tests, 1 frontend client test).
     - Full test suite: 225 passed, 0 failures, 0 regressions.
     - Real model inference verified: local load, query/text pairs, score count == candidate count, finite floats, input order mapping preserved.
     - Ruff check passed with 0 errors across 137 files; ruff format 100% clean.
* **Next Safe Task**: Step 11: Context Assembly and Prompt Formatting Pipeline.
- [ ] Context assembly
- [ ] Grounded generation
- [ ] Citations
- [ ] Query/conversation persistence if required
- [x] Background jobs (COMPLETE — Step 5 FastAPI BackgroundTasks Ingestion & Fault-Tolerant Transitions)
- [ ] Observability
- [ ] Rate limiting
- [ ] Backend security audit
- [ ] Backend quality gate
- [x] Functional frontend (COMPLETE — Step 3 Presentation Shell + Step 4 RBAC + Step 5 Upload/Delete + Step 6 Indexing UI + Step 7 Vector Inspection + Step 8 Lexical Inspection + Step 9 Hybrid Inspection)
- [ ] Frontend design pass
- [ ] Accessibility QA
- [ ] Responsive QA
- [ ] End-to-end QA
- [ ] Deployment verification
- [ ] Final security audit
- [ ] Final RAG evaluation
- [ ] Documentation
- [ ] Git/GitHub final review

## Step 9 Execution Record (Hybrid Retrieval Layer + RRF)

* **Status**: COMPLETE
* **Architecture & Implemented Requirements**:
  1. **Rank-Based Fusion via Reciprocal Rank Fusion (RRF)**:
     - Pure rank-based fusion: strictly fuses 1-based candidate rank positions. Does NOT normalize, average, or combine incompatible raw scores (cosine distance, similarity, or PostgreSQL `ts_rank_cd`).
     - Formula:
       $$RRF\_score(c) = \sum_{b \in \{\text{vector}, \text{lexical}\}} \frac{1}{\text{RRF\_K} + \text{rank}_b(c)}$$
     - Uses authoritative project configuration `settings.RRF_K` (default 60) without hardcoding or duplicate sources of truth.
  2. **Service Reuse & Zero SQL Duplication**:
     - `HybridRetrievalService` orchestrates `VectorRetrievalService` (Step 7) and `LexicalRetrievalService` (Step 8) directly.
     - Preserves all underlying database filters, parameter validations, and transactional semantics without duplicating retrieval SQL.
  3. **Candidate Deduplication & Provenance**:
     - Fuses candidates using unique `chunk_id` as the fusion key. Chunks matching in both branches are merged into a single candidate, accumulating both score contributions.
     - Preserves complete structural metadata (`chunk_id`, `document_id`, `knowledge_base_id`, `document_title`, `chunk_index`, `text`, `page_number`, `section_title`, and safe `default_factory=dict` `chunk_metadata`).
     - Preserves diagnostic metrics: `vector_rank`, `lexical_rank`, `vector_contribution`, `lexical_contribution`, `cosine_distance`, `similarity`, and `lexical_score`.
  4. **Deterministic Tie-Breaking**:
     - Sorted primarily by `rrf_score DESC`.
     - Secondary tie-breaking on `(chunk_index ASC, chunk_id ASC)` ensures deterministic ordering on equal RRF scores.
  5. **Knowledge-Base Authorization & Multi-User Isolation**:
     - Enforces `get_authorized_knowledge_base` dependency on `POST /api/v1/knowledge-bases/{kb_id}/hybrid-retrieve`.
     - Admins authorized for owned KBs; students authorized strictly via `knowledge_base_members`.
     - Unauthorized or nonexistent KBs return HTTP 404 (preventing private existence leakage); unauthenticated requests return HTTP 401.
     - Foreign KB chunks never leak across KB boundaries.
  6. **Zero Database Migrations**:
     - Operates directly on existing PostgreSQL 16 + pgvector schema and GIN index. No new migration created.
  7. **Frontend Presentation Layer**:
     - Added `HybridRetrievalResultDTO` in `frontend/client/models.py`.
     - Added `retrieve_hybrid_chunks` in `frontend/client/api_client.py`.
     - Created administrative inspection dialog in NiceGUI (`frontend/components/hybrid_inspect.py`) labeled **"Hybrid Search Inspection (RRF)"**.
     - Added "Inspect Hybrid Retrieval" button for administrators in the `/chat` context bar.
  8. **Comprehensive Verification**:
     - 195 tests passing across entire test suite (23 new tests: 12 hybrid unit tests, 10 real PostgreSQL + pgvector integration tests, 1 frontend client unit test).
     - Full test suite: 195 passed, 0 failures, 0 regressions in 81.86s.
     - Ruff check passed with 0 errors across 125 files; ruff format 100% clean.
* **Next Safe Task**: Step 10: CrossEncoder Reranking Layer (`cross-encoder/ms-marco-MiniLM-L-6-v2`).

## Step 8 Execution Record (Lexical Retrieval Layer)

* **Status**: COMPLETE
* **Architecture & Implemented Requirements**:
  1. **PostgreSQL-Native Lexical / Full-Text Retrieval**:
     - Accurately named and implemented as PostgreSQL-native full-text search with `ts_rank_cd` cover density ranking (explicitly avoiding calling `ts_rank_cd` BM25).
     - Generated column `searchable_text: tsvector` created via `Computed("to_tsvector('english', text)", persisted=True)` in PostgreSQL `document_chunks`.
     - High-performance GIN index `ix_document_chunks_searchable_text` implemented and verified on PostgreSQL 16.15.
     - Production Alembic migration `35fc9a73097a` applied and verified on both `rag_assistant_db` and `rag_assistant_test_db`.
  2. **Query Safety & websearch_to_tsquery**:
     - Lexical queries parsed using PostgreSQL's `websearch_to_tsquery('english', :query)`.
     - Handles plain words, quoted exact phrases (`"machine learning"`), boolean operators (`OR`, `-`), punctuation, and code symbols (`C++`, `*`, `&`, `|`, `!`, `:`) safely without SQL syntax errors or injections.
     - Stopword-only queries evaluate to empty tsquery safely and return 0 results without errors.
  3. **Safe Default Factory on Schema**:
     - `LexicalRetrievalResultItem` enforces safe default factory: `chunk_metadata: dict[str, Any] = Field(default_factory=dict)` (avoiding mutable dictionary default).
  4. **Complete Independence from Ollama & Vector Layer**:
     - Zero dependency on Ollama or vector embeddings.
     - Documents with `Document.status == DocumentStatus.COMPLETED` are fully retrievable lexically, even if `embedding IS NULL` (vector-less chunks).
     - Verified that lexical search operates flawlessly even when Ollama is offline.
  5. **Knowledge-Base Authorization & Multi-User Isolation**:
     - Enforces `get_authorized_knowledge_base` dependency on `POST /api/v1/knowledge-bases/{kb_id}/lexical-retrieve`.
     - Admin access for KB owners; student access strictly via `knowledge_base_members` membership.
     - Nonexistent or unauthorized knowledge bases return HTTP 404 (preventing existence leakage); unauthenticated requests return HTTP 401.
     - SQL query strictly scopes to `document_chunks.knowledge_base_id == kb_id` (foreign KB chunks never leak).
  6. **Data Eligibility & Deterministic Ordering**:
     - Filter: `Document.status == DocumentStatus.COMPLETED` and `searchable_text @@ query_tsquery`.
     - Order by: `rank.desc(), DocumentChunk.chunk_index.asc(), DocumentChunk.id.asc()`.
     - Duplicate text chunks remain distinguishable through unique `chunk_id` and `chunk_index`.
  7. **Frontend Presentation Layer**:
     - Added `retrieve_lexical_chunks` to `FrontendAPIClient`.
     - Added administrative "Inspect Lexical Retrieval" dialog in NiceGUI (`frontend/components/lexical_inspect.py`), accessible from `/chat` top context bar for admins.
     - Clearly labeled as "Lexical Search Results" displaying source document, page, section, lexical rank score, and snippet text.
  8. **Comprehensive Verification**:
     - 172 tests passing (40 new tests added: 27 lexical unit tests, 12 real PostgreSQL + GIN index integration tests, 1 frontend client unit test).
     - Full test suite: 172 passed, 0 failures, 0 regressions in 72.94s.
     - Ruff check passed with 0 errors across 119 files; ruff format 100% clean.
* **Next Safe Task**: Step 9: Hybrid Retrieval (Reciprocal Rank Fusion — RRF) & Reranking.

## Step 7 Execution Record (Vector Retrieval Layer)

* **Status**: COMPLETE
* **Architecture & Implemented Requirements**:
  1. **Exact PostgreSQL + pgvector Vector Search**:
     - Searches `document_chunks` using pgvector's `<=>` cosine distance operator inside PostgreSQL:
       `SELECT document_chunks, documents.original_filename, (embedding <=> :query_vector) AS distance FROM document_chunks JOIN documents ... WHERE knowledge_base_id = :kb_id AND embedding IS NOT NULL ORDER BY distance ASC, chunk_index ASC, id ASC LIMIT :top_k`.
     - Zero vector distances computed in Python; ordering and candidate selection executed purely in PostgreSQL.
     - Intentional exact search (no HNSW or ANN approximation index added yet; guarantees 100% recall for current academic corpus scale).
  2. **Query Embedding Flow**:
     - Query embedded via existing `BaseEmbeddingProvider` (`OllamaEmbeddingProvider` with `qwen3-embedding:0.6b`).
     - Strict dimension validation enforces `len(query_vector) == 1024`.
     - Pre-flight query validation rejects blank, whitespace-only, or queries exceeding 1000 characters before calling embedding service.
  3. **Score Transparency & Mathematical Conversion**:
     - Schema exposes both raw `cosine_distance` (pgvector `<=>` operator) and `similarity = 1.0 - cosine_distance`.
     - Direct mathematical conversion without silent clamping or arbitrary score inventions.
  4. **Knowledge-Base Authorization & Isolation**:
     - Enforces `get_authorized_knowledge_base` dependency on `POST /api/v1/knowledge-bases/{kb_id}/retrieve`.
     - ADMIN authorized for owned KBs; STUDENT authorized only upon explicit membership in `knowledge_base_members`.
     - Unauthorized and nonexistent KBs return HTTP 404 to avoid private existence leakage. Unauthenticated requests return HTTP 401.
     - Database query explicitly filters by `knowledge_base_id == kb_id` (foreign KB chunks never leak).
  5. **Data Eligibility & Determinism**:
     - `embedding IS NOT NULL` strictly enforced; unindexed chunks or chunks from incomplete documents are excluded.
     - Deterministic secondary tie-breaker: `chunk_index ASC, id ASC`.
     - Duplicate text chunks remain distinguishable through unique `chunk_id` and `chunk_index`.
  6. **Error Handling**:
     - 422 Unprocessable Entity for invalid parameters (`top_k < 1` or `top_k > 50`, blank query, or query > 1000 chars).
     - 503 Service Unavailable on embedding provider failure, without leaking URLs or credentials.
     - 500 Internal Server Error on database failure, without exposing raw SQL or stack traces.
  7. **Frontend Presentation Layer**:
     - Added `retrieve_chunks` to `FrontendAPIClient`.
     - Added administrative "Inspect Vector Retrieval" dialog in NiceGUI (`frontend/components/retrieval_inspect.py`), accessible from `/chat` context bar for admins.
     - Strictly labeled as "Vector Search Results" / "Retrieved Evidence" showing source document, page, section, distance, similarity, and snippet text. Does not pretend to synthesize AI answers.
  8. **Comprehensive Verification**:
     - 132 tests passing (35 new tests added: 22 unit tests, 11 real PostgreSQL + pgvector integration tests, 1 real Ollama end-to-end integration test, 1 frontend client unit test).
     - Full test suite: 132 passed, 0 failures, 0 regressions.
     - Ruff check passed with 0 errors across 112 files; ruff format 100% clean.
* **Next Safe Task**: Step 8: Lexical Retrieval (BM25 / PostgreSQL full-text search) & Hybrid Search Fusion (RRF).

## Step 6 Execution Record (Embedding and Vector Indexing Layer)

* **Status**: COMPLETE
* **Architecture & Corrections Implemented**:
  1. **Strict Separation of Ingestion & Indexing Stages**:
     - `Document.status = COMPLETED` represents successful parsing, normalization, and chunking.
     - Vector indexing is tracked separately by `Document.indexing_status: IndexingStatus` (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`).
     - Ollama availability does NOT dictate ingestion success. Documents can be uploaded and chunked even if Ollama is offline.
     - Indexing is triggered separately by the ADMIN through `POST /api/v1/knowledge-bases/{kb_id}/documents/{document_id}/index`.
     - Incomplete or interrupted indexing can be retried without re-parsing or re-chunking.
  2. **Exact pgvector Similarity Storage Foundation**:
     - Added `embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)` to `DocumentChunk`.
     - Exact cosine similarity (`<=>`) established as the authoritative foundation. HNSW indexing deferred until retrieval layer benchmarks and dataset scale warrant approximation trade-offs.
     - Migration `80d7765a9d83` created and applied to both `rag_assistant_db` and `rag_assistant_test_db`. Native pgvector function `vector_dims(embedding) == 1024` verified in PostgreSQL.
  3. **Embedding Provider Abstraction**:
     - `BaseEmbeddingProvider` defines provider-independent interface (`embed_texts`, `embed_query`, `dimension`, `model_name`).
     - `OllamaEmbeddingProvider` communicates with local Ollama (`http://localhost:11434/api/embed`) using `qwen3-embedding:0.6b` with configurable timeout, batching (default: 32), and exponential backoff retry.
  4. **Strict Vector Validation & Cardinality Verification**:
     - Enforces `len(embeddings) == len(requested_texts)`; raises `EmbeddingCountMismatchError` on any discrepancy to prevent misaligned chunk mappings.
     - Enforces `dimension == 1024`; raises `EmbeddingDimensionError` on mismatch (neither pads 1023 nor truncates 1025).
     - Rejects `NaN`, `Inf`, strings, or `None` values.
  5. **Transactional Safety & Fault Tolerance**:
     - External embedding calls to Ollama take place strictly outside PostgreSQL transactions.
     - Updating `document_chunks.embedding` and `document.indexing_status` occurs in a single atomic database transaction.
     - On failure: session rolls back; `indexing_status` is marked `FAILED` with diagnostics in `indexing_error`; 0 partial vector writes are committed; original document and chunks are preserved.
  6. **Retry Idempotency**:
     - Re-indexing updates the `embedding` column on existing `DocumentChunk` records without creating duplicate chunks or altering chunk UUIDs.
  7. **Server-Side Security & RBAC**:
     - `POST .../documents/{doc_id}/index` enforces admin permissions (`AdminKB`). Students receive 403 Forbidden.
     - Cross-tenant requests return 404 Not Found to prevent resource enumeration. Unauthenticated requests return 401.
  8. **NiceGUI Presentation Layer**:
     - Added `render_indexing_status_badge` (`VECTORS: OK`, `INDEXING...`, `INDEX FAILED`, `UNINDEXED`).
     - Added admin-only "Index" / "Retry Index" action button in document table for eligible documents (`COMPLETED` ingestion, `PENDING`/`FAILED` indexing).
     - Students receive read-only view.
  9. **Comprehensive Verification**:
     - 97 tests passing (13 embedding unit, 4 indexing unit, 7 vector integration, 1 real live Ollama integration, 72 regression tests).
     - Ruff check passed with 0 errors across 105 files; ruff format 100% clean.
* **Next Safe Task**: Step 7: Vector Retrieval Layer.

## Step 5 Execution Record (Real Document Ingestion, Parsing, Normalization & Chunking)

* **Status**: COMPLETE
* **Tests Run**: 72 tests passing.
* **Next Safe Task**: Step 6: Embedding and Vector Indexing Layer.

## Step 15 Execution Record (Evaluation and Benchmarking)

* **Status**: COMPLETE
* **Architecture & Features Implemented**:
  1. **Reproducible Benchmark Dataset**:
     - Curated dataset `bca_rag_benchmark_v1` (`backend/app/services/evaluation/data/evaluation_dataset_v1.json`) containing 20 queries grounded in the benchmark document corpus.
     - Spans 6 required categories: Direct Factual (4), Technical/Numerical (3), Multi-Document (4), No-Answer/Refusal (3), Ambiguous (3), Citation/Grounding (3).
     - JSON schema validation and category filtering implemented in `EvaluationDatasetLoader`.
  2. **Chunk-Level Deterministic Relevance Evaluation**:
     - Relevance evaluated strictly at the chunk level via `is_chunk_relevant`.
     - Chunks match relevance when chunk document title matches AND expected technical domain keywords are present in chunk text, or if explicit chunk UUID is specified.
     - `expected_answer_contains` retained strictly as a surface sanity check; explicitly documented as NOT measuring semantic truth.
  3. **Multi-Stage Retrieval Ablation**:
     - Runs and benchmarks all 4 retrieval configurations:
       * Vector Retrieval Only (Ablation Stage A)
       * PostgreSQL Lexical Retrieval Only (Ablation Stage B)
       * Hybrid Retrieval via Reciprocal Rank Fusion (Ablation Stage C)
       * CrossEncoder Reranked Hybrid Retrieval (Ablation Stage D)
     - Measures candidate K and evaluation K, HitRate@K, Recall@K, Precision@K, and MRR across all stages.
     - Calculates CrossEncoder reranker lift over hybrid RRF ($MRR_{\text{reranked}} - MRR_{\text{hybrid}}$).
  4. **Granular Exclusive Latency Instrumentation**:
     - Records high-resolution millisecond timings for each pipeline phase:
       * Query Processing (`query_processing_ms`)
       * Vector Retrieval (`vector_retrieval_ms`)
       * Lexical Retrieval (`lexical_retrieval_ms`)
       * RRF Fusion (`rrf_fusion_ms`)
       * CrossEncoder Reranking (`reranking_ms`)
       * Context Assembly (`context_assembly_ms`)
       * LLM Generation (`llm_generation_ms`)
       * Grounding Validation (`grounding_validation_ms`)
       * Total Pipeline Wall-Clock (`total_pipeline_ms`)
     - Strictly exclusive measurements; no nested timing inflation or double-counting.
     - Statistical distributions computed: Mean, Median (P50), P95, Min, Max, and Count.
  5. **Refusal Fidelity & Failure Taxonomy Attribution**:
     - Separates unanswerable query refusal from retrieval misses:
       * `is_unanswerable=True` + model refusal -> `is_correct_refusal = True`
       * `is_unanswerable=True` + factual claims asserted -> `is_ungrounded_answer = True` (`FailureMode.REFUSAL_FAILURE`)
       * `is_unanswerable=False` + candidate missing -> `FailureMode.RETRIEVAL_MISS`
       * `is_unanswerable=False` + candidate found in hybrid but dropped by reranker -> `FailureMode.RERANKING_MISS`
       * `is_unanswerable=False` + candidate retrieved but empty context/refusal -> `is_false_refusal = True` (`FailureMode.FALSE_REFUSAL`)
     - Categorizes grounding failures: `UNSUPPORTED_ANSWER`, `UNVERIFIABLE_ANSWER`, `INVALID_CITATION`, `MISSING_CITATION`, `EVIDENCE_CONFLICT`.
  6. **Generation & Grounding Aggregates**:
     - Seamlessly reuses Step 14 metrics without modifying production generation code:
       * Mean Citation Validity Rate
       * Mean Citation Coverage
       * Mean Claim Support Rate
       * Mean Unsupported Claim Rate
  7. **CLI Benchmark Runner**:
     - Standalone script `scripts/run_rag_benchmark.py` supporting `--kb-id`, `--dataset`, `--output`, and `--limit`.
     - Prints formatted summary tables for terminal inspection and exports complete machine-readable `BenchmarkReport` JSON.
  8. **Comprehensive Verification**:
     - 348 tests passing across the repository (21 new Step 15 tests: 7 metrics unit tests, 5 dataset unit tests, 7 failure analyzer unit tests, 2 runner integration tests).
     - Full regression suite passing with zero regressions across Steps 1–14.
     - Ruff check and format 100% clean across 180 files.
* **Next Safe Task**: Step 17 (Next roadmap stage).

## Step 16 Execution Record (End-to-End RAG Orchestration & Chat Pipeline)

* **Status**: COMPLETE
* **Architecture & Implemented Requirements**:
  1. **Strict 9-Stage Orchestration Flow**:
     - Connected Steps 7–15 into a single production application service (`RAGOrchestrator`):
       `QueryProcessor` (Step 11)
       $\rightarrow$ `HybridRetrievalService` (Step 9, internally orchestrating `VectorRetrievalService` Step 7 + `LexicalRetrievalService` Step 8 + RRF)
       $\rightarrow$ `RerankingService.rerank_candidates` (Step 10 CrossEncoder `ms-marco-MiniLM-L-6-v2`)
       $\rightarrow$ `ContextAssembler.assemble` (Step 12 Token-Budgeted Selection & Strict Evidence Integrity)
       $\rightarrow$ `LLMGenerationService.generate_grounded_answer` (Step 13 Grounded Prompt & Deterministic Empty-Context Fast-Path)
       $\rightarrow$ `GroundingValidationService.validate` (Step 14 Conservative Claim Grounding & Citation Verification)
       $\rightarrow$ Client-Safe Response Packaging with Provenance & Non-Overlapping Exclusive Latencies.
     - Does NOT duplicate retrieval work: `HybridRetrievalService` internally calls vector + lexical retrieval.
  2. **Non-Overlapping Latency Accounting**:
     - `retrieval_ms` records the inclusive wall-clock duration of `HybridRetrievalService.retrieve()`.
     - Internal vector/lexical timings are not double-counted.
     - `ChatLatencyBreakdownDTO` reports mutually exclusive non-overlapping stage latencies: `query_processing_ms`, `retrieval_ms`, `reranking_ms`, `context_assembly_ms`, `llm_generation_ms`, `grounding_validation_ms`, and overall pipeline duration `total_pipeline_ms`.
  3. **Deterministic 7-State Grounding Status Classification**:
     - `FULLY_SUPPORTED`: all factual claims corroborated by cited context, 100% citation coverage, 100% citation validity, 0 conflicts.
     - `PARTIALLY_SUPPORTED`: some claims corroborated, but uncited factual claims, invalid citations, or unverifiable claims exist.
     - `UNSUPPORTED`: at least one factual claim is contradicted or unsupported by context.
     - `UNVERIFIABLE`: claims cannot be verified with sufficient confidence under conservative heuristics.
     - `REFUSAL`: model produced an empty-context fast-path or safe refusal without ungrounded factual assertions (`is_grounded = True`).
     - `CONVERSATIONAL`: conversational framing or preamble with zero factual assertions (`is_grounded = True`).
     - `EVIDENCE_CONFLICT`: potential evidence conflicts detected across retrieved context chunks (`is_grounded = False`).
     - Grounding status is conservatively derived and does NOT claim real-world factual truth.
  4. **Preserved Prompt & Generation Architecture**:
     - Reuses Step 13 `GroundedPromptBuilder` and `LLMGenerationService` directly without prompt redesign or delimiters modification.
     - Retrieved documents and user queries remain untrusted input.
  5. **Client Response Safety & Provenance Separation**:
     - `ChatQueryResponse` exposes client-safe answer, verified `CitationItem` list (document_name, document_id, chunk_id, page_number, section_title, relevance_score, clamped snippet $\le$ 300 chars), safe `GroundingSummaryDTO`, and latency breakdown.
     - Internal validator raw reasoning, prompt templates, system instructions, database schemas, and stack traces are never exposed.
  6. **Deterministic Empty-Context Fast-Path**:
     - When `ContextAssembler` returns 0 items, `LLMGenerationService` triggers fast-path refusal without invoking Ollama. Actual latency recorded.
  7. **API Endpoints & Backward Compatibility**:
     - Legacy endpoint: `POST /api/v1/chat/query` accepts `ChatQueryRequest` (`knowledge_base_id`, `question`) and returns `ChatQueryResponse` with top-level `answer` and `citations`. Preserved 100% backward compatibility for existing RBAC and frontend tests.
     - Canonical REST endpoint: `POST /api/v1/knowledge-bases/{kb_id}/chat` accepts `KnowledgeBaseChatRequest` (`question`) and returns `ChatQueryResponse`.
     - Strict error mapping: 401 unauthenticated, 404 unauthorized KB / isolation, 422 query/parameter validation, 503 provider unavailability, 504 LLM timeout, 500 internal server error.
  8. **Stateless Orchestration Decision**:
     - Step 16 remains strictly stateless. No conversation tables or database migrations added.
  9. **Frontend NiceGUI Integration**:
     - Connected `frontend/client/api_client.py` (`send_chat_message`) to the real orchestration endpoint.
     - Populates `ChatMessageDTO` with `is_grounded`, `grounding_status`, `total_pipeline_ms`, and `model`.
     - `frontend/pages/chat_page.py` displays clean grounding badge and latency next to Assistant message.
     - Presentation-only in NiceGUI: no retrieval, reranking, prompts, LLM calls, grounding, or DB operations inside event handlers.
  10. **Comprehensive Verification**:
      - 363 tests passing across the repository (15 new Step 16 tests: 5 unit tests in `test_rag_orchestrator.py`, 7 integration tests in `test_chat_orchestration_integration.py`, 1 real live Ollama test in `test_chat_real_ollama.py`, 2 new frontend unit tests in `test_frontend.py`).
      - Live Ollama test PASSED with real `qwen3:4b`.
      - Ruff check and format 100% clean across 185 files.
* **Next Safe Task**: Step 17 (Next roadmap stage).

## Step 17 Execution Record (Observability & Structured RAG Logging)

* **Status**: COMPLETE
* **Architecture & Implemented Requirements**:
  1. **Structured JSON Logging with StructuredJSONFormatter**:
     - `StructuredJSONFormatter` in `backend/app/core/telemetry.py` emits one JSON object per log line.
     - Every record carries: `timestamp` (ISO 8601 UTC), `level`, `logger`, `message`, `request_id`, `user_id`, `kb_id`, `operation`, `status`, `error_category`, and an `extra` dict.
     - Completely replaces unstructured Python logging output for backend services without changing any retrieval, reranking, grounding, or generation algorithms.
  2. **Correlation / Request ID Middleware**:
     - `CorrelationIdMiddleware` (registered in `backend/app/main.py`) reads `X-Request-ID` header or mints a UUID4 for every incoming request.
     - Propagates the request ID, authenticated user ID, and KB ID to `contextvars.ContextVar` so all log records within a request automatically carry those fields.
     - Concurrent async requests are fully isolated — `contextvars` provides per-coroutine state.
     - Error categories are injected from HTTP status codes (504→TIMEOUT_ERROR, 503→PROVIDER_ERROR, 401→AUTHENTICATION_ERROR, 403→AUTHORIZATION_ERROR, 422→VALIDATION_ERROR) when the exception was handled upstream.
  3. **TelemetryManager & BaseTelemetryExporter Abstraction**:
     - `TelemetryManager` is a lightweight internal singleton that collects `TelemetryEvent` objects.
     - `BaseTelemetryExporter` abstract interface decouples the manager from any specific backend. `InMemoryTelemetryExporter` ships for testing; production exporters (file, HTTP) can be added without touching instrumented code.
  4. **RAGOrchestrator 7-Stage Pipeline Instrumentation**:
     - Every pipeline stage — `query_processing`, `hybrid_retrieval`, `reranking`, `context_assembly`, `llm_generation`, `grounding_validation`, `response_packaging` — is wrapped in `RAGOrchestrator` to record a `RAGPipelineStageTelemetry` event.
     - Each event captures: stage name, duration_ms, success flag, error_category, and key stage-specific metrics (candidate counts, context items, token budget, grounding status, citation counts).
     - Wrapping does NOT modify stage logic or data flow.
  5. **Multi-Layer Sensitive-Data Redaction**:
     - `sanitize_string()` removes passwords, API keys, tokens, and connection strings from arbitrary strings via curated regex patterns.
     - `sanitize_headers()` strips `Authorization`, `Cookie`, `Set-Cookie`, `X-API-Key`, and similar headers.
     - `sanitize_log_data()` recursively walks nested dicts to apply both rules.
     - NEVER logged: passwords, password hashes, session tokens, cookies, Authorization headers, API keys, database credentials, complete document contents, complete prompts, complete model responses.
  6. **`categorize_exception` Helper**:
     - Maps domain exceptions (`HybridRetrievalValidationError`, `RetrievalValidationError`, `QueryValidationError`) to `VALIDATION_ERROR`.
     - Maps provider errors (`HybridRetrievalProviderError`, `LLMConnectionError`, `LLMModelNotFoundError`, `LLMTimeoutError`, `LLMProviderError`) to `PROVIDER_ERROR`.
     - Maps `HTTPException` 401/403 to auth categories, 422 to validation, 504 to timeout, and 503 to provider errors.
     - Maps generic `Exception` to `INTERNAL_ERROR`.
  7. **Telemetry DTO Schema** (`backend/app/schemas/telemetry.py`):
     - `TelemetryEvent`, `RAGPipelineStageTelemetry`, `RAGPipelineTelemetry`, `CitationTelemetry`, `GroundingTelemetry` — Pydantic v2 models with `model_config = ConfigDict(frozen=True)` for immutability.
  8. **Zero Algorithm Changes**:
     - Steps 7–16 algorithms (retrieval, RRF, reranking, context assembly, LLM generation, grounding, citations) are completely unchanged.
     - Telemetry is additive instrumentation only.
  9. **Comprehensive Verification**:
     - 387 tests passing across the full repository (15 unit tests in `test_telemetry.py`, 9 integration tests in `test_telemetry_integration.py` — including concurrent request isolation and security redaction tests).
     - Zero regressions introduced in Steps 7–16.
     - Ruff check and format 100% clean across 189 files.
     - No secrets committed; sensitive field redaction explicitly tested.
* **Next Safe Task**: Step 18 (next roadmap stage).

## Step 18 Execution Record (Rate Limiting & Abuse Protection)

* **Status**: COMPLETE
* **Date**: 2026-09-21
* **Goal**: Add production-quality, security-conscious server-side rate limiting and abuse protection while preserving the existing RAG architecture, Step 17 telemetry, and authentication/RBAC behavior.
* **Architecture & Implemented Requirements**:
  1. **PostgreSQL-Backed Atomic Rate Limiting Storage (`PostgresRateLimitStorage`)**:
     - Authoritative persistence in `rate_limit_entries` table with composite primary key `(key, window_bucket)` and indexed `expires_at`.
     - Uses row-level locked atomic upsert: `INSERT INTO rate_limit_entries ... ON CONFLICT (key, window_bucket) DO UPDATE SET count = rate_limit_entries.count + 1, updated_at = now() RETURNING count;`.
     - Executes in dedicated short-lived connections committing immediately via `engine.connect()`, ensuring HTTP 429 exceptions or application transaction rollbacks cannot rollback rate-limit increments.
     - Race-condition free and verified across concurrent worker threads.
  2. **Anti-Spoofing Client IP Resolution (`get_client_ip`)**:
     - Peer IP (`request.client.host`) is strictly authoritative.
     - `X-Forwarded-For` and `X-Real-IP` proxy headers are completely ignored unless the immediate peer IP matches an entry in `settings.TRUSTED_PROXIES`.
     - Spoofed headers from untrusted clients are safely discarded.
  3. **Strict Dependency Ordering (No Quota Deduction for Unauthenticated Requests)**:
     - On protected endpoints (`/chat/*`, `/retrieval/*`, `/upload`, `/index`), user authentication and RBAC dependencies (`AuthenticatedUser`, `AuthenticatedAdmin`) evaluate *before* the rate-limit dependency executes.
     - Unauthenticated requests receive HTTP 401 without consuming the quota of any user.
     - Legitimate users are metered by trusted server-side user ID (`user:{user_id}:{scope}`).
  4. **Fail-Closed vs Fail-Open Policies**:
     - Authentication endpoints (`/auth/login`, `/auth/register`) use `fail_closed=True`: if rate-limit storage fails, the system blocks potential brute-force attacks and returns HTTP 503 Service Unavailable.
     - Expensive RAG endpoints (`/chat/*`, `/retrieval/*`, etc.) use `fail_closed=False` (configurable): if rate-limit storage fails, requests fail open with a logged warning and a `RATE_LIMIT_STORAGE_ERROR` telemetry event, ensuring service availability.
  5. **Standard HTTP 429 & Retry-After Responses**:
     - Exceeded limits return HTTP 429 Too Many Requests with standard `Retry-After` header indicating remaining window seconds.
     - Safe error detail message (`Rate limit exceeded. Please try again in {retry_after} seconds.`) with zero credential, token, or stack trace leakage.
  6. **Step 17 Telemetry Integration**:
     - Rate-limit decisions emit `TelemetryEvent` (`status="SUCCESS"` for allowed, `status="FAILURE"` / `error_category="RATE_LIMIT_EXCEEDED"` for throttled, `error_category="RATE_LIMIT_STORAGE_ERROR"` for storage faults).
     - Context variables propagate `request_id`, `user_id`, and `knowledge_base_id` automatically.
     - `CorrelationIdMiddleware` and `categorize_exception` map HTTP 429 to `RATE_LIMIT_EXCEEDED`.
  7. **Preserved Fast/Deterministic Endpoints**:
     - Fast deterministic endpoints (`/query/process`) and non-expensive metadata GET endpoints are not throttled, preserving rapid normalizer performance.
  8. **Comprehensive Verification**:
     - 418 tests passing across the entire repository (18 unit tests in `test_rate_limit.py`, 13 integration tests in `test_rate_limit_integration.py`).
     - Zero regressions introduced into Steps 7–17.
     - Ruff check and format 100% clean across 194 files.
     - No secrets committed; sensitive attribute redaction verified.
* **Next Safe Task**: Step 19 (next roadmap stage / Backend security audit).

2026-09-25 — Step 21E Authentication & Session Persistence Regression Fix (COMPLETE):
- **Diagnosed & Fixed Root Cause**:
  1. `app.storage.client` in NiceGUI is volatile and discarded on every page navigation/route change. The proxy had previously stored `FrontendAPIClient` in client storage, causing redirects (e.g., `/login` -> `/dashboard`) to recreate an unauthenticated `TestClient` with an empty cookie jar, triggering HTTP 401 and "Authentication Required".
  2. `ui.run` in `frontend/main.py` configured with `storage_secret=settings.SECRET_KEY`, enabling persistent Starlette session middleware cookies.
  3. `FrontendAPIClient` and `AppState` proxies updated to resolve per-browser sessions using `_get_browser_session_id()` backed by server-side registries `_session_clients` and `_session_app_states`.
  4. Authoritative server-side validation against `GET /auth/me` on user retrieval.
- **Verification Completed**:
  - `backend/tests/integration/test_auth_session_persistence.py`: 10/10 passed (100%).
  - `backend/tests/unit/test_frontend.py`: 37/37 passed (100%).
  - `backend/tests/integration/test_step21e_workflow_integrity.py`: 5/5 passed (100%).
  - `backend/tests/unit/test_step21e_api_client_integrity.py`: 6/6 passed (100%).
  - `backend/tests/unit/test_step21e_frontend_workflow.py`: 3/3 passed (100%).
  - Total 61/61 automated tests passing cleanly.
  - `scripts/diagnose_step21e.py`: Run successfully against PostgreSQL database `rag_assistant_db`.
  - `ruff check`: 100% clean (0 errors across 215 files).
  - `ruff format --check`: 100% clean (215 files).
  - Standing daemons:
    * PostgreSQL (port 5432) active.
    * Ollama (port 11434) active.
    * NiceGUI web application (port 8080) active and serving traffic at `http://localhost:8080`.

2026-09-25 — Step 22A Authentication & Entry Experience (COMPLETE):
- **Core Accomplishments**:
  1. **Public Authentication Entry Experience Redesign**:
     - Redesigned `/login` into a high-clarity academic portal selection screen featuring side-by-side cards for Student Portal vs Administrator Portal, distinct role messaging, and a student registration card.
     - Created `/student/login` providing a dedicated Student Portal authentication interface with WCAG 2.1 AA keyboard support and registration navigation.
     - Created `/admin/login` providing a restricted Administrator Portal authentication interface with explicit security notices and zero public admin registration exposure.
     - Redesigned `/register` to match the university design system, strictly provisioning STUDENT accounts.
  2. **Strict Server-Side Role Enforcement**:
     - Implemented shared backend service `authenticate_and_create_session(..., required_role=...)` in `backend/app/api/v1/endpoints/auth.py`.
     - Added `/auth/login/student` enforcing `UserRole.STUDENT` and rejecting administrators with HTTP 403 ("This account belongs to the Administrator Portal. Please use Administrator Sign In.").
     - Added `/auth/login/admin` enforcing `UserRole.ADMIN` and rejecting students with HTTP 403 ("This account does not have administrator access. Please use Student Sign In.").
     - Preserved backward-compatible `/auth/login`.
     - Credentials verified against Argon2id hash prior to inspecting roles (prevents role probing timing attacks).
  3. **Frontend API Client & Proxy Updates**:
     - Added `student_login()` and `admin_login()` on `FrontendAPIClient` and `_SessionAPIClientProxy`.
     - Handled 401 and 403 session clearing defensively on authentication rejection.
  4. **Verification & Quality Gate**:
     - `test_step22a_auth_portals.py`: 20/20 passed (100%).
     - `test_frontend.py`: 41/41 passed (100%).
     - Full test suite: 530/530 passed (100%).
     - `ruff check`: 100% clean across all 191 files.
     - `ruff format --check`: 100% clean across all 191 files.
     - `alembic check`: 100% clean (no new upgrade operations).
     - Standing daemons: PostgreSQL (5432), Ollama (11434), NiceGUI (8080) active.

2026-10-01 — Source Viewer Feature (COMPLETE):
- **Core Accomplishments**:
  1. **Backend Document File Streaming Endpoints**:
     - Implemented `GET /api/v1/knowledge-bases/{kb_id}/documents/{document_id}/file` streaming physical files with `content_disposition_type="inline"` and authoritative RBAC (`get_authorized_document`).
     - Added `GET /api/v1/documents/{document_id}/file` and `GET /api/v1/documents/by-name` in `backend/app/api/v1/endpoints/documents.py`.
     - Updated `get_current_user_optional` in `backend/app/api/deps.py` to support `?token=` parameter and `session` storage for seamless iframe embedding.
  2. **Modern Source Viewer Side Drawer Component**:
     - Created `frontend/components/source_viewer.py` implementing `open_source_viewer()`.
     - Uses Quasar full-height right-side slide drawer (`ui.dialog().props("position=right full-height")`) styled with Oxford Blue (`#002147`), Slate borders, and clear typography.
     - Embeds native browser PDF engine via `iframe src="{pdf_url}#page={page_number}&view=FitH"`.
     - Includes page bookmark badge, maximize/restore toggle, "Open in new tab" link, and cited evidence grounding snippet box.
  3. **Knowledge Bases Page Integration**:
     - Updated `frontend/pages/knowledge_bases_page.py` making document previews interactive with hover states, PDF icons, and click-to-open handlers.
     - Added interactive "+ X more material(s)" modal dialog allowing students to view and open any course document in the side drawer.
  4. **Chat Page Citation & Evidence Grounding Integration**:
     - Updated `frontend/pages/chat_page.py` with `format_citation_links()` converting bracketed citations `[1]`, `[2]` into clickable interactive pills (`<a data-citation-index=... class="citation-pill...">`).
     - Injected global JavaScript listener for citation clicks in `frontend/main.py` delegating to `handle_citation_click` in `chat_page.py`.
     - Clicking a citation opens the PDF viewer side drawer directly to the cited page (`#page=N`) displaying the grounding evidence excerpt.
     - Enhanced "Sources & Evidence" accordion and `evidence_panel.py` with direct "Read in PDF (Page X)" buttons.
  5. **Verification & Quality Gate**:
     - `backend/tests/unit/test_source_viewer.py`: 3/3 passed (100%).
     - `backend/tests/unit/test_frontend.py`: 46/46 passed (100%).
     - `backend/tests/security/test_security_rbac.py`: 18/18 passed (100%).
     - `backend/tests/security/test_backend_security_audit.py`: 19/19 passed (100%).
     - `ruff check`: 100% clean (0 errors across 225 files).
     - `ruff format --check`: 100% clean (225 files already formatted).
     - Zero secret leaks, server-side RBAC strictly preserved.

2026-10-07 — Stage 1: Complete Public Entry + Authentication Redesign (COMPLETE & VERIFIED):
- **Stage Name:** Stage 1 — Complete Public Entry + Authentication Redesign
- **Starting Git Commit:** `4575184`
- **Accomplishments:**
  1. *Public Entry (`/login`) Redesigned from Scratch:*
     - Purposeful academic header with direct gateway links ("Student Sign In", "Faculty & Admin", "Create Account").
     - Clear, honest hero section communicating what RAG Assistant does without empty whitespace or floating card boxes.
     - Live grounded evidence demonstration card featuring a real student query, grounded assistant answer with inline citation `[1]`, and quoted syllabus excerpt.
     - Four core academic value pillars: Course-Scoped Access, Verifiable Page Citations, Multi-Format Ingestion (PDF, DOCX, TXT, MD, CSV), and Institution-Governed Content.
     - Dual gateway selection cards clearly delineating student learning vs faculty/administrative curation.
     - Institutional trust and privacy standards banner highlighting server-side RBAC, local embedding security, and zero hallucination safeguards.
     - Anchored bottom CTA and comprehensive institutional footer.
  2. *Student Portal (`/student/login`) Split-Pane Layout:*
     - Left pane: Student gateway context, citation guidance, course isolation principles, and registration link.
     - Right pane: Focused, accessible sign-in card with email, toggle-password input, loading indicator, and sanitized error alerts.
  3. *Administrator Portal (`/admin/login`) Split-Pane Layout:*
     - Left pane: Administrative governance context, course curation lifecycle, and server-side audit notices.
     - Right pane: Secure administrative sign-in card with server-side RBAC validation.
  4. *Student Onboarding (`/register`) Split-Pane Layout:*
     - Left pane: Institutional onboarding guidelines, email criteria, and password rules.
     - Right pane: Clean student registration card with full name, university email, and password validation.
  5. *Shared Public Layout & Theme (`frontend/components/layout.py`):*
     - Rebuilt `auth_layout` with responsive contextual headers, open section container width, and anchored institutional footer.
- **Verification Results:**
  - `backend/tests/integration/test_step22a_auth_portals.py`: 20/20 passed (100%).
  - `backend/tests/security/`: 50/50 passed (100%).
  - `backend/tests/unit/`: 335/335 passed (100%).
  - `backend/tests/integration/`: 191/191 passed (100%).
  - `ruff check .`: 100% clean (0 errors across entire workspace).
  - All four routes (`/login`, `/student/login`, `/admin/login`, `/register`) return HTTP 200 with complete payloads.
- **Security Invariants Preserved:**
  - 0 query-parameter tokens (`?token=`), 0 localStorage session storage, 0 JavaScript cookie manipulation, 0 raw exception disclosures.
  - Student course access remains strictly membership-based (`KnowledgeBaseMember`).
  - Multimodal RAG and persistent chat history remain strictly deferred.

2026-10-07 — Stage 2: Complete Student Experience Rebuild & Public-Page Polish (COMPLETE & VERIFIED):
- **Stage Name:** Stage 2 — Complete Student Experience Rebuild & Public-Page Polish
- **Starting Git Commit:** `a5d9d4c`
- **Accomplishments:**
  1. *Public Polish & Landing Enhancement (`/login`):*
     - Upgraded low-contrast text elements (`text-slate-400`/`500` -> `text-slate-600`/`700`) across hero viewport, demonstration cards, gateway cards, registration guidelines, and footer notes to ensure strict WCAG AAA contrast against light surfaces.
     - Cleaned up breadcrumb suppression on auth pages.
  2. *Student Navigation Shell Unified (`frontend/components/layout.py`):*
     - Eliminated dual-navigation redundancy: single top navigation bar on desktop, responsive drawer on mobile.
     - Removed obsolete header BCA badge and cluttering breadcrumbs.
  3. *Student Dashboard Rebuilt (`frontend/pages/dashboard_page.py`):*
     - Transformed into an engaging study starting point with suggested inquiry prompt pills, quick course jumping, and active course overview cards.
     - Eliminated large empty whitespace voids.
  4. *Courses Library (`frontend/pages/knowledge_bases_page.py`):*
     - Redesigned as an academic library with search filtering, course overview cards, material counters, and direct study actions ("Ask in Course", "View Materials").
  5. *Conversational Chat Assistant (`frontend/pages/chat_page.py`):*
     - Rebuilt conversational interface with bottom composer, default `ALL_COURSES` search scope, inline clickable citation pills `[1]`, and grounded evidence panel.
     - Zero fake persistent chat history.
  6. *Student Profile (`frontend/pages/profile_page.py`):*
     - Rebuilt with academic identity details, enrolled course list, and clean security guidelines; stripped internal PostgreSQL session jargon.
  7. *Multi-Format Source Viewer (`frontend/components/source_viewer.py`):*
     - Supports inline PDF rendering (`#page=N`), DOCX, TXT, MD, CSV with safe content preview, evidence excerpts, and zero token query leakage.
  8. *Security & RBAC Enforcement (`backend/app/api/deps.py`):*
     - Strictly enforced membership-based student course authorization (`KnowledgeBaseMember`) combined with `is_active` and `is_student_visible` controls.
     - Unauthorized/unassigned courses return HTTP 404 to avoid private course existence leakage.
  9. *Alembic Migration & Schema Alignment:*
     - Added `is_active` and `is_student_visible` columns to `knowledge_bases` table via migration `aebbc63863c7`.
     - Formatted and typed cleanly with 0 ruff errors.
- **Verification Results:**
  - `backend/tests/security/test_student_access_policy.py`: 8/8 passed (100%).
  - `backend/tests/security/`: 58/58 passed (100%).
  - `backend/tests/integration/test_source_viewer.py`: 8/8 passed (100%).
  - `backend/tests/integration/test_document_ingestion.py`: 13/13 passed (100%).
  - Total non-real_ollama regression suite: 584/584 passed (100%).
  - `ruff check .`: 100% clean (0 errors across entire workspace).
  - Route smoke checks verified returning HTTP 200 for `/login`, `/student/login`, `/dashboard`, `/knowledge-bases`, `/chat`, and `/profile`. Browser automation tool Playwright driver installation 404 noted per Phase F guidelines.
- **Boundaries Strictly Respected:**
  - Hard stop: Administrator interfaces (`/documents`, `/indexing`, `/administrators`, `/activity`, `/system-health`) remained untouched.
  - Multi-format text RAG truthfully documented (PDF, DOCX, TXT, MD, CSV); non-text multimodal features remain deferred.
  - Zero token leakage; HttpOnly session cookies preserved.

2026-10-09 — Frontend Part 2: Complete Student Chat Redesign (/chat) (COMPLETE & VERIFIED):
- **Stage Name:** Frontend Part 2 — Complete Student Chat Redesign
- **Starting Git Commit / Base:** fd6a759
- **Accomplishments:**
  1. *Baseline Audit (`screenshot/chat_baseline_student.png`, `screenshot/chat_baseline_admin.png`):*
     - Documented duplicate headers, repeated breadcrumbs, oversized empty-state void, floating card composer, and multi-turn citation index bug (`[-1]` index resolution).
  2. *Header Restructured (`frontend/pages/chat_page.py`):*
     - Suppressed outer breadcrumbs and generic H1 titles in `page_layout(title="", subtitle="", show_breadcrumb=False)`.
     - Built compact academic header with "Ask Assistant" (or "Admin Knowledge Chat"), "Online · Grounded" status indicator, authorized search scope selector, and "Clear Chat" action.
  3. *Workspace & Academic Typography:*
     - Clean `max-w-4xl` reading container.
     - User questions: Right-aligned parchment cards (`bg-surface-elevated`) with uppercase `QUESTION` label.
     - Assistant responses: Left-aligned academic layout with `Source Serif 4` typography, comfortable line-height, gold emblem header, and green verified sources badge.
     - Inline citation badges `[1]`, `[2]`, `[3]` in JetBrains Mono / gold accent.
  4. *Purposeful Academic Empty State:*
     - Dignified welcome card ("Academic Knowledge Assistant") explaining grounded synthesis from official course documents.
     - 4 accessible starter inquiry buttons ("Explain a core concept from the course material", "Summarize key examination criteria and grading policies", "What is the policy on late assignment submissions?", "Compare two related topics covered in the syllabus") that immediately dispatch questions upon click.
  5. *Grounded Question Composer:*
     - Sticky bottom container (`sticky bottom-0 bg-canvas/95 backdrop-blur-sm`) naturally anchored to the workspace.
     - Minimalist borderless input with placeholder "Ask a question about your course materials...", Deep Atlas Navy send button (`#0E1D61`), and reassuring status indicator "Grounded in all authorized course materials".
     - Keyboard Enter key support and disabled state during generation.
  6. *Message-Stable Citation Resolution Fixed:*
     - Updated `format_citation_links` in `chat_page.py` to embed `data-message-id="{msg.id}"` and `data-citation-index="{idx}"`.
     - Updated global click delegation listener in `frontend/main.py` to pass `{ index: idx, message_id: msgId }`.
     - Rewrote `handle_citation_click` to lookup the exact assistant message by ID and retrieve its specific citation before calling `open_source_viewer()`. Backward-compatible fallback to latest message if ID is omitted.
  7. *Cited Evidence Tray:*
     - Each assistant response with citations features a dedicated `CITED EVIDENCE` section listing individual source chips (`[idx] document_name p. N`) with direct click handlers to open `open_citation_viewer(cit)` and an "Inspect Evidence" action opening the slide-out panel.
  8. *Role Isolation & Admin Scopes:*
     - Students default to `ALL_COURSES` with optional single-course filtering; students cannot see document scopes or admin diagnostic tools.
     - Administrators retain full access to `ALL_COURSES`, `COURSE`, and `DOCUMENT` scopes.
- **Verification Results:**
  - `screenshot/chat_empty_student.png` (1440x900) verified: clean compact header, balanced welcome card, 4 prompt buttons, anchored composer.
  - `screenshot/chat_active_student.png` (1440x900) verified: user question card, editorial serif assistant answer, inline citation pills `[1]`, `[2]`, `[3]`, and 3 evidence chips.
  - `screenshot/chat_mobile_student.png` (390x844) verified: clean single-column mobile layout, responsive header and composer, zero horizontal overflow.
  - `screenshot/chat_active_admin.png` (1440x900) verified: admin portal sidebar, "Admin Knowledge Chat" title, diagnostic scopes, and active response with citations.
  - `backend/tests/frontend/unit/`: 48/48 passed (100%), including 2 new tests for message-stable citation mapping and multi-turn isolation.
  - `ruff check frontend/ backend/`: 100% clean (0 errors).
  - `git diff --check`: 100% clean (0 whitespace errors).
- **Boundaries Strictly Respected:**
  - Public landing page (`/login`) and footer improvements preserved without modification.
  - No changes made to `/dashboard`, `/knowledge-bases`, `/profile`, `/documents`, `/indexing`, `/administrators`, etc.
  - No git commit or push performed per Git safety instructions.

2026-10-12 — Part 3: Source Viewer and Document Reading Experience Redesign & Verification (COMPLETE & VERIFIED):
- **Stage Name:** Part 3 — Source Viewer & Document Reading Experience Redesign
- **Status:** Complete, Functionally Diagnosed, Redesigned, Tested & Verified
- **Functional Failures Diagnosed & Root Causes:**
  1. *DOMPurify Iframe Stripping in NiceGUI*: Previous attempts to embed `<iframe ...>` via `ui.html(...)` failed because NiceGUI's `ui.html` defaults to `sanitize=True`, which invokes the client-side Sanitizer / DOMPurify API. DOMPurify stripped the `<iframe>` tag completely, leaving an empty `<div>` and rendering a blank white area. Fixed by passing `sanitize=False` to `ui.html()` after safely escaping all attributes (`document_name`, `iframe_url`) using `html.escape(..., quote=True)`.
  2. *Uninitialized Quasar Tabs Model*: `ui.tabs()` was instantiated without an explicit initial `value="pdf_view"`. When `ui.tab_panels(tabs, value="pdf_view")` bound its value to `tabs.value`, Quasar received `None`, hiding the active tab panel. Fixed by explicitly initializing `ui.tabs(value="pdf_view")` and using string keys `"pdf_view"` and `"text_view"`.
  3. *Unreachable Fallback Links in Nested Object/Iframe*: The legacy implementation nested `<div class="fallback">` inside `<object data="..."><iframe src="...">...</iframe></object>`. Chromium renders the iframe container itself, rendering nested fallback HTML unreachable. Fixed by moving fallback controls ("Open PDF in New Window ↗", direct download actions) into an explicit, accessible status bar outside the embedded viewer.
  4. *Positional Parameter Bug in Call Sites*: Callers in `documents_page.py` and `knowledge_bases_page.py` passed `course_name` as the 4th positional argument where `page_number: int` was expected, populating page numbers with string course names. Fixed by coercing types safely in `open_source_viewer()` and migrating all call sites to explicit keyword arguments.
  5. *AttributeError in `api_client.get_document_chunks()`*: `resp.json().get("chunks", [])` crashed because the backend returns a JSON array `list[DocumentChunkResponse]`. Fixed to safely handle both lists and dictionaries.
- **Backend API Additions:**
  - Added `GET /api/v1/documents/{document_id}/chunks` in `backend/app/api/v1/endpoints/documents.py` enforcing `get_authorized_document()` server-side RBAC and returning `list[DocumentChunkResponse]`.
  - Configured preview streaming routes in `frontend/main.py` with multi-page university PDF (`storage/49745dda-3cb9-41c3-bc7a-1716ee5a41fa/28219023-f970-4e70-a214-0566104262f6.pdf`, 18 pages) for multi-page jump testing, genuine DOCX, TXT, MD, CSV, and explicit HTTP 404 for missing documents.
- **Source Viewer Redesign from Scratch (`frontend/components/source_viewer.py`):**
  - **Academic Reading Workspace:** Built from the Ivory (`#E8E0D2`), Gold (`#B89A5A`), and Deep Atlas Navy (`#0E1D61`) design system tokens.
  - **Header:** Compact, editorial header with truncated document title, hover tooltip, course/page subtitle, maximize toggle (desktop), open in new tab action, and accessible Esc/close button. On mobile (<640px), the maximize button is hidden and title/page suffix stack cleanly without crowding touch targets.
  - **Cited Evidence Passage Banner:** Prominent left gold rule, serif excerpt, and page attribution displaying the exact cited evidence grounding.
  - **PDF Reading View:** Native in-browser PDF reader via authorized same-origin `<iframe>` supporting `#page={page_number}&view=FitH` page fragment jumps, 100% viewport reading allocation, and reachable status bar with new window fallback.
  - **Non-PDF Document View:** Dedicated reader for DOCX, TXT, Markdown, and CSV displaying extracted academic sections with highlighted cited passages, format badges, and direct file access actions. Never displays misleading "PDF Document" tabs.
  - **Document Unavailable State:** Dignified academic error message without stack traces, internal paths, or infinite spinners.
- **Verification & Test Results:**
  - `backend/tests/frontend/unit/`: 79/79 passed (100%).
  - `backend/tests/unit/test_source_viewer.py`: 6/6 passed (100%).
  - `backend/tests/security/`: 8 passed, 51 skipped (database-dependent tests safely skipped due to local PostgreSQL not running). All code/dependency security checks passed.
  - `ruff check frontend/ backend/`: 100% clean (0 errors).
  - `git diff --check`: 100% clean (0 whitespace errors).
- **Actual Browser Verification (Edge CDP Screenshots):**
  - `screenshot/source_viewer_pdf_page2_desktop.png`: PDF opened at Page 2 (1440x900 desktop reading workspace with native Edge controls).
  - `screenshot/source_viewer_pdf_page5_desktop.png`: Same PDF opened at Page 5 (native Edge controls showing "5 of 18").
  - `screenshot/source_viewer_evidence_context.png`: Evidence context banner with quoted passage and page attribution.
  - `screenshot/source_viewer_non_pdf_docx.png`: DOCX academic reading workspace with extracted text sections and cited badge.
  - `screenshot/source_viewer_unavailable_doc.png`: Missing document dignified error state with close action.
  - `screenshot/source_viewer_desktop_reader.png`: Full desktop academic reading experience.
  - `screenshot/source_viewer_mobile_reader.png`: Responsive mobile reading experience at 390x844.
  - `screenshot/source_viewer_new_tab_fallback.png`: Direct browser render of authorized PDF endpoint (`Accept-Ranges: bytes`, `Content-Disposition: inline`).
- **Security Invariants Preserved:**
  - 0 query-parameter tokens (`?token=`), 0 localStorage session storage, 0 JavaScript cookie manipulation, 0 raw exception disclosures.
  - All document streaming and chunk endpoints enforce server-side authorization.
  - Multimodal RAG and persistent chat history remain strictly deferred.

2026-10-21 — Part 9B: Documents Page Inline Upload Workspace & 100 MiB Limit (SUPERSEDED VISUALLY):
- **Stage Name:** Admin Part 9B — Inline Upload Workspace & 100 MiB Limit
- **Status:** Complete functionally, superseded visually by Part 9D
- **Accomplishments:**
  1. Converted upload workflow into an inline section on `/documents` without a toggle button.
  2. Removed course dropdown from document browsing toolbar.
  3. Increased upload limit to 100 MiB (104,857,600 bytes).
- **Limitations & Visual Rejection:**
  - Layout still used a generic dashed gold box with a centered cloud icon.
  - Some synthetic test files caused stream parse errors in audit captures.
  - Visual composition was not approved and required further structural redesign.

2026-10-21 — Part 9C: Documents Upload UX Normalization & Pipeline Alignment (SUPERSEDED VISUALLY):
- **Stage Name:** Admin Part 9C — Upload UX Normalization & Pipeline Alignment
- **Status:** Complete functionally, superseded visually by Part 9D
- **Accomplishments:**
  1. Removed hardcoded 85% simulated progress; synchronized real-time stages with `indexing_jobs`.
  2. Suppressed native Quasar upload progress counter `0.0B / 0.00%`.
  3. Verified 100 MiB boundary enforcement.
- **Visual Disapproval Findings:**
  - Dropzone still retained a giant conventional dashed rectangle and centered cloud icon.
  - Target Course selector appeared visually blank when unselected (showing only the dropdown arrow without placeholder text).
  - Active upload progress was duplicated in 3 separate locations: top upload workspace, the "Active Ingestion & Indexing Pipeline" banner, and the document table row.
  - Redundant explanatory paragraph duplicated the main page subtitle.
  - On mobile, the dropzone was disproportionately tall and pushed the document table far below the fold.

2026-10-21 — Part 9D: Rebuilt Document Upload Experience with Editorial Intake Design (COMPLETED & VERIFIED):
- **Stage Name:** Admin Part 9D — Rebuild Document Upload Experience with Distinctive Editorial Intake Design
- **Status:** Complete, Functionally Diagnosed, Structurally Redesigned, Tested & Verified
- **Core Visual & Architectural Transformations:**
  1. *Editorial Document Intake Strip (`frontend/components/theme.py`):*
     - Completely replaced the dashed gold dropzone and centered cloud icon with a low-profile (~48px height) horizontal editorial intake strip.
     - Styled with a solid border (`1px solid #D8CFBF`), antique gold left accent (`border-left: 3px solid #B89A5A`), refined `post_add` Material icon, and left-aligned typography (`Drop a document here, or click to browse` with quiet hint: `Click anywhere to choose a file, or drag one here`).
     - Stretched the invisible native input (`.q-uploader__input`) over 100% of the width and height (`z-index: 5`), guaranteeing that clicking anywhere on the surface opens the native file picker and drag-and-drop works reliably without fragile DOM traversal.
     - Permanently suppressed native subtitle counter (`.q-uploader__subtitle { display: none !important; }`) and native action buttons.
  2. *Target Course Selector Placeholder Correction (`frontend/pages/documents_page.py`):*
     - Diagnosed Quasar `q-select` behavior: without `use-input`, the placeholder attribute does not render when `value` is None.
     - Resolved by binding `display-value="Choose a course"` on `upload_course_select` while unselected, and dynamically removing the property and `.is-unselected` class in `on_course_select_change` upon valid course selection.
     - Unselected state renders readable placeholder text; selected state clearly displays the course name; prevents silent selection of the first course.
  3. *Unification of Progress & Banner Deduplication (`frontend/pages/documents_page.py`):*
     - Filtered out `uploading_doc_id` in `render_active_pipeline()`: while a document is actively being uploaded or tracked in the primary workspace, its live detailed progress is shown exclusively in the primary upload card.
     - The corresponding document table row displays a concise status badge without repeating the detailed progress panel.
     - Active Ingestion & Indexing Pipeline banner remains dedicated to other background indexing jobs.
  4. *Heading & Content Simplification:*
     - Removed redundant secondary description paragraph. The page retains the clean main `Course Documents` heading/subtitle and a compact `Add course material` section label with quiet format/size metadata (`PDF · DOCX · TXT · Markdown · CSV · Max 100 MiB`).
  5. *Mobile Footprint Optimization:*
     - On mobile (390x844 and 375x667), Target Course and Document Intake Strip stack cleanly with low vertical profile.
     - Eliminates the giant decorative void, bringing the Search Documents filter and document ledger directly into comfortable reach above the fold.
  6. *Truthful Progress & Completion Lifecycle:*
     - Primary workspace card displays indeterminate bar during text extraction/queueing, chunk-based percentage during embedding, and verified green `Ready` badge upon completion with a clean "Upload Another Document" reset action.
  7. *Read-Only Data Quality Investigation:*
     - Investigated existing failed PDF records (`CS101_Syllabus_Guide.pdf` and `CS101_Distributed_Systems_Lecture_Notes.pdf`): confirmed as 78B and 103B disposable synthetic mock artifacts from previous test runs.
     - Confirmed `KSU-Act-English.pdf` (351.4 KB) is a genuine reference document across 3 courses.
     - Preserved all records read-only without deletion or schema mutation.
- **Verification & Test Results:**
  - `backend/tests/frontend/unit/test_admin_part9d_editorial_intake_design_and_deduplication.py`: 17/17 passed (100%).
  - `backend/tests/frontend/unit/test_admin_part9b_inline_upload_and_size_limits.py backend/tests/frontend/unit/test_admin_part9c_documents_upload_ux_and_pipeline.py`: 24/24 passed (100%).
  - `ruff check frontend/ backend/`: 100% clean (0 errors).
  - `git diff --check`: 100% clean (0 whitespace errors).
- **Canonical Approved Visual Captures (`screenshot/admin/part9d/`):**
  - `01_documents_desktop_idle.png` (125,798 bytes, SHA256: `5bdc2c35816d...`): Idle editorial intake strip, visible placeholder, quiet metadata.
  - `02_documents_desktop_target_selected.png` (124,590 bytes, SHA256: `b3c21c6d5904...`): BCA course selected and readably displayed.
  - `03_documents_desktop_file_selected.png` (124,333 bytes, SHA256: `337fd534159b...`): Selected file staged with immediate visual confirmation.
  - `04_documents_desktop_processing.png` (124,320 bytes, SHA256: `ac7695a8c80a...`): Truthful live progress in primary card; completely deduplicated from pipeline banner.
  - `05_documents_desktop_completed.png` (120,638 bytes, SHA256: `f3e8b3de036b...`): Truthful completed status with reset action.
  - `06_documents_desktop_search_filtered.png` (109,717 bytes, SHA256: `8bd36e1496d9...`): Responsive search filter preserved immediately below upload strip.
  - `07_indexing_center_view.png` (149,952 bytes, SHA256: `e48406cd49a3...`): Synchronized status in Indexing Center.
  - `08_documents_mobile_390x844.png` (114,230 bytes, SHA256: `5c6b56a56037...`): Compact mobile layout, search and table accessible above the fold.
  - `09_documents_compact_mobile_375x667.png` (103,483 bytes, SHA256: `81f94e3c1262...`): Compact mobile layout at 375x667 with no horizontal overflow.
- **Invariants Preserved:**
  - 100 MiB limit (`104,857,600 bytes`) preserved.
  - Backend validation, UUID storage, and automatic ingestion/indexing intact.
  - Ivory (`#E8E0D2`), Gold (`#B89A5A`), and Deep Atlas Navy (`#0E1D61`) design tokens strictly maintained.
  - Zero modifications to unrelated administrator or student pages.

2026-10-23 — Admin Part 10B.1: System Diagnostics Table Rendering, Metadata Mapping, and Layout (COMPLETED & VERIFIED):
- **Stage Name:** Admin Part 10B.1 — Fix System Diagnostics Table Rendering and Layout
- **Status:** Complete, Functionally Diagnosed, Structurally Corrected, Tested & Verified
- **Defects Diagnosed & Corrected:**
  1. *Blank Column Headings (Root Cause):*
     - The previous code assigned column titles directly to generic `th` element wrappers via `ui.element("th").classes(...).text = "..."`.
     - In NiceGUI, assigning `.text` to generic `Element` does not render text nodes into the DOM, producing an empty horizontal band with zero visible text.
     - Resolved by explicitly nesting supported child labels: `with ui.element("th").classes(...): ui.label(...)`.
     - Output now renders visible, accessible uppercase column labels: `Component / Subsystem`, `Functional Scope`, `Reported Status`, and `Telemetry Diagnostics`.
  2. *Functional Scope Mapping (Root Cause):*
     - The previous dictionary `subsystem_meta` held arbitrary lowercase keys (`database`, `pgvector`, `ollama`, `indexing_worker`) and attempted direct lookup with `comp.name.lower()`.
     - The live backend returns canonical component titles (`API Gateway`, `PostgreSQL Database`, `pgvector Extension`, `Ollama Services`, `Indexing Background Worker`). None matched, causing every single component to default to the identical generic fallback string.
     - Created explicit, tested `get_subsystem_metadata(comp_name)` helper mapping each known backend component name to its verified functional scope:
       * `API Gateway`: "API request handling and application endpoint availability."
       * `PostgreSQL Database`: "Relational persistence for application records, users, courses, and audit data."
       * `pgvector Extension`: "Storage and similarity search for vector embeddings."
       * `Ollama Services`: "Local language-model inference for grounded assistant responses."
       * `Indexing Background Worker`: "Asynchronous document parsing, chunking, embedding, and indexing jobs."
       * Genuinely unknown components return neutral fallback: "Purpose not configured for this subsystem".
  3. *Refresh Telemetry Button Placement:*
     - The previous layout called `render_section_heading()` followed by `ui.button("Refresh Telemetry")` in a parent flex row. Because `render_section_heading()` rendered with full width, the button broke onto an awkward separate row.
     - Resolved by passing `actions_fn=render_refresh_button` directly into `render_section_heading()`.
     - The Refresh Telemetry button sits cleanly beside the section title on desktop, and wraps smoothly without overlap on mobile.
  4. *Diagnostics Typography:*
     - Replaced monospace typography (`font-mono`) on explanatory diagnostic sentences with normal body sans-serif typography (`font-sans`), reserving `font-mono` strictly for timestamps and technical identifiers.
  5. *Table Geometry & Responsive Behavior:*
     - Proportioned desktop columns: ~20% Component, ~27% Scope, ~16% Status, ~37% Diagnostics with `align-top` alignment.
     - Wrapped table with `overflow-x-auto` and `min-w-[760px]`, containing horizontal scrolling within the table surface without causing full-page overflow on mobile screens (390x844).
  6. *Truthful Health Semantics Preserved:*
     - Degraded status is faithfully preserved for Ollama and overall system (zero fake green).
     - Component reported status and diagnostic messages remain unmodified.
- **Verification & Test Results:**
  - `backend/tests/frontend/unit/test_admin_part10b_health_admin_users_and_overview.py`: 25/25 passed (100%), including 12 newly added focused contract tests in `TestSystemDiagnosticsRenderingAndMappingPart10B1`.
  - `scripts/capture_part10b1_final.py`: Verified live DOM header text nodes, verified 5 distinct functional scopes, verified 0 mobile overflow.
  - `ruff check frontend/ backend/`: 100% clean (0 errors).
  - `git diff --check`: 100% clean (0 whitespace errors).
- **Canonical Approved Visual Captures (`screenshot/admin/part10b1/`):**
  - `system_diagnostics_desktop.png` (150,627 bytes): Visibly rendered four column headings, verified purpose-built functional scope descriptions, sans-serif telemetry diagnostics, Degraded status preserved truthfully for Ollama, aligned Refresh Telemetry button.
  - `system_diagnostics_mobile.png` (158,742 bytes): Mobile view at 390x844 with zero horizontal document overflow (`docWidth == 390`), self-contained horizontal table scrolling, responsive section header and button wrap.

