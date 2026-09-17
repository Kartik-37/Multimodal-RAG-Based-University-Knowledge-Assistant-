# Task State

This file is maintained by Antigravity.

## Current phase

STEP 13 COMPLETE — GROUNDED PROVIDER-INDEPENDENT LLM GENERATION VERIFIED

## Rules

After every meaningful implementation change:
1. update this file;
2. record what changed;
3. record tests run;
4. record failures and their status;
Antigravity must follow all instructions in `AGENTS.md`.
Non-negotiable requirements:
- Inspect before coding.
- Minimal frontend shell first.
- Complete backend and RAG pipeline before frontend redesign.
- Complete backend quality gate before frontend redesign.
- Small, composable modules.
- Server-side authorization on every document/user/tenant operation.
- No secrets committed.
- Test every component thoroughly (unit, integration, security).
- Never claim "works on my machine" as an acceptance criterion.
- Add concise, explanatory comments so the user can understand how the code works.

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
- [x] Hybrid retrieval (COMPLETE — Step 9 Dense Vector + PostgreSQL FTS fused with Reciprocal Rank Fusion)
- [x] Reranking (COMPLETE — Step 10 Local Hugging Face CrossEncoder ms-marco-MiniLM-L-6-v2)
- [x] Query processing / understanding (COMPLETE — Step 11 Deterministic Normalization, Raw/Processed Query Preservation, NFKC, Control-Char Stripping & Technical Token Preservation)
- [x] Context assembly (COMPLETE — Step 12 Deterministic Token-Budgeted Selection, Deduplication & Strict Evidence Integrity)
- [x] Grounded generation (COMPLETE — Step 13 Provider-Independent Ollama qwen3:4b, Adversarial-Resistant Prompt Architecture, Deterministic Empty-Context Fast-Path & Citation Handoff)
- [x] Citations (COMPLETE — Step 14 Deterministic Citation Syntax & Provenance Validation, Conservative Heuristic Claim Grounding, Conflict Detection & Machine-Readable Evaluation Metrics)
- [ ] Query/conversation persistence if required
- [x] Background jobs (COMPLETE — Step 5 FastAPI BackgroundTasks Ingestion & Fault-Tolerant Transitions)
- [ ] Observability
- [ ] Rate limiting
- [ ] Backend security audit
- [ ] Backend quality gate
- [x] Functional frontend (COMPLETE — Step 3 Shell + Step 4 RBAC + Step 5 Upload/Delete + Step 6 Indexing UI + Step 7 Vector UI + Step 8 Lexical UI + Step 9 Hybrid UI + Step 10 Rerank UI + Step 11 Query DTO)
- [ ] Frontend design pass
- [ ] Accessibility QA
- [ ] Responsive QA
- [ ] End-to-end QA
- [ ] Deployment verification
- [ ] Final security audit
- [ ] Final RAG evaluation
- [ ] Documentation
- [ ] Git/GitHub final review

## Step 14 Execution Record (Citation and Grounding Validation Layer)

