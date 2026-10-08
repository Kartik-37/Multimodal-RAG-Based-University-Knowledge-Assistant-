# FRONTEND DESIGN SYSTEM — RAG ASSISTANT
# Authoritative Visual, Interaction, and Information Architecture Contract

**Canonical Academic Project Title:** Multimodal RAG-Based University Knowledge Assistant  
**Application / Product Name:** RAG Assistant  
**Authoritative Date:** 2026-10-08  
**Design Phase:** Stage 3 — Editorial Academic & Atlas Design System  

> [!IMPORTANT]
> This document is the single authoritative source of truth for all frontend, presentation, and design decisions across the RAG Assistant application. Every future Antigravity agent MUST read and adhere strictly to this contract before proposing or writing any frontend code. No agent is permitted to choose an independent, generic SaaS, or AI-generated visual style.

---

## 1. Product Visual Identity & Design Philosophy

### The Target Aesthetic: Editorial Academic / Field Atlas
The RAG Assistant presentation layer is an **editorial academic workspace** inspired by precision university cartography, archival field notes, and classical scholarly publishing. It deliberately rejects:
- Generic SaaS dashboard templates (empty floating card grids, generic card-lift shadows).
- AI startup clichés (purple gradients, glowing blobs, glassmorphic blurs, neon borders).
- University ERP / administrative bureaucracy (dense data tables, clunky grey panels).

### Core Visual Attributes
- **Confident & Intelligent**: Clear hierarchy, purposeful surfaces, and disciplined composition.
- **Tactile & Archival**: High-contrast, warm ivory paper canvas paired with deep atlas navy and restrained antique gold rules.
- **Spacious without Emptiness**: Whitespace is deliberate breathing room for scholarly focus, not an accidental void.
- **Grounded & Verifiable**: Every claim and piece of evidence is presented with dignity and clarity.

---

## 2. Color System & Semantic Tokens

### Primary Brand Palette (The Three Anchors)
| Token Name | Hex Code | Role | Description |
| :--- | :--- | :--- | :--- |
| `--color-ivory` | `#E8E0D2` | Page Canvas / Paper Background | Warm, tactile, archival ivory. Replaces cold digital whites and dull slates. |
| `--color-atlas-navy` | `#0E1D61` | Primary Typography & Navigation | Deep, authoritative atlas navy. Maximum readability, crisp structural anchor. |
| `--color-gold` | `#B89A5A` | Accents & Semantic Embellishments | Antique academic gold. Used for fine rules, badges, focus rings, and active states. |

### Semantic Token Scale
```css
:root {
  /* Surface & Canvas Tokens */
  --bg-canvas: #E8E0D2;             /* Global page background */
  --bg-surface: #F4EFE6;            /* Primary card / workspace surface */
  --bg-surface-elevated: #FCFAF6;   /* Input fields, elevated dialogs */
  --bg-surface-subtle: #DFD7C7;     /* Secondary borders / hover fills */
  
  /* Text & Typography Tokens */
  --text-primary: #0E1D61;          /* Deep Atlas Navy: Headings, body text */
  --text-secondary: #2C3A7A;        /* Secondary reading text */
  --text-muted: #5A6594;            /* Metadata, timestamps, helper labels */
  --text-inverted: #FCFAF6;         /* Text on navy buttons or badges */
  
  /* Accent & Highlight Tokens */
  --accent-gold: #B89A5A;           /* Antique Gold: Key interactive highlights */
  --accent-gold-hover: #9E8245;     /* Darker gold for active/hover */
  --accent-gold-light: #F2E8D2;     /* Gold pill/badge fill */
  --accent-gold-border: #D1B87D;    /* Gold border rules */
  
  /* Structural Borders */
  --border-delicate: #D8CEBD;       /* Primary card and container divider */
  --border-strong: #B5A893;         /* Emphasized boundaries and inputs */
  --border-focus: #B89A5A;          /* Accessible gold focus ring */
  
  /* Status & Verification Semantics (Restrained, Academic) */
  --status-verified-bg: #EAF3EC;    /* Grounded evidence pass */
  --status-verified-text: #1B5E20;  
  --status-verified-border: #A3CFAB;
  --status-warning-bg: #FBF4E6;     /* Partially grounded / unindexed */
  --status-warning-text: #8C5800;
  --status-warning-border: #E8CA8C;
  --status-error-bg: #FBEBEB;       /* Sanitized error alert */
  --status-error-text: #8A1C1C;
  --status-error-border: #E5A4A4;
}
```

