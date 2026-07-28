# Study plan

The application is built in 14 guided sessions. Each session combines pre-read,
recall, design, implementation, a deliberate failure, regression tests, and an
explain-back.

## Session format

| Block | Target |
|---|---:|
| Pre-read | 20–30 min |
| Recall | 10 min |
| Design | 15 min |
| Implementation | 45–60 min |
| Failure drill | 15–20 min |
| Tests | 15 min |
| Explain-back | 10 min |
| Checkpoint | 5 min |

## Phase 1 — Application foundations

1. Product contract, architecture, state machine, and Pydantic domain models.
2. Async FastAPI endpoints, validation, dependency injection, and idempotency.
3. Background jobs, at-least-once delivery, retries, DLQ, state, and SSE replay.
4. React hooks, streaming state, responsive UI, and frontend tests.

**Gate 1:** the synthetic product works end to end without an LLM or RAG.

## Phase 2 — RAG and agents

5. Document ingestion, traceable chunking, embeddings, pgvector, and citations.
6. Retrieval quality: golden queries, hybrid search, filters, recall@k,
   precision@k, and MRR.
7. Typed multi-agent graph, parallel branches, bounded loops, timeouts, and
   fallbacks.
8. Claim registry, citation verification, human review, and dossier exports.

**Gate 2:** every important claim in the sample dossier resolves to valid
evidence or remains explicitly unsupported.

## Phase 3 — Quality, security, and operations

9. Versioned eval dataset, failure taxonomy, deterministic graders, calibrated
   judges, pass@k, pass^k, and CI gates.
10. Threat model, typed tools, provenance, quotas, and prompt-injection fixtures.
11. Provider gateway, Bedrock adapter, deterministic fake, prompt registry,
    traces, tokens, latency, cost, and SLOs.

**Gate 3:** provider, tool, schema, and model-quality failures are bounded,
visible, and covered by regression tests.

## Phase 4 — Runtime and public case

12. Dockerfiles, Docker Compose, health checks, migrations, seeds, and graceful
    shutdown.
13. Helm on kind/k3d, replica and worker-failure drills, plus Terraform for the
    narrow AWS boundary.
14. Reproducible README, sample dossier, eval report, threat model, ADRs,
    cost/run, CI evidence, and interview drills.

**Gate 4:** a clean local environment reproduces the deterministic application,
sample dossier, and published eval evidence without private data or undocumented
infrastructure.

## Deferred

Fine-tuning, self-hosted inference, persistent EKS, multi-tenancy, enterprise
SSO, open web research, SharePoint sync, Neo4j/GraphRAG, and regulated clinical
specialization are intentionally outside the initial path.
