# Session 03 — Background jobs, retries, and SSE

## Session outcome

The learner can explain why long work leaves the HTTP request, how a
transactional outbox prevents lost jobs, why at-least-once delivery requires an
idempotent consumer, and how leases, fencing, retries, DLQ, ordered events, and
SSE reconnection keep background processing safe and observable.

## Core mental model

```text
HTTP API
   │ atomic write
   ▼
Repository
├── Run = QUEUED
└── OutboxMessage = PENDING
          │
          ▼
Outbox publisher ──► Queue ──► Worker
                                  │ claim with lease + attempt token
                                  ▼
                 RUNNING ──► COMPLETED
                    │
                    ├── retryable ──► RETRY_SCHEDULED ──► RUNNING
                    ├── permanent ──► FAILED
                    └── exhausted ──► FAILED + DLQ

Every transition appends an ordered RunEvent.
SSE sends events after Last-Event-ID and waits for new ones.
```

The queue and repository solve different problems. The queue makes work
available and redelivers unacknowledged messages. The repository decides
whether a worker currently owns the right to change a run.

## Vocabulary

| Term | Interview-ready meaning |
|---|---|
| Atomic operation | A change that becomes visible completely or not at all |
| Transaction | A group of persistence operations committed or rolled back as one unit |
| Lock | Mutual exclusion around a concurrency-sensitive critical section |
| Idempotency | Repeating one intended operation creates no additional business effect |
| Producer | A component that publishes a message to a queue |
| Consumer | A component that receives and handles queue messages |
| Queue | A buffer that decouples accepting work from executing it |
| Worker | A background consumer that executes one unit of work |
| Transactional outbox | A durable publication intent written atomically with business state |
| At-least-once delivery | A message is delivered one or more times, so duplicates are expected |
| Acknowledgement | Confirmation that a delivery can be removed from the queue |
| Visibility timeout | Time during which a received message is hidden before unacknowledged redelivery |
| Lease | Time-bounded ownership of a run by one worker |
| Fencing token | Monotonic attempt number that prevents an old worker from writing after ownership changes |
| Retry | A new attempt for a failure that may succeed later |
| Backoff | A delay that grows between retry attempts |
| DLQ | Quarantine for messages that cannot be processed after the allowed attempts |
| State | The current snapshot of a run |
| Event | An immutable fact describing something that happened to a run |
| SSE | A one-way HTTP event stream from server to client |
| Last-Event-ID | The last confirmed SSE sequence used to request only later events |

## Quick recall

1. Why should a 90-second analysis not run inside the HTTP request?
2. What does at-least-once delivery require from the consumer?
3. What problem does a transactional outbox solve?
4. What is the difference between a lease and a lock?
5. Why is a visibility timeout not sufficient without a fencing token?
6. Which failures should be retried?
7. What is the difference between current state and ordered events?
8. What does `Last-Event-ID: 5` mean?

## Interview questions

1. Design a reliable background-processing boundary for a document-analysis API.
2. Explain why exactly-once delivery is usually replaced by at-least-once delivery plus idempotency.
3. How does a transactional outbox avoid the dual-write failure between a database and a queue?
4. Two workers receive the same job concurrently. How do you guarantee one terminal state change?
5. A worker pauses beyond its lease and later resumes. How do you prevent its stale result from winning?
6. How do you classify retryable, permanent, and exhausted failures?
7. How would an SSE client reconnect without losing or mixing events?
8. Why should run events be append-only and monotonically sequenced?

## Scenario drills

### Scenario A — Run saved, queue unavailable

The API saves `Run 123` as `QUEUED`, but the queue publish fails. Explain why
this creates an orphaned run and how an outbox changes the write sequence.

### Scenario B — Publisher acknowledgement failure

The outbox publisher sends a message successfully and crashes before marking
the outbox record as published. Explain the duplicate and why it is safe.

### Scenario C — Worker crash after claim

