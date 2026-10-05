# Project Context — Multimodal RAG-Based University Knowledge Assistant

## User priority order

The latest explicit user requirements are authoritative for this review/rebuild. Do not silently reinterpret them.

The user wants:
- a thorough audit before changes;
- small and large defects fixed, not only visible UI problems;
- context/instruction files corrected so the same mistakes do not return in later Antigravity work;
- the NiceGUI frontend rebuilt from scratch, not merely recolored;
- a simple, understandable, beautiful interface that does not feel boring or generic;
- no unnecessary animation, hover effects, gradients, decorative elements, or feature clutter;
- functionality preserved unless a change is required for correctness/security or explicitly requested;
- stale UI/presentation tests deleted and recreated from scratch when they encode the wrong design/behavior;
- precise prompts for Antigravity, with no instruction taking higher priority than the user's explicit requirements;
- Git/GitHub used after meaningful completed work;
- conversation history similar to ChatGPT only when it can be implemented cleanly and persistently without compromising the core system.

When an old repository instruction conflicts with this section, preserve security/correctness and use this section for the frontend/review/rebuild decisions.

## Product

Project title:
**Multimodal RAG-Based University Knowledge Assistant**

The user-facing product should have one canonical name. Do not invent competing brand names such as "RAG Studio". A shorter user-facing label may be used only as a deliberate abbreviation of the canonical product name.

## Phase status & verified implementation baseline

The project is governed by a strict phased plan.
- **Phase 1: Security Hardening & Backend Correctness** — **COMPLETED & VERIFIED** (572 tests passed in the non-real_ollama regression suite; tests marked real_ollama were excluded from this verification).
  - *Resolved:* Query token authentication (`?token=`) removed and rejected with HTTP 401.
  - *Resolved:* Production `TestClient` import and instantiation replaced with `InProcessProductionTransport` in `FrontendAPIClient`.
  - *Resolved:* Raw session token persistence in NiceGUI `app.storage.user["auth_session_token"]` completely deleted.
  - *Resolved:* Backend `deps.py` completely decoupled from NiceGUI internals (`nicegui.app`, `nicegui_app.storage._users`).
  - *Resolved:* All user-facing exceptions sanitized via centralized `normalize_error()`.
  - *Resolved:* Source viewer embeds same-origin authenticated document streaming (`GET /api/v1/documents/{id}/file`); no tokens in URLs, no JavaScript `document.cookie` injection.
  - *Resolved:* Student course access confirmed and verified as **strictly membership-based** (`KnowledgeBaseMember`).
  - *Resolved:* Untracked scratch files removed; working tree clean.
- **Phase 2: Scope Control & Project Context Consistency** — **COMPLETED**.
- **Phase 3: Test Suite Rewrite from Scratch** — **PENDING** (Phase 3 will delete/recreate stale presentation tests around behavior/contracts).
- **Phase 4: Frontend Rebuild from Scratch** — **PENDING** (NiceGUI rebuild with restrained, clean aesthetic).
- **Multimodal RAG** — **FUTURE / DEFERRED** (Current system is multi-format text RAG).
- **Persistent Chat History** — **FUTURE / DEFERRED** (Process-memory `AppState._chat_history` is not persistent).

## Screenshot reference rule

The screenshots in the `screenshot/` folder document the existing implementation and its defects. They are **audit evidence, not a design template**. Future Phase 4 frontend work must inspect **all** supplied screenshots individually before redesigning corresponding areas.

## Architecture baseline

Keep the existing clean separation:

NiceGUI presentation
→ FastAPI API/service boundary
→ authentication/authorization
→ application/domain services
→ PostgreSQL/pgvector

RAG flow:
query validation/normalization
→ lexical retrieval + vector retrieval
→ fusion (RRF or justified alternative)
→ reranking
→ context assembly
→ grounded generation
→ citation validation
→ safe response/telemetry

Do not move database/business logic into visual components.

## Frontend rebuild contract

The frontend is allowed to be rewritten substantially or completely.

Preserve:
- backend API contracts unless a security/correctness fix requires a controlled change;
- RBAC and data isolation;
- document/citation provenance;
- authentication behavior;
- loading/error/retry behavior;
- required admin functions;
- Git history and meaningful implementation history.

Do not preserve:
- current card layout;
- current navigation labels merely because tests assert them;
- current hover/animation classes;
- current visual hierarchy;
- current source-viewer layout;
- implementation-specific HTML/CSS tests.

## Frontend product model

### Student
Primary navigation should be compact and obvious:
- Home
- Ask Assistant
- Courses
- Profile

Add **History** only if persistent conversation history is implemented correctly. Do not create a fake history page backed only by in-memory state.

### Administrator
Use grouped navigation rather than a long undifferentiated rail. Suggested groups:
- Overview
- Knowledge
- Chat/Diagnostics
- Administration
- System
- Profile

Exact labels may be changed during redesign, but the information architecture must remain simple and understandable.

### Chat
The student chat is the primary product experience.

Default hierarchy:
1. course/scope selection;
2. question composer;
3. answer;
4. citations and source evidence;
5. optional follow-up actions.

Technical retrieval diagnostics are administrator-only and should never dominate normal student chat.

### Source viewer
Prefer one simple evidence view:
- document name + course;
- cited page when available;
- PDF/document view;
- compact evidence excerpt;
- close/open-in-new-tab only when useful.

Do not require a raw auth token in the URL. Prefer the authenticated browser session on the same origin. If an iframe/browser constraint genuinely prevents that, implement a short-lived, single-purpose, server-issued viewer ticket scoped to the exact document and viewer request. Never reuse the main session token as a viewer token.

Do not load an entire large chunk corpus into the browser merely to provide a fallback viewer. Show the cited chunk(s), or paginate/bound the text when necessary.

## Security decisions

- Session cookies are HttpOnly, Secure in production, and SameSite appropriate to deployment.
- Never expose long-lived or raw session tokens to JavaScript.
- Never accept a raw session token in a document/file URL query parameter (`?token=` is rejected with 401).
- Never persist raw session tokens in NiceGUI `app.storage.user` or client-side storage.
- Backend authorization (`deps.py`) is framework-independent from NiceGUI (`nicegui.app` and `storage._users` are prohibited).
- Student course access is **strictly membership-based** (`KnowledgeBaseMember`); students cannot view or query unassigned courses.
- Never put secrets/tokens in HTML attributes, log messages, source snippets, analytics events, or browser-local persistent state unnecessarily.
- Use server-side authorization for every document/file/chunk operation.
- Source viewer access must enforce the same document authorization as API access.
- User-facing errors must be safe and actionable through centralized `normalize_error()`; raw exceptions are not UI content.
- Do not expose detailed environment/infrastructure information from public liveness endpoints.

## Multimodal truthfulness gate

The project title says multimodal. Before calling the project "multimodal" in the UI or final documentation, verify that the repository actually has:
- a supported non-text modality (for example images or rendered document pages);
- extraction/ingestion of that modality;
- a model/embedding path that represents it;
- retrieval/indexing behavior for it;
- citations/provenance back to the source modality.

Multiple file extensions alone do not make a system multimodal.

If true multimodality is not implemented in this work, use honest wording such as "multi-format RAG" in UI/help text while retaining the academic project title in official project documentation.

## Quality gate

"Perfect" means no known release-blocking defect after a whole-system audit. The agent must provide evidence:
- tests executed and results;
- lint/format/type checks when configured;
- migration check;
- security regression checks;
- source viewer browser verification;
- visual verification of every major route;
- no secret leakage;
- no stale test assertions that force superseded UI.
