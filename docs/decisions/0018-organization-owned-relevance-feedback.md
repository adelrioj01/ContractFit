# ADR 0018: Persist organization-owned relevance feedback

## Status

Accepted

## Context

Contractors need to mark catalog opportunities as relevant, not relevant, or uncertain without
changing the shared opportunity or deterministic ranking. The repository already contains an
unfinished feedback model and API tests, but no route, store contract, adapters, persistence,
migration, or browser integration. Feedback is private workflow data and must not leak across
organizations.

## Decision

Persist at most one feedback record per organization and opportunity. Public catalog opportunities
may be rated independently by every organization. An opportunity backed by an uploaded document
may be rated only by the organization that owns that document. Use the existing
`ContractFitStore.get_opportunity(opportunity_id, organization_id)` visibility rule before every
feedback read or write; an unknown or invisible opportunity returns `404`.

The authenticated HTTP contract is:

- `GET /api/opportunities/{opportunity_id}/feedback` returns the caller's record or `404` when the
  visible opportunity has no record.
- `PUT /api/opportunities/{opportunity_id}/feedback` accepts `rating` and optional `reason`, then
  creates or replaces the caller organization's record and returns it with `200`.
- `rating` is exactly `relevant`, `not_relevant`, or `unsure`. `reason` is nullable and limited to
  1,000 characters. Authentication failures return `401`; request validation failures return
  `422`.

The response is `OpportunityFeedback`: `id`, `organization_id`, `opportunity_id`, `rating`,
`reason`, `submitted_by_user_id`, `created_at`, and `updated_at`. An update preserves `id` and
`created_at`, records the current user as the latest submitter, and advances `updated_at`. Repeating
the same request is safe and returns the existing logical record.

Add these methods to `ContractFitStore` and both adapters:

```python
def get_opportunity_feedback(
    self, opportunity_id: UUID, organization_id: UUID
) -> OpportunityFeedback | None: ...

def save_opportunity_feedback(
    self, feedback: OpportunityFeedback
) -> OpportunityFeedback: ...
```

`save_opportunity_feedback` is an organization/opportunity upsert. Both adapters preserve the
existing identity and creation time on update. The SQL adapter handles a concurrent first write by
returning the row that wins the database uniqueness constraint rather than exposing an integrity
error.

Create an `opportunity_feedback` table with a UUID primary key, organization, opportunity and user
foreign keys, rating, nullable reason, and timezone-aware creation and update timestamps. Enforce a
unique constraint on `(organization_id, opportunity_id)` and indexes needed for that lookup. The
Alembic migration is the only schema-change mechanism; downgrade removes only this table and its
indexes or constraints.

The dashboard adds one compact feedback control to the opportunity detail view: three rating
choices and an optional reason. It loads the current organization's record, treats feedback `404`
as an empty state, saves through the frozen `PUT` contract, exposes progress and errors accessibly,
and does not alter ranking, pipeline status, compliance, or opportunity data.

## Verification contract

Implementation is complete only when:

- the existing `backend/tests/test_feedback_api.py` cases pass for memory and SQL adapters;
- focused tests prove stable identity and timestamps on update, private-opportunity isolation, and
  concurrent or duplicate first-write behavior;
- dashboard tests cover load, empty state, save, validation/error presentation, and keyboard and
  label accessibility;
- `alembic upgrade head`, `alembic check`, and downgrade/upgrade validation pass against PostgreSQL;
- `./scripts/verify.ps1` passes without excluding feedback tests.

## Consequences

- Feedback remains organization-owned even when the opportunity is public.
- Feedback cannot silently influence deterministic eligibility or ranking; using it for learning or
  evaluation requires a separate decision with labeled-data and privacy rules.
- The API and store changes are a coordinated contract surface. Backend, frontend, and integration
  work may proceed separately only after this ADR is accepted and must stop if implementation
  requires a different contract or migration.
- No list, delete, history, analytics, or administrator endpoint is included in this slice.
