# ADR 0008: Structured company profile evidence

## Status

Accepted

## Context

ContractFit cannot produce trustworthy company-specific rankings when a new organization has no
structured capability profile. Treating missing data as a failed requirement would also create
false no-go decisions.

## Decision

Company profiles store services, territory, capacity, credentials, insurance, contract
preferences, and structured past-performance projects. Profile completeness is reported separately
from eligibility. Missing past performance produces `needs_review`; it never produces an automatic
hard-gate failure. Matching explanations name the recorded project that supports relevant
experience.

The organization in the access token remains the sole owner of the profile. Client-supplied profile
and organization identifiers are ignored on update.

## Consequences

- New customers can configure matching without modifying seed data.
- Rankings expose missing proof instead of presenting false certainty.
- Past-performance similarity is deliberately deterministic in this phase; semantic retrieval can
  replace its token overlap only after a labeled evaluation set exists.
