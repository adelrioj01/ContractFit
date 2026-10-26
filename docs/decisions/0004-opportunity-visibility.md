# ADR 0004: Separate public catalog data from customer-owned opportunity data

- Status: Accepted
- Date: 2026-10-26

## Context

ContractFit combines opportunities discovered from a public catalog with solicitations uploaded by
customers. A catalog record should be reusable across organizations, while an uploaded solicitation,
its extracted opportunity, processing history, evidence, and review decisions must remain private.
Treating every opportunity as either globally public or organization-owned in the same way would
either duplicate the catalog unnecessarily or expose customer material.

## Decision

An opportunity without a source document is a shared catalog record. An opportunity linked to a
source document inherits that document's organization and is visible only to members of that
organization. Uploaded documents are always organization-owned; public catalog ingestion must not
attach a customer document to a shared record.

Human-review records always belong to the authenticated organization. They may reference a shared
catalog opportunity or an opportunity owned by that organization, but never a private opportunity
from another organization. Every evidence document referenced by a review must also belong to the
review's organization. These rules are enforced at both the API and repository boundaries.

## Consequences

- SAM.gov catalog records can be ingested once and matched independently for every customer.
- Customer uploads, extracted requirements, evidence, and review decisions remain tenant-isolated.
- Unknown and cross-organization identifiers produce the same not-found response at the API edge,
  avoiding disclosure that another customer's record exists.
- Future catalog enrichment that needs stored source evidence must use explicitly public source
  artifacts rather than customer-owned documents.
