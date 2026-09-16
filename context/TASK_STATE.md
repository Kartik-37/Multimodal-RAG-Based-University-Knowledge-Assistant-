# Task State

This file is maintained by Antigravity.

## Current phase

STEP 8 COMPLETE — LEXICAL RETRIEVAL LAYER VERIFIED

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
- [x] Authorization/isolation (COMPLETE — Step 4 Knowledge-Base Authorization & 404 Isolation)
- [x] Document lifecycle (COMPLETE — Step 5 Real Ingestion, Parsing, Chunking & Status Tracking)
- [x] Secure uploads (COMPLETE — Step 5 Magic-Byte Validation, Traversal Prevention & Size Limits)
- [x] Parsing (COMPLETE — Step 5 Real PDF, DOCX, TXT, MD, CSV Parsers with Page & Section Metadata)
- [x] Chunking (COMPLETE — Step 5 Deterministic Token Estimator & Overlap Chunker)
- [x] Embeddings (COMPLETE — Step 6 Provider Abstraction, Ollama qwen3-embedding:0.6b, 1024-dim Vector Storage in pgvector)
- [x] Vector retrieval (COMPLETE — Step 7 Exact pgvector Cosine Distance Search, Authorization & Provenance)
- [x] Lexical retrieval (COMPLETE — Step 8 PostgreSQL-Native tsvector + GIN Index + ts_rank_cd Full-Text Search)
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
- [x] Functional frontend (COMPLETE — Step 3 Presentation Shell + Step 4 RBAC + Step 5 Upload/Delete + Step 6 Indexing UI + Step 7 Vector Inspection + Step 8 Lexical Inspection)
- [ ] Frontend design pass
- [ ] Accessibility QA
- [ ] Responsive QA
- [ ] End-to-end QA
- [ ] Deployment verification
- [ ] Final security audit
- [ ] Final RAG evaluation
- [ ] Documentation
- [ ] Git/GitHub final review

## Step 8 Execution Record (Lexical Retrieval Layer)

* **Status**: COMPLETE
* **Architecture & Implemented Requirements**:
  1. **PostgreSQL-Native Lexical / Full-Text Retrieval**:
     - Accurately named and implemented as PostgreSQL-native full-text search with `ts_rank_cd` cover density ranking (explicitly avoiding calling `ts_rank_cd` BM25).
     - Generated column `searchable_text: tsvector` created via `Computed("to_tsvector('english', text)", persisted=True)` in PostgreSQL `document_chunks`.
     - High-performance GIN index `ix_document_chunks_searchable_text` implemented and verified on PostgreSQL 16.15.
     - Production Alembic migration `35fc9a73097a` applied and verified on both `rag_assistant_db` and `rag_assistant_test_db`.
  2. **Query Safety & websearch_to_tsquery**:
     - Lexical queries parsed using PostgreSQL's `websearch_to_tsquery('english', :query)`.
     - Handles plain words, quoted exact phrases (`"machine learning"`), boolean operators (`OR`, `-`), punctuation, and code symbols (`C++`, `*`, `&`, `|`, `!`, `:`) safely without SQL syntax errors or injections.
     - Stopword-only queries evaluate to empty tsquery safely and return 0 results without errors.
  3. **Safe Default Factory on Schema**:
     - `LexicalRetrievalResultItem` enforces safe default factory: `chunk_metadata: dict[str, Any] = Field(default_factory=dict)` (avoiding mutable dictionary default).
  4. **Complete Independence from Ollama & Vector Layer**:
     - Zero dependency on Ollama or vector embeddings.
     - Documents with `Document.status == DocumentStatus.COMPLETED` are fully retrievable lexically, even if `embedding IS NULL` (vector-less chunks).
     - Verified that lexical search operates flawlessly even when Ollama is offline.
  5. **Knowledge-Base Authorization & Multi-User Isolation**:
     - Enforces `get_authorized_knowledge_base` dependency on `POST /api/v1/knowledge-bases/{kb_id}/lexical-retrieve`.
     - Admin access for KB owners; student access strictly via `knowledge_base_members` membership.
     - Nonexistent or unauthorized knowledge bases return HTTP 404 (preventing existence leakage); unauthenticated requests return HTTP 401.
     - SQL query strictly scopes to `document_chunks.knowledge_base_id == kb_id` (foreign KB chunks never leak).
  6. **Data Eligibility & Deterministic Ordering**:
     - Filter: `Document.status == DocumentStatus.COMPLETED` and `searchable_text @@ query_tsquery`.
     - Order by: `rank.desc(), DocumentChunk.chunk_index.asc(), DocumentChunk.id.asc()`.
     - Duplicate text chunks remain distinguishable through unique `chunk_id` and `chunk_index`.
  7. **Frontend Presentation Layer**:
     - Added `retrieve_lexical_chunks` to `FrontendAPIClient`.
     - Added administrative "Inspect Lexical Retrieval" dialog in NiceGUI (`frontend/components/lexical_inspect.py`), accessible from `/chat` top context bar for admins.
     - Clearly labeled as "Lexical Search Results" displaying source document, page, section, lexical rank score, and snippet text.
  8. **Comprehensive Verification**:
     - 172 tests passing (40 new tests added: 27 lexical unit tests, 12 real PostgreSQL + GIN index integration tests, 1 frontend client unit test).
     - Full test suite: 172 passed, 0 failures, 0 regressions in 72.94s.
     - Ruff check passed with 0 errors across 119 files; ruff format 100% clean.
