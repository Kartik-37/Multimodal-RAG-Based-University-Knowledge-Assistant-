# Frontend Changelog — RAG Assistant

This changelog records all design, structural, and architectural changes to the NiceGUI presentation layer of the **RAG Assistant** (Multimodal RAG-Based University Knowledge Assistant).

---

## 2026-10-07 — Stage 1: Public Entry & Authentication Redesign (COMPLETED & VERIFIED)

- **Date:** 2026-10-07
- **Stage:** Stage 1 — Public Entry & Authentication Redesign
- **Starting Git Commit:** `4575184`
- **Files Changed:**
  - `frontend/components/layout.py`: Redesigned `auth_layout` with rich contextual public headers (`landing`, `student`, `admin`, `register`), flexible container width without rigid centering restrictions, and an anchored institutional academic footer.
  - `frontend/pages/auth_pages.py`: Completely rebuilt `/login`, `/student/login`, `/admin/login`, and `/register` from scratch.
  - `context/FRONTEND_CHANGELOG.md`: Created to document detailed frontend design decisions.
  - `context/TASK_STATE.md`: Appended Stage 1 audit and completion records.
- **Previous Behavior / Design:**
  - Public portal at `/login` consisted of a basic dark top bar, a centered "RAG Assistant" heading, and two generic floating cards ("Student Portal" and "Administrator Portal") surrounded by 70% unused, empty white space.
  - No product identity explanation: a first-time visitor could not determine what RAG Assistant does, what problems it solves, or why to trust it.
  - Sign in and registration pages (`/student/login`, `/admin/login`, `/register`) were plain forms in isolated, centered cards on empty backdrops.
  - Internal technical jargon was either stripped completely (leading to emptiness) or exposed excessively in older versions (RRF, 1024-d, pgvector, CrossEncoder).
- **New Behavior / Design Implemented:**
  - **Public Entry (`/login`)**:
    1. Deliberate public header establishing brand identity, product mark, and direct entry actions ("Student Sign In", "Faculty & Admin", "Create Account").
    2. Primary Hero viewport with clear value headline ("Grounded Knowledge Assistant for University Courses"), concise supporting paragraph, and primary CTA ("Sign in as Student") alongside secondary portals.
    3. Live Grounded Evidence Demonstration Card showing an authentic university student query, verified assistant answer with inline citation `[1]`, and exact quoted syllabus excerpt with source metadata.
    4. Structured Product Value section highlighting 4 truthful core capabilities: Course-Scoped Access, Verifiable Page Citations, Multi-Format Text Ingestion, and Institution-Governed Materials.
    5. Two-Column Dedicated Portals: Student Portal (study, ask, cite) vs Administrator/Faculty Portal (course curation, document lifecycle, vector indexing).
    6. Academic Trust & Security section: highlighting server-side RBAC, course membership isolation, and zero hallucination safeguards.
    7. Anchored bottom CTA & balanced institutional footer.
  - **Student Login (`/student/login`)**:
    - Modern 2-column balanced layout combining academic context and guidance on the left with a focused, accessible sign-in form on the right.
    - Password visibility toggle, explicit accessible labels, loading states, sanitized error reporting via `normalize_error()`.
    - Clear navigation to registration, admin sign-in, and portal home.
  - **Admin Login (`/admin/login`)**:
    - Distinct administrative aesthetic emphasizing faculty credentials, restricted access notices, and server-side RBAC enforcement.
    - Navigation to student portal and portal home.
  - **Student Registration (`/register`)**:
    - Institutional onboarding experience with academic email validation, password strength feedback, and student identity creation.
- **Reason for Change:**
  - The previous design felt empty, generic, dull, and like a floating card template rather than an intentionally designed academic SaaS product.
- **Security Implications:**
  - Strict preservation of HttpOnly session cookies (`session_id`).
  - Zero token query parameters (`?token=`), zero browser `localStorage` credentials, zero `document.cookie` manipulation.
  - All user-facing errors sanitized through `normalize_error()`.
  - Server-side role enforcement strictly preserved (`STUDENT` vs `ADMIN`).
- **Responsive Implications:**
  - Full desktop, laptop, tablet, and mobile responsiveness without horizontal overflow or clipped form controls.
  - Touch-friendly button and input sizing (minimum 44px touch targets).
- **Accessibility Implications:**
  - WCAG 2.1 AA compliant color contrast (Slate 900 on White / Slate 50).
  - Explicit `<label>` elements and `aria-label` attributes for all inputs and buttons.
  - Visible focus rings (`*:focus-visible`) with 2px Oxford Blue outlines.
  - Color is never the sole indicator of state.
