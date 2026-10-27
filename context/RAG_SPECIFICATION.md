# RAG Specification

## Objective

Build a measurable, secure RAG pipeline rather than a simple "embed chunks and ask an LLM" implementation.

## Existing pipeline

The expected core path is:
query validation/normalization
→ embedding
→ lexical retrieval
→ vector retrieval
→ hybrid fusion (RRF or justified alternative)
→ reranking
→ context assembly
→ grounded generation
→ citation validation
→ response/telemetry

Each stage must preserve authorization context.

## Multimodal requirement & current implementation scope

The official project title is **Multimodal RAG-Based University Knowledge Assistant**.

### Phase 11A & Phase 13A Visual PDF Evidence RAG (Implemented, Verified & Hardened)
Phases 11A through 13A implement genuine visual content retrieval for academic PDFs:
- **Scope constraint:** PDF visual evidence only (diagrams, flowcharts, charts, infographics, tables, scanned pages with sparse text). General audio, video, web scraping, and direct pixel-vector CLIP embeddings remain deferred to future roadmap milestones.
- **Pipeline Architecture:**
  1. **Selective Full-Document Detection:** PyMuPDF scans all document pages cheaply without early break. Evaluates structural signals: embedded raster images (+20..50), scanned/sparse text (+35), visual text cues (`Figure`, `Diagram`, `Flowchart`, `Infographic`, `Roadmap`, `Timeline`, etc.) (+25), heading cues (`List of...`, `Overview of...`, `Architecture of...`) (+25), and vector drawings (+15..30). Disregards recurring template logos by requiring large embedded images (`>= 400x400` or `>= 250,000` px) or genuine visual cues for high candidate prioritization. Excludes false positives: dense text with 5-14 simple lines and no visual cues/images, or textual mentions of "Figure" with decorative 1D horizontal dividers, score 0.0.
  2. **Page Candidate Selection & Cap:** Candidates ranked by score, capped at `VISION_MAX_PAGES_PER_DOC` (default 3 for 16 GB host), and re-sorted into document page order.
  3. **Pre-Render Memory Scale Bounding:** Pre-calculates scale matrix `pymupdf.Matrix(effective_scale, effective_scale)` *before* calling `page.get_pixmap()` to guarantee total pixels do not exceed `VISION_MAX_IMAGE_PIXELS` (default 1536×1536) prior to buffer allocation. Resolution is optimized at `VISION_RENDER_DPI = 100` (cutting vision tokens to ~1,200 and inference latency from 110s to 30s). Alpha explicitly disabled (`alpha=False`).
  4. **Vision-Language Analysis:** Local Ollama model (`qwen2.5vl:3b`) generates structured interpretation (`visual_type`, `summary`, `visible_text`, `relationships`, `uncertainties`) with prompt injection defense. Prompts explicitly demand complete itemization of all readable entries, version names, years, and categories for infographics, roadmaps, and tables. Sequential model processing unloads vision model before text embedding/generation.
  5. **Text Representation:** Structured interpretation converted to `ParsedSection` with `source_modality="visual"` and `section_title="Visual Evidence — Page N: {Type}"`.
  6. **Selective Tesseract OCR Integration:** Complements visual analysis on scanned or text-sparse pages (< 30 characters with images). Features automatic availability detection, in-memory caching, and graceful fallback when Tesseract is not installed on the host system without halting ingestion.
  7. **Indexing:** Embedded using configured 1024-d text embedding model (`qwen3-embedding:0.6b`, batch size 8) into `DocumentChunk` with visual metadata.
  8. **Retrieval & Grounded Generation:** Retrievable via dense vector, lexical, and hybrid search with cross-encoder reranking. Visual queries (detecting `diagram`, `flowchart`, `chart`, `figure`, `visual`, `infographic`, `image`, `picture`, `graphic`, `timeline`, `roadmap`) receive an automated `+1.5` score priority in CrossEncoder reranking. Full `RAGOrchestrator` generates factual answers with original-page citations. Grounding verification enriches evidence matching with document title and page metadata, verifying factual statements accurately. Citations preserve canonical `document_id`, exact 1-indexed `page_number`, `source_modality="visual"`, and `visual_type`, opening directly in source viewer at `#page=N&view=FitH`.
- **Truthful Status Policy:** If vision model is unavailable/unreachable or cap is reached, native text ingestion continues cleanly and `Document.error_message` / `IndexingJob.error_message` records truthful outcome notes (`Visual analysis complete...`, `Visual analysis partial: skipped N candidate page(s)...`, `Visual analysis skipped: Vision model (qwen2.5vl:3b) not installed/reachable`). Documents page renders info icon rather than error badge for non-fatal visual notes. No fake visual chunks or fake badges.
- **Multi-format Text Support:** Pure text PDFs and supported non-PDF formats (DOCX, TXT, Markdown, CSV) bypass visual extraction entirely.

### Authoritative student course authorization in RAG
All retrieval (lexical, vector, and hybrid) strictly enforces the authoritative course policy:
- Students can retrieve evidence and query all active, student-visible courses without prior manual enrollment.
- Restricted/private courses (`is_student_visible=False`) require explicit membership (`KnowledgeBaseMember`).
- Inactive courses are strictly excluded from all retrieval operations.
- Scoped queries (`ALL_COURSES`, `COURSE`, `DOCUMENT`) apply database-level filtering so unauthorized course chunks never leak.
- Unauthorized course queries return HTTP 404/403.

