# Roadmap

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
- Services, territory, capacity, licenses, insurance and certifications.
- Past-performance projects and contract preferences.
- Editable structured onboarding.

## Phase 3: ingestion
- [x] Manual PDF, DOCX and TXT opportunity upload.
- [x] Testable SAM.gov search client with normalized records, pagination and sanitized errors.
- [x] Persisted SAM.gov import workflow with scheduling, deduplication and amendment detection.
- [x] Secure attachment storage, SHA-256 hashing and deduplication.
- [x] Normalized amendment snapshots and version history.
- Fetch and version SAM.gov solicitation attachments.
- [x] Durable, retryable Redis-backed background processing.

## Phase 4: document intelligence
- [x] Text PDF, Word and plain-text parsing.
- [x] Requirement extraction with page-level evidence.
- [x] Local Tesseract OCR for scanned PDF pages.
- Excel attachment parsing.
- [x] Evidence-linked human-review domain model with deterministic priority and audited decisions.
- [x] Organization-scoped persisted review queue and resolution API.
- [x] Basic reviewer dashboard for correcting or dismissing low-confidence fields.
- Replace the dashboard's local reviewer identity with authenticated user identity.

## Phase 5: matching
- [x] Deterministic hard gates.
- [x] Weighted scoring.
- [x] Cached local embeddings and pgvector cosine retrieval for capabilities and scopes.
- [x] Thirty-case semantic ranking baseline with Top-1, Recall@3 and MRR metrics.
- [x] Reproducible CLI runner for lexical and local Ollama embedding evaluation.
- Semantic past-performance matching and expansion to at least 100 labeled ranking cases.
- [x] Evidence-grounded explanations.

## Phase 6: product workflow
- Ranked opportunity dashboard.
- Opportunity details and document viewer.
- Watched opportunities, deadlines and amendments.
- User relevance feedback.

## Phase 7: evaluation and hardening
- At least 100 labeled opportunities.
- Extraction, citation, eligibility and ranking metrics.
- Tenant-isolation and prompt-injection tests.
- Cost and latency budgets.

## Phase 8: paid pilot
- Five pilot organizations.
- Weekly quality review.
- Build only features supported by observed usage.
