# ANTIGRAVITY — CURRENT PROJECT REPAIR + FRONTEND REBUILD

## PROJECT

**Project title:** Multimodal RAG-Based University Knowledge Assistant

## MOST IMPORTANT SCOPE DECISION

**Do NOT implement multimodal RAG in this rebuild.**

The project title may remain unchanged because it is the academic project title, but the current implementation scope is intentionally limited to the existing **text/multi-format RAG system**.

Multimodal RAG is a **future phase**, not part of this task.

Do NOT add image understanding, image embeddings, vision-language models, OCR pipelines, visual retrieval, chart/image retrieval, multimodal embeddings, or any other multimodal implementation now.

Do NOT redesign the existing architecture around multimodal support now.

Do NOT add fake multimodal functionality merely to make the project title appear accurate.

Create/update documentation so this boundary is explicit:

> Current phase: stabilize and improve the existing text/multi-format RAG system.
> Future phase: genuine multimodal RAG will be designed and implemented separately after the current system is stable.

This scope decision has higher priority than suggestions to "complete the title" or expand the project.

---

# MY DEVELOPMENT PRIORITIES

Follow these priorities exactly in this order:

1. Understand the actual current project.
2. Find real bugs, security issues, architectural mistakes, test problems, and usability problems.
3. Fix the current backend correctly.
4. Recreate stale/bad tests instead of preserving tests that force unwanted behavior.
5. Completely redesign the frontend from scratch using the existing project stack.
6. Make the application simpler to understand and use.
7. Verify everything properly.
8. Update context/instruction files so future work does not reintroduce these problems.
9. Use Git/GitHub after every meaningful completed phase.
10. Only after this rebuild is stable should future features such as genuine multimodal RAG be considered.

Do not skip ahead because a later feature appears interesting.

---

# MY EXPLICIT REQUIREMENTS

You are working on the real repository. Do not invent missing files, behavior, architecture, or requirements.

I want:

- thorough review before major modification;
- small and large mistakes identified;
- root causes fixed, not cosmetic patches;
- regression protection so the same mistake does not return;
- context files updated to reflect final decisions;
- frontend redesigned from scratch, not just recolored;
- simple, beautiful, understandable UI;
- minimal unnecessary UI decoration;
- no unnecessary animations;
- no unnecessary hover effects;
- no excessive gradients, glass effects, glowing effects, decorative cards, badges, tooltips, or fake statistics;
- interactions only when they serve a real purpose;
- strong backend security and correctness;
- fresh frontend tests written from scratch where current tests have become design-coupled;
- FastAPI backend;
- NiceGUI frontend;
- PostgreSQL + pgvector;
- no React introduction;
- Git/GitHub as part of the workflow;
- persistent ChatGPT-like chat history only when it is implemented properly. Do not fake it with process memory.

I am not good at visual design. Do not ask me to choose colors, spacing, layouts, component styles, etc. Make professional design decisions yourself while following my explicit restrictions.

If a requirement is genuinely ambiguous and cannot be resolved from the repository or these instructions, ask one focused question instead of making a major assumption.

Do not replace my requirements with your own preferences.

---

# PHASE 0 — FREEZE THE SCOPE AND AUDIT THE REAL REPOSITORY

Before coding, read:

- `PROJECT_CONTEXT.md`
- `AGENTS.md`
- `context/ARCHITECTURE.md`
- `context/RAG_SPECIFICATION.md`
- `context/BACKEND_RULES.md`
- `context/FRONTEND_RULES.md`
- `context/TESTING_AND_SECURITY.md`
- `context/IMPLEMENTATION_PLAN.md`
- `context/TASK_STATE.md`

Also inspect the actual repository tree and all relevant implementation files.

Review:

- authentication and sessions;
- API transport;
- source/document viewer;
- citation handling;
- RAG retrieval/generation;
- frontend state;
- routes and navigation;
- admin/student pages;
- tests;
- configuration;
- migrations;
- middleware;
- static/media handling;
- screenshots in the supplied `screenshot/` folder.

Build a defect table internally with:

- file;
- defect;
- severity;
- root cause;
- fix;
- regression test.

Do not start the frontend redesign until the audit is complete.

Do not spend this phase implementing future multimodal functionality.

---

# PHASE 1 — SECURITY AND BACKEND CORRECTNESS

## 1. REMOVE RAW SESSION TOKEN FROM SOURCE VIEWER

