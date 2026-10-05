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

## Current audit status

The repository has a substantial FastAPI + NiceGUI implementation and many backend/RAG services. The current frontend is functional-looking but must be considered **superseded** for design purposes because the user explicitly requested a fresh redesign.

Important findings from the 2026-10-05 audit:

1. **Source viewer authentication currently leaks raw session credentials.** The backend accepts `?token=` and the frontend copies the raw session token into a browser-accessible cookie and document URL. This is a release-blocking security defect. Raw session tokens must never appear in query strings, HTML, client JavaScript, or browser history.
2. **Production frontend code imports `fastapi.testclient.TestClient`.** TestClient is test infrastructure and must not be the production transport boundary for a user-facing frontend. Replace it with a real HTTP/API boundary appropriate to the final deployment topology.
3. **Raw auth tokens are retained in NiceGUI application storage and exposed to frontend code.** Redesign the session flow so browser JavaScript never receives the bearer/session secret.
4. **Frontend background-generation errors can expose raw exception text.** User-facing errors must be sanitized; technical details belong in secure logs/telemetry.
5. **Current frontend tests contain implementation-specific assertions** for CSS classes, exact labels, file contents, obsolete wording, and specific HTML. These tests incorrectly freeze the old UI and must be recreated around behavior/security contracts.
6. **Conversation history is currently in-process `AppState` memory, not persistent Conversation/Message storage.** It is acceptable to defer persistent history until the core rebuild is stable. If implemented, it must use proper backend persistence and authorization isolation.
7. **The current parser registry is PDF, DOCX, TXT, Markdown, and CSV.** The inspected code does not contain an image/vision/multimodal ingestion or embedding pipeline. Therefore the implementation currently behaves like multi-format/text RAG, not a fully demonstrated multimodal RAG system. Do not falsely claim multimodal capability. Either implement real multimodal ingestion/embedding/retrieval or clearly document the current scope until that work is completed.
8. **The current source viewer is visually complicated and its captured screenshot shows a blank PDF area.** Do not assume the viewer is fixed because CSS dimensions were added; verify actual document rendering in the browser.
9. **The current frontend has substantial motion/hover/gradient CSS** despite the restrained-design rule. The new frontend must remove decorative motion and use interaction feedback only where it communicates an actual state change.
10. **The repository archive contains `.env`, `.git`, storage data, caches, `.nicegui`, and generated metadata.** Keep these out of project-sharing archives. Never commit `.env` or local corpus data. If a real secret was included in a publicly shared archive, rotate it.

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
- Never accept a raw session token in a document/file URL query parameter.
- Never put secrets/tokens in HTML attributes, log messages, source snippets, analytics events, or browser-local persistent state unnecessarily.
- Use server-side authorization for every document/file/chunk operation.
- Source viewer access must enforce the same document authorization as API access.
- Reject `?token=` authentication for source/document file endpoints after migration and add a regression test.
- User-facing errors must be safe and actionable; raw exceptions are not UI content.
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
