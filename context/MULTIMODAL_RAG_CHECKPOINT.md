# Multimodal RAG Checkpoint (Phases 11A, 11A.1, 11A.2, 11A.3 & 11A.3.1)

- **Current Step:** Phase 11A.3.1 Completed — Fix Grounding Classification and Preserve Valid Step-by-Step Answers
- **Status:** COMPLETED, VERIFIED, AND FROZEN (Introductory colon sequence framing cleanly partitioned from factual assertions, list enumerations ignored during numeric verification, step-by-step educational explanations preserved in answer sanitizer while prompt echoes and precision meta-commentary are stripped, and real end-to-end chat verified with `is_grounded=True`, `status=FULLY_SUPPORTED`, `unsupported_claim_rate=0.0`, `coverage=1.0`, and RC=0 across all strict assertions).

## Checkpoint Milestones Summary

### Checkpoint A: Ollama & Model Runtime Audit
- Verified Ollama daemon running on `http://127.0.0.1:11434` (version `0.40.7`).
- Installed models verified via `ollama list`:
  - `qwen2.5vl:3b` (ID: `fb90415cde1e`, 3.2 GB) — **Installed & Verified**.
  - `qwen3-embedding:0.6b` (ID: `ac6da0dfba84`, 639 MB) — **Installed & Verified**.
  - `qwen3:4b` (ID: `359d7dd4bcda`, 2.5 GB) — **Installed & Verified**.
- Measured memory baseline: ~3.47 GB free physical RAM out of 16 GB DDR4. CPU runner `llamacpp` utilized (Intel UHD integrated graphics).

### Checkpoint B: Strict Response Validation & Synchronous Timeout
- Hardened `backend/app/services/vision/provider.py`:
  - Removed dangerous fallback `{"summary": cleaned[:500]}` that permitted malformed prose or non-JSON output to be marked as successful evidence.
  - Added strict schema validator `_validate_model_response()` ensuring response is a JSON object, `summary` is a non-empty string, `visual_type` belongs to `SUPPORTED_VISUAL_TYPES`, and lists (`visible_text`, `relationships`, `uncertainties`) contain bounded strings. Any violation returns `is_success=False`.
  - Shared validation between async `analyze_image()` and synchronous `analyze_image_sync()`.
  - Configured `ollama.Client(host=self.base_url, timeout=self.timeout)` using underlying `httpx.Timeout` to strictly bound synchronous requests to `VISION_REQUEST_TIMEOUT` (default 120s). Handled `httpx.TimeoutException` and `TimeoutError` cleanly.

### Checkpoint C: Persistence of Visual-Processing Outcomes
- In `backend/app/services/ingestion.py`:
  - Persisted non-fatal visual outcome notes (`Visual analysis complete...`, `Visual analysis partial...`, `Visual analysis skipped...`) to `Document.error_message` and `IndexingJob.error_message`.
- In `backend/app/services/indexing.py`:
  - Protected `job.error_message` in `create_or_reuse_job()` and `execute_indexing()` from being cleared if it contains a visual status note, ensuring non-fatal visual coverage metrics survive indexing to the UI and API.
  - Fatal indexing exceptions continue to populate `indexing_error` and mark the job `FAILED`.
- In `frontend/pages/documents_page.py`:
  - Visual status notes on completed documents display an informational icon instead of a red error badge, maintaining truthful semantics between text indexing success and non-fatal visual coverage notes.

