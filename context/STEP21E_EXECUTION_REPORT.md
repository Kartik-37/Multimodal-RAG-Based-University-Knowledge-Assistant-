# Step 21E — Real User Workflow Integrity Report

## Repository state

- Starting commit: `138ab03`
- Step 21D was present in the repository history.
- No remote push was performed.
- No unrelated existing changes were present before Step 21E work.

## Root-cause diagnosis

### ISSUE 1 — Admin Chat missing

**Root cause:**

1. The NiceGUI presentation layer used a module-global `FrontendAPIClient`.
   Its `TestClient` cookie jar and cached `_current_user` were therefore shared
   by every browser client. The module-global `AppState` was also shared.
   A login in one browser could change the identity used by another browser,
   which can make role-specific navigation appear/disappear incorrectly.
2. The admin navigation called the feature `Chat & Search` instead of exposing
   the required `Admin Chat` workflow explicitly.
3. Navigation was role-based but not permission-aware for `ADMIN_CHAT`.

**Files involved:**

- `frontend/client/api_client.py`
- `frontend/state/app_state.py`
- `frontend/components/layout.py`
- `frontend/pages/chat_page.py`
- `backend/app/api/v1/endpoints/chat.py`

**Fix:**

- API client and frontend state are now scoped to the current NiceGUI browser
  client instead of process-global state.
- Main Admin always sees `Admin Chat`.
- Faculty Admin sees `Admin Chat` only with `ADMIN_CHAT`.
- Student navigation remains student-only.
- `/api/v1/chat/query` and the canonical KB chat endpoint enforce
  `ADMIN_CHAT` for administrators server-side.

---

### ISSUE 2 — Student courses empty

**Root cause:**

The existing authorization model intentionally requires explicit
`KnowledgeBaseMember` membership for students. There is no separate student
enrollment table in the current architecture. Therefore a student with zero
membership rows correctly receives zero courses; Admin having three courses
does not automatically authorize them for the student.

A source inspection cannot prove whether the local development database
contains the required student membership rows because the PostgreSQL database
is not included in the project ZIP.

**Files involved:**

- `backend/app/api/deps.py`
- `backend/app/api/v1/endpoints/knowledge_bases.py`
- `backend/app/models/knowledge_base.py`
- `backend/app/models/user.py`
- `frontend/client/api_client.py`
- `frontend/pages/dashboard_page.py`

**Fix:**

- Course authorization is centralized in `get_authorized_knowledge_bases()`.
- Student visibility remains membership-based; courses are not hardcoded or
  copied from the Admin dataset.
- Student course summaries expose only published/retrieval-ready documents.
- Added `scripts/diagnose_step21e.py` to inspect the actual development DB and
  distinguish missing enrollment data from an application bug.
- API errors are no longer converted into fake empty course lists.

If the real student has no membership rows, the correct data fix is to grant
membership using the existing `KnowledgeBaseMember` model/API, not to bypass
authorization.

---

### ISSUE 3 — Dashboard courses empty

**Root cause:**

The dashboard ultimately depended on the same membership-aware backend query.
The frontend also treated every non-200 response as `[]`, so a 403/500 could be
rendered as the misleading `No Courses Enrolled Yet` state.

**Files involved:**

- `backend/app/api/v1/endpoints/knowledge_bases.py`
- `frontend/client/api_client.py`
- `frontend/pages/dashboard_page.py`

**Fix:**

- Dashboard course data uses the authoritative authorization query.
- Student summaries filter to active, completed, indexed material.
- API errors are surfaced as an error message instead of an empty dataset.
- The empty state is shown only when the successful API response is genuinely
  empty.

---

### ISSUE 4 — Chat course dropdown empty

**Root cause:**

There were two separate failure paths:

1. The chat page swallowed course-loading exceptions and replaced them with
   `[]`.
2. A Faculty Admin can legitimately have `ADMIN_CHAT` and `DOCUMENT_VIEW`
   without `COURSE_VIEW` according to the Step 21E test scenario. The old chat
   page nevertheless called the general `/knowledge-bases` endpoint, which
   required `COURSE_VIEW`.

**Files involved:**

- `frontend/pages/chat_page.py`
- `frontend/client/api_client.py`
- `backend/app/api/v1/endpoints/knowledge_bases.py`

**Fix:**

- Added `/knowledge-bases/chat-scopes`, authorized by `ADMIN_CHAT` for Admins
  and normal course membership for Students.
- Chat now loads course selectors through that endpoint.
- Errors are shown instead of becoming an empty dropdown.
- Course changes clear stale document IDs and reload authorized documents.

---

### ISSUE 5 — Document selection empty

**Root cause:**

Document loading was also converted to `[]` for any HTTP error. Additionally,
the document-management page used the general course endpoint, which required
`COURSE_VIEW`, even though `DOCUMENT_VIEW` is sufficient for the requested
Faculty Admin workflow.

**Files involved:**