* **Status**: COMPLETE
* **Architecture & Implemented Requirements**:
  1. **Conservative Deterministic Heuristic Grounding**:
     - Operates as a conservative deterministic heuristic validator measuring whether generated claims have evidence characteristics consistent with supplied context.
     - Does NOT claim definitive semantic entailment or real-world truth.
     - Favors `UNVERIFIABLE` rather than falsely declaring `SUPPORTED` when confidence is insufficient.
     - Known limitations clearly documented: paraphrasing with heavy synonym replacement may be missed, common vocabulary can introduce false overlap if not stopword-filtered, and entity/numerical matching is an auxiliary signal.
  2. **Independent Citation Syntax & Provenance Verification**:
     - `CitationValidator` detects standard tags (`[source_X]`) and malformed patterns (`[source_]`, `(source_1)`).
     - Resolves valid tags to exact `ContextItem` provenance (chunk UUID, document ID, title, page, section).
     - Zero citations metric rule: `citation_validity_rate` is 0.0 when `citations_found == 0` (never 1.0).
  3. **Sentence & Claim Segmentation with Protected Tokens**:
     - `SentenceSplitter` partitions answers by line breaks and sentence terminals without variable-width lookbehinds.
     - Trailing citation markers are cleanly preserved with their attributing sentence.
     - Negative guards protect abbreviations (`e.g.`, `i.e.`, `Dr.`, `vs.`), decimals (`3.14`), versions (`v1.2.3`), list prefixes (`1.`, `-`), and code spans.
     - Classifies conversational preambles/refusals so they are not evaluated as ungrounded factual assertions.
  4. **Multi-Faceted Claim Grounding & Strict Entity Invariance**:
     - `ClaimVerifier` enforces content-word recall against stopword-filtered vocabularies.
     - Strict entity & numerical invariance: claims asserting numbers (e.g. `1970` vs `1950`) or technical acronyms (e.g. `SJF` vs `FCFS`) absent from the cited source chunk are flagged as `UNSUPPORTED`.
     - Extracts the highest-overlap sentence snippet from the evidence chunk as human-auditable proof.
     - Detects uncited claims corroborated by retrieved context (`SUPPORTED_UNCITED`).
  5. **Conservative Evidence Conflict Detection**:
     - `ConflictDetector` performs pairwise comparison over bounded context items for opposing polarities (e.g. `preemptive` vs `non-preemptive`) or conflicting explicit values associated with the same technical entity.
     - Preserves source neutrality without deciding which source is correct.
  6. **Mathematically Bounded Metric Contracts**:
     - `citation_validity_rate` = `valid / found` if `found > 0` else `0.0`.
     - `citation_coverage` = `cited_claims / factual_claims` if `factual_claims > 0` else `0.0`.
     - `claim_support_rate` = `supported / factual_claims` if `factual_claims > 0` else (`1.0` if empty context refusal else `0.0`).
     - `unsupported_claim_rate` = `(unsupported + unverifiable) / factual_claims` if `factual_claims > 0` else `0.0`.
     - All metrics strictly bounded to `[0.0, 1.0]` with zero division safeguards.
  7. **Comprehensive Verification**:
     - 327 total tests passing across entire test suite (25 new tests: 24 unit tests, 1 integration test).
     - Ruff check passed with 0 errors across 169 files; ruff format 100% clean.
* **Next Safe Task**: Step 15: Quantitative RAG Evaluation Harness & Benchmarking.


## Step 13 Execution Record (Grounded Provider-Independent LLM Generation Layer)

* **Status**: COMPLETE
* **Architecture & Implemented Requirements**:
  1. **Provider-Independent Abstraction**:
     - `BaseLLMProvider` abstract contract enforces strict provider decoupling with canonical properties (`provider_name`, `model_name`) and `generate(system_instruction, user_prompt, ...)`.
     - `OllamaLLMProvider` implements local inference with `qwen3:4b` over HTTP (`/api/chat`).
     - `LLMGenerationService` depends exclusively on `BaseLLMProvider`, allowing seamless addition of future providers (OpenAI, Anthropic, Gemini, local vLLM).
  2. **Adversarial-Resistant Prompt Architecture**:
     - `GroundedPromptBuilder` enforces strict hierarchy: System Instructions > Retrieved Evidence (untrusted data) > User Question (user-controlled input).
     - Model is explicitly instructed that neither retrieved evidence nor user queries can override system grounding rules, confidentiality, or source constraints.
     - Delimiters (`=== RETRIEVED EVIDENCE (UNTRUSTED DATA) ===`, `--- BEGIN EVIDENCE [source_X] ---`, `--- END EVIDENCE [source_X] ---`) provide clean structural separation. Internal delimiter collision strings within chunks are neutralized without mutating content.
  3. **Deterministic Empty-Context Fast-Path**:
     - When `ContextAssemblyResult` has 0 items, `LLMGenerationService` immediately returns a deterministic refusal (`"I could not find any relevant information in the available documents to answer your question."`) with `is_empty_context=True` and `latency_ms=0.0` without invoking the LLM provider, guaranteeing zero hallucination.
  4. **Citation Handoff Preservation**:
     - Embeds Step 12 `source_1`, `source_2` markers into prompt evidence blocks.
     - Parses candidate referenced source tags (`[source_X]`) into `sources_referenced`.
     - Strictly delegates citation validation, factuality checking, and URL linking to Step 14.
  5. **Safe Error Handling & Diagnostic Metadata**:
     - Explicit domain exceptions: `LLMError`, `LLMProviderError`, `LLMConnectionError`, `LLMTimeoutError`, `LLMModelNotFoundError`, `LLMResponseError`.
     - Preserves only safe diagnostic metadata (`prompt_tokens`, `output_tokens`, `latency_ms`, duration metrics); strictly excludes secrets, internal paths, headers, or raw exception traces.
     - Failures never result in fabricated answers.
  6. **Comprehensive Verification**:
     - 302 total tests passing across entire test suite (23 new tests: 21 unit tests, 2 integration tests).
     - Real integration test verified live inference with local Ollama `qwen3:4b`, producing grounded completions with citation markers and validating connection error handling.
     - Ruff check passed with 0 errors across 157 files; ruff format 100% clean.
