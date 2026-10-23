# Roadmap

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
- Manual opportunity upload.
- SAM.gov adapter.
- Attachment hashing, deduplication and snapshots.
- Retryable background processing.

## Phase 4: document intelligence
- PDF, scanned PDF, Word and Excel parsing.
- Requirement extraction with page-level evidence.
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
