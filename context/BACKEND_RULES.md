# Backend Rules

## Authentication and session security

- Hash passwords with Argon2id or an equally strong KDF.
- Never store plaintext passwords.
- Use short-lived/revocable session credentials.
- Cookie sessions must use HttpOnly and Secure in production, with an intentional SameSite policy.
- CSRF protection is required for cookie-authenticated state-changing requests where the deployment topology needs it.
- Never expose raw session credentials to browser JavaScript.
- Never persist raw auth/session tokens in client-accessible local/session storage.
- Never accept raw session tokens through URL query parameters.

### Source/document viewing

A source-viewer endpoint is not a special security exception. It must use the same server-side authorization rules as the normal document API.

Forbidden pattern:
`/documents/{id}/file?token=<raw-session-token>`

Also forbidden:
- copying the session token into `document.cookie` with `ui.run_javascript`;
- embedding the session token in `<iframe>`, `<object>`, or `<embed>` URLs;
- writing the token to logs, telemetry, HTML, browser history, or referrer-visible URLs.

Preferred pattern:
1. same-origin authenticated browser request using the normal HttpOnly session;
2. if browser embedding technically prevents this, a short-lived server-issued viewer ticket scoped to one document/request, with a dedicated validation path and no reuse of the main session token.

Page numbers may be sent as URL fragments (`#page=N`) because the fragment is not transmitted as an HTTP credential.

## Production/test boundary

Do not import or instantiate `fastapi.testclient.TestClient` from production frontend/application code.

Tests may use `TestClient` to test the backend. Production code must communicate over the actual service boundary using a real HTTP client or another explicitly documented deployment-safe transport.

The API client should remain centralized; only its transport implementation should change.

## Authorization

Every protected resource must be authorized server-side.

Never fetch a document/chunk/file by ID and then rely on the frontend to decide whether the user may see it.

Prefer authorization-aware database/service queries.

## Input validation

Validate:
- UUIDs/IDs;
- query length;
- pagination and sorting;
- upload size/count;
- filenames;
- content type;
- metadata;
- provider configuration.

Never use client filenames as storage paths.

## Error safety

API responses must expose safe, stable error contracts.

Never return:
- stack traces;
- SQL/database URLs;
- absolute filesystem paths;
- access tokens;
- provider credentials;
- raw exception reprs.

Map internal exceptions to safe user-facing categories while retaining technical details only in protected telemetry/logging.

## File safety

Treat uploaded files as hostile input.

Required protections include:
- allowlist and content validation;
- file size/count limits;
- safe temporary storage;
- path traversal protection;
- parser resource limits/timeouts;
- cleanup;
- controlled storage keys;
- no executable upload types.

## Data isolation

Prove through tests that User A cannot:
- read User B's document;
- retrieve User B's chunks;
- stream User B's source file;
- mutate User B's data;
- infer sensitive metadata through error messages or counts.

## External dependencies

Every external provider gets:
- explicit timeout;
- bounded retry where safe;
- failure state handling;
- structured logging;
- clear fallback semantics where correctness permits.

## Health endpoints

Keep liveness minimal. Do not expose application environment, dependency topology, credentials, paths, or detailed infrastructure diagnostics from a public liveness endpoint.

Readiness may expose a minimal dependency status appropriate to the deployment, but must not reveal internal exception details.

## CORS/CSRF

Production origins must be explicit and environment-specific.

Do not combine permissive `allow_headers=["*"]` / credentialed CORS with arbitrary origins.

Review CSRF controls whenever cookies authenticate API requests.

## Logging

Never log:
- passwords;
- authorization headers;
- raw session tokens;
- API keys;
- private document contents;
- sensitive user queries by default.

## RAG security

Treat retrieved document text as untrusted data. Retrieved text may contain prompt-injection instructions and must never override system/developer security rules.

## Multimodal truthfulness

Do not advertise multimodal support until the backend implements and tests a non-text modality path through ingestion, representation/embedding, retrieval, and citation/provenance.