* **Next Safe Task**: Step 14: Citation Validation and Factual Grounding Evaluation.


## Step 12 Execution Record (Deterministic Context Assembly Layer)

* **Status**: COMPLETE
* **Architecture & Implemented Requirements**:
  1. **Strict Evidence Integrity**:
     - Chunk text is completely immutable during context assembly.
     - Never truncates, rewrites, summarizes, cleans, normalizes, merges, or alters chunk text or punctuation.
     - Never introduces "[TRUNCATED]" or any truncation behavior.
     - Consistent oversized candidate policy: if a candidate does not fit within the remaining token budget, it is skipped, and subsequent candidates continue to be evaluated against the remaining budget. If no candidate fits, an empty context item list is returned.
  2. **Configured Defaults without Module Import Freezing**:
     - Uses established project configuration pattern with dynamic evaluation (`default_factory=lambda: settings.MAX_CONTEXT_TOKENS` and `default_factory=lambda: settings.RAG_TOP_K_RERANK`).
     - Zero duplicate configuration variables introduced.
  3. **Preservation of Raw vs. Processed Query Distinction**:
     - Preserves `original_query` (raw user query) and `query` (Step 11 processed query) independently.
     - ContextAssembler performs zero query normalization, rewriting, expansion, or summarization.
  4. **Authorization vs. Integrity Separation**:
     - ContextAssembler is strictly an internal domain service, not an authorization or RBAC layer.
     - Validates candidate `knowledge_base_id` consistency against request `knowledge_base_id` when supplied, raising `ValueError` on cross-KB candidate contamination without performing database queries.
  5. **Token Accounting & TokenEstimator Usage**:
     - Uses existing deterministic `TokenEstimator` from `backend.app.services.chunking`.
     - Explicitly documented and tested as an estimator (`test_uses_existing_token_estimator`), making no claim of exact LLM token counts.
  6. **Deduplication & Reranker Ordering**:
     - Evaluates candidates strictly in their incoming Step 10 CrossEncoder rank order.
     - Applies two-tier deduplication: `chunk_id` tracking and exact content hash (SHA-256 of `text.strip()`).
     - Drops exact duplicates while incrementing `items_deduplicated` counter without merging partially overlapping chunks.
  7. **Full Provenance Preservation**:
     - Each selected `ContextItem` is assigned a 1-based sequential attribution identifier (`source_1`, `source_2`, ...).
     - Fully preserves document title, page number, section title, chunk metadata, reranker rank & raw float score, RRF score, and estimated tokens.
  8. **Zero Database Migrations & Zero New Dependencies**:
     - Pure in-memory domain service; no new database tables or schema changes.
     - Zero external dependencies added.
  9. **Comprehensive Verification**:
     - 279 total tests passing across entire test suite (20 new tests: 17 unit tests, 3 integration tests).
     - Unit tests verify zero text mutation, oversized candidate skipping, subsequent smaller candidate inclusion, exact budget fitting, empty result on all exceeding, deterministic repeated execution, deduplication, provenance, query preservation, and zero external network/database dependencies.
     - Integration tests verify end-to-end flow from Step 11 QueryProcessor -> Steps 7-9 Retrieval -> Step 10 CrossEncoder -> Step 12 ContextAssembler with real PostgreSQL 16.15 + pgvector.
     - Ruff check passed with 0 errors across 146 files; ruff format 100% clean.
* **Next Safe Task**: Step 13: Grounded Generation (Prompt Engineering & Ollama LLM Inference).


## Step 11 Execution Record (Deterministic Query Processing Layer)

