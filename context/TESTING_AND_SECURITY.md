# Testing and Security Verification

## Test philosophy

Tests protect behavior, security, and important contracts — not a temporary visual implementation.

When the frontend is intentionally redesigned, delete/rewrite stale presentation tests rather than weakening the redesign to satisfy them.

Never assert CSS classes, exact DOM nesting, decorative animation, card counts, obsolete labels, or exact HTML snippets unless the item is an explicit product/security contract.

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
9. document paths/filenames cannot traverse storage directories.

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