The current design has the equivalent of query-token authentication and browser-side access to the raw session token.

Remove all patterns equivalent to:

- `request.query_params.get("token")` for the normal session token;
- putting the main session token into `?token=`;
- JavaScript reading or writing the raw main session token;
- `document.cookie` manipulation for the main authentication credential;
- document URLs containing the raw main session token.

Required end state:

- main authentication remains server-protected;
- browser JavaScript never receives the raw main session token;
- raw session tokens are never put into source/document URLs;
- source viewer authorizes every document access server-side;
- source viewer uses canonical document identifiers.

Prefer same-origin authenticated requests.

If the NiceGUI architecture absolutely requires a separate browser-visible credential, it must be a dedicated short-lived document-viewer ticket, scoped to one document and one purpose. It must not be the normal session token and must not be exchangeable for the main session.

Add regression tests proving:

- `?token=<main session token>` does not authenticate source access;
- User A cannot access User B's source;
- expired/invalid credentials fail safely;
- no main session token appears in generated source URLs.

## 2. REMOVE FASTAPI TESTCLIENT FROM PRODUCTION FRONTEND TRANSPORT

If `fastapi.testclient.TestClient` is used by production frontend code, remove it.

Tests may use TestClient.

Production frontend transport must use an appropriate real application boundary. Use an actual HTTP client such as `httpx` when the frontend/backend communicate through HTTP, or a clean internal service abstraction when they are in one process.

Do not create a fake HTTP implementation simply to satisfy tests.

Add regression coverage proving production code does not depend on TestClient.

## 3. REVIEW SESSION STATE

Audit all persistent/session state handling, including any helpers resembling:

- `_get_persistent_token()`;
- `_set_persistent_token()`;
- `get_session_token()`;
- session proxy logic;
- browser storage.

Do not put raw credentials into unnecessarily persistent browser-accessible state.

Preserve user/session isolation across requests.

## 4. SAFE ERROR HANDLING

Do not expose raw Python exceptions to end users.

Replace `str(e)`-style UI errors with safe user-facing messages and internal logging.

Never expose:

- tracebacks;
- SQL errors;
- filesystem paths;
- internal service URLs;
- provider/API responses containing secrets;
- credentials.

Add regression tests.

## 5. SAFE HTML / CITATION / SOURCE CONTENT

Review every dynamic `ui.html(...)` and every HTML string construction.

Document names, snippets, course names, URLs, citations, and retrieved content are untrusted input.

Escape/sanitize correctly or use safe NiceGUI components.

Do not use `javascript:void(0)` or similar shortcuts.

---

# PHASE 2 — DO NOT EXPAND INTO MULTIMODAL RAG

This entire phase is a **scope-control phase**, not an implementation phase.

Determine and document exactly what the current RAG system supports today.

The current implementation may support formats such as PDF, DOCX, TXT, Markdown and CSV. Treat this as **multi-format/text RAG** unless there is an actual working multimodal pipeline.

Do NOT add:

- image embeddings;
- vision-language models;
- image retrieval;
- OCR-based visual retrieval;
- image/table/chart understanding;
- multimodal vector indexes;
- multimodal ingestion;
- visual-region citations.

Instead:

1. Document the current supported ingestion/retrieval behavior honestly.
2. Mark genuine multimodal RAG as a future roadmap item.
3. Ensure no current documentation falsely claims that multimodal RAG is already implemented.
4. Do not refactor current working text RAG merely to prepare for a speculative future feature.

The future feature must be isolated as a later architectural phase, not mixed into this rebuild.

---

# PHASE 3 — DELETE AND RECREATE STALE FRONTEND TESTS

Do not patch obsolete frontend tests line by line when they encode unwanted design requirements.

The known large frontend test file and other stale frontend-specific tests must be reviewed.

Where they are tightly coupled to obsolete CSS/HTML/text/layout, delete and recreate them from scratch.

New tests must protect behavior, correctness and security.

Test:

- API request/response mapping;
- authentication lifecycle;
- 401/403 behavior;
- safe error normalization;
- DTO parsing;
- citation mapping;
- answer/markdown safety;
- session/user isolation;
- chat state transitions;
- route access semantics;
- source viewer authorization;
- token leak prevention;
- required route registration;
- safe HTML handling;
- important empty/error/loading states.

Do NOT test:

