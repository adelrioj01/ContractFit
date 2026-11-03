# ADR 0012: Resolve conflicting private-opportunity scalars atomically

## Status

Accepted

## Context

Extraction preserves every cited requirement and represents contradictory deadline, location,
set-aside, or value fields as unknown on the opportunity. The review queue previously emitted one
low-confidence item per requirement, so a reviewer could not make one explicit choice for the
conflicted field. Resolving a review also recorded only the decision and did not update the scalar
used by deterministic matching.

An organization can view both document-owned opportunities and public catalog opportunities. A
review owned by one organization must not mutate a public opportunity shared with other tenants.
Updating a private opportunity and its review in separate store calls would also permit partial
writes.

## Decision

- Group contradictory scalar requirements into one `CONFLICTING_VALUES` review per opportunity
  field, preserving all source evidence in document order.
- Use stable field names prefixed with `opportunity:` and an explicit allowlist for deadline,
  place of performance, set-aside, and estimated value.
- Accept only deterministic corrections that normalize to one of the extracted, evidence-backed
  candidates. Store a deterministic candidate snapshot on the review and require the current
  requirement to retain matching evidence before applying it. Refresh pending stale reviews after
  re-extraction. Keep the original requirements and evidence immutable.
- Apply the corrected scalar and terminal review audit fields through one store operation. The SQL
  implementation performs both updates in one database transaction; the in-memory implementation
  validates both results before replacing either object.
- Reject organization-owned corrections to public opportunities. A future organization-scoped
  override for public catalog data requires a separate data-model decision.

## Consequences

Matching can consume a reviewed private scalar while retaining the exact extracted evidence for
the selected candidate. Invalid, stale, cross-organization, or unsupported corrections leave both
records unchanged. No database migration is required.

The current decision does not define public-catalog overrides or automatic reapplication of a
resolved correction after re-extraction. Those behaviors remain follow-up work and must not be
implemented by mutating shared catalog rows.
