# zEvidence

Source-grounded multi-agent evidence dossier builder.

> Every claim traces to evidence.

zEvidence turns a bounded set of user-provided documents into an auditable
evidence dossier. Its first vertical is vendor due diligence: compare
requirements with proposals and technical documents, identify support and
contradictions, surface gaps and risks, and preserve a citation trail for every
important claim.

This repository is also a guided AI Engineering lab. The goal is to build and
explain a complete agentic application—from async API and concurrent state to
RAG evaluation, agent security, observability, and local Kubernetes—without
using cloud deployment as a substitute for learning those contracts.

## Status

Planning foundation. The product contract, architecture, and study sequence are
defined; functional implementation starts in Study Session 1.

This is a reproducible public case, not a continuously hosted demo. The final
case will run locally and include sample outputs, eval evidence, failure drills,
and architecture decisions.

## Product contract

Inputs:

- evaluation requirements;
- vendor proposals;
- technical documentation;
- policies, certifications, and presentations.

Outputs:

- met and unmet requirements;
- source evidence and citations;
- gaps and contradictions;
- risks and open questions;
- a human-reviewed recommendation;
- Markdown, PDF, and PowerPoint exports.

Trust rule: retrieved text is untrusted data. It cannot create a valid citation,
change tool policy, or turn an unsupported claim into a fact.

See [Product contract](docs/product-contract.md).

## Planned architecture

The daily development loop stays local:

- React frontend;
- async FastAPI API;
- Python worker;
- PostgreSQL with pgvector;
- deterministic model, queue, and object-store adapters;
- OpenTelemetry or Langfuse-compatible traces;
- Docker Compose;
- kind or k3d with Helm.

AWS is intentionally narrow and optional:

- Amazon Bedrock for real-model integration tests;
- S3 for document objects;
- SQS with a DLQ for at-least-once job delivery;
- least-privilege IAM and budget controls.

There is no persistent EKS, ECS, RDS, ALB, or NAT environment in the study
path. Unit tests must run without AWS or a paid model.

See [Architecture](docs/architecture.md) and
[ADR 0001](docs/decisions/0001-local-first-study-runtime.md).

## Agent graph

The initial graph has four bounded responsibilities:

1. **Evidence Extractor** proposes claims and evidence from retrieved chunks.
2. **Contradiction/Skeptic** finds conflicts, gaps, and unanswered questions.
3. **Citation Verifier** validates claim support and source identity.
4. **Report Synthesizer** assembles only verified claims into the dossier.

Extractor and skeptic may run in parallel. Verification and synthesis are
gates. Loops, tools, tokens, and time are bounded.

## Delivery gates

1. **Deterministic application:** frontend, API, worker, state, and streaming
   work end to end without an LLM or RAG.
2. **Cited dossier:** ingestion, retrieval, agent graph, and claim registry
   produce a reviewable report.
3. **Reliability contract:** evals, security fixtures, provider failures,
   traces, and cost are measured.
4. **Reproducible case:** Docker Compose, local Kubernetes, optional AWS
   adapters, CI evidence, and interview material are complete.

The full 14-session sequence is in the [Study plan](docs/study-plan.md).

## Principles

- Deterministic contracts before model behavior.
- No shared mutable request state.
- At-least-once delivery must be idempotent and observable.
- Structured output is validated before state changes.
- Retrieval quality is measured separately from generation quality.
- Missing evidence remains missing.
- Synthetic data only in git.
- No external action selected by the model.

## License

No license has been selected yet. Until one is added, the source remains
copyrighted and is published for review rather than reuse.