- exact colors;
- exact CSS utility classes;
- exact card counts;
- exact DOM nesting;
- exact animation names;
- arbitrary wording;
- visual styling that is not a product contract.

A test exists to protect behavior, not to force the previous design back into the application.

Do not increase test count artificially.

---

# PHASE 4 — FRONTEND REBUILD FROM SCRATCH

This must be a real redesign.

Do not:

- recolor existing pages;
- only change border radii;
- rearrange the same cards;
- rename headings;
- add a new banner and call it a redesign.

Start from the actual user tasks and redesign:

- information hierarchy;
- navigation;
- page structure;
- component grouping;
- spacing;
- typography;
- interaction model;
- responsive layout.

Use **NiceGUI**. Do not introduce React.

## Overall design direction

The UI should feel:

- simple;
- calm;
- professional;
- modern without looking like a generic AI SaaS template;
- comfortable for long study sessions;
- visually clear;
- easy to understand on first use.

I cannot reliably specify visual design myself, so make the design decisions yourself within these constraints.

## Strong visual restrictions

Do not add unnecessary:

- animations;
- hover transformations;
- gradients;
- glassmorphism;
- glowing elements;
- decorative backgrounds;
- excessive rounded containers;
- badges/pills;
- tooltips;
- fake statistics;
- large marketing slogans;
- redundant information cards.

Animation is allowed only when it communicates a real state such as loading, success, or a meaningful transition.

Hover is allowed only when it clearly indicates an interactive element and provides value.

## Student navigation

Keep navigation compact and understandable:

- Home
- Ask Assistant
- Courses
- Profile
- History only when true persistent history exists

Do not expose admin tools to students.

## Student Home

The primary action should be obvious.

The page should quickly communicate:

- where the student is;
- what they can ask;
- what course/material context is available.

Do not turn the home page into an analytics dashboard.

## Courses

Students should quickly understand:

- available courses;
- available study materials;
- which course is active/selectable.

Use lists/grids only when they improve scanning.

## Chat

This is the most important screen.

Prioritize:

1. current course/scope;
2. question composer;
3. readable conversation;
4. answer content;
5. citations/evidence;
6. optional source inspection.

The answer must be the visual priority.

Do not expose retrieval internals to normal students.

Do not make every response look like a technical debug panel.

Loading must be simple.

Errors must be understandable and actionable without exposing internals.

## Citations

Citations should be easy to understand and clearly attached to the relevant answer content.

A user should be able to inspect the referenced source without fighting through a complex interface.

## Source viewer

Rebuild this component as well.

The supplied screenshot showing a large blank document/PDF area is a functional problem, not just a style issue.

The redesigned source viewer should communicate:

- document title;
- useful course context when relevant;
- cited page/section;
- actual document content/viewer;
- concise evidence excerpt;
- close/back action.

Do not create unnecessary tabs.

Do not load the entire document/chunk corpus when only one cited source is needed.

Verify against an actual supported document in a real browser session.

Do not accept "the iframe has height" as proof that document viewing works.

## Admin

Admin functionality can be rich, but navigation should be grouped logically, for example:

- Overview
- Knowledge
- Chat/Diagnostics
- Administration
- System
- Profile

Avoid a wall of unrelated links.

## Responsive design

Do not merely shrink desktop pages.

Design deliberate mobile behavior for:

- navigation;
- course selection;
- chat composer;
- messages/citations;
- source viewer;
- admin tables/tools where applicable.

---

# PHASE 5 — CHAT HISTORY IS OPTIONAL AND MUST BE REAL

I would like ChatGPT-like conversation history, but it is not allowed to destabilize the rebuild.

Do not implement fake persistent history using only in-memory frontend state.

If you implement history in this task, it must include:

- persistent Conversation/Message storage;
- secure ownership checks;
- appropriate APIs/services;
- multiple conversations;
- loading old conversations after restart;
- new conversation creation;
- safe user isolation;
- tests.

If proper history cannot be completed without compromising the current rebuild:

**defer it cleanly.**

Document it as the next controlled feature.

A correct deferred feature is better than a half-working fake feature.

---

# PHASE 6 — UPDATE THE CONTEXT FILES

After implementation, update these files so future Antigravity work cannot easily reintroduce the mistakes:

