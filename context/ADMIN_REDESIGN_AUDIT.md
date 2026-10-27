# Administrator Experience Redesign Audit

**Date:** 2026-10-19  
**Phase:** Stage 4 / Frontend Part 8 — Complete Administrator Experience Reset  
**Status:** Comprehensive Audit Complete & Approved for Implementation  
**Product:** Multimodal RAG-Based University Knowledge Assistant (RAG Assistant)

---

## 1. Executive Summary & Audit Mission

Antigravity has conducted a complete audit of the Administrator frontend experience across all registered administrative routes, backend API contracts, access-control policies, and visual representations.

The previous Administrator Overview and Navigation (Part 8A) successfully solved navigation duplication and student-redirect contracts, but the presentation was not visually approved due to:
- A large outlined telemetry container filled with 6 individual status pills.
- A row of 4 repetitive outlined buttons duplicating the persistent left sidebar.
- Separate card-like containers stacked vertically for each function.
- Repeated navigation links to Indexing, Courses, and Audit Log in multiple places on a single page.
- Dense data tables following multiple preceding cards.
- Excessive uppercase section labels.
- A card-for-every-subsystem pattern in System Health and Indexing.
- A blocking "Select a Course" barrier card on the Documents page.

This document records the exact route registrations, permissions, known defects, duplicate functionality to be excised, and the proposed final architecture for every administrative surface.

---

## 2. Administrator Destinations & Route Registration

All routes are registered in `frontend/main.py` and guarded client-side by `frontend/security/access_control.py` and server-side by backend FastAPI dependencies (`backend/app/api/deps.py`).

| Destination | Registered Route | Page Module | Authoritative Permission Requirement | Primary Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Overview** | `/dashboard` | `frontend/pages/dashboard_page.py` | `ADMIN` role (`is_main` or any faculty admin) | High-level operational workspace: system pulse, attention queue, repository summary |
| **Courses** | `/knowledge-bases` | `frontend/pages/knowledge_bases_page.py` | `COURSE_VIEW` or `is_main` | Course catalog administration, syllabus repository creation, document scoping |
| **Documents & Processing** | `/documents` | `frontend/pages/documents_page.py` | `DOCUMENT_VIEW` or `DOCUMENT_INDEX` or `is_main` | Unified workspace: multi-format document curation & cross-course vectorization queue |
| **Indexing (Alias)** | `/indexing` | `frontend/pages/indexing_page.py` | `DOCUMENT_INDEX` or `DOCUMENT_INDEX_RETRY` or `is_main` | Backward-compatibility alias route redirecting to `/documents?view=processing` |
| **Administrators & Permissions** | `/administrators` | `frontend/pages/admin_users_page.py` | `ADMIN_VIEW` or `is_main` | RBAC directory, account provisioning, course scoping, and fine-grained permission assignment |
| **Activity & Audit** | `/activity` | `frontend/pages/activity_page.py` | `ADMIN_VIEW` or `is_main` | Immutable chronological audit ledger of catalog changes, document lifecycle, and governance |
| **System Health** | `/system-health` | `frontend/pages/system_health_page.py` | `ADMIN_VIEW` or `is_main` | Deep diagnostic matrix for PostgreSQL, pgvector, Ollama runtime, and worker daemon |
| **Test Assistant** | `/chat` | `frontend/pages/chat_page.py` | `ADMIN_CHAT` or `is_main` | Verification tool for administrators to test conversational retrieval against authorized courses |
| **My Profile** | `/profile` | `frontend/pages/profile_page.py` | Authenticated session | Academic identity, session status, governance panel, and sign-out controls |
| **Source Reader** | `/reader` | `frontend/pages/reader_page.py` | `DOCUMENT_VIEW` or student course access | Full-page authenticated document reading with citation jumping and evidence excerpts |

---

## 3. Inventory of Duplicate & Redundant UI Elements

Across the administrator application, the following duplicate and redundant interface patterns were identified and slated for removal:

1. **Redundant Quick Action Button Row on Overview:**
   - *Current:* An "ACADEMIC MANAGEMENT ACTIONS" container featuring 4 buttons: `Manage Courses`, `Manage Documents`, `Open Indexing Center`, and `Audit Log`.
   - *Problem:* These 4 buttons sit directly adjacent to the persistent left sidebar which already displays `Courses`, `Documents`, `Indexing`, and `Activity & Audit`.
   - *Action:* Completely remove the redundant action button row. The sidebar is the authoritative and permanent navigation pattern.

2. **Repeated Deep Links on Overview:**
   - *Current:* Multiple sections each feature repeated links to the same destination (`Detailed Diagnostics` + `System Health` in nav; `View Indexing Center` + `Open Queue` + `Indexing Center` in nav; `Manage Courses` in header + in table row + in nav).
   - *Problem:* Visual clutter and repeated calls to action.
   - *Action:* Consolidate each section to a single, contextual navigation link.

