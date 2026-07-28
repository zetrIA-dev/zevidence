# Architecture

## Runtime boundary

| Capability | Local default | Optional AWS adapter |
|---|---|---|
| Frontend | React | — |
| API | FastAPI | — |
| Jobs | Python worker + deterministic queue | SQS + DLQ |
| Relational state | PostgreSQL | — |
| Vector search | pgvector | — |
| Objects | local adapter | S3 |
| Models | deterministic fake provider | Bedrock |
| Observability | OpenTelemetry or Langfuse-compatible local stack | — |
| Runtime | Docker Compose; kind/k3d + Helm | — |

AWS infrastructure is limited to Bedrock access, S3, SQS/DLQ, least-privilege
IAM, lifecycle, and budget controls. The study path does not include a
persistent cloud application runtime.

## Data flow

```text
React
  │ create dossier, upload documents, start run
  │ query state and consume SSE events
  ▼
FastAPI ─────────► PostgreSQL + pgvector
  │                         ▲
  │ enqueue                 │ state, claims, evidence, events
  ▼                         │
Queue ───────────────► Python worker
                             │
                             ▼
                 typed multi-agent graph
                 extractor ─┐
                 skeptic   ──┼► verifier ► synthesizer
                            │
                            └► claim registry ► export
```

## State and concurrency

- Dependencies are request-scoped; mutable request state never lives in a
  process global.
- A run is addressed by `run_id` and protected by an idempotency key.
- Queue delivery is at-least-once, so duplicate handling is part of the domain
  contract.
- Run events have a monotonic sequence. SSE clients reconnect with
  `Last-Event-ID`.
- Evidence is immutable. Reprocessing creates a new run and preserves the
  previous provenance.

## Grounding

Chunks preserve document identity, page or section, offsets, and embedding
version. Retrieval is always filtered by dossier.

The claim registry links every claim to evidence IDs. Citation verification
checks that the evidence exists and that the source locator resolves to the
ingested document. The synthesizer cannot promote an unsupported claim.

## Reliability

- Timeouts at model, tool, queue, and storage boundaries.
- Classified retries with bounded backoff.
- DLQ for exhausted asynchronous work.
- Structured-output validation before state transitions.
- Bounded agent loops and tool budgets.
- Explicit provider fallback recorded in the run.
- Deterministic fakes for unit and concurrency tests.

## Security

Documents, chunks, metadata, and tool output are untrusted. The system uses
typed allowlisted tools, strict payload validation, provenance, resource quotas,
and adversarial fixtures. v1 has no model-selected egress or external writes.

Only synthetic documents and eval cases are committed.

## Observability

Runs record trace ID, prompt and schema versions, model/provider, tool calls,
retries, tokens, latency, estimated cost, and grader results. Raw content does
not need to leave the local environment to measure system behavior.