* **Status**: COMPLETE
* **Architecture & Implemented Requirements**:
  1. **Deterministic Single Normalization Boundary**:
     - `QueryProcessor` implemented in `backend/app/services/query_processing.py` as the single, centralized, deterministic query normalization service.
     - Strips dangerous non-printable ASCII/Unicode control characters (`0x00-0x08, 0x0B-0x0C, 0x0E-0x1F, 0x7F`), preventing null-byte injection and terminal escape sequence issues.
     - Applies Unicode NFKC normalization (standardizes typographic ligatures `ﬁ` -> `fi` and full-width Latin/digit characters `ＡＢＣ` -> `ABC` while preserving composed accented characters like `café`).
     - Standardizes internal whitespace: converts `\r\n`, `\r`, `\n`, and `\t` into single spaces and collapses multiple spaces.
     - Strips leading and trailing whitespace.
  2. **Raw vs. Processed Query Preservation**:
     - Preserves the exact user query string in `original_query`.
     - Returns `processed_query` alongside `original_query` in `QueryProcessingResult`.
     - Avoids permanently destroying the user query, facilitating auditability and future evaluation.
     - Retains existing retrieval schemas (`VectorRetrievalResponse`, `LexicalRetrievalResponse`, `HybridRetrievalResponse`, `RerankResponse`) without unnecessary modification, preventing coupling.
  3. **Preservation of Technical Tokens & Meaningful Punctuation**:
     - Zero destructive regex stripping (no `re.sub(r"[^a-zA-Z0-9 ]", "", q)`).
     - Fully preserves programming languages, frameworks, database keywords, status codes, and hyphenated identifiers: `C++`, `C#`, `.NET`, `PostgreSQL`, `pgvector`, `Python 3.12`, `HTTP 401`, `BCA Sem-4`, `SELECT * FROM users`, and quoted phrases (`"machine learning"`).
     - Treats SQL and shell strings strictly as literal data without interpretation.
  4. **Strict Boundaries & Zero Semantic Rewriting**:
     - Zero LLM inference, zero synonym hallucination, zero keyword expansion, zero external network calls.
     - Stopwords are intentionally preserved (PostgreSQL lexical search handles language stopwording natively, and vector embeddings require natural syntax).
  5. **Idempotence & Diagnostic Metadata**:
     - Strictly idempotent: `process(process(q).processed_query).processed_query == process(q).processed_query`.
     - `character_count`: Processed query string length.
     - `token_estimate`: Deterministic word/punctuation count via `TokenEstimator`.
     - `has_quotes`: Diagnostic boolean for quoted phrases.
     - `has_technical_tokens`: Diagnostic boolean for technical identifiers and symbols (never alters retrieval or ranking logic).
     - Safe dictionary defaults (`Field(default_factory=dict)`).
  6. **Security & Validation**:
     - Rejects empty or whitespace-only queries with `QueryValidationError` (HTTP 422).
     - Rejects queries exceeding `settings.RETRIEVAL_MAX_QUERY_LENGTH` (1000 characters).
  7. **API Endpoint & Integration**:
     - `POST /api/v1/query/process` registered in `backend/app/api/v1/router.py` and protected by `AuthenticatedUser`.
     - Verified end-to-end integration: processed query flows smoothly through Vector (Step 7), Lexical (Step 8), Hybrid RRF (Step 9), and CrossEncoder (Step 10).
  8. **Zero Database Migrations**:
     - In-memory deterministic processing; no database schema modifications or query history tables created.
  9. **Comprehensive Verification**:
     - 259 total tests passing across entire test suite (34 new tests: 29 unit tests, 4 integration tests, 1 frontend client test).
     - Full test suite: 259 passed, 0 failures, 0 regressions in 140s.
     - Ruff check passed with 0 errors across 142 files; ruff format 100% clean.
* **Next Safe Task**: Step 12: Context Assembly and Token-Budgeted Prompt Builder.
- [ ] Grounded generation
- [ ] Citations
- [ ] Query/conversation persistence if required
- [x] Background jobs (COMPLETE — Step 5 FastAPI BackgroundTasks Ingestion & Fault-Tolerant Transitions)
- [ ] Observability
- [ ] Rate limiting
- [ ] Backend security audit
- [ ] Backend quality gate
- [x] Functional frontend (COMPLETE — Step 3 Shell + Step 4 RBAC + Step 5 Upload/Delete + Step 6 Indexing UI + Step 7 Vector UI + Step 8 Lexical UI + Step 9 Hybrid UI + Step 10 Rerank UI)
- [ ] Frontend design pass
- [ ] Accessibility QA
- [ ] Responsive QA
- [ ] End-to-end QA
- [ ] Deployment verification
- [ ] Final security audit
- [ ] Final RAG evaluation
- [ ] Documentation
- [ ] Git/GitHub final review

## Step 10 Execution Record (CrossEncoder Reranking Layer)