3. **Duplicated Top Stat Cards on Indexing and Activity:**
   - *Current:* `Indexing Center` renders 4 cards (`TOTAL JOBS`, `ACTIVE JOBS`, `ATTENTION`, `COMPLETED`), immediately followed by filter tabs displaying the exact same numbers: `All Jobs (2)`, `Active (0)`, `Needs Attention (0)`, `Completed (2)`. `Activity & Audit` similarly renders 3 stat cards duplicating the table filter counts.
   - *Problem:* Redundant data that adds zero value while pushing the actual operational queue/table down the screen.
   - *Action:* Remove the top stat cards. Let the filter pills in the toolbar display truthful counts directly.

4. **Nested Card-in-Card Hierarchies on System Health & Indexing:**
   - *Current:* In `System Health`, an outer card container wraps 6 identical sub-cards, one for each component. In `Indexing Center`, an outer card wraps another card for "System Idle".
   - *Problem:* Visual repetition and excessive border nesting.
   - *Action:* Replace nested cards with clean, structured, responsive data tables and lists.

5. **Blocking "Select a Course" Barrier Card on Documents:**
   - *Current:* Navigating to `/documents` without a `kb_id` parameter renders a giant card with 3 course cards, forcing the user to select a course before seeing any documents.
   - *Problem:* Prevents global document visibility, searching, and filtering.
   - *Action:* Default to showing all accessible documents in a scannable directory table with a course filter dropdown ("All Courses" or specific course).

6. **Static Informative Header Cards on Administrators Page:**
   - *Current:* Two large cards at the top ("MAIN ADMINISTRATOR" and "FACULTY ADMINISTRATOR") explaining roles, taking up vertical space.
   - *Problem:* Static text displaces the actual directory of administrators.
   - *Action:* Replace with a compact one-line governance summary note.

7. **Excessive Uppercase Micro-Labels:**
   - *Current:* Ubiquitous uppercase headings (`SYSTEM OPERATIONAL TELEMETRY`, `ACADEMIC MANAGEMENT ACTIONS`, `INDEXING QUEUE & PROCESSING`, `COURSE KNOWLEDGE REPOSITORIES`, `RECENT ADMINISTRATIVE ACTIVITY`).
   - *Action:* Use editorial sentence-case headings and clean hierarchy per `context/FRONTEND_DESIGN_SYSTEM.md`.

---

## 4. Before / After Feature & Navigation Map

| Page | Old Design (Part 8A Baseline) | New Redesign Architecture |
| :--- | :--- | :--- |
| **Sidebar Navigation** | Grouped navigation in drawer; functional but cluttered group headers. | Clean editorial sidebar: unified group labels, consistent icon spacing, active indicator bar in gold/navy, account footer. |
| **Overview (`/dashboard`)** | Outlined telemetry box with 6 chips, 4 duplicate action buttons, 2-column card grid, large course table, recent activity card. | Compact operational workspace: Truthful System Condition Bar (Operational / Degraded / Outage), Attention Panel (failed jobs only), 2 purposeful split columns (Active Courses & Ingestion Queue), no redundant button row. |
| **Courses (`/knowledge-bases`)** | Student catalog card grid with "Manage Docs" button on cards. | Professional Course Management directory table: Name, Code, Description, Published Status, Verified Material Count, Scope/Visibility, and Actions (`Documents`, `Test Chat`). Dedicated `+ New Course` dialog. |
| **Documents (`/documents`)** | Blocking "Select a Course" container with 3 cards; no global document list. | Unified Document Workspace: Global document table with Course Filter, Status Filter, Search, and `+ Upload Material` dialog. Row actions: `Read`, `Chunks`, `Delete`. |
| **Indexing (`/indexing`)** | 4 stat cards at top, large card with nested "System Idle" card, separate completed jobs card. | Operational Queue Ledger: Clean live header, filter toolbar with counts (`All`, `Active`, `Failed`, `Completed`), clean responsive queue table with stage, chunks, and contextual retry. |
| **Administrators (`/administrators`)** | 2 large role explanation cards, segmented card list of users, dense modal. | Streamlined RBAC Directory: Compact governance note, user directory table with role badge, course scope, permissions count, status, and edit/delete actions. Structured 4-section provisioning drawer/dialog. |
| **Activity & Audit (`/activity`)** | 3 duplicate stat cards, dense timeline list inside card. | Clean Audit Ledger: Unified toolbar with search, category pills, outcome filter, and readable audit event table (Timestamp, Actor, Category, Action, Target, Outcome, Details). |
| **System Health (`/system-health`)** | Status banner + large card containing 6 nested sub-cards. | Diagnostic Subsystem Matrix: Truthful overall condition banner + structured diagnostic table (Subsystem, Scope, Reported Status, Diagnostics telemetry). |
| **Test Assistant (`/chat`)** | Chat interface labeled "Admin Knowledge Chat". | Clear "Test Assistant" destination under System & Tools in sidebar, preserving the approved chat interface and scoping. |
| **Profile (`/profile`)** | Approved Part 7C design. | Preserved 100%: Clean identity card, Governance & Permissions panel, Return to Dashboard, Sign Out. |

