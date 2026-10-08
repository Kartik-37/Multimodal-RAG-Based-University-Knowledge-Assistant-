# AGENTS.md — Antigravity Master Instructions

## Mission

Build and maintain the **Multimodal RAG-Based University Knowledge Assistant** as a secure, understandable, maintainable FastAPI + NiceGUI application.

The user's latest explicit requirements are authoritative for the frontend rebuild and test reset. Never change the requested goal into a more convenient interpretation.

## Read before coding

Read, in order:
1. `PROJECT_CONTEXT.md`
2. `context/FRONTEND_DESIGN_SYSTEM.md`
3. `context/ARCHITECTURE.md`
4. `context/RAG_SPECIFICATION.md`
5. `context/BACKEND_RULES.md`
6. `context/FRONTEND_RULES.md`
7. `context/TESTING_AND_SECURITY.md`
8. `context/IMPLEMENTATION_PLAN.md`
9. `context/TASK_STATE.md`

Then inspect the actual repository and the screenshot folder.

## Current rebuild mode

This is a **repair + frontend-rebuild phase**, not a normal incremental UI polish.

The existing frontend may be replaced from scratch. The instruction "do not rewrite working functionality merely for cleanliness" means do not break working business/security behavior; it does NOT forbid a complete visual/UI rewrite explicitly requested by the user.

Do not preserve obsolete tests merely because they currently pass.

## Mandatory order for this task

### Phase A — audit

Before modifying implementation:
- inspect backend, frontend, tests, context files, migrations, configuration, dependency files, screenshots;
- identify real defects and architecture inconsistencies;
- run the existing checks that are available;
- separate real behavior/security defects from design differences;
- record findings in `context/TASK_STATE.md`.

### Phase B — security/correctness repair

Fix release-blocking defects first, including:
1. raw session token in source/document URL query parameters;
2. browser-JavaScript access to raw session tokens;
3. production use of `fastapi.testclient.TestClient`;
4. raw exception text shown in user-facing UI;
5. any authorization regression introduced while repairing the source viewer.

Do not accept a cosmetic workaround for a security problem.

### Phase C — tests from scratch

Delete/rewrite only the stale frontend/presentation tests that encode superseded UI behavior.

Create new tests around behavior and security. Tests must NOT assert:
- exact CSS class strings;
- exact wording unless wording is a true product requirement;
- exact card arrangement;
- exact DOM nesting;
- implementation-specific HTML fragments;
- the existence of a particular animation;
- stale branding.

Tests SHOULD assert:
- role and route access semantics;
- authentication/session behavior;
- API client request/response contracts;
- citation mapping;
- source-viewer authorization;
- absence of token leakage;
- sanitized user-facing error behavior;
- per-user state isolation;
- essential UI route smoke rendering.

Never add a fake test just to increase the pass count.

### Phase D — frontend rebuild from scratch

Use the current screenshots only as audit evidence, not as a design template.

Rebuild the NiceGUI frontend with:
- simple information architecture;
- clear typography hierarchy;
- restrained palette;
- generous whitespace;
- few purposeful surfaces;
- one obvious primary action per screen;
- strong readable chat layout;
- citations that are easy to see and click;
- source viewer that actually renders a document in-browser;
- mobile/tablet behavior intentionally designed;
- accessible keyboard focus and labels.

Do NOT merely change colors, fonts, or a few classes.

Do NOT add:
- decorative gradients;
- glassmorphism;
- animated background effects;
- card lift/scale hover effects;
- unnecessary tooltips;
- fake metrics;
- excessive badges;
- extra dashboard cards;
- auto-playing/looping animation.

Hover/transition feedback is allowed only for an actual interactive control and should be restrained. Processing states may use a minimal status indicator; do not use pulse/spin purely for decoration.

### Phase E — persistent conversation history (conditional)

Conversation history is a feature request, not a reason to destabilize the core RAG system.

Implement it only when:
- there is a real backend Conversation/Message model or equivalent persistent store;
- each conversation belongs to an authorized user/tenant;
- history queries are permission-filtered server-side;
- old conversations survive application restart;
- deleting/renaming/starting a conversation has clear backend semantics;
- tests prove cross-user isolation.

