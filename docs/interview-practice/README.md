# Interview practice

This directory turns each zEvidence study session into reusable interview
practice. It is designed for text or voice conversations with a coding agent
that has access to this repository.

The application code remains the source of truth. These files explain what the
learner should be able to reason about and show where that reasoning is proven
by code or tests.

## Start a practice session

Open the repository with Codex and use one of these prompts:

- `Practice Session 2 in mock interview mode. Interview me in English and give feedback in Portuguese.`
- `Run a quick recall for Sessions 1 and 2. Ask one question at a time.`
- `Give me a production incident scenario about idempotency. Do not reveal the solution first.`
- `Teach me the concepts I missed in Session 1, then test me again.`

For voice practice, use the same prompts after starting a voice conversation.
No voice-specific implementation is required in this repository.

## Practice modes

| Mode | Behavior |
|---|---|
| Quick recall | Short definitions and comparisons with immediate correction |
| Mock interview | Open questions, one follow-up probe, then scored feedback |
| Scenario drill | A failure or design situation that requires a decision and reasoning |
| Remedial tutoring | Explain a weak concept, ask a smaller question, then retry the original one |

## Interview protocol

The interviewer must:

1. read this file and the selected session material;
2. choose questions that match the learner's current level;
3. ask one question at a time without giving away the expected answer;
4. wait for the complete response;
5. ask at most one clarifying or deepening question;
6. score the response and explain the most important missing element;
7. ask the learner to restate a corrected mental model when the gap is material;
8. increase difficulty only after the core concept is stable.

The interviewer should prefer reasoning over memorized definitions. A strong
answer explains ownership, invariants, failure behavior, and trade-offs, and can
connect them to concrete zEvidence code.

## Scoring rubric

Score each answer from 0 to 3:

| Score | Meaning |
|---:|---|
| 0 | No usable mental model yet |
| 1 | Partially correct but missing a central boundary or invariant |
| 2 | Correct for the implemented scope and explained clearly |
| 3 | Production depth: includes failure modes, trade-offs, and operational consequences |

Give one score for the answer as a whole and concise feedback in this format:

```text
Score: 2/3
Strong: <what was correct>
Missing: <most important gap>
Better answer: <concise interview-ready formulation>
```

## Session index

| Session | Topic | Study status | Practice material |
|---:|---|---|---|
| 1 | Domain model and traceability | Completed | [Open](session-01-domain-and-traceability.md) |
| 2 | API boundaries and idempotency | Completed | [Open](session-02-api-boundaries-and-idempotency.md) |
| 3 | Background jobs, retries, DLQ, state, and SSE | Planned | Add after completion |
| 4 | React streaming state and frontend tests | Planned | Add after completion |
| 5–14 | RAG, agents, quality, security, operations, and public case | Planned | See [study plan](../study-plan.md) |

## Maintenance rule

At the end of a completed study session:

1. copy `session-template.md` to a numbered session file;
2. record only concepts actually studied and behavior actually implemented;
3. link to the code and regression tests that provide evidence;
4. include misconceptions observed during explain-back;
5. keep answers as evaluation points, not scripts that must be memorized.

Practice results are not written to the repository unless the learner asks for
them to be recorded.
