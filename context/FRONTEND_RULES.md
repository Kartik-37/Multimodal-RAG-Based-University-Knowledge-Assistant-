# Frontend Rules — NiceGUI

## Technology

- NiceGUI only.
- Python-first implementation.
- Do not introduce React/Next/Vue/Angular unless the user explicitly changes the decision.
- Keep API/business logic out of page components.

## Rebuild mode (Phase 4)

- Phase 4 will be a **complete frontend rebuild from scratch** in NiceGUI.
- The existing frontend layout is **superseded** and must NOT be merely recolored, rebordered, or patched.
- Do NOT implement this rebuild in Phase 2; Phase 2 is strictly context and documentation consistency.

## Screenshot reference rule

- The screenshots in the `screenshot/` folder document the existing implementation and its defects; they are **audit evidence, not a design template**.
- Future Phase 4 frontend work must inspect **all** supplied screenshots individually before redesigning corresponding areas to understand the user journey, existing flaws, and functional needs.

## User experience target

The UI must be:
- simple to understand;
- beautiful without being decorative;
- calm and trustworthy;
- readable for long sessions;
- responsive on desktop/tablet/mobile;
- visually distinct enough to feel designed, not generated from a generic SaaS template.

The user's explicit design preference is stronger than the current screenshot styling.

## Do not do

Do not add visual elements merely because a dashboard template contains them.

Avoid:
- excessive cards;
- gradient backgrounds;
- glassmorphism;
- giant hero copy;
- decorative illustrations that do not aid the task;
- glowing effects;
- repeated badges/pills;
- card lift/scale on hover;
- large motion effects;
- pulsing/spinning decorative icons;
- unnecessary tooltips;
- duplicate navigation;
- fake analytics;
- dense operational data on student pages.

## Motion

Default to no animation.

Use a transition only when it makes an interaction easier to understand. Keep it short and subtle.

Use a progress indicator only when there is a real asynchronous process. A static status label is preferred when it communicates the state clearly.

Honor reduced-motion preferences where the browser/UI framework supports it.

## Visual hierarchy

Every primary page should make these obvious:
1. where the user is;
2. what they can do now;
3. what the primary action is;
4. what happened after the action;
5. how to recover from failure.

Use spacing and typography before adding more containers.

## Student information architecture

Default primary navigation:
- Home
- Ask Assistant
- Courses
- Profile
- History only after persistent history exists.

Keep student pages free of retrieval internals and administrator diagnostics.

## Administrator information architecture

Group administration into a small number of understandable sections:
- Overview
- Knowledge
- Chat/Diagnostics
- Administration
- System
- Profile

Do not expose every technical operation as a top-level navigation item.

## Chat UX

The chat page is the main product experience.

Preferred structure:
- concise page header;
- course/scope selector;
- conversation area;
- readable assistant answer;
- visible citation references;
- source/evidence access near the citation;
- composer fixed or naturally positioned at the bottom;
- clear loading/error state.

Do not fill the chat screen with implementation details such as RRF scores, vector scores, reranker internals, or debugging data for students.

Admin diagnostics may be reachable through a deliberate secondary control.

## Citation UX

Citations should be legible in the answer.

Clicking a citation should open the specific authorized evidence source, ideally at the cited page.

Do not rely on raw HTML/JavaScript hacks when a normal NiceGUI interaction can perform the same action safely.

Citation data is untrusted input. Escape/validate content and do not inject arbitrary document names/snippets into raw HTML.

## Source viewer UX

Keep it focused:
- document name;
- course/context;
- page number;
- source document view;
- cited evidence excerpt when available;
- close action.

Do not require the user to understand authentication tokens, URL parameters, object/embed fallbacks, or internal retrieval metadata.

The same-origin authenticated session should authorize the document request. No main session token may be placed in the URL or read by browser JavaScript.

Do not render every chunk of a large document at once. Bound, paginate, or show only relevant evidence.

## Authentication and session rules in frontend

- **No raw token persistence:** Raw session tokens must NEVER be stored in `app.storage.user["auth_session_token"]`, browser `localStorage`, or client-side JavaScript.
- **Session isolation:** The frontend uses an in-memory session client mapping (`_session_clients[session_id]`) keyed by Starlette session ID.
- **Student course authorization:** Student course access is governed by the authoritative catalog policy (`context/FRONTEND_DESIGN_SYSTEM.md`): active, student-visible courses are accessible automatically; restricted courses require membership (`KnowledgeBaseMember`); inactive or unauthorized courses return 404.

