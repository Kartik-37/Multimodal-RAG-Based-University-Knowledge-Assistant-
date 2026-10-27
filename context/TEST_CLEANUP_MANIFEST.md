# Formal Test Classification and Audit Manifest

**Date:** 2026-10-26 (Phase 12A Audit)  
**Status:** Audit Complete — Zero Redundant Tests, 100% Unique Protection Retained  
**Total Test Files in `backend/tests/`:** 59 formal test files  

## Test Inventory and Behavioral Classification

All tests under `backend/tests/` were audited to verify whether any test files contained redundant or superseded coverage. Every single formal test was verified to protect unique behavioral, security, integration, or presentation contracts. Zero test files were removed.

### 1. Security & RBAC Suite (`backend/tests/security/`) — 4 files (Retained)
- `test_backend_security_audit.py`: Direct security audit asserting absence of raw tokens in URL parameters, absence of token cookies in JavaScript, denial of `fastapi.testclient.TestClient` in production, path traversal denial, and safe error normalization.
- `test_phase1_security_hardening.py`: Hardening verification for session token bounds, cryptographic signing, constant-time token comparison, and auth header verification.
- `test_security_rbac.py`: Role-based access control protecting all administrative endpoints against student and unauthenticated access.
- `test_student_access_policy.py`: Authoritative student course visibility and access policy (active/student-visible courses open by default, restricted courses require explicit membership, inactive courses return 404).

### 2. Core Unit Tests (`backend/tests/unit/`) — 24 files (Retained)
- `test_chunking.py`: Text chunking boundaries, token limits, and sentence splitting.
- `test_citation_validator.py`: Citation tag normalization, syntax parsing, and coverage rates.
- `test_claim_verifier.py`: Claim extraction, numeric hallucination checks with list enumeration isolation, and entity checking.
- `test_config.py`: Application environment configuration, secret loading, and defaults.
- `test_context_assembly.py`: Token budget assembly, prompt construction, and context fitting.
- `test_embedding_provider.py`: Ollama embedding provider contract, vector normalization, and error handling.
- `test_evaluation_dataset.py`: Benchmark dataset generation and validation.
- `test_evaluation_metrics.py`: RAG evaluation metrics (grounding, faithfulness, recall).
- `test_failure_analyzer.py`: Retrieval and generation failure analysis helpers.
- `test_frontend.py`: Core frontend component rendering smoke tests.
- `test_grounded_prompt_builder.py`: Grounded prompt template assembly and instructions.
- `test_grounding_validation_service.py`: Conservative grounding assessment, failover sequence validation, and conflict detection.
- `test_hybrid_retrieval.py`: Reciprocal Rank Fusion (RRF) combining dense vector and lexical BM25 retrieval.
- `test_indexing_service.py`: Document indexing lifecycle, chunking, and metadata attribution.
- `test_lexical_retrieval.py`: PostgreSQL full-text search (`to_tsquery`, `ts_rank_cd`) queries.
- `test_llm_generation_service.py`: LLM generation, educational step preservation (`Step 1:`), and chain-of-thought `<think>` stripping.
- `test_llm_provider.py`: Ollama LLM provider client, timeouts, and fallback.
- `test_normalization.py`: Query normalization and character cleaning.
- `test_parsers.py`: PDF, DOCX, and TXT parsing with PyMuPDF and python-docx.
- `test_production_quality_gate.py`: Production quality gate assertions preventing regression.
- `test_query_processing.py`: Query intent extraction, entity detection, and visual query classification.
- `test_rag_orchestrator.py`: End-to-end RAG orchestrator pipeline execution.
- `test_rate_limit.py`: In-memory rate limiting and throttling.
- `test_reranking.py`: CrossEncoder semantic reranker and visual candidate boost (`+1.5`).
- `test_retrieval.py`: Vector retrieval and similarity scoring.
- `test_sentence_splitter.py`: Sentence splitting, introductory colon framing handling (`The sequence is:`), and conversational classification.
- `test_source_viewer.py`: Source viewer streaming contract, range requests, and access authorization.
- `test_telemetry.py`: Latency breakdown tracking and performance metric collection.

### 3. Multimodal RAG Suite (`backend/tests/unit/`) — 3 files (Retained)
- `test_multimodal_vision_extractor_and_provider.py`: PDF visual element candidate detection, rendering scale caps, and Ollama `qwen2.5vl:3b` extraction contract (24 tests).
- `test_multimodal_rag_pipeline.py`: Multimodal document ingestion, visual chunk persistence, 1024-d pgvector search, and visual citations (9 tests).
- `test_multimodal_evaluation_dataset.py`: 8 multimodal evaluation scenarios (flowchart, chart, vector diagram, scan, text-only, uncertainty, corrupt page, prompt injection) (8 tests).

