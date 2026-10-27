# Testing and Security Verification

## Test philosophy

Tests protect behavior, security, and important contracts — not a temporary visual implementation.

- **Phase 3 Scope:** Stale presentation tests that encode superseded UI behavior will be deleted and recreated from scratch in Phase 3.
- **Phase 2 Scope Boundary:** Tests must NOT be modified in Phase 2.
- **Never assert:** CSS class strings, exact colors, exact DOM nesting, decorative animations, card arrangement/counts, obsolete wording, or implementation-specific HTML fragments.
- **Always assert:** Role and route access semantics, authentication/session behavior, API client request/response contracts, citation mapping, source-viewer authorization, absence of token leakage, sanitized user-facing error behavior, per-user state isolation, and essential UI route smoke rendering.

## Unit tests

Cover:
- validators;
- chunking/normalization;
- metadata rules;
- retrieval fusion;
- citation mapping;
- context budgeting;
- authorization helpers;
- session/state transitions;
- safe error mapping;
- frontend citation formatting helpers without requiring a specific CSS design.

## Integration/API tests

Cover:
- authentication;
- authorization;
- pagination/schemas;
- upload limits;
- ingestion lifecycle;
- retrieval and reranking;
- citation provenance;
- document/file streaming;
- error contracts;
- migration integrity.

### Note on Windows Local PostgreSQL Execution
PostgreSQL on this workstation is installed as a portable binary at `D:\Kartik\pgsql\pgsql\bin\postgres.exe` with database cluster at `D:\Kartik\pgsql\data`. It is NOT registered as an automatic Windows Service (`Get-Service` will return nothing). To run database-backed integration and security tests, launch `postgres.exe` as a persistent background daemon (`& "D:\Kartik\pgsql\pgsql\bin\postgres.exe" -D "D:\Kartik\pgsql\data"`). Both `rag_assistant_db` (production/dev) and `rag_assistant_test_db` (test) exist and are maintained as separate databases owned by `rag_app_user`. Never execute test migrations or destructive fixtures against `rag_assistant_db`.

## Source-viewer security regression tests

Must include all of these:

1. an authenticated user can stream an authorized document through the canonical endpoint;
2. unauthenticated access is rejected;
3. a user cannot stream another user's/unauthorized course document;
4. an expired/revoked session is rejected;
5. `?token=<valid-main-session-token>` is rejected and is not treated as authentication;
6. source-viewer code does not copy raw session tokens to JavaScript/browser cookies;
7. source-viewer URLs contain no raw session credential;
8. untrusted document names/snippets cannot break out of an HTML attribute or inject script/event handlers;
9. document paths/filenames cannot traverse storage directories;
10. `app.storage.user` is not used to persist raw auth session tokens;
11. backend `deps.py` contains zero NiceGUI dependencies or storage fallbacks;
12. production frontend client does not import or instantiate `TestClient`;
13. registration failure and API error paths never expose raw Python exception details;
14. student course access enforces authoritative catalog policy (active/student-visible courses open by default, restricted courses require membership, inactive courses blocked with 404);
15. document upload and automatic indexing enforce strict permission boundaries (upload requires `DOCUMENT_UPLOAD`, auto-indexing requires `DOCUMENT_INDEX` or `is_main`; documents awaiting indexing are never marked completed; error strings are sanitized through `normalize_error()` with zero credential, SQL, or filesystem leakage).

## Frontend API client tests

Test the production client contract through a testable transport seam.

Do not test production frontend code by requiring `TestClient` inside the implementation itself.

Test:
- successful request/response mapping;
- authentication lifecycle;
- safe handling of 401/403;
- normalized errors;
- timeout/provider failure mapping;
- citation and DTO mapping.

## App state tests

Test:
- per-session isolation;
- adding a question;
- receiving an answer;
- reset/clear;
- cancellation/failed generation;
- safe user-facing error mapping.

Do not treat in-process state as persistent history.

## End-to-end core path

At minimum:
1. register/login;
2. upload document;
3. document indexes;
4. query;
5. answer contains valid citations;
6. citation opens the correct authorized source page;
7. unauthorized user cannot access the same source.

If persistent history is implemented, also test:
8. conversation survives restart;
9. user B cannot read user A's conversation;
10. starting/renaming/deleting a conversation follows authorization rules.

## Security tests

Explicitly test:
- IDOR/BOLA;
- cross-user retrieval leakage;
- cross-user file streaming leakage;
- path traversal;
- malformed/oversized files;
- malicious filenames;
- rate limiting;
- invalid/expired/revoked tokens;
- CSRF when applicable;
- SSRF when applicable;
- prompt injection resistance;
- sensitive data leakage through errors/logs;
- cache isolation.

## RAG evaluation

Maintain known query/evidence pairs and test:
- Recall@K;
- MRR;
- nDCG;
- hit rate;
- reranker lift;
- citation correctness;
- insufficient-evidence behavior;
- stage latency.

Do not claim retrieval quality from a subjective visual demo.

## Visual QA

Visual correctness is separate from backend tests.

Manually/browser-verify every major screenshot route after the redesign, including:
- login/registration;
- student home;
- courses;
- chat;
- citation/source viewer;
- profile;
- admin dashboard;
- admin knowledge/document management;
- indexing;
- admin users/activity/health as retained.

Check:
- desktop;
- mobile/narrow viewport;
- empty/loading/error states;
- long filenames;
- long answers;
- many citations;
- keyboard focus.

A screenshot showing a non-empty viewer shell with a blank document is a failure even if the source-viewer component renders without exceptions.

## Multimodal Verification & Security Suite (Phases 11A, 11A.1, 11A.2, 11A.3)

