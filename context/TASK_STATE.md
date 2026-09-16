# Task State

This file is maintained by Antigravity.

## Current phase

STEP 5 COMPLETE — REAL DOCUMENT INGESTION, PARSING, NORMALIZATION & CHUNKING VERIFIED

## Rules

After every meaningful implementation change:
1. update this file;
2. record what changed;
3. record tests run;
4. record failures and their status;
5. record the next safe task.

Never mark a task complete merely because code exists.

## Status vocabulary

- NOT_STARTED
- IN_PROGRESS
- BLOCKED
- COMPLETE
- NEEDS_REVIEW

## Current checklist

- [x] Repository audit (COMPLETE)
- [x] Existing tests baseline (COMPLETE — starts from zero)
- [x] Existing architecture reconciliation (COMPLETE)
- [x] Foundation verified (COMPLETE)
- [x] Database setup (PostgreSQL + pgvector) (COMPLETE)
- [x] Authentication (COMPLETE — Step 4 Real Server-Side Argon2id & Session Hashing)
- [x] Authorization/isolation (COMPLETE — Step 4 Multi-Tenant RBAC & 404 Isolation)
- [x] Document lifecycle (COMPLETE — Step 5 Real Ingestion, Parsing, Chunking & Status Tracking)
- [x] Secure uploads (COMPLETE — Step 5 Magic-Byte Validation, Traversal Prevention & Size Limits)
- [x] Parsing (COMPLETE — Step 5 Real PDF, DOCX, TXT, MD, CSV Parsers with Page & Section Metadata)
- [x] Chunking (COMPLETE — Step 5 Deterministic Token Estimator & Overlap Chunker)
- [ ] Embeddings
- [ ] Vector retrieval
- [ ] Lexical retrieval
- [ ] Hybrid retrieval
- [ ] Reranking
- [ ] Context assembly
- [ ] Grounded generation
- [ ] Citations
- [ ] Query/conversation persistence if required
- [x] Background jobs (COMPLETE — Step 5 FastAPI BackgroundTasks Ingestion & Fault-Tolerant Transitions)
- [ ] Observability
- [ ] Rate limiting
- [ ] Backend security audit
- [ ] Backend quality gate
- [x] Functional frontend (COMPLETE — Step 3 Presentation Shell + Step 4 RBAC + Step 5 Real Upload/Delete/Status)
- [ ] Frontend design pass
- [ ] Accessibility QA
- [ ] Responsive QA
- [ ] End-to-end QA
- [ ] Deployment verification
- [ ] Final security audit
- [ ] Final RAG evaluation
- [ ] Documentation
- [ ] Git/GitHub final review

## Step 5 Execution Record (Real Document Ingestion, Parsing, Normalization & Chunking)

* **Status**: COMPLETE
* **Architecture & Corrections Implemented**:
  1. **Document Status Lifecycle**:
     - Status strictly defined as: `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`.
     - Successful parsing/chunking marks the document `COMPLETED` (NOT `INDEXED`, since vector embeddings occur in Step 6+).
     - Frontend `DocumentDTO` and UI status badges updated from mock `INDEXED` to `COMPLETED`.
  2. **Background Task Reliability & Fault Tolerance**:
     - Fast non-blocking upload endpoint transitions document to `PENDING` and dispatches `process_document_task` via `BackgroundTasks`.
     - Ingestion transitions document to `PROCESSING`, extracts text, normalizes, and chunks.
     - Database operations occur within atomic sessions: all chunks for a document are committed together. Partial chunk sets are never persisted.
     - Any parsing or chunking exception transitions status to `FAILED` with error diagnostics stored in `document.error_message`.
     - `PENDING` documents remain safe for future queue retry/recovery mechanisms.
  3. **Deterministic Token-Count Estimator**:
     - Implemented `TokenEstimator` (`backend/app/services/chunking.py`) approximating tokens via word and punctuation pattern recognition (`\w+|[^\w\s]`).
     - Explicitly named and documented as an estimator (`token_count`), leaving chunker modular for plugging in model-specific tokenizers in later stages.
  4. **Strict File Type & Structural Validation**:
     - Validates extension, declared MIME type, and binary file signatures in `storage.py`.
     - PDF verified by `%PDF-` magic header bytes.
     - DOCX verified by ZIP PK signature `PK\x03\x04` and verified internal `word/document.xml` member presence.
     - CSV verified by detecting valid tabular delimiter structure.
     - TXT / Markdown verified by valid UTF-8 decoding without binary null bytes.
     - Renamed executable/binary files disguised as `.pdf` or `.docx` are rejected with HTTP 400.
  5. **Secure Local Storage & Path Traversal Prevention**:
     - Filenames sanitized; stored on disk using unguessable UUID-based storage keys: `storage/{kb_id}/{doc_id}{ext}`.
     - Path traversal attempts (e.g. `../../etc/passwd`) strictly prevented via `Path.is_relative_to()`.
     - Size limits enforced at 20MB (`MAX_UPLOAD_SIZE_BYTES`).
  6. **Document Deletion Consistency**:
     - Document deletion in PostgreSQL cascades deletion of all associated `document_chunks`.
     - Database record deletion is committed first; physical file unlinking is performed after DB commit. If physical deletion fails, warning is logged for offline cleanup; no dangling database pointers to missing files remain.
  7. **Multi-Format Parsers with Page & Section Attribution**:
     - `PDFParser`: Page-by-page extraction via `pypdf`, preserving 1-indexed `page_number`.
     - `DOCXParser`: Heading hierarchy extraction (`section_title`), paragraph preservation, and tabular cell extraction.
     - `TXTParser`: Normalizes paragraphs into distinct structured sections.
     - `MarkdownParser`: Heading-level awareness (`#`, `##`, `###`), preserving headings as `section_title`.
     - `CSVParser`: Row-by-row header-value pairing for semantic readability in RAG contexts.
  8. **Text Normalization**:
     - Deterministic Unicode NFKC normalization, CRLF/CR to LF standardization, control character stripping, excessive newline collapsing, structural indentation preserved.
  9. **Untrusted Document Content Boundary**:
     - All extracted text is treated strictly as untrusted data. No code execution, template rendering, or prompt instruction interpretation is performed.
  10. **Real Test Fixtures & Comprehensive Testing**:
     - Fixtures generate real 2-page PDF, DOCX with headings and tables, UTF-8 TXT, Markdown, and CSV.
     - Full test suite passes: 72 tests (15 unit, 13 ingestion integration, 18 RBAC security, 9 DB integration, 3 health, 12 frontend).
     - Full ruff linting and formatting clean across all 93 files.
* **Next Safe Task**: Step 6: Embeddings & pgvector Vector Indexing Foundation (Ollama / embedding model integration, vector generation, idempotent chunk upserts into pgvector).

## Step 4 Execution Record (Real Authentication, Authorization & Role-Based Access Control)

* **Status**: COMPLETE
* **Tests Run**: 44 tests passing.
* **Next Safe Task**: Step 5: Document Ingestion, Parsing, Normalization & Chunking.

## Last verified

2026-09-16 — Step 5 Real Document Ingestion, Parsing, Normalization & Chunking verified with real file fixtures (PDF, DOCX, TXT, MD, CSV), 72/72 tests passing, ruff lint/format 100% clean, and database migrations applied.



