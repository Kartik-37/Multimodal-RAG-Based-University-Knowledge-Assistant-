# Task State

This file is maintained by Antigravity.

## Current authoritative phase — 2026-10-05

**FINAL AUDIT — SECURITY HARDENING + FRONTEND REBUILD**

The previous Step 23 frontend/source-viewer design work is historical. The user explicitly requested a complete frontend redesign and a fresh frontend test suite, so the old design is **superseded** for implementation purposes.

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
- **Status:** **COMPLETED**
- **Accomplishments:**
  - Current RAG scope documented truthfully as **Multi-Format Text RAG** (PDF, DOCX, TXT, Markdown, CSV).
  - Genuine Multimodal RAG (vision models, OCR, image embeddings, visual retrieval) explicitly documented as **FUTURE / DEFERRED**.
  - Official project title **Multimodal RAG-Based University Knowledge Assistant** preserved across all documentation.
  - Removed all stale instructions regarding `?token=`, `document.cookie` injection, `app.storage.user` token persistence, and `TestClient` production usage.
  - Documented authoritative membership-based student course authorization rule.
  - Documented that Phase 4 will be a complete **frontend rebuild from scratch** in NiceGUI (current UI is superseded; restrained aesthetic, no decorative animations/gradients/glassmorphism).
  - Documented screenshot reference rule: screenshots in `screenshot/` folder are audit evidence of existing defects/flows, not a design template; all screenshots must be reviewed prior to redesign.
  - Documented testing rules: Phase 3 will rewrite tests from scratch to protect behavior/contracts/security without asserting CSS classes, colors, or DOM nesting.
  - Confirmed zero application code changes and zero test changes during Phase 2.

### Phase 3: Frontend Test Suite Rewrite
- **Status:** **PENDING**
- **Scope:** Delete and recreate stale presentation tests around behavior/contracts/security. Do not test CSS classes, exact DOM nesting, decorative animations, or card arrangements.

### Phase 4: Frontend Rebuild from Scratch
- **Status:** **PENDING**
- **Scope:** Rebuild NiceGUI student and admin experiences with clean typography, restrained palette, generous whitespace, accessible controls, and responsive layout.

### Multimodal RAG
- **Status:** **FUTURE / DEFERRED**
- **Scope:** Vision-language models, OCR pipelines, image embeddings, image retrieval, and visual citations will be designed and implemented in a separate roadmap phase after current text RAG is stable.

### Persistent Chat History
- **Status:** **FUTURE / DEFERRED**
- **Scope:** Durable Conversation/Message database models, server-side tenant isolation, and history management will be implemented as a controlled feature without destabilizing core RAG.

### Repository hygiene
- [x] Remove `frontend/client/Untitled-1.txt` (confirmed clean).
- [ ] Keep `.env`, `.git`, `storage/`, caches, `.nicegui/`, bytecode, and generated dumps out of source-sharing archives.
- [ ] Check Git history/diff for secrets before every push.

## Required acceptance criteria

This phase is complete only when:
1. no main session token is accepted in a source/file query string;
2. no raw main session token is sent to browser JavaScript;
3. production frontend does not import/use FastAPI `TestClient`;
4. source viewer is server-authorized and renders an actual document in the browser;
5. user-facing errors never expose raw exceptions;
6. frontend tests are behavior/security focused and survive visual redesign;
7. student/admin pages are rebuilt from scratch in NiceGUI;
8. the UI is simple, restrained, readable, and responsive;
9. unnecessary animation/hover/decorative effects are removed;
10. project documentation matches real multimodal capability;
11. Git/GitHub contains meaningful commits and no secrets.

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