---

## 5. Security & Authorization Guarantees

1. **Authoritative Server-Side RBAC:** All page actions communicate with backend FastAPI endpoints that enforce token validation, user active checks, and permission checks (`deps.py`).
2. **Client-Side Capability Consistency:** `frontend/security/access_control.py` ensures the UI reflects server authorization without exposing forbidden controls.
3. **Route Isolation:**
   - Authenticated student visiting `/dashboard` is automatically forwarded to `/chat`.
   - Authenticated administrator visiting `/dashboard` sees the Administrator Overview.
   - Unauthorized attempts to access `/administrators`, `/documents`, etc., fail closed with access-restricted empty state or redirect.
4. **Error Sanitization:** All user-facing error messages pass through `normalize_error()`. Raw exception strings, database stack traces, filesystem paths, and tokens are never rendered.
5. **Session Security:** No raw session tokens are stored in `app.storage.user` or exposed to browser JavaScript. Same-origin HttpOnly cookies handle authentication.

---

## 6. Part 10B Corrective Audit & Truthful Diagnostics Resolution

During the Part 10B audit, the following remaining defects across Administrator sub-surfaces were identified and corrected:

1. **System Health Status Truthfulness & Preview Mode Reporting:**
   - *Defect:* `FrontendAPIClient.get_system_health()` in preview mode returned components with `status="healthy"` and overall status `"healthy"` despite stating database decoupled. `dashboard_page.py` also converted missing status to healthy via `(system_health.status or "healthy").lower()`.
   - *Resolution:* In preview mode, `get_system_health()` returns `status="preview"` with components explicitly labeled unverified/simulated. Status badge component updated with dedicated `PREVIEW` status (slate `#475569`, neutral styling). Overview and System Health pages both map missing/null status to `"unknown"` (never `"healthy"`), and render explicit `Interactive Preview Mode (Simulated Infrastructure)` banner when `preview`.
   - *Live Mode:* Live backend health response preserves detailed subsystem diagnostics. Failed requests raise informative exceptions with HTTP status and backend detail (never silently replaced with mock healthy data).

2. **Administrators & Permissions Course-Name Resolution and Error Guards:**
   - *Defect:* Course loading failures were silently converted to `available_courses = []`, showing "No active courses registered in catalog", and raw UUID strings were displayed in the Course Scope column.
   - *Resolution:* Implemented module-level helpers `get_course_map()`, `resolve_course_display_name()`, and `extract_assigned_course_ids()`.
   - Distinguishes 3 states: (1) success with courses, (2) success empty (`[]`), (3) catalog failure (`courses_error`).
   - Course Scope column in Directory table renders human-readable course names (e.g. `Computer Architecture`, `Official University Regulations`) with tooltip showing remaining courses if > 2.
   - Permissions Dialog resolves course names and IDs safely; guards `save_permissions()` against executing when `courses_error` is present so assigned scopes cannot be wiped.
   - Provisioning modal guards against creating faculty admins without a valid course catalog.
   - Honest error banner with `Retry Catalog` action displayed whenever catalog loading fails.

3. **Overview Simplification & Consistency:**
   - *Defect:* Column 2 previously checked `elif active_jobs: ... else: "Queue Idle: All embeddings synchronized"`. When `active_jobs == 0` and `failed_jobs > 0`, it falsely claimed all embeddings were synchronized. Overview also displayed full, unbounded course lists duplicating the Course Management view.
   - *Resolution:* Column 2 now displays an attention alert linking directly to `/documents?view=processing` whenever failed jobs exist and active jobs are 0. Bounded Course Repositories summary to 4 courses (`course_summaries[:4]`) with a `+ N more courses in Course Management →` link.

4. **PostgreSQL Test-Database Diagnosis & Resolution:**
   - *Defect:* Connection timeout to `rag_assistant_test_db` on port 5432 previously caused 5 integration test errors and skipped security tests.
   - *Diagnosis:* PostgreSQL on this Windows machine is an unmanaged portable binary (`D:\Kartik\pgsql\pgsql\bin\postgres.exe`), not a registered Windows Service (`Get-Service` returns nothing). Ephemeral subshell commands starting it terminated upon subshell exit. Both `rag_assistant_db` (production/dev) and `rag_assistant_test_db` (test) exist and are valid databases owned by `rag_app_user`.
   - *Resolution:* Launched `postgres.exe` as a persistent daemon task (`task-2062`). Ran integration tests (`test_indexing_and_admin_rbac_integration.py`: 5/5 passed) and security tests (`test_backend_security_audit.py`: 19/19 passed) with 100% pass rates.
