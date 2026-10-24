# ADR 0001: Persist field-level human reviews

- Status: Accepted
- Date: 2026-10-24

## Context

ContractFit extracts consequential solicitation requirements. Low-confidence values must not be
treated as verified, and reviewers need the original evidence, an auditable decision, and strict
organization scoping. The existing review domain model was transient and could not support a
worker process, restarts, or multiple API instances.

## Decision

Persist each field-level review in `review_items`, with its evidence excerpts in the ordered
`review_evidence` child table. Every repository read requires `organization_id`. An optional
opportunity foreign key uses `SET NULL` so an audit record can survive opportunity deletion, while
evidence retains its source-document reference. A unique organization/opportunity/field constraint
prevents the processing pipeline from producing duplicate review work.

Pending items are immutable domain values. Resolution and dismissal create validated terminal
copies that record reviewer identity and timestamps. API callers supply organization and reviewer
IDs for the current prototype; authenticated identity will replace these caller-supplied values.

## Consequences

- Background workers and API instances share one durable review queue.
- Evidence and decisions remain inspectable after restart.
- Organization filtering is enforced in both in-memory and SQL repositories.
- Deleting a source document referenced as evidence remains restricted.
- Authentication remains required before multi-tenant production use.
