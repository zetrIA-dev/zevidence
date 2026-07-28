# Product contract

## Problem

Evidence-heavy reviews are slow because requirements, claims, and supporting
material live across documents with inconsistent structure. A fluent summary
does not solve that problem if the reader has to reopen every source to verify
it.

zEvidence builds the traceability first. The report is a view over a claim and
evidence registry, not free-form text that later receives decorative citations.

## First vertical

Vendor due diligence over documents supplied by the user.

Inputs may include:

- requirements and evaluation criteria;
- proposals and statements of work;
- product and architecture documentation;
- policies and certifications;
- presentations.

The dossier reports:

- requirements supported by evidence;
- unsupported requirements and missing material;
- contradictory claims;
- risks and open questions;
- a human-reviewed recommendation;
- citations that resolve to document, page or section, and excerpt.

## Trust contract

Each important claim has exactly one state:

- `supported`: cited evidence directly supports the claim;
- `conflicting`: available sources disagree or qualify the claim;
- `unsupported`: no retrieved evidence meets the support contract.

The system must not infer `supported` from confidence, repetition, vendor tone,
or model fluency. Evidence IDs and source locators are validated outside the
model.

## Initial agents

| Agent | Responsibility |
|---|---|
| Evidence Extractor | Propose claims and candidate evidence for each requirement |
| Contradiction/Skeptic | Find conflicts, omissions, and unanswered questions |
| Citation Verifier | Validate claim support and citation identity |
| Report Synthesizer | Assemble verified claims into the final dossier |

## v1 constraints

- User-provided documents only.
- Single-user, single-tenant development model.
- Synthetic examples and eval data.
- No open web research.
- No external actions selected by the model.
- Human review before the recommendation becomes final.
- Local execution is the primary path.

## Success evidence

The case is complete when a clean local environment can reproduce a cited
sample dossier and its eval results, including known retrieval, generation,
citation, concurrency, and prompt-injection failures.