Do not present in-memory `AppState._chat_history` as durable history.

### Phase F — verification

Run:
- unit tests;
- integration tests;
- security tests;
- migration tests/checks;
- lint/format/type checks already configured;
- source viewer regression tests;
- browser/manual visual QA for every screenshot route;
- responsive checks;
- long-document/long-answer/citation/error scenarios.

If a check cannot run because the environment lacks PostgreSQL/pgvector/Ollama/browser tooling, say so explicitly. Do not fabricate a pass.

## Backend rules

- Never use `TestClient` as the production frontend HTTP transport.
- Keep API/database logic out of NiceGUI visual components.
- Keep backend authorization framework-independent: `backend/app/api/deps.py` must NEVER import `nicegui` or access NiceGUI storage internals (`storage._users`).
- Enforce authorization in backend service/query layers.
- Enforce authoritative student course authorization: all ACTIVE and STUDENT_VISIBLE courses are automatically available to students without prior enrollment. Inactive courses are strictly excluded. Restricted/private courses (`is_student_visible=False`) require explicit membership (`KnowledgeBaseMember`). Unassigned restricted courses return HTTP 404 to avoid private existence leakage.
- Never trust client document IDs, course IDs, file paths, role values, or filters.
- Use bounded payloads and timeouts.
- Never leak stack traces, SQL, filesystem paths, hostnames, ports, tokens, or raw provider exceptions to clients. Route all user-facing errors through `normalize_error()`.
- Never log tokens or private document contents.

## Frontend Design & Testing Authority

- The frontend presentation layer is strictly governed by `context/FRONTEND_DESIGN_SYSTEM.md` (Ivory `#E8E0D2`, Gold `#B89A5A`, Deep Atlas Navy `#0E1D61`).
- Stale presentation tests must NEVER override or constrain the current approved design system.
- Tests protect behavior, authorization, and security contracts, not frozen visual implementation details (exact CSS classes, DOM nesting, card arrangements, or animations).
- Future agents MUST read `context/FRONTEND_DESIGN_SYSTEM.md` before implementing or modifying frontend code.

## Current RAG scope & multimodal truthfulness

- Official project title: **Multimodal RAG-Based University Knowledge Assistant** (canonical title must be preserved).
- Current implementation: **Multi-format TEXT RAG** supporting PDF, DOCX, TXT, Markdown, and CSV.
- Genuine Multimodal RAG (vision-language models, OCR pipelines, image embeddings, visual retrieval) is intentionally **deferred to a future roadmap phase**.
- Do not claim or advertise multimodal support in UI, API responses, or documentation until non-text modality support is actually implemented in that future phase.

## Screenshot reference rule

- Screenshots in the `screenshot/` folder document the existing implementation and its defects; they are **audit evidence, not a design template**.
- Future Phase 4 frontend work must inspect **all** supplied screenshots individually before redesigning corresponding areas.

## Source-viewer rules

The source viewer is security-sensitive.

Required:
- canonical document UUID route;
- server-side authorization before file streaming;
- normal authenticated same-origin browser request whenever possible;
- no raw token query authentication;
- no `document.cookie = ...` JavaScript for the session secret;
- no token embedded into iframe/object URLs;
- no unescaped untrusted HTML attributes/content in raw `ui.html` sinks;
- page fragments such as `#page=N` may be used because fragments are not sent as HTTP credentials;
- verification that the PDF actually renders in the browser, not only that the container has height.

## Git/GitHub

After each meaningful completed change:
1. inspect `git diff`;
2. run relevant tests/checks;
3. update `context/TASK_STATE.md`;
4. commit with a small, meaningful commit message;
5. push to GitHub when a remote is configured and normal workflow permits.

Do not fabricate a remote or claim a push occurred if no remote is configured.
Do not commit `.env`, storage corpus data, caches, generated HTML dumps, local databases, or secrets.

## Documentation

Update context files whenever a design/security/architecture decision changes so a future agent cannot reintroduce the defect.
