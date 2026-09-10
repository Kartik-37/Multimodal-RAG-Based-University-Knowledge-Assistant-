# Testing and Security Verification

## Test pyramid

### Unit tests
Test:
- validators
- domain rules
- chunking
- metadata
- fusion
- citation mapping
- context budgeting
- authorization helpers
- state transitions

### Integration tests
Test with real test infrastructure:
- database
- pgvector
- authentication
- document ingestion
- retrieval
- reranking
- generation adapters
- background jobs

### API tests
Test:
- status codes
- schemas
- auth
- authorization
- pagination
- invalid inputs
- upload limits
- errors

### End-to-end tests
At least cover:
1. register
2. login
3. upload document
4. document processes
5. document becomes searchable
6. query
7. answer contains valid citations
8. another user cannot access the document

## Security tests

Explicitly test:
- IDOR/BOLA
- cross-user retrieval leakage
- cross-user mutation
- path traversal
- malicious filenames
- oversized uploads
- malformed documents
- rate limiting
- invalid tokens
- expired/revoked sessions
- CSRF if applicable
- SSRF if URL ingestion exists
- prompt injection handling
- sensitive data leakage through errors/logs
- cache isolation

## Prompt injection

Treat retrieved documents as untrusted content.

A document may contain instructions such as:
"ignore previous instructions."

The system must treat those as document content, not system instructions.

The model must not:
- reveal secrets
- reveal hidden prompts
- execute document instructions
- bypass access control

## RAG evaluation tests

Maintain known query/evidence pairs.

Test:
- retrieval recall
- hybrid retrieval
- reranker ordering
- citation correctness
- insufficient-evidence behavior

## Regression gate

A change to retrieval must not be accepted solely because a demo looks better.

Run the evaluation suite and compare metrics.

## Performance tests

Measure:
- ingestion throughput
- embedding throughput
- retrieval latency
- reranking latency
- end-to-end latency

Set practical thresholds after establishing baseline measurements.

## Final security review

Before release:
- inspect dependency vulnerabilities
- inspect secrets
- inspect auth flows
- inspect authorization queries
- inspect upload handling
- inspect CORS/CSRF
- inspect security headers
- inspect rate limits
- inspect logging
- inspect production settings
