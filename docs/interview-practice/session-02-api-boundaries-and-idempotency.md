# Session 02 — API boundaries and idempotency

## Session outcome

The learner can place validation and behavior in the correct application layer,
explain request-scoped dependency injection, and design an idempotent run
creation endpoint that remains safe under concurrent retries.

## Core mental model

```text
HTTP request
    │
    ▼
Schema ── validates transport shape and types
    │
    ▼
Route ─── translates HTTP into an application call
    │
    ▼
Service ─ enforces the use case and business relationships
    │
    ▼
Domain ── protects entity-local invariants
    │
    ▼
Repository ─ retrieves and persists through an atomic storage boundary
```

The service object is created per request, so it cannot leak request-local state
between users. The repository is shared because it represents durable storage,
but atomic operations must protect concurrency-sensitive invariants.

This session stores exact submitted content in the deterministic in-memory
adapter, records its hash, and completes the explicit ingestion transitions.
Durable object storage and production ingestion are deferred to Session 5.

For run creation, the idempotency key is scoped to the dossier. The repository
atomically checks and creates the run:

- first request: create one run and return `201`;
- same key and equivalent document set: return the existing run with `200` and
  `Idempotent-Replayed: true`;
- same key and different document set: return `409`;
- concurrent equivalent requests: persist one run only.

## Vocabulary

| Term | Interview-ready meaning |
|---|---|
| API schema | The typed transport contract for request and response shape |
| Route | The thin HTTP adapter that extracts inputs and calls one use case |
| Service | The application layer that coordinates repositories and enforces business rules |
| Domain model | An entity that protects invariants valid without external lookup |
| Repository | The persistence abstraction that retrieves entities and owns atomic storage operations |
| Dependency injection | Supplying collaborators at the boundary instead of constructing hidden dependencies inside the use case |
| Request scope | A fresh service instance for each HTTP request |
| Idempotency key | A client-provided identity for one intended operation and payload |
| Schema error | A malformed transport input, represented here by `422` |
| Business conflict | A well-formed request that violates ownership, state, or prior-operation meaning |

Schema failures intentionally use FastAPI's field-oriented `detail` response,
while application failures use the stable domain-oriented `error` envelope.

## Quick recall

1. Which layer rejects an extra JSON field?
2. Which layer checks whether a document belongs to the requested dossier?
3. Which layer reads the `Idempotency-Key` header?
4. Which layer retrieves a document from storage?
5. Which layer must atomically ensure that two retries create one run?
6. Why are API request schemas separate from frozen domain models?

## Interview questions

1. Explain the difference between schema validation and business validation.
2. Why should a FastAPI route stay thin?
3. Why is `DossierService` request-scoped while the repository is shared?
4. Where should idempotency be implemented, and why is a read-then-write sequence unsafe?
5. What should happen when the same idempotency key is reused with a different payload?
6. How would this in-memory design evolve to PostgreSQL without changing the service contract?
7. Why do identical idempotency keys remain valid for different dossiers?

## Scenario drills

### Scenario A — Extra status field

A client sends `status: "completed"` while creating a dossier. The JSON is
otherwise valid. Decide which layer rejects it and explain the security and
consistency benefit.

### Scenario B — Correct UUID, wrong owner

A run request contains a valid document UUID, but the document belongs to a
different dossier. Explain the expected response and which layers participate
in detecting it.

### Scenario C — Concurrent duplicate requests

Two identical run requests with the same idempotency key arrive at nearly the
same time. A repository first performs an unlocked lookup and then inserts.
Explain the race, the required atomic boundary, and the regression test.

### Scenario D — Same key, changed intent

A client successfully creates a run for document A, then retries the key with
document B. Explain why returning the first run silently is unsafe.

## Expected answer elements

These are evaluation points, not answers that must be memorized.

### Schema versus business validation

- Schemas validate transport shape, types, required values, and local field
  constraints before the use case runs.
- The service validates meaning that requires repository lookup, such as
  existence, ownership, and readiness.
- Domain models protect invariants local to an entity.

### Layer ownership

- The route owns HTTP extraction and response translation, not business rules.
- The service coordinates the use case and remains independent of FastAPI.
- The repository abstracts persistence and owns storage-level atomicity.
- Dependency injection makes lifetimes and substitutes explicit and testable.

### Idempotency

- The key identifies one intended operation within a deliberate scope.
- Equivalent document IDs are canonicalized so ordering does not change intent.
- Check-and-create must be atomic; otherwise concurrent requests can both insert.
- A replay returns the original result and reports that it was replayed.
- Reusing the key for a different canonical payload is a conflict, not a retry.

### Request isolation

- A fresh service prevents mutable request context from leaking across requests.
- Shared storage is expected, but it must not contain request-specific working
  state outside persisted entities.
- The current lock is a deterministic in-memory adapter; a database adapter
  would use a unique constraint and transactional conflict handling.

## Common misconceptions

- The repository does not receive HTTP requests. The route receives them, and
  the service calls the repository through an application interface.
- Not every validation belongs in the service. Shape belongs to schemas and
  entity-local invariants belong to domain models.
- Idempotency does not mean ignoring every repeated request. The system must
  verify that the repeated key represents the same intended payload.
- A process-global service is not needed to preserve state. Durable state lives
  behind the repository; services can be request-scoped.
- An in-memory lock demonstrates the atomic contract but does not coordinate
  multiple processes or replicas.

## Evidence in the repository

- [API schemas](../../src/zevidence/api/schemas.py)
- [HTTP routes](../../src/zevidence/api/routes.py)
- [Dependency scopes](../../src/zevidence/api/dependencies.py)
- [Application service](../../src/zevidence/application/service.py)
- [Repository contract and in-memory adapter](../../src/zevidence/application/repository.py)
- [Run and concurrency tests](../../tests/api/test_runs.py)
- [Dossier API tests](../../tests/api/test_dossiers.py)
- [Document API tests](../../tests/api/test_documents.py)

## Exit criteria

- The learner can place schema, route, service, domain, and repository duties
  without prompting.
- The learner can explain request scope versus shared persistence.
- The learner can describe the concurrent read-then-write race.
- The learner can explain all three idempotency outcomes.
- The learner can answer the schema-versus-business-validation question in
  concise English.
