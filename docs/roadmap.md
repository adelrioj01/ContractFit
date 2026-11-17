# Roadmap

Current reconciliation and file-ownership notes are recorded in
[`docs/handoffs/2026-11-05-phase-1-reconciliation.md`](handoffs/2026-11-05-phase-1-reconciliation.md).

## Portfolio presentation foundation

- [x] Give ContractFit an independent repository identity and outcome-focused README.
- [x] Separate implemented, experimental, planned, and out-of-scope capabilities.
- [x] Publish editable architecture and AI decision-flow diagrams.
- [x] Publish an evidence-backed technical case study and development-agent workflow.
- [x] Version deterministic evaluation baselines and expose one verification command.
- [x] Add contribution, security, changelog, and clean-onboarding guidance.
- [ ] Record and publish a three-to-five-minute product demo (intentionally deferred).
- [ ] Capture committed product screenshots after a Docker-backed visual review.
- [ ] Publish a hosted environment with operational telemetry.

## Implemented MVP vertical slice
- [x] Sample facilities-contractor profile.
- [x] Saved solicitation text ingestion.
- [x] Requirement extraction with verbatim line-level evidence.
- [x] Deterministic eligibility gates.
- [x] Hybrid semantic fit scoring with optional local Ollama inference.
- [x] Ranked opportunity dashboard and JSON API.
- [x] Three-case labeled evaluation harness and CI coverage.

The current hardening target is production-ready catalog and document ingestion. Persistence,
scheduled SAM.gov synchronization, manual document ingestion, background processing, OCR, and the
human-review queue are implemented end to end. The document path has passed a Docker smoke test
with both plain text and image-only PDF inputs.

## Implemented persistence foundation
- [x] SQLAlchemy models for contractor profiles, source documents, opportunities, and requirements.
- [x] PostgreSQL repository adapter behind a storage protocol.
- [x] Alembic migration with foreign keys, indexes, and evidence-preserving fields.
- [x] Automatic migrations when the Docker API service starts.
- [x] SQLite repository tests plus the fast in-memory adapter for unit tests.

## Phase 0: validation
- Interview 15 facilities-service contractors.
- Collect five sanitized company profiles.
- [x] Create five isolated synthetic company profiles for multi-tenant product testing.
- Manually deliver ranked opportunity reports.
- Obtain at least two paid-pilot commitments.

## Phase 1: foundation
- API, PostgreSQL, Redis and Docker Compose.
- [x] Provider-independent organizations, user accounts, memberships and signed access tokens.
- [x] Authenticated organization and reviewer identity for the human-review workflow.
- [x] Enforce authenticated organization boundaries for company profiles and profile-based matching.
- [x] Enforce authenticated organization boundaries for documents, jobs and uploaded opportunities.
- [x] Define explicit ownership and visibility rules for the shared SAM.gov opportunity catalog.
- [x] Reject cross-organization opportunity and evidence references in human-review creation.
- Password-login rate limiting, password reset and email verification.
- Migrations, logging, tests and CI.

## Phase 2: company profiles
- [x] Services, territory, capacity, licenses, insurance and certifications.
- [x] Past-performance projects and contract preferences.
- [x] Editable structured onboarding with completeness reporting.

## Phase 3: ingestion
- [x] Manual PDF, DOCX and TXT opportunity upload.
- [x] Testable SAM.gov search client with normalized records, pagination and sanitized errors.
- [x] Persisted SAM.gov import workflow with scheduling, deduplication and amendment detection.
- [x] Secure attachment storage, SHA-256 hashing and deduplication.
- [x] Normalized amendment snapshots and version history.
- [x] Fetch and version SAM.gov solicitation attachments by source snapshot.
- [x] Durable, retryable Redis-backed background processing.

## Phase 4: document intelligence
- [x] Text PDF, Word and plain-text parsing.
- [x] Requirement extraction with page-level evidence.
- [x] Local Tesseract OCR for scanned PDF pages.
- Excel attachment parsing.
- [x] Evidence-linked human-review domain model with deterministic priority and audited decisions.
- [x] Organization-scoped persisted review queue and resolution API.
- [x] Basic reviewer dashboard for correcting or dismissing low-confidence fields.
- [x] Replace the dashboard's local reviewer identity with authenticated user identity.

## Phase 5: matching
- [x] Deterministic hard gates.
- [x] Weighted scoring.
- [x] Cached local embeddings and pgvector cosine retrieval for capabilities and scopes.
- [x] Thirty-case semantic ranking baseline with Top-1, Recall@3 and MRR metrics.
- [x] Reproducible CLI runner for lexical and local Ollama embedding evaluation.
- [x] Deterministic evidence-aware past-performance matching.
- Semantic past-performance matching and expansion to at least 100 labeled ranking cases.
- [x] Evidence-grounded explanations.

## Phase 6: product workflow
- [x] Ranked opportunity dashboard.
- [x] Opportunity details with page-level source navigation.
- [x] Organization-owned opportunity pipeline with status, owner and next action.
- [x] Organization-owned editable compliance matrix with source citations, status, priority,
  responsible user, due date and explicit business evidence.
- [x] Read-only deterministic amendment comparison across SAM.gov snapshots and analyzed
  organization attachments, with both source citations preserved.
- [x] Persisted amendment acknowledgements and selective compliance-matrix updates.
- [x] Organization-scoped compliance CSV export with source citations and business evidence.
- [x] Watched opportunities, deadline reminders and amendment change alerts.
- [x] Organization email preferences, auditable outbox and optional SMTP worker.
- [x] Organization-owned relevance feedback with dashboard controls and PostgreSQL persistence.

## Phase 7: evaluation and hardening
- At least 100 labeled opportunities.
- [x] Reproducible extraction, exact-value, citation, eligibility, gate and ranking metrics.
- [x] Versioned tenant-isolation and deterministic instruction-text regression tests.
- LLM prompt-injection, role-boundary, encoding and exfiltration tests when a model enters the
  document-extraction path.
- [x] Deterministic local latency budgets and a machine-readable CI quality report.
- [x] PostgreSQL concurrency regression for amendment acknowledgement idempotency.
- [x] PostgreSQL concurrency regression for organization-owned feedback first writes.
- OCR, network, queue and optional local-model latency and resource budgets.

## Phase 8: paid pilot
- Five pilot organizations.
- Weekly quality review.
- Build only features supported by observed usage.
