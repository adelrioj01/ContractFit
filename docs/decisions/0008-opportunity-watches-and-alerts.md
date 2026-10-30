# Organization-owned opportunity watches and deterministic alerts

## Status

Accepted

## Context

SAM.gov opportunities and snapshots are shared catalog data. A company's decision to monitor an
opportunity, notification state, and follow-up history are private workflow data. Synchronization
may replay unchanged records, so alert generation must be idempotent.

## Decision

Store watches and alerts in organization-owned tables. Generate deadline and latest-snapshot
alerts deterministically when the organization opens its alert feed. Deduplicate every alert by
organization and a stable key containing the opportunity, event, date or snapshot hash.

The shared SAM synchronization process does not write customer-owned alert rows. This preserves
the catalog boundary and lets each organization materialize its own feed independently.

## Consequences

- One public opportunity can be watched independently by multiple organizations.
- Replaying an unchanged snapshot or reopening the feed cannot create duplicate alerts.
- Removing a watch removes its alerts through the database relationship.
- In-app alerts work without email infrastructure or model inference.