- `PROJECT_CONTEXT.md`
- `AGENTS.md`
- `context/ARCHITECTURE.md`
- `context/RAG_SPECIFICATION.md`
- `context/BACKEND_RULES.md`
- `context/FRONTEND_RULES.md`
- `context/TESTING_AND_SECURITY.md`
- `context/IMPLEMENTATION_PLAN.md`
- `context/TASK_STATE.md`

Do not just append contradictory notes.

Rewrite obsolete rules where necessary.

The final context must explicitly state:

- no raw session token in source URLs;
- no production TestClient transport;
- raw exceptions are not shown to users;
- UI tests are behavior-focused;
- frontend uses restrained interaction design;
- multimodal RAG is deferred;
- current RAG scope is text/multi-format RAG;
- persistent history is either implemented properly or explicitly deferred.

`TASK_STATE.md` must record:

- what was found;
- what was fixed;
- what was intentionally deferred;
- the next safe development phase.

---

# PHASE 7 — CLEANUP AND REPOSITORY HYGIENE

Remove stale generated artifacts when they are clearly not source files.

Review:

- `.env` / secrets;
- `.gitignore`;
- local storage/corpus;
- `.nicegui`;
- caches;
- `__pycache__`;
- generated debug dumps;
- accidental temporary files.

Do not delete required test fixtures or real source data without checking their purpose first.

Never commit secrets.

---

# PHASE 8 — VERIFICATION

Run the real supported project environment.

At minimum run configured:

- full pytest suite;
- security tests;
- source viewer tests;
- migration checks;
- Ruff checks/format checks if configured;
- type checks if configured;
- browser/manual visual QA.

Verify major routes and workflows including:

- login;
- registration;
- student home;
- courses;
- chat;
- citations;
- source viewer with a real supported document;
- student profile;
- admin dashboard;
- knowledge/documents;
- indexing;
- administrator management;
- activity/audit;
- system health;
- responsive behavior.

Also verify:

- empty states;
- long filenames;
- long answers;
- many citations;
- zero citations;
- provider/backend failures;
- unauthorized document access;
- expired sessions;
- query-token rejection;
- multiple users cannot cross-read state/history.

Never claim something passed unless it was actually run.

If an environment dependency prevents a test/check, record exactly what prevented it.

---

# PHASE 9 — GIT/GITHUB WORKFLOW

After every meaningful completed phase:

1. inspect the diff;
2. run relevant tests/checks;
3. update `context/TASK_STATE.md`;
4. commit with a clear message;
5. push to the existing GitHub remote/workflow.

Use meaningful commits, not a commit after every file edit.

Suggested commits:

- `fix(security): harden source viewer session handling`
- `refactor(frontend): replace production testclient transport`
- `test(frontend): recreate behavior-focused tests`
- `feat(frontend): rebuild student experience`
- `feat(frontend): rebuild administrator experience`
- `fix(frontend): rebuild source viewer and evidence UX`
- `feat(chat): add persistent conversation history` only when fully implemented
- `docs(context): update architecture and development rules`

Do not rewrite Git history or force-push unless explicitly instructed.

---

# DEFINITION OF DONE

This task is complete only when:

- the current project has been audited;
- real security/correctness defects are fixed;
- source viewer authentication no longer exposes the main session token;
- production frontend does not depend on FastAPI TestClient;
- raw backend exceptions are not exposed in UI;
- stale frontend tests have been recreated where appropriate;
- frontend has been genuinely redesigned, not recolored;
- UI is simple and visually coherent;
- unnecessary animation/hover/decorative effects are removed;
- source viewer actually displays real supported evidence content;
- context files prevent the repaired mistakes from returning;
- current RAG remains the existing text/multi-format system;
- multimodal RAG is clearly deferred rather than half-implemented;
- history is either properly implemented or cleanly deferred;
- tests/checks actually run and results are reported honestly;
- Git commits/pushes are completed for meaningful phases.

Do not call the result "perfect". Report what was actually verified.

---

# FINAL REPORT REQUIRED

At the end give me:

1. all important defects found, grouped by severity;
2. exact changes made;
3. files created/deleted/replaced;
4. tests/checks actually run and their real results;
5. anything not verified and why;
6. confirmation that multimodal RAG was intentionally NOT implemented in this phase;
7. whether persistent chat history was implemented or deferred;
8. Git commit hashes for completed phases;
9. the recommended next phase, which must NOT be multimodal RAG unless the current system is first verified stable.

Do not quietly add extra features beyond this scope.
