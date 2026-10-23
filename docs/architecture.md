# Architecture

ContractFit begins as a modular monolith. It can later split ingestion and document processing into independent workers without changing the domain contracts.

## Data flow

```text
SAM.gov or manual upload
          |
          v
Opportunity ingestion and versioning
          |
          v
Document parsing and OCR
          |
          v
Structured requirements with evidence
          |
          +--> Deterministic eligibility gates
          |
          +--> Semantic capability matching
          |
          v
Explainable score and human review
          |
          v
Dashboard, alerts and feedback
```

## Boundaries

- API: authentication, organization boundaries, orchestration and HTTP contracts.
- Ingestion: source adapters, downloads, hashing, deduplication and version history.
- Document processing: parsing, OCR, structured extraction and citation preservation.
- Matching: hard gates, weighted scores, semantic similarity and explanations.
- Evaluations: labeled datasets, regression metrics, cost and latency reporting.
- Web: onboarding, opportunity review, evidence inspection and feedback.

## Invariants

1. Eligibility calculations are deterministic.
2. Every extracted requirement retains evidence.
3. Unknown mandatory information triggers review.
4. Customer data is isolated by organization.
5. Model prompts and versions are traceable.
6. Jobs are idempotent and retryable.
