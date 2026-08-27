# Session 01 — Domain model and traceability

## Session outcome

The learner can explain why an auditable dossier is a graph of immutable,
traceable records rather than a polished free-form report. The learner can
separate dossier, document, run, claim, and evidence responsibilities and can
diagnose citations that do not resolve to the exact source used by a run.

## Core mental model

```text
Dossier
├── defines the analysis scope and requirements
├── owns Documents
└── owns Runs
    └── produces Claims
        └── cite Evidence
            └── resolves to an exact location in a Document
```

A run is a reproducible analysis attempt over a fixed set of documents. Adding
a document later does not change an old run. Reprocessing creates a new run so
the prior result and provenance remain auditable.

Traceability is a cross-entity invariant:

```text
claim.run_id == run.id
run.dossier_id == dossier.id
evidence.document_id is in run.document_ids
document.dossier_id == dossier.id
document is ready
document hash, evidence hash, and exact offsets resolve
```

A hash proves content identity, not meaning, ownership, run membership, or that
a locator points to the cited excerpt. All checks are needed.

## Vocabulary

| Term | Interview-ready meaning |
|---|---|
| Dossier | The durable analysis scope: requirements, documents, runs, and lifecycle |
| Document | An ingested source owned by one dossier, with status and content identity |
| Run | One immutable analysis attempt over an explicit document snapshot |
| Claim | A statement produced by a run and classified by its evidence state |
| Evidence | A source excerpt with document identity, exact offsets, human locator, and hash |
| Supported | Available evidence substantiates the claim |
| Conflicting | Available evidence supports incompatible conclusions or values |
| Unsupported | No valid evidence in the run substantiates the claim |
| Traceability | The ability to follow a claim back through its run and evidence to exact source content |
| Idempotency | Repeating the same accepted operation produces no additional business effect |
| Retry | A new attempt after a retryable failure, bounded and observable |

## Quick recall

1. What is the difference between a dossier and a run?
2. Why does evidence need both a content hash and a source locator?
3. Why can a supported or conflicting claim not have an empty evidence list?
4. Why must an unsupported claim have no evidence IDs?
5. What should happen if a requested state transition is not defined?
6. If a document is added after a run completes, does it become part of that run?

## Interview questions

1. Why is an auditable claim registry more trustworthy than a free-form model report?
2. How would you model provenance for a document-analysis system?
3. Which invariants cannot be validated inside the `Claim` schema alone, and why?
4. What is the difference between validating an entity and validating a relationship across entities?
5. How would you preserve reproducibility when a dossier receives new documents?
6. When should a failed operation be retried, sent for investigation, or rejected permanently?

## Scenario drills

### Scenario A — A document arrives late

A run analyzes two documents and completes. A third relevant document is then
added to the dossier. A stakeholder asks the system to attach it to the old
result. Decide what the system should do and explain the audit consequence.

### Scenario B — A convincing but invented citation

A model produces a plausible supported claim and an evidence UUID, but that UUID
does not exist in storage. Explain where the failure should be detected and why
the claim must not be promoted.

### Scenario C — Valid content from the wrong run

An evidence excerpt and hash are correct, and the document belongs to the same
dossier, but the document was not selected for this run. Explain why the claim
is still invalid.

### Scenario D — Locator drift

The excerpt hash is correct, but the stored offsets point to a different piece
of the document. Explain what this reveals about hashes and locators.

## Expected answer elements

These are evaluation points, not answers that must be memorized.

### Dossier versus run

- The dossier is the durable business scope and lifecycle.
- A run is one execution attempt with an explicit document snapshot.
- Runs preserve history; they do not mutate when dossier membership changes.

### Auditable provenance

- A claim references evidence rather than only presenting generated prose.
- Evidence identifies the source document and exact excerpt location.
- Cross-entity checks prove run membership and dossier ownership.
- Immutable content hashes expose later source or excerpt changes.

### Claim statuses

- `supported` means valid available evidence substantiates the statement.
- `conflicting` is evidence-backed and exposes disagreement rather than hiding it.
- `unsupported` is explicit uncertainty and must not carry invented citations.

### Failure handling

- Retry only failures that may succeed without changing the request.
- Bound retries and preserve the final failure for investigation.
- Reject unsupported state transitions rather than guessing intent.
- A new document requires a new run over the new snapshot.

## Common misconceptions

- A dossier is not the first execution step. It is the aggregate that owns the
  analysis scope across multiple runs.
- A hash alone does not prove a citation is relevant or belongs to the run.
- `conflicting` does not mean missing evidence; it requires evidence for the
  incompatible positions.
- Retry and idempotency are related but different: retries repeat attempts;
  idempotency prevents duplicate business effects.
- A field schema cannot prove relationships that require looking up other
  entities. That validation belongs at a boundary with access to them.

## Evidence in the repository

- [Domain models](../../src/zevidence/domain/models.py)
- [State machines](../../src/zevidence/domain/state_machine.py)
- [Cross-entity traceability](../../src/zevidence/domain/traceability.py)
- [Traceability failure tests](../../tests/domain/test_traceability.py)
- [Synthetic Northstar dossier](../../tests/domain/test_northstar_dataset.py)
- [Versioned synthetic dataset](../../tests/fixtures/northstar/dataset.json)

## Exit criteria

- The learner can draw the five-entity relationship without assistance.
- The learner can explain why a new document requires a new run.
- The learner can distinguish supported, conflicting, and unsupported claims.
- The learner can name at least four traceability checks beyond schema shape.
- The learner can answer the dossier-versus-run question concisely in English.
