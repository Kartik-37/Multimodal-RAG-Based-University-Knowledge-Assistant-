# Implementation Plan — Multimodal RAG-Based University Knowledge Assistant

## Authoritative Master Phases (2026-10-05 Rebuild)

1. **Phase 1: Security Hardening & Backend Correctness** — **COMPLETED & VERIFIED**
   - Query-token authentication (`?token=`) removed and rejected with HTTP 401.
   - Production `TestClient` eliminated in favor of `InProcessProductionTransport`.
   - Raw session-token persistence in `app.storage.user` deleted.
   - Backend `deps.py` decoupled from NiceGUI internals (`nicegui.app`, `storage._users`).
   - All user-facing exceptions sanitized via `normalize_error()`.
   - Source viewer converted to same-origin HttpOnly cookie streaming.
   - Student course access confirmed strictly membership-based (`KnowledgeBaseMember`).
   - 572 tests passed in the non-real_ollama regression suite; tests marked real_ollama were excluded from this verification.
2. **Phase 2: Scope Control & Project Context Consistency** — **COMPLETED & VERIFIED**
   - Documented actual current scope: Multi-Format Text RAG (PDF, DOCX, TXT, Markdown, CSV).
   - Documented Genuine Multimodal RAG (vision/OCR) as a future phase.
   - Resolved all conflicting or stale documentation across context files.
3. **Phase 3: Frontend Test Suite Rewrite** — **PENDING**
   - Delete and recreate stale presentation tests that freeze the obsolete UI.
   - Protect behavior, API contracts, auth, security, and workflows.
   - Strictly prohibit assertions on CSS classes, colors, HTML nesting, or animations.
4. **Phase 4: Frontend Rebuild from Scratch** — **PENDING**
   - Rebuild the NiceGUI frontend with simple, restrained, accessible UI.
   - Inspect all 21+ screenshots in `screenshot/` as audit evidence.
   - No glassmorphism, no decorative gradients, no unnecessary animations/hover effects.
   - High priority on grounded answers, readable citations, and responsive design.
5. **Future Roadmap Phases:**
   - **Persistent Chat History:** Implement durable Conversation/Message models and cross-user isolation when ready.
   - **Multimodal RAG:** Implement image extraction, vision-language representations, and visual retrieval pipelines.

---

## Historical Gate Reference

## Gate 1 — Project foundation

Implement/verify:
- configuration
- environment handling
- database
- migrations
- logging
- error model
- health/readiness
- CI
- Git hygiene

Acceptance:
- clean startup
- migration succeeds
- tests execute
- secrets are excluded

## Gate 2 — Authentication

Implement:
- registration
- login
- logout
- session/token lifecycle
- password hashing
- rate limiting
- authorization foundation

Acceptance:
- auth tests pass
- cross-user tests pass

## Gate 3 — Documents

Implement:
- upload
- validation
- storage abstraction
- document lifecycle
- metadata
- deletion
- versioning if required

Acceptance:
- malicious/invalid upload tests pass
- ownership tests pass

## Gate 4 — Ingestion

Implement:
- parser abstraction
- parsing
- normalization
- chunking
- metadata
- background jobs
- retries
- idempotency

Acceptance:
- representative documents process successfully
- failures are recoverable
- no duplicate indexing on retry

## Gate 5 — Embeddings and vector index

Implement:
- embedding abstraction
- provider adapters
- batch processing
- pgvector schema/index
- model/dimension tracking

Acceptance:
- dimensions validated
- reindexing works
- provider failure is safe

## Gate 6 — Lexical retrieval

Implement:
- PostgreSQL lexical search
- authorization filters
- ranking
- pagination/limits

Acceptance:
- lexical retrieval tests pass

## Gate 7 — Hybrid retrieval

Implement:
- vector retrieval
- candidate merge
- RRF or justified fusion
- metadata/provenance

Acceptance:
- evaluation dataset demonstrates expected behavior
- no cross-user leakage

## Gate 8 — Reranking

Implement:
- reranker interface
- selected reranker adapter
- bounded candidate list
- fallback behavior
- metrics

Acceptance:
- reranker tests pass
- evaluation reports reranker impact

## Gate 9 — Context and generation

Implement:
- context builder
- token/size budgeting
- grounded prompt construction
- provider abstraction
- answer generation
- citation validation
- insufficient-evidence behavior

Acceptance:
- citations map to actual evidence
- unsupported answers are handled safely

## Gate 10 — Conversations and query history

Implement only what the project specification requires:
- conversations
- messages
- query records
- retrieval metadata

Acceptance:
- ownership and deletion semantics tested

## Gate 11 — Backend quality gate

Run:
- all unit tests
- integration tests
- API tests
- security tests
- RAG evaluation
- lint
- type checks
- dependency/security checks
- migration checks

STOP if a critical/high issue remains.

## Gate 12 — Functional frontend

Implement the complete user journey with minimal styling.

## Gate 13 — Frontend design pass

Apply the full design system.
Perform responsive/accessibility/visual QA.

## Gate 14 — Production readiness

Verify:
- Docker/deployment
- environment configuration
- database migrations
- backups/restore strategy where applicable
- logging
- monitoring
- rate limits
- security headers
- CI
- documentation

## Gate 15 — Final audit

Create a final report:
- completed features
- tests
- evaluation metrics
- known limitations
- security findings
- performance findings
- deployment instructions

Do not call the project complete if important findings remain unresolved.