### Checkpoint D: Selective Candidate Scan, Scoring, and Pre-Render Memory Safety (Phase 11A.2)
- In `backend/app/services/vision/pdf_extractor.py`:
  - **Full Document Scan:** Scans all pages in a PDF without breaking early at the cap, ensuring important later diagrams are never missed.
  - **Candidate Scoring:** Inexpensive structural scoring `_evaluate_page()` prioritizing:
    - Substantial embedded raster images (+20..50 points).
    - Scanned/sparse text with graphic structures (+35 points).
    - Visual text cues (`Figure`, `Diagram`, `Flowchart`, `Architecture`, etc.) (+25 points).
    - Significant vector drawings (+15..30 points).
  - **Decorative Line Exclusion:** Pages with dense text (> 300 chars) and 5–14 simple vector paths without visual cues or images score 0.0, eliminating false-positive vision calls on ordinary ruled lines or layout borders.
  - **Candidate Cap & Page Ordering:** Scores candidates, selects top `VISION_MAX_PAGES_PER_DOC` (default 3 for 16 GB host), and re-sorts them into natural document page order for sequential processing.
  - **Pre-Render Memory Scale Bounding:** Calculates rendering scale matrix `pymupdf.Matrix(effective_scale, effective_scale)` *before* calling `page.get_pixmap()` to guarantee total pixels do not exceed `VISION_MAX_IMAGE_PIXELS` (default 1536×1536), eliminating peak allocation spikes. Alpha is explicitly disabled (`alpha=False`).

### Checkpoint E: Real Vision Smoke Test (`scripts/verify_vision_model.py`)
- Created bounded developer verification tool generating a clean synthetic flowchart PNG (`INPUT -> PROCESS -> OUTPUT`).
- Executed live inference using real `OllamaVisionProvider` with `qwen2.5vl:3b`.
- **Result:** Success (`is_success=True`).
  - Model: `qwen2.5vl:3b` via CPU runner (`llamacpp`, 4096 context).
  - Latency: 45.86 seconds.
  - Extracted Labels: `['input', 'process', 'output']`.
  - Summary: `"A simple flowchart illustrating the process of data transformation, showing an input, a process, and an output."`

### Checkpoint F: Real End-to-End Student Chat Answer Verification (`scripts/verify_multimodal_chat_real.py`)
- Executed against isolated PostgreSQL test database (`rag_assistant_test_db`).
- Synthesized 2-page academic PDF: Page 1 (Native text overview without failover details), Page 2 (Visual flowchart diagram: `Health Monitor --(timeout)--> Failover Controller --(promotes)--> Standby Node`).
- **Authorization Verification:** Student verified to access active Course A and blocked with HTTP 404 from private Course B (zero private existence leakage).
- **Ingestion & Visual Analysis:**
  - Page 1 native text extracted without rendering.
  - Page 2 visual candidate detected and scored (score: 55.0).
  - Live `qwen2.5vl:3b` analyzed Page 2 in 84.12s, generating a structured visual section with `visual_type="flowchart"`, `source_modality="visual"`, and page number 2.
- **Memory Safety:** `qwen2.5vl:3b` stopped prior to embedding and generation, restoring available RAM.
- **Chunking & Indexing:** `qwen3-embedding:0.6b` persisted 1024-d pgvector vectors. Visual chunk #2 mapped to Page 2.
- **Full RAG Orchestration & Grounded Chat Answer:**
  - Student query: `"What is the automated failover sequence shown in the protocol diagram from Health Monitor to Standby Node?"`
  - Hybrid retrieval + cross-encoder reranker retrieved Page 2 visual evidence as Top Hit.
  - Live `qwen3:4b` generated answer referencing Health Monitor, Failover Controller, and Standby Node.
  - Returned 3 citations, including Citation [2]: Page 2, Modality: visual, Type: flowchart, Viewer URL: `/api/v1/documents/{doc_id}/file#page=2&view=FitH`.
  - All test database rows and storage artifacts cleaned up in guaranteed `finally` block.

### Checkpoint H: Refined Visual Candidate Selection & 7 Deterministic Tests (Phase 11A.3)
- In `backend/app/services/vision/pdf_extractor.py`:
  - `has_vector_evidence` requires `drawing_count >= 15` or `(drawing_count >= 2 and has_2d_shapes)` or `(drawing_count >= self.min_vector_drawings and (is_sparse or image_count > 0))`.
  - Ordinary text discussion mentioning "Figure" or "Diagram" with decorative 1D horizontal separator lines scores 0.0, eliminating false-positive candidate detection.
  - 24/24 tests in `test_multimodal_vision_extractor_and_provider.py` pass cleanly.

