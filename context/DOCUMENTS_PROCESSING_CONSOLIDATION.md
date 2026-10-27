# Documents & Processing Consolidation Specification

**Phase:** Stage 4 / Admin Part 10A & 10A.1 — Unify Documents and Indexing into One Workspace (Hardened & Verified)  
**Status:** Approved Architecture & Implementation Blueprint  
**Date:** 2026-10-22  

---

## 1. Executive Summary

Previously, administrative document management and indexing queue operations were split across two distinct destinations:
- `/documents` — Document intake (two-step sequential workspace), document directory, search, status pills, chunk inspection, source viewer, and document deletion.
- `/indexing` — Cross-course vectorization queue, job status filters (All, Active, Needs Attention, Completed), search, chunk/vector progress metrics, diagnostic error details, attempt badges, and authorized retries.

This split created fragmented workflows: administrators uploading or monitoring documents had to leave the Documents workspace to check vectorization details or retry failed jobs, and course rows in `/knowledge-bases` repeated redundant links to both destinations.

**Part 10A and Part 10A.1 consolidate both operations into a unified Documents workspace (`/documents`) with two in-page views:**
1. **Documents View (Default):** File intake, repository table, status filters, search, and inline expandable progressive disclosure for per-document stage diagnostics and authorized retry.
2. **Processing View:** The complete cross-course operational vectorization queue with live polling, status filtering, search across material/course/stage/error, diagnostic details, attempt counters, and authorized inline retry.

### Part 10A.1 Corrective Hardening:
- **Truthful Status Decision:** Replaced flawed queue status indicator with pure helper `compute_queue_status_indicator()`. When failed jobs exist (`failed_count > 0`), the indicator unambiguously displays a rose dot and `N failed job(s) need attention`. Never shows green "Queue idle & synchronized" when failures exist.
- **Polling Failure Resilience:** Replaced silent exception suppression (`except Exception: pass`) with safe logging (`logger.warning`). Polling errors preserve cached jobs without mutating their authoritative status, and truthfully update the live indicator to amber `"Sync disrupted — retrying..."`.
- **Document Refresh Cache Protection:** Implemented `fetch_all_scoped_documents(courses, fetch_fn)`. Differentiates total failure, partial failure, and success. Total failure during background polling preserves cached documents and displays an error alert with a Retry action, preventing false empty states ("No Documents Available"). Partial failure renders available documents with a warning banner.
- **Honest 100-Job History Cap & Pagination:** Endpoint `GET /knowledge-bases/indexing-jobs` now supports `limit` and `offset` query parameters. Frontend labels the view truthfully as `Recent Jobs ({total_count})` or `Recent Jobs ({total_count} cap)` with section caption `(recent 100 jobs)` instead of claiming to show `All Jobs`.
- **Mobile Responsive Tightening:** Reduced page header scale, switcher pill padding, and consolidated the queue status indicator and `Refresh Workspace` button onto a single horizontal line (`flex-nowrap`, `min-w-0`, `truncate`, `shrink-0`) to prevent unnecessary vertical stacking on 390x844 and 375x667.

---

## 2. Feature & Architectural Mapping

| Capability | Old Architecture | Consolidated Part 10A Architecture |
| :--- | :--- | :--- |
| **Workspace Route** | Split between `/documents` and `/indexing` | Primary workspace at `/documents` with in-page view switcher (`?view=documents` or `?view=processing`) |
| **Legacy Route Compatibility** | Standalone `/indexing` page | `/indexing` maintained as backward-compatible route rendering the shared Processing view |
| **Sidebar Navigation** | Redundant "Indexing" under standalone "Processing" group | Simplified: "Documents" under "Content". "Indexing" and "Processing" group removed from primary sidebar |
| **Course Row Actions** | Each course row repeated `Documents` and `Indexing` buttons | Removed duplicate `Indexing` button; `Documents` button navigates to `/documents?kb_id=...` |
| **Document Row Diagnostics** | Surface-level status only; required navigating away for failure details or retry | Progressive disclosure: inline expandable details row revealing stage, attempt #, chunk counts, sanitized error, and authorized Retry |
| **Cross-Course Processing Queue** | Only on `/indexing` | Available directly inside Documents via the "Processing" in-page tab |
| **Active Pipeline Banner** | Contained external link navigating to `/indexing` | Contextual button switching directly to the in-page "Processing" view |
| **Filter Label Visibility** | Selected navy filter pills exhibited text contrast failure (invisible navy text on navy pill) | Explicit CSS styling (`.filter-pill-selected`, `.q-btn--flat.filter-pill-selected *`) guaranteeing crisp white `#FFFFFF` text |
| **Empty State Integrity** | Backend errors could be masked as "No documents found" or "Queue idle" | Strict distinction: Loading vs Real Data vs Genuine Empty vs Request Failure with Retry action |

