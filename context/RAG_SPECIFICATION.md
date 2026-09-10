# RAG Specification

## Objective

Build a complete, measurable RAG pipeline rather than a simple "embed chunks and ask an LLM" implementation.

## 1. Ingestion

Supported file types must be explicit and configurable.

Pipeline:

upload
→ validation
→ safe temporary storage
→ file hashing/deduplication
→ parsing
→ text normalization
→ structural metadata extraction
→ chunking
→ metadata assignment
→ embedding
→ indexing
→ status = INDEXED

Failures must be persisted with safe diagnostic information.

### Upload security

- maximum file size
- maximum files per request
- extension allowlist
- MIME/content sniffing where appropriate
- parser timeouts/resource limits
- archive bomb protection where archives are supported
- safe filenames
- generated internal storage keys
- no user-controlled filesystem paths
- no executable upload types
- cleanup of temporary files

## 2. Parsing

Use an abstraction:

DocumentParser.parse(input) -> ParsedDocument

ParsedDocument should preserve useful structure:
- text
- page/section information when available
- headings
- source offsets where possible
- metadata

Do not make downstream retrieval depend on a single parser library.

## 3. Chunking

Chunking must be configurable.

Consider:
- target token/character length
- overlap
- semantic/structural boundaries
- headings
- page boundaries
- tables/code where supported

Every chunk must retain:
- document ID
- document version
- chunk ID
- position/order
- source metadata
- page/section information where available

Do not silently concatenate unrelated sections.

## 4. Embeddings

Embedding provider interface:

embed_texts(texts) -> vectors
embed_query(query) -> vector

Requirements:
- provider-independent adapter
- batch support
- retry policy
- timeout
- dimension validation
- model/version recorded
- deterministic configuration
- re-embedding strategy when model changes

Never insert a vector whose dimensionality does not match the configured index.

## 5. Lexical retrieval

Implement strong lexical retrieval using PostgreSQL full-text capabilities or another explicitly justified lexical engine.

The lexical retriever should:
- normalize query
- search indexed text
- return ranked candidates
- enforce authorization filters
- enforce document/version filters
- have explicit top-k

## 6. Vector retrieval

Use pgvector or another selected vector backend.

Vector search must:
- filter by authorized documents before returning candidates;
- use the configured embedding model;
- use an appropriate distance metric;
- have explicit top-k;
- expose retrieval scores internally for evaluation.

## 7. Hybrid retrieval

Combine lexical and vector candidates.

Preferred baseline:
- retrieve a reasonably broad candidate set from each retriever;
- normalize only when mathematically justified;
- use Reciprocal Rank Fusion (RRF) or another explicitly justified fusion method;
- preserve provenance: lexical/vector contribution and rank.

Do not simply add incomparable raw BM25 and cosine scores without calibration.

## 8. Reranking

Reranking is required.

Use an adapter such as:

reranker.rank(query, candidates) -> ranked candidates

The implementation must be provider/model independent.

Possible strategies:
- local cross-encoder
- hosted reranker
- lightweight fallback

The reranker must:
- have bounded candidate count;
- have timeouts;
- be measurable;
- not bypass authorization;
- preserve chunk/document IDs;
- expose scores for evaluation.

Do not run an expensive model over the entire corpus.

## 9. Context assembly

Context selection must:
- respect a hard token/character budget;
- remove duplicate/near-duplicate chunks where appropriate;
- preserve document/page/section metadata;
- avoid mixing unauthorized content;
- maintain enough surrounding context for coherence.

Use a deterministic context builder.

## 10. Grounded generation

The generation layer receives:
- user question
- selected evidence
- citation metadata
- system grounding rules

Rules:
- answer from retrieved evidence;
- distinguish supported information from uncertainty;
- do not invent citations;
- do not claim a source says something when it does not;
- if evidence is insufficient, say so;
- do not expose hidden prompts/secrets.

The LLM provider is an adapter, never hardwired into application services.

## 11. Citations

Every cited claim should map to an actual retrieved chunk/source.

Citation records should preserve:
- document ID
- document version
- chunk ID
- page/section when available
- retrieval/rerank metadata as appropriate

The API should make citations machine-readable.

## 12. Query pipeline

Recommended:

1. authenticate user
2. validate query
3. optionally normalize/rewrite query
4. create query embedding
5. lexical retrieval
6. vector retrieval
7. RRF/selected fusion
8. reranking
9. context selection
10. grounded prompt
11. generation
12. citation validation
13. response
14. metrics/audit event

If any provider fails, use an explicitly defined fallback only when it does not compromise correctness.

## 13. Evaluation

Build an evaluation harness.

Track at least:
- Recall@K
- Precision@K where labels permit
- MRR
- nDCG
- hit rate
- reranker lift
- answer faithfulness/groundedness using a defensible evaluation method
- citation correctness
- latency by pipeline stage
- failure rate

Create a small reproducible evaluation dataset.

Do not optimize retrieval based only on subjective demo quality.

## 14. RAG observability

Record safe metrics:
- query latency
- embedding latency
- lexical retrieval latency
- vector retrieval latency
- fusion latency
- reranking latency
- generation latency
- candidate counts
- selected context count
- provider/model identifiers

Do not log raw document text or sensitive user queries by default.

## 15. Caching

Cache only where correctness permits.

Potential cache targets:
- embeddings for deterministic content/model combinations
- safe provider responses where appropriate
- retrieval results only with careful authorization/model/version keys

Never allow a cache key to cause cross-user data leakage.

## 16. Deletion/reindexing

Deleting a document must remove or invalidate:
- searchable chunks
- vectors
- object storage
- related retrieval references

Reindexing must not leave two active versions unintentionally searchable.

Use versioning and transactional state changes.
