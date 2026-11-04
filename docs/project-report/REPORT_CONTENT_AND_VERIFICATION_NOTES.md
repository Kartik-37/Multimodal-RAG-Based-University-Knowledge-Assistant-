# RAG Assistant — Project Report Content & Verification Notes

**Document Status:** Audit & Verification Record  
**Target Submission:** BCA Major / Minor Project Report (`2025-2026`)  
**Department:** School of Computing, Kaushalya The Skill University, Ahmedabad  
**Official Academic Title:** *Multimodal RAG-Based University Knowledge Assistant*  
**Application Name:** RAG Assistant  
**Date of Verification:** November 4, 2026  

---

## 1. Project Snapshot & Git Provenance

- **Repository Root:** `d:\Kartik\RAG-Assistant-Step21E`
- **Current Git Commit:** `deaceec` (`Wed Nov 4 14:11:44 2026 +0530`)
- **Commit Message:** `feat(rag): generalize RAG answer pipeline, relevance gating, retry budget, and citation deduplication (Phase 27)`
- **Authoritative Operational Phase:** **Phase 27** (Generalized Academic RAG Pipeline, Relevance Gating, Shared Retry Budget, Separation of Deliberation & Clean Synthesis).
- **Previous Milestones Integrated:** Phase 26 (Canned Answer Retirement), Phase 25 (Student Chat Scoping), Phase 24 (Admin Overview & Directives), Phase 22 (RAG Benchmarking), Phase 21E (Frontend Modernization & RBAC Hardening), Phases 11A–11A.3 (Visual Evidence Grounding).

---

## 2. Report Document Inventory & Structure

The complete BCA Project Report has been generated in two synchronized formats in `docs/project-report/`:
1. `RAG_Assistant_Project_Report_Draft.docx` — Fully styled, editable Microsoft Word document strictly adhering to Kaushalya The Skill University (KSU) Part-1 and Part-2 formatting guidelines.
2. `RAG_Assistant_Project_Report_Draft.pdf` — High-fidelity PDF exported directly via Microsoft Word COM automation (`16.0`) with identical page layout and pagination.
3. `rendered_pages/` — 46 rendered 150-DPI visual proof images (`page_01.png` through `page_46.png`) used for automated and manual visual quality assurance.

### Structural Summary
- **Total Physical Pages:** 46
- **Front Matter Pages (Section 1 — Unnumbered):** 4 pages (Cover Page, University Certificate, Company Certificate, Company Profile).
- **Preliminary Pages (Section 2 — Roman `v` to `x`):** 6 pages (Acknowledgement `v`, Abstract `vi`, Table of Contents `vii`–`viii`, List of Figures `ix`, List of Tables `x`).
- **Main Report Chapters (Section 3 — Arabic `1` to `36`):** 36 pages (Chapters 1 to 6 and References).
- **Chapter Count:** 6 full chapters + References.
- **Figure Count:** 16 figures (1 timeline chart, 6 system design diagrams, 9 high-resolution genuine application screenshots).
- **Table Count:** 17 tables (2 requirements tables, 10 database schema tables, 3 hardware/software stack tables, 2 testing summary tables).
- **References Count:** 12 peer-reviewed academic papers, books, and authoritative first-party technical documentation entries.
- **Abstract Word Count:** 217 words (Strictly compliant with KSU template ceiling of 350 words; formatted in Times New Roman 12 pt, italic, justified, 1.5 line spacing).

---

## 3. Inspected Repository Artifacts & Evidence Base

The report content was derived strictly from code inspection, configuration analysis, test execution records, and actual application UI states:

### Architecture & Backend Services
- `backend/app/main.py`: Application lifespan, route registration, CORS, middleware.
- `backend/app/core/config.py`: Environment configuration, token budgets, model definitions (`qwen3:4b`, `qwen3-embedding:0.6b`, `qwen2.5vl:3b`).
- `backend/app/api/deps.py`: Server-side session verification, bearer token extraction, role validation (framework-independent, zero NiceGUI storage leaks).
- `backend/app/services/ingestion/`: Multi-format parsers (`pypdf`, `python-docx`, text, markdown, CSV), SHA-256 deduplication, 500-token chunking.
- `backend/app/services/embedding/`: 1024-dimensional Ollama embedding provider, dimensional validation, batching.
- `backend/app/services/retrieval/`: Dual-stage hybrid retrieval, PostgreSQL `tsvector` + GIN lexical search, `pgvector` HNSW cosine similarity, Reciprocal Rank Fusion ($k=60$), Sentence-Transformers Cross-Encoder (`ms-marco-MiniLM-L-6-v2`) reranking.
- `backend/app/services/llm/`: Grounded prompt engineering (`Directive 8`), Ollama provider integration, native deliberation separation, conservative preamble stripping.
- `backend/app/services/grounding/`: Overlap verification, citation mapping to canonical document UUIDs and physical page numbers.

### Database Models & Migrations
- `backend/app/models/`: SQLAlchemy 2.0 ORM declarations for `users`, `user_sessions`, `knowledge_bases`, `knowledge_base_members`, `documents`, `document_chunks`, `indexing_jobs`, `conversations`, `chat_messages`, `rate_limit_entries`.
- `backend/alembic/versions/`: Verified migration history confirming table structures, indexes (HNSW for vectors, GIN for tsvectors), and foreign key constraints.

