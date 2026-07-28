# ADR 0001: Use a local-first study runtime

- Status: Accepted
- Date: 2026-07-28

## Context

The primary goal is to learn how the parts of an agentic application connect:
async APIs, frontend streaming state, concurrency, RAG, agents, evals, security,
and observability. Cloud deployment is established experience and would consume
time without closing the current capability gap.

The project should still exercise AWS services that are directly relevant to
the target role and inexpensive to use.

## Decision

Run React, FastAPI, the Python worker, PostgreSQL/pgvector, observability,
Docker Compose, and Kubernetes locally.

Use deterministic local adapters by default. Add optional AWS adapters for:

- Amazon Bedrock;
- S3;
- SQS with a DLQ;
- the minimum IAM, lifecycle, and budget controls needed by those services.

Do not create a persistent EKS, ECS, RDS, ALB, NAT, or public application
environment during the study path.

## Consequences

- Unit and concurrency tests run without network access or model cost.
- AWS integration remains explicit and can be tested with isolated development
  resources.
- The final case proves reproducibility rather than uptime of a public demo.
- Runtime deployment to another provider may be evaluated later, but is not a
  definition-of-done requirement.