* **Status**: COMPLETE
* **Architecture & Implemented Requirements**:
  1. **Provider-Independent CrossEncoder Reranking**:
     - `BaseRerankerProvider` abstract contract enforces strict provider isolation.
     - `HuggingFaceCrossEncoderProvider` implements local inference using `sentence-transformers` (`cross-encoder/ms-marco-MiniLM-L-6-v2`).
     - Thread-safe lazy model loading via `threading.Lock()` ensures the model is loaded once and shared across requests.
     - Non-blocking execution via `asyncio.to_thread` keeps FastAPI's event loop unblocked during CPU inference.
     - Completely local inference; zero paid APIs or external inference services.
  2. **Raw Float Score Contract & Ordering**:
     - Raw finite CrossEncoder scores are preserved without internal rounding (`reranker_score: float`).
     - Candidates are sorted strictly by `reranker_score DESC`.
     - Deterministic tie-breaking on `(chunk_index ASC, str(chunk_id) ASC)` on equal scores.
     - Formatting to 6 decimal places is restricted strictly to presentation time in the UI (`f"{item.reranker_score:.6f}"`).
     - CrossEncoder scores are used solely for final candidate ranking; never combined or averaged with RRF or vector/lexical scores.
  3. **Preservation of Full Step 9 Provenance**:
     - Preserves all upstream fields: `chunk_id`, `document_id`, `knowledge_base_id`, `document_title`, `chunk_index`, `text`, `page_number`, `section_title`, safe `chunk_metadata` dictionary.
     - Preserves all diagnostic branch metrics: `rrf_score`, `vector_rank`, `lexical_rank`, `vector_contribution`, `lexical_contribution`, `cosine_distance`, `similarity`, and `lexical_score`.
     - Adds `reranker_score` (raw float) and `reranker_rank` (1-indexed position).
  4. **Strict Architectural Boundary**:
     - Operates strictly on hybrid candidates retrieved from Step 9 (`HybridRetrievalService.retrieve`).
     - Does NOT implement Step 11 or any of: query rewriting/expansion, context assembly, LLM generation, citations, grounding validation, or chat answer generation.
  5. **Configuration Discipline**:
     - Reuses existing `settings.RRF_K` (60), `settings.RERANKER_MODEL` (`cross-encoder/ms-marco-MiniLM-L-6-v2`), `settings.RAG_TOP_K_RETRIEVAL` (20), `settings.RAG_TOP_K_RERANK` (5), `settings.RETRIEVAL_MIN_TOP_K` (1), and `settings.RETRIEVAL_MAX_TOP_K` (50).
     - Added only `RERANK_BATCH_SIZE: int = 32`.
     - Zero duplicate configuration sources.
  6. **Zero Database Migrations**:
     - Purely computational in-memory reranking over retrieved candidate chunks. No schema changes or migrations.
  7. **Security & Authorization**:
     - Enforces `get_authorized_knowledge_base` dependency on `POST /api/v1/knowledge-bases/{kb_id}/rerank`.
     - Admins authorized for owned KBs; students authorized strictly via `knowledge_base_members`.
     - Unauthorized or nonexistent KBs return HTTP 404 (preventing existence leakage); unauthenticated requests return HTTP 401.
     - Foreign KB chunks never leak across knowledge base boundaries.
  8. **Frontend Presentation Layer**:
     - Added `RerankResultDTO` in `frontend/client/models.py`.
     - Added `rerank_chunks` method in `frontend/client/api_client.py`.
     - Created administrative inspection dialog in NiceGUI (`frontend/components/rerank_inspect.py`) labeled **"CrossEncoder Reranking Inspection"**.
     - Added "Inspect Reranking" button for administrators in the `/chat` context bar.
  9. **Comprehensive Verification**:
     - 225 total tests passing across entire test suite (30 new tests in Step 10: 21 unit tests, 1 real CrossEncoder inference integration test, 7 PostgreSQL integration tests, 1 frontend client test).
     - Full test suite: 225 passed, 0 failures, 0 regressions.
     - Real model inference verified: local load, query/text pairs, score count == candidate count, finite floats, input order mapping preserved.
     - Ruff check passed with 0 errors across 137 files; ruff format 100% clean.
* **Next Safe Task**: Step 11: Context Assembly and Prompt Formatting Pipeline.
- [ ] Context assembly
- [ ] Grounded generation
- [ ] Citations
- [ ] Query/conversation persistence if required
- [x] Background jobs (COMPLETE — Step 5 FastAPI BackgroundTasks Ingestion & Fault-Tolerant Transitions)
- [ ] Observability
- [ ] Rate limiting
- [ ] Backend security audit
- [ ] Backend quality gate
- [x] Functional frontend (COMPLETE — Step 3 Presentation Shell + Step 4 RBAC + Step 5 Upload/Delete + Step 6 Indexing UI + Step 7 Vector Inspection + Step 8 Lexical Inspection + Step 9 Hybrid Inspection)
- [ ] Frontend design pass
- [ ] Accessibility QA
- [ ] Responsive QA
- [ ] End-to-end QA
- [ ] Deployment verification
- [ ] Final security audit
- [ ] Final RAG evaluation
- [ ] Documentation
- [ ] Git/GitHub final review

