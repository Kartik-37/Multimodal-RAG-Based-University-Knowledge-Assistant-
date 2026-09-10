# Backend Rules

## Security

### Authentication
- Hash passwords with Argon2id or an equally strong password KDF.
- Never store plaintext passwords.
- Never place long-lived secrets in browser-accessible storage.
- Rotate/revoke sessions/tokens.
- Apply login rate limits.
- Use generic authentication failure messages.

### Authorization
Authorization is checked on every protected resource.

Never do:
`Document.objects.get(id=document_id)`

without an ownership/authorization constraint.

Prefer the equivalent of:
`get authorized document for current user`

Ownership must be enforced in the database query/service layer, not merely in the UI.

### Multi-user isolation

Test explicitly that:
- User A cannot read User B's document.
- User A cannot retrieve User B's chunks through search.
- User A cannot infer private document metadata through counts/errors.
- User A cannot mutate User B's data by changing IDs.
- background jobs retain ownership context safely.

### Input validation

Validate:
- query length
- pagination
- sort/filter values
- UUIDs/IDs
- upload sizes
- filenames
- metadata
- provider configuration

Reject malformed input early.

### SSRF

If URL ingestion exists:
- allow only explicitly supported URL schemes;
- reject localhost/private/link-local/reserved addresses;
- resolve DNS safely;
- re-check redirects;
- limit response size;
- use strict timeouts;
- prevent access to cloud metadata endpoints.

If URL ingestion is not required, do not add it.

### File safety

Never use an uploaded filename as a filesystem path.

Use generated IDs and controlled storage directories.

### SQL/data safety

- parameterized queries/ORM;
- no raw SQL string interpolation;
- transactions for stateful workflows;
- constraints for invariants.

### API safety

- explicit request/response schemas;
- bounded payloads;
- consistent error responses;
- no debug mode in production;
- no stack traces to clients.

## Reliability

Every external dependency gets:
- timeout
- bounded retry
- clear failure state
- structured logging
- circuit/fallback strategy when appropriate

Retries must not duplicate writes.

## Transactions

Use transactions for workflows such as:
- create document + ingestion job
- state transition + related records
- deletion
- reindex activation

Use row locks where concurrent workers could produce conflicting state.

## Background jobs

Jobs must be:
- idempotent
- retry-safe
- observable
- bounded
- cancellable where practical

Never trust client-side job completion claims.

## Performance

Watch for:
- N+1 queries
- missing indexes
- loading all chunks
- oversized context
- sequential embedding requests
- unbounded file parsing
- expensive reranking candidate counts

Use profiling/measurement before premature optimization.

## Dependency management

Pin/lock dependencies.

Review security advisories.

Do not install packages merely because an AI model suggested them.

## Logging

Use structured logs.

Never log:
- passwords
- auth headers
- API keys
- access tokens
- private document contents
- full sensitive queries by default

## Health

Provide separate:
- liveness
- readiness

Readiness should reflect required dependencies.

Do not expose detailed infrastructure diagnostics publicly.

## API documentation

Document:
- authentication
- request/response schemas
- errors
- pagination
- upload behavior
- search behavior
- citations
- rate limits where relevant


## Code comments and documentation

The user is learning the project and wants comments that explain code without creating noise.

Add comments when they explain:
- why a security decision exists;
- why a non-obvious algorithm is used;
- how a RAG stage affects downstream retrieval/generation;
- why a transaction/lock/retry is necessary;
- why a workaround exists;
- what a configuration setting changes;
- any non-obvious provider/library behavior.

Prefer comments that explain WHY and important project impact, not comments that merely repeat WHAT the code says.

Use short docstrings for public services, classes, important functions, and interfaces.

Do not comment every obvious line. Avoid comments such as:
`# increment counter`
when the code already makes that obvious.

Where a module implements a major RAG stage, include a brief module-level explanation of:
- what the stage does;
- what enters it;
- what it produces;
- how it affects later stages.

When security-sensitive behavior is intentionally strict, explain the reason in a concise comment.