- **What Was Deliberately NOT Changed:**
  - Protected application pages (`/dashboard`, `/knowledge-bases`, `/documents`, `/chat`, `/indexing`, `/administrators`, `/activity`, `/system-health`, `/profile`) remain untouched.
  - Backend API contracts, authentication endpoints, and database models are completely preserved.
  - Multi-format TEXT RAG scope is preserved (PDF, DOCX, TXT, Markdown, CSV). Multimodal RAG and persistent chat history remain deferred.
- **Verification Results:**
  - Unit tests: 335 passed, 0 failed.
  - Security tests: 50 passed, 0 failed.
  - Integration tests: 191 passed, 0 failed.
  - Total test suite: 576 passed, 0 failed.
  - Ruff check: 0 errors across all files.

---

## 2026-10-07 — Stage 2: Complete Student Experience Rebuild & Public-Page Polish (COMPLETED & VERIFIED)

- **Date:** 2026-10-07
- **Stage:** Stage 2 — Complete Student Experience Rebuild & Public-Page Polish
- **Starting Git Commit:** `a5d9d4c`
- **Files Changed:**
  - `frontend/components/layout.py`: Unified student navigation shell with single top navigation header, removed persistent drawer redundancy, removed BCA header badge, and eliminated unnecessary breadcrumbs on public and student routes.
  - `frontend/components/theme.py`: Refined high-contrast academic color palette tokens and focus states.
  - `frontend/pages/auth_pages.py`: Polished public landing (`/login`) with WCAG AAA high-contrast text, hero demonstration card, academic trust indicators, and sharpened student sign-in portals.
  - `frontend/pages/dashboard_page.py`: Rebuilt student dashboard as an academic study hub with prompt pills, fast course jumps, and study activity highlights without empty whitespace voids.
  - `frontend/pages/knowledge_bases_page.py`: Rebuilt course library with search filtering, course overview cards, material counters, and direct study actions.
  - `frontend/pages/chat_page.py`: Rebuilt conversational assistant with bottom composer, default `ALL_COURSES` search scope, inline clickable citation pills `[1]`, and grounded evidence panel.
  - `frontend/pages/profile_page.py`: Rebuilt student profile with institutional identity, enrolled courses, and clean security guidelines; stripped internal PostgreSQL session jargon.
  - `frontend/components/source_viewer.py`: Rebuilt multi-format source document viewer supporting PDF (`#page=N`), DOCX, TXT, MD, CSV with safe content preview, evidence excerpts, and zero token query leakage.
  - `backend/app/api/deps.py`: Hardened course visibility and document retrieval dependencies ensuring strict membership-based authorization (`KnowledgeBaseMember`) combined with `is_active` and `is_student_visible` flags.
  - `backend/app/api/v1/endpoints/knowledge_bases.py`: Maintained strict 404 responses for unassigned/unauthorized courses.
  - `alembic/versions/aebbc63863c7_add_kb_is_active_and_student_visible.py`: Migration for `is_active` and `is_student_visible` columns.
  - `backend/tests/security/test_student_access_policy.py`: Added comprehensive security suite testing Cases A through I.
- **Security & Authorization Invariants Preserved:**
  - Zero raw tokens in URLs or browser JS; native HttpOnly session cookie synchronization.
  - Strict membership-based student authorization: unassigned courses return HTTP 404 to prevent private course existence leakage.
  - Multi-format text RAG strictly documented (PDF, DOCX, TXT, MD, CSV); non-text multimodal features remain deferred.
  - Zero fake persistent chat history.
  - Hard stop: zero modifications to administrator interfaces (`/documents`, `/indexing`, `/administrators`, `/activity`, `/system-health`).
- **Verification Results:**
  - `backend/tests/security/`: 58/58 passed (100%).
  - `backend/tests/integration/test_source_viewer.py`: 8/8 passed (100%).
  - `backend/tests/integration/test_document_ingestion.py`: 13/13 passed (100%).
  - Full non-real_ollama regression suite: 584/584 passed (100%).
  - `ruff check .`: 100% clean (0 errors across entire workspace).
  - HTTP 200 route smoke tests verified for `/login`, `/student/login`, `/dashboard`, `/knowledge-bases`, `/chat`, and `/profile`. Browser automation tool Playwright driver installation 404 noted per Phase F guidelines.

