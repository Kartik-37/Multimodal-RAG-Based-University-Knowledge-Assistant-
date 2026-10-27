# Multimodal RAG-Based University Knowledge Assistant

**Application / Product Name:** RAG Assistant

A secure, production-grade Retrieval-Augmented Generation (RAG) system designed for university course knowledge and academic assistance.

> **Current Implementation Scope:** Visual PDF Evidence + Multi-Format Text RAG (PDF, DOCX, TXT, Markdown, CSV).
> **Roadmap Note:** General audio, video, web scraping, and direct CLIP pixel-vector embeddings remain deferred to future milestones. The official academic project title is preserved.

---

## 1. Project Overview

The **Multimodal RAG-Based University Knowledge Assistant** delivers grounded academic answers with precise source citations across university course materials.

### Core Architecture
- **Backend API**: Python (>= 3.11, tested on Python 3.14) with FastAPI, organized around domain services and strict security boundaries.
- **Presentation Layer**: NiceGUI (Python-first UI). API and database queries are kept strictly outside UI components.
- **Database & Vectors**: PostgreSQL 16 with `pgvector` v0.8.6 storing 1024-dimensional embeddings, document metadata, and session hashes.
- **RAG Pipeline**:
  1. *Validation & Ingestion*: Multi-format parsing (PDF, DOCX, TXT, Markdown, CSV) with safe storage keys and validation.
  2. *Hybrid Retrieval*: Combines lexical full-text search (`tsvector` with English dictionary) and vector similarity (`pgvector` cosine distance).
  3. *Fusion*: Reciprocal Rank Fusion (RRF) merging candidate results.
  4. *Reranking*: Local Hugging Face Cross-Encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) scoring relevant passages.
  5. *Context Assembly*: Hard token budget enforcement, deduplication, and source provenance tracking.
  6. *Grounded Generation*: Local Ollama service (`qwen3:4b`) producing grounded completions with citation markers (`[source_X]`).
  7. *Citation Validation*: Verifies every citation against retrieved chunk evidence.

---

## 2. Authentication & Security Architecture

1. **Framework-Independent Backend Authorization**:
   - Backend `deps.py` authenticates requests framework-independently via native HttpOnly session cookies (`session_id`) or `Authorization: Bearer` headers (for API clients/tests).
   - Zero dependency on NiceGUI internals (`nicegui.app` or `nicegui_app.storage._users`).
2. **No Raw Token Persistence in Client Storage**:
   - Raw session tokens are never persisted in NiceGUI `app.storage.user`, browser `localStorage`, or client-side JavaScript.
   - Frontend sessions survive page navigation via server-side in-memory proxy (`_session_clients`) mapped to Starlette session IDs.
3. **Source Viewer Security**:
   - Document streaming (`GET /api/v1/documents/{id}/file`) authenticates via native same-origin HttpOnly cookies.
   - Query parameter authentication (`?token=`) is strictly rejected with HTTP 401.
   - Source viewer iframe URLs never contain authentication tokens.
   - JavaScript `document.cookie` injection is strictly prohibited.
4. **Centralized User-Facing Error Sanitization**:
   - All errors reaching the UI pass through `normalize_error()` in `frontend/client/error_handler.py`.
   - Database errors, SQL syntax, filesystem paths, hostnames, ports, tokens, tracebacks, and raw Python exceptions are redacted before rendering.
5. **Role-Based Access Control (RBAC) & Student Authorization**:
   - Student course access is **strictly membership-based** (`KnowledgeBaseMember`). Students can only view documents and query courses where they are assigned members.
   - Administrators possess elevated permissions: `FACULTY_ADMIN` is scoped to assigned/created courses; `MAIN_ADMIN` possesses global authority.
6. **Production Transport**:
   - `FrontendAPIClient` does not import or use `fastapi.testclient.TestClient` in production. It uses deployment-safe `InProcessProductionTransport` or native `httpx.Client`.

---

## 3. Project Status & Roadmap

- **Phase 1: Security & Backend Correctness Hardening** — **COMPLETED & VERIFIED**.
- **Phase 2: Scope Control & Project Context Consistency** — **COMPLETED & VERIFIED**.
- **Phase 3: Test Suite Rewrite** — **COMPLETED & VERIFIED** (Contract-based frontend tests).
- **Phase 4: Frontend Rebuild from Scratch** — **COMPLETED & VERIFIED** (Restrained NiceGUI interface with Ivory `#E8E0D2`, Gold `#B89A5A`, Deep Atlas Navy `#0E1D61`).
- **Persistent Chat History** — **COMPLETED & VERIFIED** (Database-backed `Conversation` and `Message` models with tenant isolation).
- **Admin Panel Redesign (Parts 10A, 10B.1, 10B.2)** — **COMPLETED & VERIFIED** (Service Health Board, consolidated documents table, administrator course grants).
- **Phase 11A / 11A.1 / 11A.2: Multimodal RAG for Visual PDF Evidence** — **COMPLETED & CANONICALLY VERIFIED**:
  - Full lightweight scan of PDF pages, structural relevance scoring, decorative line false-positive elimination, and top candidate ranking (`VISION_MAX_PAGES_PER_DOC = 3`).
  - Pre-render scale matrix bounding (`VISION_MAX_IMAGE_PIXELS = 1536×1536`) allocating bounded Pixmaps without peak memory spikes.
  - Real local vision inference with `qwen2.5vl:3b` generating structured visual evidence (`source_modality="visual"`, `visual_type="flowchart"`).
  - Memory-safe sequential execution: vision model unloaded to preserve RAM before text embedding (`qwen3-embedding:0.6b`) and generation (`qwen3:4b`).
  - End-to-end verified live student chat path (`scripts/verify_multimodal_chat_real.py`) with hybrid retrieval, cross-encoder reranking, and grounded answers citing Page 2 visual flowchart (`#page=2&view=FitH`).
  - 46/46 unit tests passing across multimodal, citation validation, and LLM generation suites.

---

## 4. Getting Started

### Prerequisites
- Python >= 3.11 (tested on Python 3.14)
- PostgreSQL 16 with `pgvector`
- Local Ollama daemon running with `qwen3:4b` and `qwen3-embedding:0.6b`
- Vision model (optional for real vision inference): `ollama pull qwen2.5vl:3b`

### Running Automated Checks
```powershell
# Run the complete test suite (excluding external real Ollama live calls)
pytest backend/tests/ -m "not real_ollama"

# Run security hardening tests
pytest backend/tests/security/

# Run linter
ruff check .
```
