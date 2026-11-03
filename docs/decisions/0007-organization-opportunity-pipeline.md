# ADR 0007: Organization-owned opportunity pipeline

## Status

Accepted

## Context

SAM.gov opportunities are a shared catalog, while bid decisions, assignments, notes, and next
actions are private customer data. Adding workflow fields directly to an opportunity would leak one
organization's decisions into another organization's view and would prevent independent workflows.

## Decision

Store workflow in a separate `pipeline_items` table with a mandatory organization boundary and a
unique `(organization_id, opportunity_id)` relationship. Public and uploaded opportunities keep
their existing visibility rules. An organization may add only an opportunity it can already see.

Pipeline status is deterministic and limited to `new`, `evaluating`, `pursue`, `no_go`,
`preparing_bid`, and `submitted`. Assignment is an optional user reference; removing a user clears
the assignment without deleting the pipeline item.

## Consequences

- Multiple organizations can track the same public opportunity without sharing workflow data.
- Pipeline API operations must always derive organization ownership from the access token.
- Opportunity deletion removes its workflow entries; organization deletion removes all its entries.
- Amendment alerts can later attach to the organization-owned pipeline item without changing the
  shared SAM.gov catalog.
