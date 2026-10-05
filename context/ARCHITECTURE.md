# Architecture — Multimodal RAG-Based University Knowledge Assistant

## High-level flow

NiceGUI frontend (Presentation Layer)
→ FrontendAPIClient (In-memory per-session transport)
→ FastAPI API layer (Framework-independent endpoints)
→ authentication/authorization (HttpOnly cookie, PostgreSQL UserSession, RBAC)
→ application services (Ingestion, Hybrid Retrieval, Generation)
→ domain logic
→ repositories / CRUD
→ PostgreSQL 16 / pgvector v0.8.6 (1024-d embeddings)
→ local Hugging Face Cross-Encoder & local Ollama (qwen3:4b)

### RAG Scope & Truthfulness

> **Current Implementation:** Production-grade **Multi-Format Text RAG** supporting PDF, DOCX, TXT, Markdown, and CSV.  
> **Roadmap Note:** Genuine **Multimodal RAG** (vision-language models, OCR pipelines, image embeddings, visual retrieval) is a planned future phase. The official academic project title is preserved.

RAG query flow:

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

## Authentication & Session Architecture

The application enforces a strict separation between the FastAPI authentication layer and the NiceGUI presentation layer:
1. **Framework-Independent Backend**:
   - `backend/app/api/deps.py` does not import or depend on NiceGUI (`nicegui.app`, `nicegui_app.storage._users`).
   - Authentication is resolved via standard `session_id` HttpOnly cookie or standard `Authorization: Bearer <token>` header.
   - Tokens in query strings (`?token=`) are strictly rejected with HTTP 401.
2. **Session Persistence & Storage**:
   - Server-side in PostgreSQL `user_sessions` table: stores SHA-256 hashed token, `user_id`, `expires_at`, and revocation status.
   - Client-side in NiceGUI: raw session tokens are **never** persisted in `app.storage.user`, `localStorage`, or client-side JavaScript.
   - Page navigation persistence: Managed via server-side in-memory proxy `_session_clients[session_id]` mapped to Starlette session ID.
3. **Session Lifecycle**:
   - Expired sessions (`expires_at < now()`) are rejected with HTTP 401.
   - Logout invokes `/api/v1/auth/logout`, marks session revoked in PostgreSQL, clears the client cookie jar, removes in-memory client, and deletes browser cookie.
   - Multiple browser sessions remain strictly isolated with independent cookie jars.

## Authorization Model & Student Access

1. **Authoritative Student Access Rule**:
   - Course access is **strictly membership-based** (`KnowledgeBaseMember`).
   - A student can only view documents, list courses, and query courses where they are an active, assigned member.
   - Unassigned courses and documents are inaccessible to students (HTTP 404/403).
2. **Administrator Scopes**:
   - `FACULTY_ADMIN`: Scoped to courses they created or belong to, with granular permissions.
   - `MAIN_ADMIN`: Global administrative authority across all courses, documents, chat scopes, and user administration.

## Error Normalization Architecture

1. **Centralized User-Facing Sanitization**:
   - `normalize_error(err, context=...)` in `frontend/client/error_handler.py` inspects all errors reaching the UI.
   - Automatically redacts:
     - SQL queries and database error names (`psycopg`, `sqlalchemy`, `OperationalError`, `IntegrityError`).
     - Connection strings, hostnames, and ports (`127.0.0.1`, `localhost`, `5432`, `11434`).
     - Internal filesystem paths (`C:\`, `D:\`, `/home/`, `/tmp/`).
     - Tokens, cookies, and bearer credentials.
     - Python runtime exceptions (`ValueError:`, `AttributeError`, `TypeError`, `Traceback`).
   - Preserves user-friendly, safe validation messages (e.g. password minimum length, valid email requirements).
2. **Internal Telemetry**:
   - Detailed stack traces and provider exceptions belong exclusively in structured server logs/telemetry, never in user-facing UI components or alert boxes.

## Source Viewer Architecture

- Documents are streamed via canonical UUID endpoint: `GET /api/v1/documents/{document_id}/file`.
- Authenticates automatically via browser's same-origin HttpOnly session cookie.
- No tokens are placed in iframe/object URLs.
- No JavaScript `document.cookie` injection is permitted.
- Server-side authorization check executes before streaming document bytes.
- Page fragments (`#page=N`) are permitted for browser jump navigation without transmitting credentials.

## Frontend Rebuild Strategy (Phase 4)

- The frontend will be rebuilt from scratch using NiceGUI.
- Current screenshot styling is audit evidence of existing defects, not a design template.
- Principles:
  - Clean typography and clear hierarchy over nested card containers.
  - Simple, restrained aesthetic without glassmorphism, decorative gradients, or animated backgrounds.
  - Motion restricted strictly to real state communication (minimal loading/progress).
  - Designed responsive behavior for desktop, tablet, and mobile.
  - Citations and grounded answers are the primary visual focus of the chat experience.
