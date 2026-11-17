# ADR 0009: Synthetic multi-company development dataset

## Status

Accepted

## Context

Multi-tenant ranking and onboarding need repeatable test data before sanitized customer profiles
are available. Invented data must not be presented as customer evidence or a live procurement
record.

## Decision

The development seed creates five fixed organizations covering HVAC, janitorial, landscaping,
electrical, and plumbing services. Each organization has its own user, profile, credentials, and
past-performance evidence. A shared `synthetic-demo` opportunity catalog exercises different
territories, set-asides, capacity bands, and scopes.

Organization-owned uploaded documents remain visible only to their owner. Shared synthetic
opportunities contain no customer document or cross-tenant evidence reference. The UI and README
label the dataset as synthetic, and fixed UUIDs make resets reproducible.

## Consequences

- Developers can compare rankings across organizations without using customer information.
- The dataset is suitable for functional and isolation testing, not for accuracy or market claims.
- Replacing a synthetic profile with sanitized customer data requires explicit provenance and
  consent rather than silently editing these fixtures.
