# BCA Project RAG

A production-oriented Retrieval-Augmented Generation application.

## Important

Start with `AGENTS.md`.

Antigravity must read the context files before implementation.

## Development order

1. Audit existing repository.
2. Create/verify minimal frontend shell.
3. Build and verify the complete backend.
4. Run the strict backend quality/security gate.
5. Complete and polish the frontend.
6. Run whole-system QA.
7. Commit cleanly and keep GitHub CI green.

## Technology baseline

Backend: Python + FastAPI. Django is intentionally not part of the baseline stack. Django is intentionally not part of the baseline stack.

Database: PostgreSQL + pgvector.

Frontend: NiceGUI (Python-first). Do not introduce React unless the user explicitly changes this decision.

LLMs/embeddings/rerankers: provider-independent adapters.

## Git

Git and GitHub are required.

Never commit secrets or local sensitive data.

## What "complete" means

The application must include the complete RAG pipeline:
ingestion → parsing → chunking → embeddings → lexical retrieval → vector retrieval → hybrid fusion → reranking → context assembly → grounded generation → citations → evaluation.

It must also provide secure multi-user access and production-quality failure handling.