## Error states & centralized normalization

Never display raw Python exceptions, SQL errors, traceback fragments, provider error payloads, file paths, tokens, or secret configuration.

All error details reaching the UI must pass through `normalize_error()` in `frontend/client/error_handler.py`:
- Redacts database errors, SQL queries, filesystem paths, hostnames, ports, tokens, and technical exception names (`OperationalError`, `ValueError:`, etc.).
- Returns context-appropriate, actionable error messages for `chat`, `auth`, `document`, `course`, and `admin`.
- Preserves useful safe validation messages (e.g., minimum password length, valid email address).
- Technical detail belongs in structured server logs/telemetry, never in user-facing alerts.

## Loading states

Prefer meaningful progress/status:
- Uploading
- Processing
- Indexing
- Ready
- Failed — Retry

A simple text/icon status is enough unless the user benefits from actual progress.

## Accessibility

Required:
- keyboard navigation;
- visible focus;
- semantic labels;
- readable contrast;
- accessible validation/error messages;
- logical tab order;
- usable controls on touch screens;
- reduced motion support.

## Responsive rules

Desktop is not the only layout.

Mobile must have an intentionally designed navigation pattern and usable chat composer. Do not merely compress a multi-column desktop dashboard.

## Component discipline

Create components for repeated meaningful interaction patterns.

Do not wrap every small element in an abstraction.

Keep state ownership easy to understand.

## Visual QA checklist

Check every major route in:
- empty state;
- normal state;
- long-content state;
- error state;
- narrow/mobile viewport;
- keyboard navigation.

For chat specifically verify:
- long question;
- long answer;
- many citations;
- zero citations;
- citation opens source;
- source viewer loads actual document;
- unauthorized document access is denied;
- generation failure does not expose exception text.

## Student Home & Role-Based Navigation Architecture (Part 6B)

- **Chat is the Student Home:** `/chat` is the authoritative default home and landing workspace for authenticated students.
- **Student Dashboard Retired:** The separate student dashboard at `/dashboard` has been retired from the normal student user flow to eliminate duplication of the composer, sidebar history, and course discovery.
- **Direct `/dashboard` Routing:** When an authenticated student accesses `/dashboard`, they are automatically forwarded to `/chat`. When an authenticated administrator accesses `/dashboard`, they are served the real operational Administrator Dashboard.
- **Student Navigation Links:** Shared student navigation contains `Assistant` (`/chat`), `Courses` (`/knowledge-bases`), and `Profile` (`/profile`). No duplicate "Home" or "Dashboard" link is shown to students.
- **Safe Return Routing:** Login and auth portals validate `return_to` destinations against safe internal relative routes (`/chat`, `/knowledge-bases`, `/profile`, `/reader`, `/documents`, `/indexing`, `/dashboard`), resolving `/dashboard` to `/chat` for students.
- **Admin Dashboard Preserved:** The operational Administrator Dashboard at `/dashboard` must never be redirected to chat for administrators.

## Assistant vs. New Chat & Unified Conversation History (Part 6C)

- **Assistant is a Destination:** The `Assistant` navigation link (`/chat`) navigates to the student assistant workspace while preserving the active conversation thread when returning from other pages (Courses or Profile).
- **New Chat is an Action:** The `New Chat` button starts a fresh draft conversation, unselects any conversation, clears messages and citations, resets the composer draft, resets query scope to `ALL_COURSES`, updates browser URL, and closes the mobile drawer.
- **Single Source of Truth for History:** Conversation history is rendered exclusively in the shared left sidebar drawer (`sidebar_drawer`). The chat page (`frontend/pages/chat_page.py`) must NOT create a duplicate mobile dialog (`mobile_history_dialog`) or extra history toggle buttons.
- **Unified Mobile Drawer:** On mobile viewports (`< 1024px`), the header hamburger button opens the unified drawer containing New Chat, Assistant, Courses, Profile, and Recent Chats. Selecting an action automatically closes the drawer.
- **In-Place Reactive Refresh:** Clicking New Chat or a saved conversation while on `/chat` updates the view in-place via `state.notify()` and `history.replaceState` without a full page reload.

## Student Profile & Account Information Architecture (Part 7)

