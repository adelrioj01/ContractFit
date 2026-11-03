# ADR 0016: Persist selected amendment applications

## Status

Accepted

## Context

Amendment comparison is deterministic and read-only, but a proposal team must record which changes
it reviewed and deliberately carry selected changes into its private compliance workspace. Copying
old coverage decisions to changed requirements would claim unsupported business evidence.

## Decision

Persist one organization-owned acknowledgement for each opportunity and ordered snapshot pair. The
API recomputes the comparison at write time and accepts only material requirement pairs present in
that comparison. Acknowledgements record the reviewer, timestamp, snapshots and canonicalized exact
selections. Only organization administrators may apply the change to the workspace.

Applying a selected removal marks an existing compliance row `not_applicable`. Applying an addition
creates a `pending` row with the new source citation. A changed requirement performs both actions:
the old row remains as auditable history and the new row starts pending without inherited business
evidence. Compliance updates and the acknowledgement are committed together by the repository.
The SQL repository locks affected rows and updates only the superseded status and timestamp, so a
concurrent edit cannot be erased by a stale full-row copy. If concurrent identical acknowledgements
meet the unique constraint, the losing request reads and returns the committed winner.

## Consequences

- No model or browser-provided description can invent an amendment relationship.
- Organizations acknowledge the same public amendment independently.
- Repeating the same acknowledgement is idempotent; a different selection for an acknowledged pair
  is rejected instead of silently rewriting the audit record.
- Old coverage, ownership and notes remain attached to the superseded row, while new requirements
  require fresh human evidence.
- Metadata-only changes remain visible in comparison but do not mutate compliance rows.
- Tenant relationships are enforced by repository validation as well as ordinary foreign keys. Any
  future external database writer must use the same service boundary or add composite database
  constraints before writing these records directly.
