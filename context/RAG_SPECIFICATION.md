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
However, genuine multimodal RAG (vision-language models, OCR pipelines, image embeddings, visual retrieval) is intentionally **deferred to a future roadmap phase**.

The current implemented system is **production-grade multi-format TEXT RAG** supporting:
- PDF (structured text extraction via `pypdf`)
- DOCX (text and heading extraction via `python-docx`)
- TXT (plain text with boundary checks)
- Markdown (header and block extraction)
- CSV (tabular row normalization)

Do not advertise multimodal retrieval or claim vision capabilities in the UI, API, or documentation until the non-text modality pipeline is genuinely implemented in that future phase.

### Authoritative student course authorization in RAG
All retrieval (lexical, vector, and hybrid) strictly enforces student membership:
- Students can only retrieve evidence and query courses where they are an active, assigned member (`KnowledgeBaseMember`).
- Scoped queries (`ALL_COURSES`, `COURSE`, `DOCUMENT`) apply database-level filtering so foreign course chunks never leak.
- Unassigned course queries return HTTP 404/403.

## Ingestion

Supported file types are explicit and configurable.

upload
→ validation
→ safe temporary storage
→ hashing/deduplication
→ parsing
→ normalization
→ structural metadata
→ chunking
→ metadata
→ embeddings/representations
→ indexing
→ INDEXED

Failures must persist safe diagnostics only.

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
- never let document prompt injection override system rules.

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
