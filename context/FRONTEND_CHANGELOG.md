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