### Color Usage Rules
1. **Navy on Ivory**: All body text and primary headings must maintain high contrast (minimum 7:1 contrast ratio, surpassing WCAG AAA).
2. **Never Use Gold for Low-Contrast Text**: Gold (`#B89A5A`) is strictly prohibited as a body text color on ivory surfaces. It is reserved for borders, icons, badge borders, and button backgrounds with inverted deep navy text.
3. **No Gradient Slop**: Solid, editorial color blocking only. Never introduce purple, blue, or rainbow gradient overlays.

---

## 3. Typography & Typesetting Contract

### Primary Typeface: Modern Editorial Sans
- **Font Family**: `'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
- **Optional Scholarly Serif Accent**: `'Source Serif 4', Georgia, serif` (permitted strictly for grand display headlines or quoted manuscript excerpts).
- **Monospace Code/Data**: `'JetBrains Mono', monospace`.

### Standard Editorial Type Scale
| Role | Size | Weight | Line Height | Letter Spacing | Usage |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Display** | 36px / 2.25rem | 800 (ExtraBold) | 1.15 | -0.03em | Hero headlines, primary page titles |
| **H1** | 28px / 1.75rem | 700 (Bold) | 1.20 | -0.02em | Section titles, course library headers |
| **H2** | 22px / 1.375rem| 700 (Bold) | 1.25 | -0.01em | Card titles, assistant answer headers |
| **H3** | 18px / 1.125rem| 600 (SemiBold) | 1.30 | 0.00em | Modal headers, filter group titles |
| **Body Large** | 16px / 1.00rem | 400 (Regular) | 1.55 | 0.00em | Assistant answers, introductory copy |
| **Body Standard**| 14px / 0.875rem| 400 (Regular) | 1.50 | 0.00em | General UI text, descriptions |
| **Small / Meta** | 12px / 0.75rem | 500 (Medium) | 1.40 | +0.01em | Citations, badges, timestamps |
| **Button / Nav** | 13px / 0.8125rem| 600 (SemiBold)| 1.00 | +0.01em | Navigation items, primary action buttons |

---

## 4. Navigation Architecture

### Single Unified Student Navigation Header
- **Desktop**: A single, elegant horizontal top navigation bar anchored to the top of the viewport.
  - Brand Mark: `RAG Assistant` (with subtle gold book icon).
  - Navigation Links:
    1. **Home** (`/dashboard`)
    2. **Ask Assistant** (`/chat`)
    3. **Courses** (`/knowledge-bases`)
    4. **Profile** (`/profile`)
  - User Status & Action: Student Name, Role badge (`STUDENT`), and Sign Out action.
- **Mobile / Tablet**: Responsive collapsible menu drawer carrying the identical 4 navigation links without layout clipping or hidden controls.
- **Strictly Eliminated**:
  - No persistent left sidebar on student screens.
  - No duplicate top navbar and sidebar simultaneously.
  - No "BCA" static badge in the global navigation bar.
  - No generic breadcrumb chains ("<- Back to Dashboard / Dashboard > ...") on normal student pages. A contextual back button is allowed only in focused source inspection.

---

## 5. Student UX & Page Contracts

### A. Student Dashboard (`/dashboard`)
- **Philosophy**: An inspiring study hub that answers *"What can I learn right now?"*
- **Composition**:
  1. **Scholarly Greeting**: Personalized academic welcome with current session scope indicator.
  2. **Central Quick-Inquiry Composer**: Seamless input box with direct prompt action ("Ask across all courses").
  3. **Curated Inquiry Prompt Pills**: Clickable suggested academic inquiries that immediately jump into Chat with pre-filled questions.
  4. **Active Course Atlas**: Clean course cards displaying enrolled/available active courses with document counts and direct study actions.
  5. **No Empty Voids**: Balanced whitespace framed with delicate gold and ivory rules. No fake recent history if persistent history is not implemented.

### B. Course Library (`/knowledge-bases`)
- **Philosophy**: An academic course atlas and reference library, not a database CRUD table.
- **Composition**:
  - Real-time search filter by course code or title.
  - Clear course cards with title, description, verified material count, and two primary actions:
    - **Ask in Course**: Launches Chat scoped directly to that specific course.
    - **View Materials**: Inspects published documents and syllabus materials.

### C. Conversational Assistant (`/chat`)
- **Philosophy**: The screen itself is the assistant. No giant nested containers or cluttering scope panels.
- **Default Scope**: **`ALL_COURSES`**. Students can type a question immediately without having to pre-select a course.
- **Structure**:
  1. **Compact Scope Selector**: Subtle dropdown defaulting to `Search All Available Courses`, with optional course narrowing.
  2. **Conversation Stream**: Natural conversational bubbles with distinct editorial styling:
     - User inquiries: Clean deep navy blocks with inverted text.
     - Assistant responses: Ivory parchment surface, deep navy typography, comfortable reading line length (max 72ch).
  3. **Grounded Citations**: Prominent inline citation pills `[1]` rendered in antique gold and navy.
  4. **Bottom Composer**: Fixed or naturally anchored question input with send button and loading indicator.
  5. **Helpful Empty State**: Displays concise assistant guidance and 4 sample academic inquiry prompts.

### D. Multi-Format Source Viewer (`/components/source_viewer.py`)
- **Philosophy**: High-fidelity evidence verification without technical debug jargon.
- **Capabilities**:
  - **PDF Documents**: Inline browser rendering with `#page=N` fragment jump.
  - **Non-PDF Materials** (DOCX, TXT, MD, CSV): Clean, formatted, sanitized text preview with relevant evidence passage highlighted.
  - **Evidence Drawer**: Slide-out verification panel displaying document title, course context, page badge, and cited grounding excerpt.
  - **Security Invariant**: Strictly authenticated via same-origin HttpOnly session cookies. Never inject tokens into iframe URLs or browser JavaScript.

