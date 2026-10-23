# Roadmap

## Implemented MVP vertical slice
- [x] Sample facilities-contractor profile.
- [x] Saved solicitation text ingestion.
- [x] Requirement extraction with verbatim line-level evidence.
- [x] Deterministic eligibility gates.
- [x] Hybrid semantic fit scoring with optional local Ollama inference.
- [x] Ranked opportunity dashboard and JSON API.
- [x] Three-case labeled evaluation harness and CI coverage.

The current hardening target is human review and external opportunity ingestion. Persistence,
manual document ingestion, background processing and OCR are implemented end to end.

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
- Authentication and organization boundaries.
- Migrations, logging, tests and CI.

## Phase 2: company profiles
- Services, territory, capacity, licenses, insurance and certifications.
- Past-performance projects and contract preferences.
- Editable structured onboarding.

## Phase 3: ingestion
- [x] Manual PDF, DOCX and TXT opportunity upload.
- SAM.gov adapter.
- [x] Secure attachment storage, SHA-256 hashing and deduplication.
- Amendment snapshots and version history.
- [x] Durable, retryable Redis-backed background processing.

## Phase 4: document intelligence
- [x] Text PDF, Word and plain-text parsing.
- [x] Requirement extraction with page-level evidence.
- [x] Local Tesseract OCR for scanned PDF pages.
- Excel attachment parsing.
- Review queue for low-confidence fields.

## Phase 5: matching
- Deterministic hard gates.
- Weighted scoring.
- Semantic past-performance matching.
- Evidence-grounded explanations.

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