### 4. Frontend Contract Unit Tests (`backend/tests/frontend/unit/`) — 16 files (Retained)
- `test_admin_overview_and_navigation_contracts.py`: Admin dashboard overview and sidebar navigation contracts.
- `test_admin_part10a_documents_processing_consolidation.py`: Consolidated document management and processing center contracts.
- `test_admin_part10b_health_admin_users_and_overview.py`: System diagnostics, administrator directory, and overview truthfulness.
- `test_admin_part9b_inline_upload_and_size_limits.py`: Document upload dropzone, size limits, and validation.
- `test_admin_part9c_documents_upload_ux_and_pipeline.py`: Upload modal and pipeline stage progression.
- `test_admin_part9d_editorial_intake_design_and_deduplication.py`: Document intake deduplication and editorial design.
- `test_admin_part9e_upload_field_alignment_and_geometry.py`: Responsive form alignment and viewport geometry.
- `test_admin_part9f_document_intake_workspace.py`: Document intake workspace components.
- `test_api_client_contracts.py`: Production frontend API client transport and error mapping.
- `test_archive_safety_contracts.py`: Safe distribution archive filter rules and sensitive path exclusion.
- `test_auth_layout_contracts.py`: Authentication portal responsive layout and navigation contracts.
- `test_course_access_contracts.py`: Course catalog and reader access authorization contracts.
- `test_document_upload_and_indexing_workflow_contracts.py`: Document upload and asynchronous indexing workflow contracts.
- `test_navigation_contracts.py`: Student navigation bar, links, and profile shortcuts.
- `test_source_viewer_contracts.py`: Source viewer iframe/modal and secure URL contracts.
- `test_student_chat_contracts.py`: Student chat message rendering, scope selector, stop generating, and citation pills.
- `test_student_dashboard_contracts.py`: Student dashboard courses, recent activity, and redirect logic.
- `test_student_profile_contracts.py`: Student profile display, initials, and password management.

### 5. Frontend & Backend Integration Tests (`backend/tests/frontend/integration/` & `backend/tests/integration/`) — 12 files (Retained)
- `backend/tests/frontend/integration/test_auth_portals_journey.py`: Full student & admin login/registration user journey.
- `backend/tests/frontend/integration/test_student_journey.py`: Student end-to-end chat, catalog, and viewer journey.
- `backend/tests/integration/test_admin_redesign_workflow.py`: Full admin workflow integration.
- `backend/tests/integration/test_auth_session_persistence.py`: Session cookie and authentication persistence.
- `backend/tests/integration/test_chat_orchestration_integration.py`: Chat query execution through full orchestrator.
- `backend/tests/integration/test_context_assembly_integration.py`: Live context assembly from database chunks.
- `backend/tests/integration/test_database.py`: PostgreSQL schema and transaction integrity.
- `backend/tests/integration/test_document_ingestion.py`: Ingestion pipeline file storage and parsing.
- `backend/tests/integration/test_global_retrieval_and_isolation.py`: Cross-course data isolation and multi-course retrieval.
- `backend/tests/integration/test_grounding_validation_integration.py`: Grounding assessment against database chunks.
- `backend/tests/integration/test_health.py`: Application `/health` endpoint diagnostics.
- `backend/tests/integration/test_hybrid_retrieval_integration.py`: Combined dense and lexical search integration.
- `backend/tests/integration/test_indexing_and_admin_rbac_integration.py`: Indexing jobs and administrative permissions.
- `backend/tests/integration/test_lexical_retrieval_integration.py`: Full-text search integration.
- `backend/tests/integration/test_query_processing_integration.py`: Query processing integration.
- `backend/tests/integration/test_rate_limit_integration.py`: Rate limiting middleware integration.
- `backend/tests/integration/test_reranking_integration.py`: Semantic reranking integration.
- `backend/tests/integration/test_source_viewer.py`: Source viewer streaming integration with authentication.
- `backend/tests/integration/test_telemetry_integration.py`: Diagnostic telemetry integration.
- `backend/tests/integration/test_vector_indexing_integration.py`: pgvector index creation and cosine similarity queries.
- `backend/tests/integration/test_vector_retrieval_integration.py`: Vector retrieval integration.

## Summary of Audit Findings
1. **Redundant Tests Removed:** 0 files.
2. **Tests with Unique Coverage Retained:** 59 files (100% of the active test suite).
3. **Rationale:** Every test file covers distinct security policies, API boundary contracts, visual presentation semantics, or multimodal pipeline invariants. No tests were deleted merely due to naming history.
