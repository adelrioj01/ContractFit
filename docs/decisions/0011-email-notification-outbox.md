# ADR 0011: Organization-owned email notification outbox

## Status

Accepted

## Context

In-app alerts are private customer workflow data, but users may not keep ContractFit open. Email
delivery must not block SAM synchronization or API requests, and retries must never duplicate a
message for the same organization and alert.

## Decision

Store one notification preference per organization and one immutable email delivery per
organization-alert pair. An opt-in worker refreshes watched-opportunity alerts, materializes only
alerts created after opt-in, and sends claimed deliveries only when both SMTP and the explicit
sending flag are configured. Development keeps messages pending and inspectable instead of
pretending they were sent.

Templates are deterministic and contain no model-generated claims. Delivery attempts, failures,
timestamps, recipient and final status remain auditable.

## Consequences

- Customer recipients and delivery history remain organization-scoped.
- API and ingestion processes do not depend on SMTP availability.
- A transactional claim prevents concurrent workers from taking the same row. SMTP itself provides
  at-least-once delivery: a process crash after remote acceptance but before recording success can
  still duplicate a message, so the product does not claim exact-once email delivery.
- Disabling or changing preferences cancels incompatible pending deliveries before transmission.
- A failed delivery can be retried up to a bounded attempt limit without duplicating outbox rows.
- Daily digest grouping and provider-specific authentication remain future increments.