## Step 9 Execution Record (Hybrid Retrieval Layer + RRF)

* **Status**: COMPLETE
* **Architecture & Implemented Requirements**:
  1. **Rank-Based Fusion via Reciprocal Rank Fusion (RRF)**:
     - Pure rank-based fusion: strictly fuses 1-based candidate rank positions. Does NOT normalize, average, or combine incompatible raw scores (cosine distance, similarity, or PostgreSQL `ts_rank_cd`).
     - Formula:
       $$RRF\_score(c) = \sum_{b \in \{\text{vector}, \text{lexical}\}} \frac{1}{\text{RRF\_K} + \text{rank}_b(c)}$$
     - Uses authoritative project configuration `settings.RRF_K` (default 60) without hardcoding or duplicate sources of truth.
  2. **Service Reuse & Zero SQL Duplication**:
     - `HybridRetrievalService` orchestrates `VectorRetrievalService` (Step 7) and `LexicalRetrievalService` (Step 8) directly.
     - Preserves all underlying database filters, parameter validations, and transactional semantics without duplicating retrieval SQL.
  3. **Candidate Deduplication & Provenance**:
     - Fuses candidates using unique `chunk_id` as the fusion key. Chunks matching in both branches are merged into a single candidate, accumulating both score contributions.
     - Preserves complete structural metadata (`chunk_id`, `document_id`, `knowledge_base_id`, `document_title`, `chunk_index`, `text`, `page_number`, `section_title`, and safe `default_factory=dict` `chunk_metadata`).
     - Preserves diagnostic metrics: `vector_rank`, `lexical_rank`, `vector_contribution`, `lexical_contribution`, `cosine_distance`, `similarity`, and `lexical_score`.
  4. **Deterministic Tie-Breaking**:
     - Sorted primarily by `rrf_score DESC`.
     - Secondary tie-breaking on `(chunk_index ASC, chunk_id ASC)` ensures deterministic ordering on equal RRF scores.
  5. **Knowledge-Base Authorization & Multi-User Isolation**:
     - Enforces `get_authorized_knowledge_base` dependency on `POST /api/v1/knowledge-bases/{kb_id}/hybrid-retrieve`.
     - Admins authorized for owned KBs; students authorized strictly via `knowledge_base_members`.
     - Unauthorized or nonexistent KBs return HTTP 404 (preventing private existence leakage); unauthenticated requests return HTTP 401.
     - Foreign KB chunks never leak across KB boundaries.
  6. **Zero Database Migrations**:
     - Operates directly on existing PostgreSQL 16 + pgvector schema and GIN index. No new migration created.
  7. **Frontend Presentation Layer**:
     - Added `HybridRetrievalResultDTO` in `frontend/client/models.py`.
     - Added `retrieve_hybrid_chunks` in `frontend/client/api_client.py`.
     - Created administrative inspection dialog in NiceGUI (`frontend/components/hybrid_inspect.py`) labeled **"Hybrid Search Inspection (RRF)"**.
     - Added "Inspect Hybrid Retrieval" button for administrators in the `/chat` context bar.
  8. **Comprehensive Verification**:
     - 195 tests passing across entire test suite (23 new tests: 12 hybrid unit tests, 10 real PostgreSQL + pgvector integration tests, 1 frontend client unit test).
     - Full test suite: 195 passed, 0 failures, 0 regressions in 81.86s.
     - Ruff check passed with 0 errors across 125 files; ruff format 100% clean.
* **Next Safe Task**: Step 10: CrossEncoder Reranking Layer (`cross-encoder/ms-marco-MiniLM-L-6-v2`).

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

2026-09-17 — Step 14 Citation and Grounding Validation Layer verified with deterministic sentence segmentation, citation syntax & ContextItem provenance resolution, conservative heuristic claim grounding with strict entity & numerical invariance, conservative evidence conflict detection, bounded quantitative metrics (citation_validity_rate, citation_coverage, claim_support_rate, unsupported_claim_rate), 327/327 tests passing across entire test suite, ruff lint/format 100% clean, and end-to-end integration verified with real Step 12 & Step 13 data contracts.