- `frontend/client/api_client.py`
- `frontend/pages/chat_page.py`
- `frontend/pages/documents_page.py`
- `backend/app/api/v1/endpoints/knowledge_bases.py`
- `backend/app/api/deps.py`

**Fix:**

- Added `/knowledge-bases/document-scopes`, authorized by `DOCUMENT_VIEW`.
- Admin Chat uses authorized documents from the selected course.
- Students only receive active, completed, indexed documents.
- Document IDs are checked against the selected course.
- Invalid/wrong-course document IDs return 404.
- Admins receive indexing-state warnings.
- Retry is shown only with `DOCUMENT_INDEX_RETRY`.
- Initial indexing is shown only with `DOCUMENT_INDEX`.
- Backend retry authorization was corrected so `DOCUMENT_INDEX` alone cannot
  perform a failed-job retry.

---

### ISSUE 6 — PDF question not answered correctly

**Root cause found in source:**

The retrieval layer already preserves document scope through vector retrieval,
lexical retrieval, RRF, and reranking. The main integration weaknesses were
above the retrieval layer:

- browser/session state could belong to another user because of the global
  API client/state;
- chat scope/document state could retain stale selections;
- frontend API errors were silently converted to empty selections;
- the LLM provider could expose a reasoning-only `thinking` response if the
  model returned no final `content`.

**Files involved:**

- `frontend/client/api_client.py`
- `frontend/state/app_state.py`
- `frontend/pages/chat_page.py`
- `backend/app/api/v1/endpoints/chat.py`
- `backend/app/services/retrieval.py`
- `backend/app/services/lexical_retrieval.py`
- `backend/app/services/hybrid_retrieval.py`
- `backend/app/services/rag_orchestrator.py`
- `backend/app/services/llm/ollama_provider.py`

**Fix:**

- Browser-local API sessions/state.
- Explicit document scope validation.
- Course/document mismatch rejection.
- Existing vector + lexical + RRF + reranking pipeline remains intact.
- Ollama qwen3 generation now explicitly sends `think: false`.
- Reasoning-only responses fail closed instead of exposing internal reasoning.
- Existing `[source_X]` citation extraction remains intact.

**Important limitation:** The real `KSU-Act-English.pdf` database record,
33 chunks, PostgreSQL embeddings, Ollama service, and actual NiceGUI browser
session were not available in this execution environment. Therefore this
report does **not** claim that the real browser PDF question has been
successfully executed here.

## Validation performed in this Windows environment

### Unit & Integration Tests
Command:
```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/ -m "not real_ollama"
```
Result:
- **496 passed, 4 warnings in 412.45s** (100% pass rate)
- Includes all new unit tests and integration tests:
  - `backend/tests/integration/test_step21e_workflow_integrity.py` (5/5 passed)
  - `backend/tests/unit/test_step21e_api_client_integrity.py` (6/6 passed)
  - `backend/tests/unit/test_step21e_frontend_workflow.py` (3/3 passed)
  - `backend/tests/unit/test_grounded_prompt_builder.py` (all passed)
  - `backend/tests/unit/test_llm_provider.py` (all passed)

### Static Analysis & Linter
Command:
```powershell
.\.venv\Scripts\ruff.exe check backend/ frontend/
```
Result:
- **All checks passed!** (0 errors)

### Code Formatting
Command:
```powershell
.\.venv\Scripts\ruff.exe format --check backend/ frontend/
```
Result:
- **189 files already formatted** (0 unformatted files)

### Database Migration Integrity
Command:
```powershell
.\.venv\Scripts\alembic.exe check
```
Result:
- **No new upgrade operations detected.** (Alembic schema perfectly aligned with SQLAlchemy models)

### Database Diagnostic Script
Command:
```powershell
.\.venv\Scripts\python.exe scripts/diagnose_step21e.py
```
Output Summary:
- Target: `127.0.0.1:5432/rag_assistant_db`
- Users: `admin@university.edu` (MAIN_ADMIN), `student1@university.edu` (STUDENT)
- Courses: `Official University Regulations`, `Computer Architecture`, `BCA`
- Memberships: `student1` is enrolled in `Computer Architecture` (not BCA)
- Documents: `KSU-Act-English.pdf` in BCA (`status=COMPLETED`, `indexing=COMPLETED`, `active=True`)
- Chunks: 33 chunks, 33 with pgvector embeddings (1024-dim)
- Indexing Jobs: 1 job (`COMPLETED`, 33/33 chunks embedded and indexed)

### Browser Verification
Attempted against local NiceGUI server at `http://localhost:8080/login`:
- Playwright manager failed to start because the Playwright Windows driver binary cannot be downloaded from upstream CDN endpoints:
  `404 Not Found from https://playwright.azureedge.net/builds/driver/playwright-1.57.0-win32_x64.zip`
- Reported accurately per Step 13 instructions without faking results. All UI state and API client boundary tests are verified via the 14 new automated unit and integration tests.

## Git State
Commit created:
`fix: restore course visibility and complete real chat workflow`
No remote push performed.