- **Database Isolation & Safety Guard (`backend/app/db/session.py`):**
  - `validate_test_database_url()` enforces that all verification scripts and integration tests connect strictly to `rag_assistant_test_db` or approved test database prefixes (`test_`, `rag_test_`).
  - Throws `RuntimeError` immediately upon detecting `rag_assistant_db`, eliminating any possibility of test pollution or test data leakage into the production database.
- **Extractor & Provider Tests (`backend/tests/unit/test_multimodal_vision_extractor_and_provider.py`):**
  - Asserts full document scan evaluates all pages without early breakout, ranking and prioritizing later important diagrams over early minor candidates.
  - Asserts decorative line filtering: pages with dense text (> 300 chars) and 5–14 simple vector drawing paths without visual cues/images score 0.0, eliminating wasted vision requests.
  - Refined candidate selection asserts `has_vector_evidence` requires `drawing_count >= 15` or `(drawing_count >= 2 and has_2d_shapes)` or `(drawing_count >= self.min_vector_drawings and (is_sparse or image_count > 0))`.
  - Asserts 7 deterministic scenarios: plain text (0 candidates), embedded image (1 candidate), flowchart shapes (1 candidate), scanned page (1 candidate), text discussing figures (0 candidates), decorative line with "Figure" mention (0 candidates), and later diagram page prioritization.
  - Asserts pre-render scale reduction: matrix scale calculated *before* `page.get_pixmap()` allocation to guarantee peak memory respects `VISION_MAX_IMAGE_PIXELS` (1536×1536).
  - Asserts strict Ollama JSON response validation, synchronous timeout bounding, and error recovery.
- **Pipeline & Vector Retrieval Tests (`backend/tests/unit/test_multimodal_rag_pipeline.py`):**
  - Asserts ingestion creates visual chunks with `source_modality="visual"`, `visual_type`, and `model_name`.
  - Asserts non-PDF documents and text-only PDFs trigger zero vision calls.
  - Asserts idempotent re-ingestion cleans preexisting chunks to prevent duplicate visual chunks.
  - Asserts 1024-d dense vector search returns visual chunks with high similarity for diagram queries.
  - Asserts citation items retain `source_modality` and exact source page fragment for the viewer.
- **Reranker Visual Prioritization Tests (`backend/tests/unit/test_reranking.py`):**
  - Asserts `is_visual_query()` detection and `+1.5` score priority for visual candidates during CrossEncoder reranking, ensuring visual diagram chunks take precedence when questions inquire about diagrams/flowcharts.
- **Evaluation Dataset Suite (`backend/tests/unit/test_multimodal_evaluation_dataset.py`):**
  - Verifies the 8 mandatory evaluation scenarios: embedded flowchart, trend chart, vector path diagram, scanned page, text-only PDF, communicated uncertainty, corrupt page partial coverage, and adversarial prompt injection containment.
- **LLM Reasoning & Grounding Tests (`test_llm_generation_service.py`, `test_claim_verifier.py`, `test_sentence_splitter.py`, `test_grounding_validation_service.py`):**
  - Phase 11A.3.1: Asserts `SentenceSplitter` distinguishes pure introductory framing (`The sequence is:`, `The workflow is:`, etc.) from conversational preambles, splitting factual sequence assertions into factual claims.
  - Phase 11A.3.1: Asserts `_sanitize_llm_answer()` strips Ollama chain-of-thought `<think>` scratchpads, trailing prompt instruction echoes, and precision directives while preserving legitimate student-requested numbered steps (`Step 1:`, `1.`, etc.).
  - Phase 11A.3.1: Asserts `extract_numbers()` in `ClaimVerifier` filters list item numbers and step labels (`1.`, `Step 1:`) after colons, semicolons, line breaks, or open parentheses so enumeration formatting is not penalized as numerical hallucination.
- **End-to-End Live Student Chat Verification (`scripts/verify_multimodal_chat_real.py`):**
  - Verifies complete live flow: synthetic PDF ingestion -> real `qwen2.5vl:3b` vision analysis -> memory release via sequential unload -> real `qwen3-embedding:0.6b` 1024-d pgvector indexing -> full `RAGOrchestrator` query execution -> grounded answer with Page 2 visual citation -> viewer URL contract -> course isolation -> test DB cleanup.
  - Phase 11A.3.1 / Phase 12A: Stricter acceptance assertions enforce factual grounding (`status="FULLY_SUPPORTED"`, `is_grounded=True`, `unsupported_claim_rate=0.0`, `citation_coverage=1.0`, `citation_validity_rate=1.0`, and all claim DTOs verified supported) and entity ordering (`Health Monitor` -> `Failover Controller` -> `Standby Node`), explicitly rejecting `CONVERSATIONAL` for factual sequence answers.
  - Confirms all 8 assertions pass with Return Code 0.
- **Safe Distribution Archive Contracts (`backend/tests/frontend/unit/test_archive_safety_contracts.py`):**
  - Phase 12A: 68 contract tests verify that `.env`, `.git/`, `storage/` (uploaded user documents), `scratch/` (SQL database dumps), `bca_rag_assistant.egg-info`, `screenshot/archive/`, and runtime caches are strictly excluded from shareable project archives, while `.env.example`, canonical code, documentation, and approved screenshots are preserved.
- **Prompt Injection Defense:**
  - Image content is untrusted data. Vision model prompts explicitly instruct the model to analyze visual content strictly as inert evidence and never execute directives visible in images.

## Final release gate

Before declaring complete:
- full test suite passes in the real supported environment;
- lint/format/type checks pass where configured;
- migration check passes;
- security regression suite passes;
- no known critical/high defect;
- no raw credentials in URL/JS/logs;
- no stale test assertions forcing superseded UI;
- no secret files in the project archive;
- project documentation matches actual capabilities, including whether the system is truly multimodal.