## Ingestion

Supported file types are explicit and configurable.

upload
→ `UPLOADING` (browser byte transmission)
→ `VALIDATING` (format, size, signature checks)
→ `SAVING` (safe storage and DB record creation)
→ `EXTRACTING` (parser text and structural metadata extraction)
→ `CHUNKING` (section chunking and persistence)
→ `QUEUED_FOR_INDEXING` (ingestion confirmed, vector job queued)
→ `EMBEDDING` (embedding generation for persisted chunks)
→ `WRITING_VECTORS` (`STORING_VECTORS`) (vector persistence to pgvector)
→ `VERIFYING` (count reconciliation and vector existence verification)
→ `COMPLETED` (fully ready for semantic retrieval)

Failures must persist safe diagnostics only (masked via `normalize_error()`). Incomplete data must never be marked complete.

## Parsing

Use a parser abstraction. Parsed output should preserve useful:
- text;
- pages/sections;
- headings;
- source offsets where available;
- metadata;
- non-text modality references where multimodal ingestion is enabled.

## Chunking

Chunking must be configurable and preserve:
- document ID/version;
- chunk ID;
- position;
- page/section;
- modality/source metadata where applicable.

Do not silently mix unrelated sections.

## Retrieval

### Lexical

Strong lexical retrieval with authorization filters, bounded top-k, normalized query handling, and measurable ranking.

### Vector

Use pgvector or the selected vector backend. Authorization filters must be applied before returning candidates.

### Hybrid

Fuse broad candidate sets using RRF or another justified method. Preserve lexical/vector provenance for evaluation.

### Reranking

Reranking is required. Bound candidate count, preserve authorization, use timeouts/retries appropriately, and record scores for evaluation.
- **Visual Query Prioritization:** When queries contain visual intent indicators (`diagram`, `flowchart`, `chart`, `figure`, `visual`, `illustration`, `architecture diagram`, `protocol diagram`), the CrossEncoder reranker injects a `+1.5` score priority for visual candidates (`source_modality == "visual"`), guaranteeing that visual diagram evidence is assigned `source_1` citation priority ahead of adjacent text.

## Context assembly

Use a deterministic hard budget. Preserve document/page/section/modality provenance. Remove duplicate/near-duplicate evidence where appropriate.

## Grounded generation

Retrieved content is untrusted evidence, not instructions.

The model must:
- answer from evidence;
- distinguish uncertainty;
- refuse unsupported claims;
- never invent citations;
- never reveal hidden prompts/secrets;
- never let document prompt injection override system rules;
- **answer directly and concisely by default**: provide the factual answer immediately in the first sentence without conversational filler, question repeating, or generic preambles (e.g., "Based on the provided documents...", "According to the context...");
- **reasoning deliberation sanitization & step-by-step preservation**: `_sanitize_llm_answer()` strips Ollama chain-of-thought deliberation preambles, `<think>` blocks, prompt instruction echoes, and meta-commentary (`However, the user question specifically asks... We must be precise.`), while strictly preserving legitimate numbered educational steps (`Step 1:`, `1.`, `2.`, etc.) and sequence statements;
- **grounding sentence segmentation & colon framing separation**: `_INTRO_COLON_REGEX` cleanly separates introductory colon framing (`The sequence is:`, `The workflow is:`, `The steps are:`, etc.) from factual assertions when followed by substantive text. Ordinal step indicators (`Step 1:`, `1.`) are stripped from factual claims so list numbering syntax does not contaminate factual claims;
- **claim verifier list numbering invariance**: `ClaimVerifier.extract_numbers()` ignores list item enumerations occurring at line beginnings, after colons/semicolons, or preceded by `step \d+`, ensuring markdown list enumeration syntax is never penalized as an ungrounded entity while preserving strict verification of asserted domain numbers and acronyms;
- **synthesize rather than transcribe**: synthesize retrieved evidence into a direct, focused response;
- **length calibration policy**:
  - Simple factual questions receive a direct one-sentence or short-paragraph answer;
  - Questions requiring explanation receive a direct answer followed by concise supporting points;
  - Questions explicitly requesting comprehensive explanations, step-by-step instructions, or comparisons receive the full structured detail requested;
- **preserve academic rigor**: never drop essential definitions, formulas, exceptions, conditions, or citations to achieve brevity;
- **eliminate boilerplate post-processing**: sanitize leading preamble phrases unless they express legitimate uncertainty.

## Citations

Every citation must map to a real retrieved source/chunk and preserve:
- document ID/version;
- chunk ID;
- page/section/region when available;
- relevant retrieval/rerank metadata.

Citation clicks should use canonical document IDs, not filenames as security identifiers and never raw auth tokens.

## Source viewer integration

The source viewer must request the authorized document through the authenticated application boundary.

Forbidden:
- raw main-session token in query parameter;
- JavaScript-written session cookie;
- session token in iframe/object URL.

Allowed:
- normal same-origin session cookie;
- page fragment such as `#page=N`;
- a dedicated short-lived, narrowly scoped viewer ticket when technically necessary.

## Evaluation

Track at least:
- Recall@K;
- Precision@K where labels permit;
- MRR;
- nDCG;
- hit rate;
- reranker lift;
- answer groundedness/faithfulness using a defensible evaluation method;
- citation correctness;
- stage latency;
- failure rate.

## Observability

Record safe metrics only. Do not log raw documents, secrets, access tokens, or sensitive queries by default.