A worker receives a message, claims the run, and dies without acknowledging the
delivery. Explain the roles of visibility timeout, lease expiry, and reclaim.

### Scenario D — Stale worker returns

Worker A holds attempt token 1. Its lease expires and Worker B acquires attempt
token 2. Worker A later tries to complete the run. Decide what the repository
must do.

### Scenario E — Retry storm

A provider times out repeatedly. Explain classification, exponential backoff,
maximum attempts, terminal run state, and DLQ behavior.

### Scenario F — SSE disconnect

The client received events 1–5 and disconnected while processing continued.
Explain the reconnect request, server-side filtering, ordering, and run scope.

## Expected answer elements

These are evaluation points, not answers that must be memorized.

### Reliable enqueue

- The API responds after durable acceptance, not after long processing.
- The run and outbox record are written within one atomic boundary.
- The publisher marks the outbox only after queue publication.
- A crash between publish and mark can duplicate the message, so the consumer
  contract remains idempotent.

### Safe consumption

- The queue hides a received message until acknowledgement or visibility expiry.
- A worker atomically claims the run rather than relying on an unlocked status check.
- An active lease rejects concurrent ownership; an expired lease permits reclaim.
- Each reclaim increments the fencing token.
- Terminal writes compare the presented token with the current token.

### Failure policy

- Transient infrastructure or provider failures receive bounded retries.
- Schema, ownership, and permanent business failures do not retry.
- Backoff prevents a failing dependency from receiving an immediate retry storm.
- Exhaustion produces explicit `FAILED` state and a DLQ record for investigation.
- A duplicate message cannot bypass the stored retry-not-before boundary.

### State, events, and SSE

- State answers where the run is now; events explain how it arrived there.
- Event sequences are monotonic within one run and never mix run IDs.
- Reconnection requests events with sequence greater than `Last-Event-ID`.
- The stream continues waiting while the run is non-terminal and closes after a
  terminal event. Comment heartbeats prevent a quiet connection from appearing
  abandoned during long work or backoff.

## Common misconceptions

- A transactional outbox is not the entire producer-consumer architecture. It
  is the durable bridge between the business write and the queue producer.
- Ignoring a duplicate blindly is unsafe. The consumer first checks persisted
  run ownership and state, then acknowledges a confirmed duplicate.
- A lock and a lease are not interchangeable. A lock protects a short atomic
  section; a lease represents time-bounded ownership of long-running work.
- A visibility timeout redelivers work but does not stop the old worker from
  returning. Fencing prevents its stale write.
- Retry is not an error category for every failure. Only failures that may
  succeed without changing the request qualify.
- SSE is not the run state itself. It transports the ordered event history.

## Evidence in the repository

- [Job, lease, event, and run models](../../src/zevidence/domain/models.py)
- [Run retry state machine](../../src/zevidence/domain/state_machine.py)
- [Atomic outbox, leases, fencing, and event repository](../../src/zevidence/application/repository.py)
- [At-least-once queue and outbox publisher](../../src/zevidence/application/queue.py)
- [Retrying idempotent worker](../../src/zevidence/application/worker.py)
- [SSE route and Last-Event-ID replay](../../src/zevidence/api/routes.py)
- [Worker failure drills](../../tests/application/test_worker.py)
- [SSE replay and live-stream tests](../../tests/api/test_events.py)

The deterministic publisher and worker are driven explicitly in tests. Wiring
them into long-lived process startup and graceful shutdown belongs to the later
runtime sessions.

## Exit criteria

- The learner can explain the full API-to-worker flow without prompting.
- The learner can distinguish producer, consumer, outbox, queue, and worker.
- The learner can explain why at-least-once delivery is safe here.
- The learner can diagnose the dual-write, duplicate-delivery, crashed-worker,
  stale-worker, retry-exhaustion, and SSE-reconnection scenarios.
- The learner can give a concise English explanation of lease plus fencing.
