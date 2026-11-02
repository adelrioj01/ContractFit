# ADR 0011: Deterministic amendment comparison

## Status

Accepted

## Context

SAM.gov synchronization preserves immutable normalized snapshots, and analyzed attachments retain
the snapshot hash that produced them. A contractor needs to understand what changed without having
the system silently transfer an old compliance decision to a materially different requirement.
Requirement identifiers are extraction-specific, so identifiers alone cannot establish equivalence
across two documents.

## Decision

Expose a read-only comparison between two snapshots. Catalog fields use exact comparison.
Organization-owned extracted requirements are first matched by normalized category, description,
and mandatory flag. After exact matches, mark a pair changed only when exactly one old and one new
unmatched requirement remain in the same normalized category. Multiple candidates are ambiguous and
remain separate additions and removals.

Every result carries the old and new evidence objects. Comparison reads attachments only from the
authenticated organization and never changes compliance rows automatically. No model is used to
make deterministic equivalence decisions.

## Consequences

- Unchanged, added, removed, and unambiguous changed requirements are reproducible and auditable.
- Two organizations may see different requirement comparisons when only one has analyzed the
  relevant attachments; neither can see the other's extracted evidence.
- Conservative matching may produce extra additions and removals instead of a convenient but
  unsupported changed pair.
- Persisted acknowledgements, semantic suggestions for human confirmation, and selective updates to
  the compliance matrix remain future work.
