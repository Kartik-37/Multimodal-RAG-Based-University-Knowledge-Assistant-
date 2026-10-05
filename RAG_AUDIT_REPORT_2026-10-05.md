# RAG Assistant Repository Audit — 2026-10-05

## Executive result

The project is much more substantial than a basic RAG demo: it has FastAPI services, PostgreSQL/pgvector integration, hybrid retrieval, reranking, grounding/citation logic, RBAC, ingestion services, NiceGUI pages, and a large test suite.

However, the archive is **not ready to be treated as final**. The biggest problems are not cosmetic:

- source-viewer authentication currently exposes the raw session credential in the URL and browser JavaScript;
- the production frontend uses FastAPI's `TestClient` as its HTTP transport;
- the frontend can surface raw exception strings;
- the current tests freeze the previous frontend design and therefore actively fight the requested redesign;
- persistent conversation history does not yet exist;
- the title says multimodal, but the inspected parser/embedding path is text-oriented and did not show a genuine image/vision pipeline;
- the source-viewer screenshot still visibly contains a blank document area;
- the archive contains local secrets/config/data and generated artifacts that should not be shared.

## Repository inspection

Approximate inspected scale:
- 310 backend application files;
- 91 frontend files;
- 196 test files;
- thousands of local storage/corpus files in the archive.

Static checks that could be run in the audit container:
- Python `compileall` succeeded for backend/frontend Python modules.
- `git diff --check` succeeded on the extracted working tree.
- Full pytest collection/execution could not be independently completed in the audit container because its environment does not have the project's PostgreSQL/pgvector runtime dependencies available. Historical pass counts in `TASK_STATE.md` were not treated as current proof.

## Security findings

### Critical: raw session token in document URL

`backend/app/api/deps.py` accepts `request.query_params.get("token")` when cookie/bearer credentials are absent.

`frontend/components/source_viewer.py` then:
- retrieves the raw session token;
- writes it into `document.cookie` using browser JavaScript;
- appends it to the `/file` URL as `?token=...`.

This is exactly the class of leak that secure HttpOnly sessions are intended to prevent. URLs may appear in browser history, access logs, monitoring, screenshots, copied links, and referrer contexts.

### High: TestClient in production frontend

`frontend/client/api_client.py` imports `fastapi.testclient.TestClient` and constructs it as `_http` for normal application requests.

The frontend should have a real transport abstraction. Tests can still use TestClient to test the backend, but production application code should not depend on a test-only transport.

### High: raw token in NiceGUI storage/client flow

`_get_persistent_token()` / `_set_persistent_token()` store `auth_session_token` in NiceGUI user storage and then make it available to frontend code. This is unnecessary credential exposure and should be replaced by a secure server-side session flow.

### High: raw exception shown to user

`frontend/state/app_state.py` stores `str(e)` and then builds a chat message containing the raw exception. This violates the frontend rule that raw backend/provider exceptions are not UI content.

### Medium: health endpoint information exposure

The liveness endpoint returns environment/version details. Liveness should be minimal; detailed dependency/environment information belongs in protected operational endpoints.

### Medium: CORS review required

The production CORS/credential combination should be rechecked for explicit deployment origins and CSRF requirements rather than relying on permissive development defaults.

## Correctness/architecture findings

### Source viewer route duplication

There are multiple document file-viewing paths. Consolidate around one canonical authorization-aware stream path where practical. A document UUID, not a filename, should be the primary identity for citations/source viewing.

### Unbounded chunk rendering

The source viewer can load all indexed chunks into the browser. This does not scale for large documents. Show only cited chunks or use bounded/paginated retrieval.

### No durable conversation history

`AppState._chat_history` is process memory. It is useful for a session but is not ChatGPT-like persistent history. Do not label it as persistent.

### Per-render current-user calls

The frontend's current-user property repeatedly calls the backend rather than using a carefully scoped cache/refresh mechanism. Review this during the API client/session rewrite to reduce redundant DB calls without weakening server authority.

### Raw HTML security surface

The source viewer builds raw HTML with document names/URLs/snippets. These values must be escaped or rendered through safe NiceGUI primitives. Citation HTML has the same general risk and should be simplified.

