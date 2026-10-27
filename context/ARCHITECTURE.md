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

> **Current Implementation (Phases 11A, 11A.1, 11A.2, 11A.3 — COMPLETED & FROZEN):** **Visual PDF Evidence + Multi-Format Text RAG**. Supports PDF visual diagrams, flowcharts, charts, and scanned pages alongside structured text from PDF, DOCX, TXT, Markdown, and CSV.
> **Visual Architecture:** PDF text + selected visual pages → PyMuPDF bounded extraction (`_evaluate_page()` scoring) → local vision-language analysis (`qwen2.5vl:3b`) → structured text representation of visual evidence → chunking and 1024-d text embedding (`qwen3-embedding:0.6b`) → pgvector hybrid retrieval → CrossEncoder reranking with `+1.5` visual query intent boost → grounded answer with `#page=N` PDF citation.
> **Roadmap Note:** Direct pixel-vector CLIP embeddings, audio, video, and general web scraping remain deferred to future milestones.

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

A document and its indexing jobs follow an explicit, verified lifecycle:
1. `UPLOADING` — Browser sends raw document bytes.
2. `VALIDATING` — Backend verifies format, size limit, and mime signature.
3. `SAVING` — File safely stored in filesystem/blob storage and persistent DB record created.
4. `EXTRACTING` — Parser extracts plain text and structural metadata.
5. `CHUNKING` — Document split into configured chunk windows and persisted.
6. `QUEUED_FOR_INDEXING` — Ingestion succeeded; persistent `IndexingJob` queued.
7. `EMBEDDING` — Dense vector representations computed for each chunk.
8. `WRITING_VECTORS` (`STORING_VECTORS`) — Generated embeddings persisted to pgvector.
9. `VERIFYING` — Vector counts validated against chunk total.
10. `COMPLETED` — Document fully indexed and ready for retrieval.
Failure state: `FAILED` (with stage-specific diagnostic explanation).

### Automatic Pipeline Orchestration
Upload automatically transitions to Ingestion (`process_document_task`).
Upon successful chunk storage, the pipeline verifies admin indexing authority (`DOCUMENT_INDEX` or `is_main`).
If authorized, `IngestionPipeline` automatically creates/primes the `IndexingJob`, signals `notify_indexing_worker()`, and dispatches `index_document_task()`.
If unauthorized, the document remains in `QUEUED_FOR_INDEXING` awaiting authorized action.
State transitions must be validated and idempotent against duplicate callbacks or race conditions.

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

## Student Entry Route & Navigation Architecture (Part 6B & 6C)

1. **Primary Student Workspace**:
   - `/chat` is the default landing workspace for authenticated students.
   - Successful student logins and registrations navigate directly to `/chat`.
   - The separate student dashboard has been retired from the student flow to eliminate functional duplication of the composer, persistent sidebar history, and Course Library.
2. **Role-Aware `/dashboard` Route**:
   - When an authenticated student accesses `/dashboard`, they are client-side forwarded to `/chat`.
   - When an authenticated administrator (`user.role == "ADMIN"`) accesses `/dashboard`, the real operational Administrator Dashboard is served.
3. **Student Navigation & History Architecture (Part 6C)**:
   - **Assistant (`/chat`)**: Workspace destination in the sidebar. Preserves active conversation history and state when returning from other pages (Courses or Profile).
   - **New Chat (`+ New Chat`)**: Unambiguous primary action in sidebar. Clears active messages and citations, unselects active conversation, clears draft, resets search scope to `ALL_COURSES`, updates browser URL, and closes mobile drawer without deleting saved conversations.
   - **Unified Conversation History**: The shared application drawer (`sidebar_drawer`) is the single source of truth for conversation history on both desktop and mobile. Duplicate chat-page mobile history dialogs and duplicate toggle buttons have been eliminated.
   - Breadcrumbs resolve to `Assistant` (`/chat`) as root for students and `Dashboard` (`/dashboard`) as root for administrators.

## Multimodal PDF Evidence Architecture (Phase 11A, 11A.1 & 11A.2)

1. **Selective Visual Candidate Detection**:
   - Native PyMuPDF parser inspects all pages cheaply without rendering or early breakout.
   - Evaluates structural signals: raster image coverage (>5%), vector drawing count/area, sparse text (<50 chars), and visual text cues (`Figure`, `Diagram`, `Flowchart`, `Architecture`, etc.).
   - Decorative line filter excludes dense text pages (>300 chars) with 5–14 simple vector paths and zero visual cues, preventing unnecessary vision processing.
   - Top candidates ranked by relevance score and capped at `VISION_MAX_PAGES_PER_DOC` (default 3), processed in page order.
2. **Pre-Render Memory Scale Bounding**:
   - Calculates target scale matrix `pymupdf.Matrix(effective_scale, effective_scale)` prior to allocating `page.get_pixmap()` to guarantee total pixels do not exceed `VISION_MAX_IMAGE_PIXELS` (default 1536×1536).
   - Alpha channel explicitly disabled (`alpha=False`). Peak memory is bounded before buffer allocation.
3. **Sequential Model Processing & Memory Safety**:
   - Single-model-at-a-time execution policy: vision model (`qwen2.5vl:3b`) unloaded before text embedding (`qwen3-embedding:0.6b`) and generation (`qwen3:4b`).
   - Recommended Windows environment variable: `OLLAMA_MAX_LOADED_MODELS=1`.
4. **Full Chat-Answer Path & Provenance Citations**:
   - Visual evidence parsed into `ParsedSection` with `source_modality="visual"` and indexed into 1024-d pgvector.
   - Hybrid retrieval and cross-encoder reranking feed visual evidence directly to `RAGOrchestrator`.
   - LLM generation cites visual evidence with exact `#page=N&view=FitH` provenance and visual modality metadata.
