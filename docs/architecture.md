# Architecture

## Implemented vertical slice

`Upload -> LocalFileStorage -> DocumentParser -> SourceDocument/DocumentPage -> RequirementExtractor -> Opportunity -> OpportunityMatcher -> MatchResult`

The extractor always stores the exact supporting line and document ID. The matcher runs hard
business gates independently from semantic scoring, so an LLM cannot override a missing license,
expired deadline, unsupported territory, incompatible set-aside, or contract-capacity limit.
Semantic scoring is provided through a small interface: the local Ollama adapter can be enabled
without changing product logic, while a deterministic lexical fallback keeps tests and demos
reproducible.

Uploaded files are content-addressed by SHA-256 and stored outside the database. Parsed text is
persisted per page, which lets every extracted requirement cite a stable document and page. Pages
with insufficient embedded text are marked `needs_ocr` and rendered for local Tesseract OCR.
Durable `ProcessingJob` records and a Redis queue move parsing, OCR and extraction outside the API
process; a separate worker retries failures and recovers unfinished jobs after restart.

The external-ingestion boundary includes a typed SAM.gov client that normalizes the provider's
payload before it reaches product logic. A separate scheduler persists bounded ingestion runs,
paginates the source, deduplicates opportunities by provider identity, and records immutable
content-hashed snapshots only when provider data changes. Failed runs retain sanitized audit data
and can be retried safely. The human-review boundary models field-level decisions with organization
ownership, source evidence, deterministic priority and auditable terminal transitions.

## Persistence boundary

The API depends on the `ContractFitStore` protocol. `InMemoryStore` keeps unit tests and local
experiments fast; `SqlAlchemyStore` is the production adapter. SQLAlchemy records are deliberately
separate from Pydantic domain models so database concerns cannot leak into extraction or matching.
Alembic is the only supported mechanism for changing the PostgreSQL schema.

ContractFit begins as a modular monolith. SAM ingestion and document processing already execute as
independent processes over shared persistence without changing the domain contracts.

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
