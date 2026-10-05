# Frontend Test Rewrite Specification

This file is the implementation contract for recreating the frontend tests from scratch.

## Replace, do not patch

The existing `backend/tests/unit/test_frontend.py` is heavily coupled to the previous UI and mixes integration/database mutation with presentation assertions. Do not incrementally edit it. Delete it and create a new focused test module.

Review and rewrite these additional stale modules as needed:
- `backend/tests/unit/test_student_dashboard_fixes.py`
- `backend/tests/unit/test_step21e_frontend_workflow.py`
- `backend/tests/unit/test_source_viewer.py`

Keep backend/security behavior tests that remain valid, but remove assertions that freeze the old visual implementation.

## New test_frontend.py responsibilities

1. API-client contract
   - successful login/logout;
   - 401/403 clears client auth state;
   - safe error normalization;
   - DTO conversion for chat/citation/document/course responses;
   - invalid input validation.

2. Frontend state
   - user message append;
   - assistant response append;
   - clear/reset;
   - generation failure maps to a safe user-facing error;
   - per-session state does not bleed between sessions.

3. Citation helpers
   - `[1]`/`[source_1]` mapping to the correct citation object;
   - invalid citation tokens remain ordinary text;
   - normal markdown links are not accidentally converted;
   - output cannot include a session token;
   - untrusted document name/snippet cannot inject arbitrary raw HTML/event handlers.

4. Navigation/access semantics
   - student can reach required student routes;
   - admin-only routes require admin authorization;
   - student cannot invoke admin-only API actions;
   - do not assert exact human-readable navigation labels unless they are an explicit requirement.

5. Route smoke tests
   - required routes register;
   - rendering does not raise for representative authenticated roles;
   - do not assert card count, CSS classes, or exact HTML.

## New source viewer tests

Test behavior, not styling:
- authorized stream succeeds;
- unauthenticated stream fails;
- cross-user/cross-course stream fails;
- revoked/expired session fails;
- query-string token authentication is rejected;
- generated viewer URL contains no main session token;
- `document.cookie` is not used to write the raw session token;
- untrusted display fields are escaped/safely rendered;
- canonical document UUID is used.

## Test quality rules

- Each test should have one clear responsibility.
- Avoid global database cleanup that makes unrelated tests depend on execution order.
- Prefer fixtures/factories over repeated hard-coded records.
- Do not increase test count for the sake of reporting a bigger number.
- Do not write source-code substring tests unless checking a security invariant that cannot be tested through behavior; even then prefer runtime behavior.
- Tests must remain valid after a reasonable visual redesign.
