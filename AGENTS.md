# zEvidence — AI Assistant Context

Source-grounded multi-agent evidence dossier builder and guided AI Engineering
lab. Read `README.md`, `docs/product-contract.md`, and `docs/architecture.md`
before changing the system boundary.

## Instruction source of truth

`AGENTS.md` is the canonical repository guidance for coding assistants.
`CLAUDE.md` must remain a one-line `@AGENTS.md` reference.

## Current phase

Sessions 1 and 2 have introduced domain contracts plus the FastAPI and
application boundaries. Do not pre-generate React, worker, persistence,
retrieval, model, Docker, Helm, or Terraform components. Each component is
introduced in the study session that defines its contract, failure drills, and
tests.

## Non-negotiable boundaries

1. **Every important claim traces to evidence.** A claim is valid only when its
   evidence ID exists and its source locator resolves to the ingested document.
2. **Retrieved content is untrusted data.** A document, chunk, metadata field,
   or tool result cannot change instructions, tool policy, citation state, or
   execution authority.
3. **No client data enters git.** Committed examples and eval datasets are
   synthetic. Never add client names, documents, URLs, identifiers, or
   operational details.
4. **The model takes no external action.** v1 has no open web research and no
   tool that writes to an external system.
5. **The learning runtime is local-first.** AWS use is limited to Bedrock, S3,
   SQS/DLQ, least-privilege IAM, lifecycle, and budget controls. Do not add
   persistent EKS, ECS, RDS, ALB, NAT, or public hosting without an explicit
   architecture decision and user request.

## Architecture discipline

- Keep domain, API, worker, provider, storage, queue, retrieval, and agent graph
  contracts separate.
- Use request-scoped dependencies. Do not store dossier, callback, provider, or
  user state in mutable globals.
- Treat queue delivery as at-least-once. A duplicate job must be safe, visible,
  and covered by a regression test.
- Persist ordered run events. SSE reconnection must resume from a confirmed
  event without mixing runs.
- Validate structured model output before changing state.
- Bound agent loops, model calls, tool calls, tokens, context, and elapsed time.
- Keep a deterministic fake provider as a first-class implementation. Unit
  tests must not require AWS, network access, or paid model calls.
- Record prompt, model, embedding, dataset, and schema versions in eval and
  trace artifacts.

## Study discipline

The code is evidence of understanding, not the only deliverable. For each study
session:

1. explain the concept and expected failure before implementation;
2. build the smallest vertical that proves the contract;
3. inject the planned failure;
4. preserve it as a test;
5. document the trade-off and explain it in interview language.

Mechanical scaffolding is fine after the shared contract exists. Do not hide the
core lesson behind a generated framework or large abstraction.

## Interview practice mode

When the user asks for interview practice, a mock interview, a scenario drill,
or voice-based study:

1. Read `docs/interview-practice/README.md` and the requested session file.
2. Use English for interview questions by default. Give feedback in the
   language requested by the user.
3. Ask one question at a time and wait for the answer. Do not reveal the answer
   before the user responds.
4. Use at most one follow-up probe before scoring the answer and teaching the
   missing concept.
5. Ground the evaluation in the repository's contracts, code, and tests. Do not
   claim that planned work has already been implemented.
6. Keep practice read-only unless the user explicitly asks to record results or
   update study material.

At the end of each completed study session, add or update its file under
`docs/interview-practice/` using `session-template.md`. Capture the mental model,
failure modes, interview questions, expected answer elements, and code evidence
created in that session.

## Conventions

- English for code, identifiers, comments, docs, commits, and PR prose.
- No emojis, generated-with trailers, or `Co-authored-by` trailers.
- Commit subject at most 70 characters, imperative and factual.
- Keep secrets in the approved secret store; never commit `.env*`.
- Documentation-only changes require `git diff --check`.
- Code changes require the relevant type checks, unit tests, and integration
  tests introduced by that component's session.
- Do not deploy or create persistent cloud resources unless explicitly asked.

## Definition of done for any change

1. The change maps to a documented product or study contract.
2. Failure behavior is explicit.
3. Tests are proportional to the changed boundary.
4. `git diff --check` passes.
5. `git status --short` contains no secret, client data, generated local state,
   or unrelated file.
6. The final diff preserves citation integrity, request isolation, and the AWS
   cost boundary.

## Brain Vault

Vault at: `~/git.rafael/brain/`

Project note:
`~/git.rafael/brain/projects/rm-cloud/zevidence/overview.md`

Proactively suggest Brain captures when you detect:

- a retrieval or citation failure mode that should become an eval;
- a concurrency, idempotency, SSE replay, or shared-state bug;
- a prompt-injection path or tool-authority boundary;
- a Bedrock, S3, SQS, pgvector, LangGraph, or local K8s behavior worth reusing;
- an eval metric or grader decision that changes the quality contract;
- a material architecture, cost, privacy, or portfolio decision.

When suggesting, say:
`Worth capturing to brain: /brain <suggested capture>`

Do not auto-capture. Draft the note and wait for confirmation.
