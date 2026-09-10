# Project Context — BCA Project RAG

## Product goal

Build a complete Retrieval-Augmented Generation application that can ingest user documents, securely process and index them, retrieve relevant evidence using strong retrieval techniques, rerank that evidence, and generate grounded answers with source citations.

The system is intended to be a serious end-to-end RAG project, not a toy chatbot.

The user wants:
- strong backend correctness and security first;
- complete implementation of the planned RAG system;
- provider-independent LLM support;
- user accounts and protected user data;
- Git/GitHub throughout development;
- a necessary but minimal frontend early so the backend can be exercised;
- a refined, elegant, human-designed frontend only after backend verification;
- no "AI-generated dashboard" appearance.

## Current project status

The user's learning/build roadmap has reached Part 95 and the last part is complete. The next objective is to build the complete application described by the roadmap/specification.

Important historical decision:
- Hybrid search is part of the retrieval architecture.
- Reranking was not previously implemented and must now be included in the final build.
- Do not interpret the earlier stopping point as the final architecture.

Because the exact text of all earlier roadmap parts may not be present in the repository, the agent MUST inspect the repository and existing project documentation before implementation. Do not invent missing project-specific behavior.

## Recommended technology baseline

### Backend
- Python
- FastAPI
- Pydantic
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- pgvector
- Redis for cache/queue coordination where useful
- Celery or another mature background-job mechanism when asynchronous processing is required

### Frontend
Recommended default:
- NiceGUI
- Python-first UI
- reusable UI components
- carefully organized frontend modules

The user does not want React because they are not familiar with React and do not want a large JavaScript/TypeScript file structure. NiceGUI is therefore the preferred frontend framework for this project.

Use NiceGUI for the user-facing application while keeping the backend architecture clean and service-oriented.

Do NOT add Django merely to provide frontend functionality. Django and FastAPI together would duplicate responsibilities and make the project harder to understand and maintain. Use FastAPI + NiceGUI unless the existing repository contains a strong architectural reason to preserve another framework.

### Storage
PostgreSQL is the authoritative application database.
pgvector is the default vector store so relational permissions, metadata and vector retrieval can share a consistent transactional system.

Object storage should be abstracted behind a storage interface. Local filesystem storage may be used for development; production deployment should be able to switch to S3-compatible storage without rewriting application logic.

### Model providers
LLM and embedding providers must be abstracted.

The application must be able to support, through adapters/configuration:
- OpenAI
- Gemini
- compatible hosted providers
- local/self-hosted models such as Llama-family models
- other compatible providers

No business logic should depend directly on one provider's SDK.

If an LLM is unavailable, the backend must fail clearly and safely rather than fabricate an answer.

## Product principles

1. Grounded answers over confident answers.
2. Source evidence must be traceable.
3. User data isolation is mandatory.
4. Backend correctness before visual polish.
5. Retrieval quality must be measurable.
6. External providers are unreliable dependencies.
7. Every important failure needs an explicit recovery path.
8. Keep architecture understandable; do not over-engineer.
9. Human-centered UI over generic AI-dashboard aesthetics.
10. Accessibility and responsive behavior are part of quality, not optional extras.

## Security baseline

The application is multi-user.

Every protected resource must be authorized for the authenticated user/tenant.

Use:
- secure password hashing such as Argon2id;
- short-lived authentication/session credentials where applicable;
- HttpOnly/Secure/SameSite cookies when cookie authentication is used;
- CSRF protection for cookie-authenticated state-changing requests;
- server-side authorization;
- strict upload validation;
- file size/count limits;
- safe temporary-file handling;
- path traversal protection;
- content-type and extension validation;
- safe document parser configuration;
- SSRF protection for any URL ingestion feature;
- rate limiting;
- security headers;
- structured audit events;
- secret management through environment/configuration;
- dependency pinning/lock files;
- safe error responses.

Do not claim that parsing a document is safe merely because its extension is PDF/DOCX/etc. Treat uploaded content as hostile input.

## Quality target

The word "perfect" means the agent must use a strict engineering quality gate, not that software can be mathematically guaranteed defect-free.

No known critical/high defect may remain at release.