### Presentation & Frontend (NiceGUI 3.16.0)
- `frontend/client/chat_page.py`: ChatGPT-style left sidebar layout, active conversation management, real-time generation termination ("Stop Generating").
- `frontend/client/composer.py`: Course scope selection popover, instant live course filtering (`ALL_COURSES` vs `COURSE`).
- `frontend/client/citations.py`: Grouped document citation cards with clickable page chips.
- `frontend/client/reader_page.py`: Dedicated `/reader` workspace with native browser PDF streaming, `#page=N` jump navigation, and collapsible evidence grounding drawer.
- `frontend/client/admin_pages.py`: Administrative dashboard, course catalog visibility management, document indexing status, system health telemetry.

---

## 4. Test Verification & Empirical Quality Gates

The implementation's reliability and security boundaries were verified against the repository's test suites and live execution logs:

1. **Backend Unit Test Baseline:**
   - **518 Unit Tests Passed (100% pass rate, 0 failures)** across chunking, normalization, parsers, token budgeting, prompt construction, grounding validation, sentence splitting, citation resolution, and rate limiting.
2. **Frontend Unit Contracts (`backend/tests/frontend/unit/`):**
   - **93 Passed, 0 Failed (100%)** covering API client resilience, role navigation boundaries, scope persistence, and reader route contracts.
3. **Security Hardening Suite (`backend/tests/security/`):**
   - **30 Total Tests (13 passed offline, 17 live-db/env dependent skipped, 0 failures)** verifying zero token leakage in URLs (`?token=`), absence of browser-JS accessible session secrets, HttpOnly cookie enforcement, and centralized error sanitization (`normalize_error()`).
4. **Live Ollama & pgvector Benchmark Suite (`screenshot/phase27_live_ollama_results.json`):**
   - Live execution verified against local Ollama (`qwen3:4b`) and PostgreSQL 16:
     - `What is Flutter?`: Full explanatory synthesis in natural prose from `[source_1]` (Page 18) with `llm_invoked=True`, `provider_calls=1`, `retry_occurred=False`.
     - `What is a widget in Flutter?`: High-precision explanation from `[source_1]` (Page 34) without canned Python text or hardcoded category descriptions.
     - `What is the name of this Act?`: Correct factual synthesis of *"Kaushalya the Skill University Act 2021"* from `[source_5]` with 100% `FULLY_SUPPORTED` grounding.
     - Out-of-Scope Control: Generic refusal without hallucination or fake citations for non-syllabus topics.

---

## 5. Metadata Placeholders Requiring Student & Guide Confirmation

In strict compliance with academic honesty instructions, no student identities, enrollment numbers, guide designations, or corporate profiles were fabricated. The following placeholders are explicitly formatted in brackets in the DOCX/PDF and require student input prior to binding:

| Placeholder in Report | Location | Required Value / Action |
| :--- | :--- | :--- |
| `[ENTER STUDENT FULL NAME]` | Cover, Certificate, Ack. | Student's official enrolled full name. |
| `[ENTER ENROLMENT NUMBER]` | Cover, Certificate, Ack. | Student's university registration / enrollment number. |
| `[CONFIRM PROJECT GUIDE NAME]` | Cover, Certificate, Ack. | Official name of assigned faculty project guide. |
| `[CONFIRM DATE]` | Certificate Page | Date of formal project evaluation / viva. |
| `Company Certificate Required` | Page 3 | If external apprenticeship was completed, replace placeholder with company certificate; otherwise retain academic in-house N/A statement. |
| `Company Profile Required` | Page 4 | If external company was involved, enter company profile; otherwise retain academic in-house N/A statement. |

---

## 6. Academic Originality & Similarity Check Status

- **Student Requested Target:** Below 8% similarity (`<8%`).
- **Institutional Reality & Tool Access:**
  - Official Turnitin and iThenticate similarity detection tools are licensed exclusively at the institutional university level (via university library / department coordinator accounts).
  - No public or unauthorized third-party plagiarism websites were used to upload the student's project report, preventing repository leakage or unauthorized commercial archiving.
  - **Status:** **Similarity check not executed in this local engineering environment.** The student must submit the draft report through the authorized Kaushalya The Skill University Turnitin coordinator / faculty guide account.
- **Originality Engineering Safeguards Implemented:**
  - Zero patchwriting or text-spinning: All technical explanations of RAG, vector retrieval, RRF, Cross-Encoder reranking, and Ollama synthesis were authored from scratch based on primary architectural design and original research papers.
  - Every external algorithm, equation, and framework is explicitly attributed via numbered citations `[1]` through `[12]` in Chapter 1, Chapter 3, and Chapter 4, mapping to peer-reviewed citations in References.
  - Template sample content (e.g., sample Networth test cases, template guidelines, generic login table) was completely eradicated.
  - Scope boundaries are stated with complete academic truthfulness: Visual PDF evidence and multi-format text RAG are documented as completed; arbitrary video/audio processing and CLIP pixel embeddings are explicitly disclaimed as future work.