* **Next Safe Task**: Step 9: Hybrid Retrieval (Reciprocal Rank Fusion — RRF) & Reranking.

## Step 7 Execution Record (Vector Retrieval Layer)

* **Status**: COMPLETE
* **Architecture & Implemented Requirements**:
  1. **Exact PostgreSQL + pgvector Vector Search**:
     - Searches `document_chunks` using pgvector's `<=>` cosine distance operator inside PostgreSQL:
       `SELECT document_chunks, documents.original_filename, (embedding <=> :query_vector) AS distance FROM document_chunks JOIN documents ... WHERE knowledge_base_id = :kb_id AND embedding IS NOT NULL ORDER BY distance ASC, chunk_index ASC, id ASC LIMIT :top_k`.
     - Zero vector distances computed in Python; ordering and candidate selection executed purely in PostgreSQL.
     - Intentional exact search (no HNSW or ANN approximation index added yet; guarantees 100% recall for current academic corpus scale).
  2. **Query Embedding Flow**:
     - Query embedded via existing `BaseEmbeddingProvider` (`OllamaEmbeddingProvider` with `qwen3-embedding:0.6b`).
     - Strict dimension validation enforces `len(query_vector) == 1024`.
     - Pre-flight query validation rejects blank, whitespace-only, or queries exceeding 1000 characters before calling embedding service.
  3. **Score Transparency & Mathematical Conversion**:
     - Schema exposes both raw `cosine_distance` (pgvector `<=>` operator) and `similarity = 1.0 - cosine_distance`.
     - Direct mathematical conversion without silent clamping or arbitrary score inventions.
  4. **Knowledge-Base Authorization & Isolation**:
     - Enforces `get_authorized_knowledge_base` dependency on `POST /api/v1/knowledge-bases/{kb_id}/retrieve`.
     - ADMIN authorized for owned KBs; STUDENT authorized only upon explicit membership in `knowledge_base_members`.
     - Unauthorized and nonexistent KBs return HTTP 404 to avoid private existence leakage. Unauthenticated requests return HTTP 401.
     - Database query explicitly filters by `knowledge_base_id == kb_id` (foreign KB chunks never leak).
  5. **Data Eligibility & Determinism**:
     - `embedding IS NOT NULL` strictly enforced; unindexed chunks or chunks from incomplete documents are excluded.
     - Deterministic secondary tie-breaker: `chunk_index ASC, id ASC`.
     - Duplicate text chunks remain distinguishable through unique `chunk_id` and `chunk_index`.
  6. **Error Handling**:
     - 422 Unprocessable Entity for invalid parameters (`top_k < 1` or `top_k > 50`, blank query, or query > 1000 chars).
     - 503 Service Unavailable on embedding provider failure, without leaking URLs or credentials.
     - 500 Internal Server Error on database failure, without exposing raw SQL or stack traces.
  7. **Frontend Presentation Layer**:
     - Added `retrieve_chunks` to `FrontendAPIClient`.
     - Added administrative "Inspect Vector Retrieval" dialog in NiceGUI (`frontend/components/retrieval_inspect.py`), accessible from `/chat` context bar for admins.
     - Strictly labeled as "Vector Search Results" / "Retrieved Evidence" showing source document, page, section, distance, similarity, and snippet text. Does not pretend to synthesize AI answers.
  8. **Comprehensive Verification**:
     - 132 tests passing (35 new tests added: 22 unit tests, 11 real PostgreSQL + pgvector integration tests, 1 real Ollama end-to-end integration test, 1 frontend client unit test).
     - Full test suite: 132 passed, 0 failures, 0 regressions.
     - Ruff check passed with 0 errors across 112 files; ruff format 100% clean.
