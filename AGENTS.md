# AGENTS.md — Antigravity Master Instructions

## Mission

Build the complete BCA Project RAG application as a production-quality, secure, maintainable RAG system.

The existing project specification/roadmap is the source of truth. The user has completed Part 95 of the learning/build roadmap and wants the complete system implemented, including every required RAG stage and reranking. Do not stop at hybrid search.

Read these files before making architectural or implementation decisions:

1. `PROJECT_CONTEXT.md`
2. `context/ARCHITECTURE.md`
3. `context/RAG_SPECIFICATION.md`
4. `context/BACKEND_RULES.md`
5. `context/FRONTEND_RULES.md`
6. `context/TESTING_AND_SECURITY.md`
7. `context/IMPLEMENTATION_PLAN.md`
8. `context/TASK_STATE.md`

Also inspect the actual repository before changing anything. Existing working code is evidence, not permission to blindly preserve defects.

## Non-negotiable workflow

### Phase 0 — Inspect before coding

- Inspect the complete repository.
- Locate existing backend, frontend, database, tests, configuration, Docker files and documentation.
- Identify what already exists versus what is missing.
- Run the existing test suite before modifying code.
- Run static checks/lint/type checks that already exist.
- Produce an internal implementation map.
- Never delete or rewrite working functionality merely to make the project look cleaner.

### Phase 1 — Minimal frontend shell

Create only the NiceGUI frontend structure necessary to exercise and verify backend APIs:
- app shell
- authentication screens
- document/upload area
- search/query screen
- basic result rendering
- error/loading states

Do NOT spend time on visual polish yet.

### Phase 2 — Backend first

Implement the complete backend and RAG pipeline before substantial frontend redesign.

Backend includes:
- configuration/secrets
- authentication and authorization
- users and tenant isolation
- document ingestion
- parsing
- normalization
- chunking
- metadata
- embeddings
- vector storage
- lexical/BM25-style retrieval
- hybrid retrieval
- fusion
- reranking
- context assembly
- provider-independent LLM generation
- citations/source attribution
- conversation/query persistence where specified
- background jobs
- observability
- rate limiting
- audit logging
- health/readiness endpoints
- error handling
- migrations
- API contracts

### Phase 3 — Backend quality gate

Do not proceed to frontend polish until:

- unit tests pass
- integration tests pass
- security tests pass
- migration tests pass
- authorization/isolation tests pass
- ingestion failure/retry tests pass
- retrieval tests pass
- reranking tests pass
- citation tests pass
- API contract tests pass
- lint/type checks pass
- no known critical/high defect remains
- secrets are not committed
- dependency/security checks have been run where available
- production configuration has been reviewed

"Works on my machine" is not an acceptance criterion.

### Phase 4 — Frontend completion

Only after the backend gate passes:
- implement the complete UI
- establish the design system
- refine information architecture
- improve responsiveness
- improve accessibility
- add thoughtful empty/loading/error states
- remove visual rough edges
- perform visual QA against real backend data

### Phase 5 — Final audit

Perform a whole-system audit:
- security
- correctness
- performance
- accessibility
- API consistency
- database integrity
- RAG quality
- failure handling
- UX
- documentation
- deployment reproducibility

Fix findings before declaring completion.

## Coding behavior

- Prefer small, composable modules.
- Keep business logic out of route handlers.
- Validate all external input.
- Treat every client value as untrusted.
- Never trust a document ID, user ID, tenant ID, file path, role or filter supplied by a client.
- Enforce authorization server-side.
- Use transactions for multi-step state changes.
- Use idempotency for retryable ingestion/job operations.
- Never expose stack traces or secrets through API responses.
- Never log passwords, tokens, API keys, raw authorization headers or sensitive document contents.
- Use parameterized queries/ORM expressions.
- Avoid N+1 database access.
- Avoid unbounded queries and unbounded request bodies.
- Use explicit timeouts on external calls.
- Handle provider failures without corrupting database state.
- Make retries bounded and observable.
- Prefer deterministic behavior where possible.
- Do not add dependencies without justification.
- Do not invent APIs from libraries; check the installed version/documentation.

## Git/GitHub

Git and GitHub are mandatory parts of the workflow.

Before meaningful implementation:
- initialize/use Git correctly
- create a sensible `.gitignore`
- make a clean baseline commit

Use small, meaningful commits such as:
- `feat: add document ingestion pipeline`
- `fix: prevent cross-user document access`
- `test: add hybrid retrieval integration tests`

Never commit:
- `.env`
- API keys
- passwords
- private certificates
- local databases containing sensitive data
- generated secrets
- huge build artifacts

Keep branches/commits understandable. Before merging a feature, run the relevant tests. If GitHub Actions is configured, keep CI green.

## Decision discipline

When requirements are ambiguous:
1. inspect the repository and existing specification;
2. prefer the least surprising architecture;
3. preserve compatibility when practical;
4. document the decision;
5. do not silently invent product behavior.

Do not ask the user questions for decisions that can be safely resolved from these instructions. Ask only when a decision materially changes scope, data model, security, or product behavior.

## Definition of done

A feature is not done because code was written.

A feature is done only when:
- implementation exists,
- tests exist,
- tests pass,
- security implications are addressed,
- errors/failures are handled,
- documentation is updated,
- Git state is clean enough to review,
- and the feature works through the real integration path.


## Framework decision

Use:
- FastAPI for the backend/API.
- NiceGUI for the frontend.

Do NOT use Django as a second backend framework by default. Django + FastAPI would duplicate routing, authentication, ORM/application responsibilities and make the project harder to understand. Add Django only if an existing repository requirement proves it is necessary.

## Code comments

The user wants appropriate comments so they can understand what code does and how it affects the project.

Therefore:
- add concise explanatory comments around non-obvious logic;
- explain security-sensitive decisions;
- explain important RAG-stage interactions;
- explain tricky concurrency, retry, transaction and provider behavior;
- add docstrings to important public interfaces;
- avoid noisy comments that restate obvious code.

Comments must remain accurate as code changes. Remove or update stale comments during refactors.