### Checkpoint I: Database Isolation Guard (`validate_test_database_url`)
- In `backend/app/db/session.py`:
  - Added whitelist `APPROVED_TEST_DB_NAMES = {"rag_assistant_test_db"}` and prefixes `APPROVED_TEST_DB_PREFIXES = ("test_", "rag_test_")`.
  - `validate_test_database_url()` throws `RuntimeError` immediately if any test script attempts to run against `rag_assistant_db`.
  - Added unit test in `test_production_quality_gate.py` (15/15 pass).

### Checkpoint J: Visual Intent Prioritization in Reranking
- In `backend/app/services/reranking/service.py`:
  - Added `is_visual_query()` detecting visual vocabulary (`diagram`, `flowchart`, `chart`, `figure`, `visual`, `illustration`).
  - Added `+1.5` score priority for visual candidates during CrossEncoder reranking, guaranteeing that diagrams are assigned `source_1` citation priority when queried.

### Checkpoint K: LLM Reasoning Sanitization, Sentence Splitter & Claim Verifier Hardening
- In `backend/app/services/llm/service.py`:
  - `_sanitize_llm_answer()` strips Ollama chain-of-thought scratchpads and extracts factual conclusion sentences.
  - Filtered section attribution candidates to avoid false matches on short strings like "Page 1".
- In `backend/app/services/grounding/claim_verifier.py`:
  - Stripped markdown inline list prefixes (`1. `, `2. `) from numeric checks so markdown enumeration is not falsely flagged as numeric hallucination.
- In `backend/app/services/grounding/sentence_splitter.py`:
  - Protected escaped periods in numbered list items (`1.___ESC_DOT___`).

### Checkpoint L: Real End-to-End Chat Verification (`scripts/verify_multimodal_chat_real.py`)
- Live end-to-end execution with `qwen2.5vl:3b`, `qwen3-embedding:0.6b`, and `qwen3:4b` passed with Return Code 0 across all 8 assertions:
  1. Grounding contract: `is_grounded=True, status=FULLY_SUPPORTED, citation_coverage=1.0, citation_validity_rate=1.0, unsupported_claim_rate=0.0`.
  2. Direct sequence in answer: `Health Monitor -> Failover Controller -> Standby Node`.
  3. Citation matches test document UUID.
  4. Citation points to Page 2.
  5. Citation modality is `visual`, type is `flowchart`.
  6. Source viewer URL: `/api/v1/documents/{doc_id}/file#page=2&view=FitH`.
  7. Course isolation verified (active Course A accessible, restricted Course B returns HTTP 404).
  8. Clean teardown and database restored to pristine state.

### Checkpoint M: Grounding Classification Correction & Step-by-Step Answer Preservation (Phase 11A.3.1)
- In `backend/app/services/grounding/sentence_splitter.py`:
  - Added `_INTRO_COLON_REGEX` separating introductory colon framing (`The sequence is:`, `The workflow is:`, `The steps are:`, etc.) from factual content.
  - Stripped ordinal list indicators (`Step 1:`, `1.`, `(1)`) from extracted claims so list markers do not pollute factual assertions.
  - Pure framing/preambles (`Here is a summary of the topic.`) and safe refusals remain classified as conversational.
  - Added prompt-echo and precision meta-commentary patterns to `_CONVERSATIONAL_REGEX`.
- In `backend/app/services/grounding/claim_verifier.py`:
  - `extract_numbers()` ignores list enumerations at line beginnings, after colons/semicolons, or preceded by `step \d+`, preventing list numbers from triggering numeric hallucination penalties.
- In `backend/app/services/llm/service.py`:
  - `_sanitize_llm_answer()` preserves legitimate numbered educational steps (`Step 1:`, `1.`, etc.) and sequence statements while removing `<think>` tags, source-analysis scaffolding, prompt echoes, and chain-of-thought leakage (`However, the user question specifically asks... We must be precise.`).