- **Account Details, Not Credentials:** The account information section is labeled "Account Details", using clean sentence-case labels (`Full Name`, `Email Address`, `Account Role`, `Portal Access`, `Account Status`). No passwords, tokens, internal IDs, or secrets are ever displayed.
- **Truthful Status Labels:** Avoid misleading security/session claims such as "Session Verified" or "Active Session" unless an authoritative backend verification check is run. Present truthful, factual labels: `● Signed in` badge and `Active` status row derived from `user.is_active`.
- **Honest 3-State Course Loading:** Course loading strictly decouples into 3 distinct states:
  1. *Populated Courses:* Preview up to 5 courses with verified document counts and "+N more courses" link to `/knowledge-bases`.
  2. *Genuine Empty State:* Honest academic empty state ("No accessible courses are currently available.") without claiming errors or zero-count bugs.
  3. *Course Request Failure:* Safely normalized error notification via `normalize_error()` explaining courses could not be loaded, with a working Retry action (never falsely claiming no courses exist).
- **Deterministic Initials & Identity:** Profile displays full name with wrapping support (`break-words`), email with break support (`break-all`), deterministic initials avatar, and role badge. Missing or long names are handled safely.
- **Comprehensive Sign-Out Reset:** Sign-out calls `api_client.logout()`, resets in-memory `AppState` (`clear_chat()`, `active_kb = None`, `reset_session_state()`), and redirects to login without deleting backend-persisted conversations.
- **Administrator Profile Integrity:** Admin profile retains operational governance summary ("Governance & Permissions", "Management Scope", "Assigned Permissions"), and direct navigation to `Manage Courses`, `Indexing Center`, and `Return to Dashboard`.

## Global Breadcrumb Removal, Avatar Visibility & Initials Rules (Part 7B)

- **No Redundant Breadcrumb Strip:** The shared layout (`frontend/components/layout.py`) must NOT render the redundant `[Back] Assistant > ...` navigation bar on normal student or administrator pages. Primary navigation belongs in the shared sidebar drawer. Content starts at a clean, natural offset (`padding: 2rem 1rem`) below the application header.
- **Genuine Navigation Preserved:** Do not remove the reader's in-document return navigation (`/reader`), sidebar navigation, or Administrator `Return to Dashboard`.
- **Visible Avatar Specification:** The profile identity card avatar must use `.bg-surface-navy` (or `.bg-primary-navy` backed by `var(--color-atlas-navy)`), `border-2 border-gold`, and `text-inverted` (`#FAF6F0`) with explicit dimensions (`w-14 h-14 sm:w-16 sm:h-16`) and flex centering. It must never rely on missing utility classes that cause white-on-white text against elevated surfaces.
- **Unified Initials Derivation:** Use `get_user_initials(full_name, email)` centrally. Always strip parenthetical role annotations (e.g. `(Student)`, `(Admin)`, `(Faculty)`), extract only alphabetical characters, handle single-word names cleanly (e.g. `Morgan` -> `MO`), and fall back safely to email prefix or `"U"`. Never allow punctuation (like `'('`) to enter avatar badges.
- **Profile Single New Chat Action (Superseded by Part 7C):** In Part 7B, New Chat was briefly consolidated into the identity card; in Part 7C, this was recognized as redundant with the global sidebar and completely removed.

## Profile Architecture & Complete Elimination of In-Page Chat Launchers (Part 7C)

- **Profile is an Account Page, Not a Chat Launcher:** The Profile page (`/profile`) must NOT render any `New Chat`, `Ask Assistant`, `Return to Assistant`, `Start Chat`, or other chat-launching action. The Profile page is exclusively an account-information and academic-catalog access page. The application shell's global left sidebar remains the sole and authoritative provider of `+ New Chat`.
- **Elimination of Duplicated Identity Cards:** Never repeat Full Name, Email Address, and Account Role in a separate "Account Details" card. All identity, portal access, and session metadata belong in the compact top identity header where each piece of data appears exactly once.
- **Content-Driven Layout (Zero Stretched Blank Cards):** Never use `flex flex-col justify-between items-stretch` across adjacent cards with unequal content height. Layouts must be content-driven to prevent empty white voids.
- **Natural Mobile Typography & Word Wrapping:** Mobile email addresses must use `[overflow-wrap:anywhere] break-words text-xs sm:text-sm` instead of unconstrained `break-all` to prevent ugly mid-word line breaks (such as `ed\nu`). Avatars and names must scale gracefully (`w-13 h-13 sm:w-16 sm:h-16`, `text-xl sm:text-2xl`).