* **Next Safe Task**: Step 8: Lexical Retrieval (BM25 / PostgreSQL full-text search) & Hybrid Search Fusion (RRF).

## Step 6 Execution Record (Embedding and Vector Indexing Layer)

* **Status**: COMPLETE
* **Architecture & Corrections Implemented**:
  1. **Strict Separation of Ingestion & Indexing Stages**:
     - `Document.status = COMPLETED` represents successful parsing, normalization, and chunking.
     - Vector indexing is tracked separately by `Document.indexing_status: IndexingStatus` (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`).
     - Ollama availability does NOT dictate ingestion success. Documents can be uploaded and chunked even if Ollama is offline.
     - Indexing is triggered separately by the ADMIN through `POST /api/v1/knowledge-bases/{kb_id}/documents/{document_id}/index`.
     - Incomplete or interrupted indexing can be retried without re-parsing or re-chunking.
  2. **Exact pgvector Similarity Storage Foundation**:
     - Added `embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)` to `DocumentChunk`.
     - Exact cosine similarity (`<=>`) established as the authoritative foundation. HNSW indexing deferred until retrieval layer benchmarks and dataset scale warrant approximation trade-offs.
     - Migration `80d7765a9d83` created and applied to both `rag_assistant_db` and `rag_assistant_test_db`. Native pgvector function `vector_dims(embedding) == 1024` verified in PostgreSQL.
  3. **Embedding Provider Abstraction**:
     - `BaseEmbeddingProvider` defines provider-independent interface (`embed_texts`, `embed_query`, `dimension`, `model_name`).
     - `OllamaEmbeddingProvider` communicates with local Ollama (`http://localhost:11434/api/embed`) using `qwen3-embedding:0.6b` with configurable timeout, batching (default: 32), and exponential backoff retry.
  4. **Strict Vector Validation & Cardinality Verification**:
     - Enforces `len(embeddings) == len(requested_texts)`; raises `EmbeddingCountMismatchError` on any discrepancy to prevent misaligned chunk mappings.
     - Enforces `dimension == 1024`; raises `EmbeddingDimensionError` on mismatch (neither pads 1023 nor truncates 1025).
     - Rejects `NaN`, `Inf`, strings, or `None` values.
  5. **Transactional Safety & Fault Tolerance**:
     - External embedding calls to Ollama take place strictly outside PostgreSQL transactions.
     - Updating `document_chunks.embedding` and `document.indexing_status` occurs in a single atomic database transaction.
     - On failure: session rolls back; `indexing_status` is marked `FAILED` with diagnostics in `indexing_error`; 0 partial vector writes are committed; original document and chunks are preserved.
  6. **Retry Idempotency**:
     - Re-indexing updates the `embedding` column on existing `DocumentChunk` records without creating duplicate chunks or altering chunk UUIDs.
  7. **Server-Side Security & RBAC**:
     - `POST .../documents/{doc_id}/index` enforces admin permissions (`AdminKB`). Students receive 403 Forbidden.
     - Cross-tenant requests return 404 Not Found to prevent resource enumeration. Unauthenticated requests return 401.
  8. **NiceGUI Presentation Layer**:
     - Added `render_indexing_status_badge` (`VECTORS: OK`, `INDEXING...`, `INDEX FAILED`, `UNINDEXED`).
     - Added admin-only "Index" / "Retry Index" action button in document table for eligible documents (`COMPLETED` ingestion, `PENDING`/`FAILED` indexing).
     - Students receive read-only view.
  9. **Comprehensive Verification**:
     - 97 tests passing (13 embedding unit, 4 indexing unit, 7 vector integration, 1 real live Ollama integration, 72 regression tests).
     - Ruff check passed with 0 errors across 105 files; ruff format 100% clean.
* **Next Safe Task**: Step 7: Vector Retrieval Layer.

## Step 5 Execution Record (Real Document Ingestion, Parsing, Normalization & Chunking)

* **Status**: COMPLETE
* **Tests Run**: 72 tests passing.
* **Next Safe Task**: Step 6: Embedding and Vector Indexing Layer.

## Last verified

2026-09-16 — Step 8 Lexical Retrieval Layer verified with real PostgreSQL 16.15 full-text search (generated tsvector column and GIN index, websearch_to_tsquery, and ts_rank_cd cover density ranking), completely independent of Ollama and vector retrieval, 172/172 tests passing, ruff lint/format 100% clean, knowledge-base authorization and isolation enforced, safe default_factory on schemas, and administrative inspection UI hooked into presentation layer.