### Checkpoint N: Test Suite & Code Quality Verification
- **Unit Suites:**
  - `backend/tests/unit/test_multimodal_vision_extractor_and_provider.py`: 24 passed.
  - `backend/tests/unit/test_multimodal_rag_pipeline.py`: 9 passed.
  - `backend/tests/unit/test_multimodal_evaluation_dataset.py`: 8 passed.
  - `backend/tests/unit/test_production_quality_gate.py`: 15 passed.
  - `backend/tests/unit/test_reranking.py`: 21 passed.
  - `backend/tests/unit/test_llm_generation_service.py`: 11 passed.
  - `backend/tests/unit/test_sentence_splitter.py`: 9 passed.
  - `backend/tests/unit/test_claim_verifier.py`: 6 passed.
  - `backend/tests/unit/test_grounding_validation_service.py`: 10 passed.
  - `backend/tests/unit/test_citation_validator.py`: 5 passed.
  - **Total Focused Unit & Quality Gate Tests: 118/118 passed (100% pass rate).**
- **Linting & Formatting:**
  - `.\.venv\Scripts\ruff.exe check backend\app\services\grounding\ backend\app\services\llm\ scripts\verify_multimodal_chat_real.py`: All checks passed (0 errors).
  - `git diff --check`: 0 errors.

### Checkpoint O: Strict Acceptance, Repository Cleanup & Safe Archive (Phase 12A)
- **Stricter Real Chat Acceptance:**
  - `scripts/verify_multimodal_chat_real.py` enforces `grounding.status == "FULLY_SUPPORTED"`, `grounding.is_grounded is True`, `unsupported_claim_rate == 0.0`, `citation_coverage == 1.0`, `citation_validity_rate == 1.0`, and validates all claim DTOs are supported.
  - Verified live execution against `rag_assistant_test_db`: 100% full support, Page 2 visual flowchart citation, and complete sequence `Health Monitor` -> `Failover Controller` -> `Standby Node`.
- **Scratch & Disposable Cleanup:**
  - Pruned 12 disposable one-off investigation/test scripts from `scratch/`.
  - Preserved private local database backup `scratch/db_backup/rag_assistant_db_backup_20261014_123058.sql` (1.12 MB).
- **Formal Test Audit (`context/TEST_CLEANUP_MANIFEST.md`):**
  - Audited all 59 formal test files in `backend/tests/`: 0 redundant tests, 100% retained.
- **Screenshot Inventory Regeneration (`context/SCREENSHOT_CLEANUP_MANIFEST.md`):**
  - Updated inventory of all 226 files in `screenshot/` with exact dimensions, SHA256 prefixes, and reference mappings (220 Keep, 6 Archived, 0 Delete).
- **Safe Distribution Archive Generator (`scripts/create_safe_project_zip.py`):**
  - Strictly excludes `.env`, `.git/`, `storage/`, `scratch/`, `*.sql`, `bca_rag_assistant.egg-info`, `screenshot/archive/`, and runtime caches.
  - Tested via 68 tests in `backend/tests/frontend/unit/test_archive_safety_contracts.py`.
  - Built and verified `dist/RAG-Assistant-safe.zip` (639 files, 48.10 MB uncompressed, 41.42 MB compressed, 0 sensitive violations).

## Memory Policy & Operating Guidelines for 16 GB Host
- Observed peak memory when running both `qwen2.5vl:3b` (2.8 GB RAM) and `qwen3-embedding:0.6b` (1.2 GB RAM) concurrently dropped free RAM to ~379 MB.
- Unloading `qwen2.5vl:3b` via `ollama stop qwen2.5vl:3b` promptly released 2.8 GB, restoring free RAM to ~4.66 GB to ~9.2 GB.
- Recommended Windows production configuration for 16 GB RAM:
  - Process visual PDF pages sequentially.
  - Keep `VISION_MAX_PAGES_PER_DOC=3` and `VISION_RENDER_DPI=150`.
  - Set system environment variable `OLLAMA_MAX_LOADED_MODELS=1` in Windows system properties if embedding and vision models cause memory pressure during concurrent operations, allowing Ollama to swap models gracefully.

