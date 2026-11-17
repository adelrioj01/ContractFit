# ADR 0005: Serialize scheduled SAM.gov synchronization

## Status

Accepted

## Context

ContractFit supports both a long-running SAM.gov scheduler and an operator-triggered `--once`
command. Both entry points can target the same PostgreSQL catalog. The synchronization flow reads
the latest opportunity snapshot before deciding whether to update the opportunity and append a new
snapshot, so overlapping runs could otherwise race and create duplicate history or fail on the
provider-identity constraint.

The SAM identity migration also changes opportunity uniqueness from `source_id` to
`(source, source_id)`. A downgrade cannot restore global `source_id` uniqueness after two providers
have legitimately stored the same identifier.

## Decision

Every production SAM synchronization acquires a PostgreSQL session advisory lock before creating
an ingestion run. The lock is shared by scheduled and one-shot execution and is held until the
entire synchronization finishes. A competing execution fails immediately without writing a
misleading ingestion-run record.

Before downgrading the identity migration, Alembic checks for duplicate `source_id` values. It
aborts before dropping SAM history tables when restoring the old constraint would lose data or
fail partway through the downgrade.

## Consequences

- Only one supported SAM synchronization runs against a database at a time.
- Operators get an explicit error instead of partial duplicate work.
- The migration remains reversible when the old uniqueness invariant still holds.
- Cross-provider identifier collisions require an explicit data decision before downgrade.