## Multimodal mismatch

The parser factory currently registers:
- PDF
- DOCX
- TXT
- Markdown
- CSV

The inspected repository did not show a clear image extraction, vision model, image embedding, or multimodal retrieval path.

Therefore the current implementation should not claim genuine multimodal RAG until that capability exists. This is an academic correctness/documentation issue, not merely a branding detail.

## Frontend visual audit from supplied screenshots

The screenshots show a coherent and generally polished academic SaaS look, but it is too dense and too dashboard-oriented for the user's requested simple product.

Specific observations:

- Primary navigation is long and operational for the student.
- Many pages use repeated cards, pills, borders, badges, and small labels.
- The chat page gives too much space to scope/evidence chrome compared with the answer itself.
- The source viewer is complicated and, in the supplied captured state, visibly shows a blank PDF rendering area.
- Admin pages expose many operational sections simultaneously; grouping would improve comprehension.
- Login/registration are visually separate from the rest of the application and use several branded labels.
- Branding is inconsistent: `RAG Studio`, `Academic Assistant`, `University RAG Assistant`, and project-level BCA naming all coexist.
- The code contains many hover/transition/animation classes even though the desired style is deliberately restrained.

## Design direction for the rebuild

Do not copy the screenshot layout.

Build around the user's actual task:

### Student
Home → Ask → Courses → Profile

### Chat
Course scope → question → answer → citation → source

### Admin
Overview → Knowledge → Chat/Diagnostics → Administration → System → Profile

Use typography, spacing, alignment, and a small number of surfaces to create hierarchy. Do not solve every visual problem by adding another card.

## Test audit

The current `backend/tests/unit/test_frontend.py` is 944 lines and contains a mixture of:
- true API/DTO behavior tests;
- database-mutating integration-like tests;
- exact strings;
- source-code content assertions;
- CSS class checks;
- current UI assumptions.

Examples include assertions about obsolete corpus labels and exact auth-page styling. These tests will force an implementation to retain the old UI.

The replacement suite should focus on behavior/security and remain stable across visual redesigns.

## Repository/archive hygiene

The supplied archive contains `.env`, `.git`, `storage`, `.nicegui`, caches, bytecode, egg-info, and a generated `frontend/client/Untitled-1.txt` HTML capture.

Do not share or commit this whole archive as a source package.

At minimum, exclude:
- `.env`;
- `.git` when producing a clean source bundle for review;
- `storage/` corpus data;
- `.nicegui/`;
- `.pytest_cache/`;
- `.ruff_cache/`;
- `__pycache__/`;
- generated egg-info when not required;
- captured/generated HTML dumps.

The `.env` values were not reproduced in this report. If a real credential was ever published externally, rotate it rather than relying on `.gitignore` retroactively.

## Required next implementation order

1. [COMPLETED - Phase 1] Secure session/source-viewer transport (HttpOnly cookie, no tokens in URLs, no persistent storage of raw tokens).
2. [COMPLETED - Phase 1] Replace production TestClient transport with InProcessProductionTransport.
3. [COMPLETED - Phase 1] Sanitize all user-facing errors via centralized normalize_error().
4. [PENDING - Phase 3] Rewrite frontend tests from scratch around behavior, security, and contracts.
5. [PENDING - Phase 4] Rebuild the NiceGUI UI from scratch (simple, restrained, accessible, responsive).
6. [PENDING - Phase 4] Verify actual source document rendering in a browser.
7. [FUTURE / DEFERRED] Decide/implement/document persistent history (Conversation/Message models).
8. [COMPLETED & VERIFIED - Phase 2] Current scope documented honestly as Multi-Format Text RAG (PDF, DOCX, TXT, Markdown, CSV); genuine Multimodal RAG deferred to future roadmap phase.
9. [ONGOING] Run full security + integration + visual QA (572 tests passed in the non-real_ollama regression suite; tests marked real_ollama were excluded from this verification).
10. [ONGOING] Commit and push cleanly through Git/GitHub (Phase 1 committed as cfb824e; Phase 2 committed and pushed to origin/main).