### E. Student Profile (`/profile`)
- **Philosophy**: Academic identity and authorized curriculum overview.
- **Content**:
  - Full Name, University Email, and Role (`STUDENT`).
  - Active Enrolled Courses catalog.
  - Account security guidelines and session sign out.
  - Zero internal PostgreSQL diagnostics, session hashes, or raw database IDs.

---

## 6. Authoritative Student Course Access Policy

```
[Student Authenticated Session]
               │
               ▼
   [Server-Side Query Filter in deps.py]
               │
               ├─► Course is active=True AND student_visible=True ────► ACCESS GRANTED (Default Catalog)
               │
               ├─► Course is active=True AND KnowledgeBaseMember exists ─► ACCESS GRANTED (Restricted Course)
               │
               └─► Course is inactive=False OR (student_visible=False AND NOT member) ──► HTTP 404 NOT FOUND
```

- **Default Availability**: Normal students have immediate access to all active, published, student-visible courses without mandatory prior manual enrollment.
- **Restricted / Private Courses**: Courses marked `is_student_visible=False` are strictly protected and require explicit `KnowledgeBaseMember` assignment.
- **Fail-Closed Protection**: Inactive courses or unauthorized private courses return HTTP 404 to prevent information leakage.
- **RAG & Retrieval Consistency**: Lexical search, vector search, hybrid fusion, reranking, and source viewing enforce this identical rule server-side.

---

## 7. Motion, Accessibility & Quality Invariants

- **Motion**: No decorative animations, pulsing logos, or hover card transforms. Transitions are restricted to 150ms subtle color shifts on interactive buttons and inputs.
- **Accessibility**:
  - Strict WCAG 2.1 AA / AAA contrast across all text elements.
  - Explicit visible focus rings (`outline: 2px solid #B89A5A; outline-offset: 2px;`) on all interactive controls.
  - Semantic HTML landmarks (`<nav>`, `<main>`, `<header>`, `<footer>`, `<dialog>`).
- **Forbidden Visual Patterns**:
  - ❌ Slate/blue generic SaaS theme remnants.
  - ❌ Purple/blue decorative gradients.
  - ❌ Glassmorphism and backdrop-filter blurs.
  - ❌ Card lift / scale hover effects (`hover:-translate-y-1`).
  - ❌ Fake persistent chat history or fake analytics cards.
  - ❌ Unsanitized raw exception strings.