---

## 3. Permission Contract & Least Privilege Enforcement

| Capability | Required Permission / Role | Backend Enforcement | Frontend Enforcement |
| :--- | :--- | :--- | :--- |
| **Access Documents Workspace** | `DOCUMENT_VIEW` or `DOCUMENT_INDEX` or `DOCUMENT_INDEX_RETRY` or `MAIN_ADMIN` | API endpoint checks | `can_access_route(user, "/documents")` |
| **List Documents** | `DOCUMENT_VIEW` or `MAIN_ADMIN` | `GET /knowledge-bases/{kb_id}/documents` checks `DOCUMENT_VIEW` | Documents view requires `DOCUMENT_VIEW`. Users lacking it see an access note with a button to switch to Processing. |
| **List Indexing Jobs** | `DOCUMENT_VIEW` or `DOCUMENT_INDEX` or `DOCUMENT_INDEX_RETRY` or `MAIN_ADMIN` | `GET /knowledge-bases/indexing-jobs` checks `DOCUMENT_VIEW \| DOCUMENT_INDEX \| DOCUMENT_INDEX_RETRY` | Processing view permitted for indexers and viewers |
| **Upload Document** | `DOCUMENT_UPLOAD` or `MAIN_ADMIN` | `POST /knowledge-bases/{kb_id}/documents/upload` | Upload intake step visible only when permitted |
| **Delete Document** | `DOCUMENT_DELETE` or `MAIN_ADMIN` | `DELETE /knowledge-bases/{kb_id}/documents/{doc_id}` | Delete action rendered only when permitted |
| **Trigger Indexing** | `DOCUMENT_INDEX` or `MAIN_ADMIN` | `POST /knowledge-bases/{kb_id}/documents/{doc_id}/index` | Gated server and client side |
| **Retry Failed Indexing** | `DOCUMENT_INDEX_RETRY` or `MAIN_ADMIN` | `POST /knowledge-bases/{kb_id}/documents/{doc_id}/index/retry` | Retry action rendered only when permitted |

---

## 4. UI/UX Design System Specifications

### 4.1 In-Page View Switcher
- Placed prominently beneath the page header:
  - `Documents (N)` — showing total accessible documents count.
  - `Processing (M)` — showing active/failed job badges (amber dot for running, rose dot for failed).
- Compact, pill-based design adhering to Ivory (`#E8E0D2`), Deep Atlas Navy (`#0E1D61`), and Gold (`#B89A5A`).
- Supports URL query parameter synchronization (`?view=documents` vs `?view=processing`) to enable deep links and preserve state across browser reloads.

### 4.2 Progressive Disclosure in Documents Table
- An expand/collapse chevron button in each document row.
- When toggled, reveals a warm parchment sub-pane (`.doc-details-pane`):
  - Current processing stage (e.g. `Extracting`, `Chunking`, `Embedding`, `Verifying`).
  - Quantitative chunk progress (e.g. `12 / 12 chunks indexed`).
  - Attempt counter (`Attempt #2`).
  - Sanitized diagnostic message or failure reason (if failed).
  - Contextual `Retry` action button (if failed and `DOCUMENT_INDEX_RETRY` permitted).

### 4.3 Filter Contrast Resolution
- The blank selected-filter-label defect was caused by CSS conflict where Quasar's `.q-btn--flat.text-primary` applied `color: #0E1D61 !important` (Deep Atlas Navy) over a background of `.bg-primary-navy` (`#0E1D61`), rendering text completely invisible.
- Resolved centrally in `frontend/components/theme.py` with high-specificity selectors forcing `color: #FFFFFF !important;` on all child nodes of `.filter-pill-selected`.

---

## 5. Backward Compatibility Guarantee

1. **Route `/indexing`:**
   - Kept registered in `frontend/main.py`.
   - Renders the shared Processing view with `active_route="/indexing"` and a navigation return bar.
   - Preserves all integration tests and bookmarks without 404 or behavioral regression.
2. **Authoritative Sidebar Definition:**
   - Single source of truth in `frontend/components/layout.py`.
   - Sidebar reflects:
     - Overview (`/dashboard`)
     - Content (`Courses`, `Documents`)
     - Administration (`Administrators & Permissions`, `Activity & Audit`)
     - Operations & Tools (`System Health`, `Test Assistant`)
     - Account (`My Profile`, `Sign Out`)
