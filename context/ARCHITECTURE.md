# Architecture

## High-level flow

NiceGUI frontend
→ FastAPI API layer
→ authentication/authorization
→ application services
→ domain logic
→ repositories
→ PostgreSQL/pgvector
→ background jobs / external model providers

RAG query:

User
→ authenticated query API
→ query normalization
→ query embedding
→ lexical retrieval
→ vector retrieval
→ candidate merge
→ rank fusion
→ reranking
→ context selection
→ grounded prompt construction
→ LLM provider
→ answer + citations
→ response validation
→ persistence/observability

## Layer boundaries

### API
Responsible for:
- HTTP concerns
- request/response schemas
- authentication extraction
- status codes
- pagination
- input validation
- dependency wiring

API routes should not contain complex retrieval or database business logic.

### Application services
Responsible for use cases:
- register/login
- upload document
- process document
- search
- answer query
- manage conversations
- delete document
- reindex document

### Domain
Responsible for business invariants:
- ownership
- document lifecycle
- ingestion status
- chunk validity
- retrieval result semantics
- citation integrity

### Infrastructure
Responsible for:
- PostgreSQL
- pgvector
- Redis
- model provider adapters
- object storage
- parsers
- background workers

## Suggested modules

backend/
  app/
    api/
    core/
    db/
    models/
    schemas/
    repositories/
    services/
    rag/
      ingestion/
      retrieval/
      reranking/
      generation/
      evaluation/
    providers/
    workers/
    security/
    observability/
  tests/

Do not force this exact directory layout if the existing repository has a coherent alternative. Preserve good existing structure.

## Data model baseline

At minimum, evaluate the need for:

- User
- Session / refresh-token record
- Document
- DocumentVersion
- DocumentAccess / ownership relationship if sharing is supported
- IngestionJob
- Chunk
- Embedding
- Conversation
- Message
- RetrievalEvent
- Citation
- AuditEvent

Avoid storing duplicate data without a reason.

A document should have a clear lifecycle, for example:
UPLOADED → QUEUED → PROCESSING → INDEXED
and failure states such as:
FAILED

State transitions must be validated.

## Database rules

- migrations are authoritative;
- never manually mutate production schema;
- foreign keys and indexes must be deliberate;
- unique constraints should enforce true invariants;
- use transactions around state transitions;
- use row locking where concurrent updates can race;
- design indexes from real query patterns;
- use pgvector indexes appropriate to the chosen distance/model;
- benchmark vector indexes against the expected dataset size;
- avoid loading entire documents/chunk collections into application memory.

## Concurrency

The system must remain correct when:
- a user uploads the same file twice;
- a job is retried;
- two workers process the same document;
- a user deletes a document while processing is running;
- a query arrives while indexing is incomplete;
- an external provider times out;
- the client retries a request.

Use idempotency keys or deterministic content hashes where appropriate.

## API conventions

Use versioned APIs, e.g. `/api/v1/...`.

Responses should be consistent.
Errors should use a stable machine-readable structure.

Never return internal exception text, SQL, filesystem paths or provider secrets.

Pagination must have explicit limits.

Uploads must have explicit size limits.

## Configuration

Centralize configuration with typed settings.

Separate:
- development
- test
- production

Never hardcode secrets.

Provide `.env.example`, not `.env`.

## Deployment baseline

Provide reproducible development/deployment setup:
- Dockerfile(s)
- compose configuration where useful
- health endpoint
- readiness checks
- database migration step
- worker startup
- frontend build
- CI

Do not expose PostgreSQL/Redis publicly by default.


## NiceGUI integration

NiceGUI should remain a presentation layer, not the place for core business logic.

Preferred flow:
NiceGUI page/component
→ API/service client
→ FastAPI endpoint/service
→ domain/application layer
→ repositories/infrastructure

Do not place database queries, authorization rules, RAG orchestration, or provider-specific logic directly inside NiceGUI event handlers.

Keep the frontend modules small and discoverable:
frontend/
  pages/
  components/
  client/
  state/
  assets/

The exact names may be adapted to the existing repository.

Do not create dozens of tiny files merely for abstraction. Use a component/module when it improves reuse or clarity.
