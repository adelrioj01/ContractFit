# ADR 0006: Import SAM.gov attachments into an organization workspace

## Status

Accepted

## Context

The public SAM.gov API returns attachment URLs in `resourceLinks`. ContractFit needs the source
files to extract requirements and citations. The catalog opportunity remains shared across
customers, while extracted evidence and review decisions belong to one customer.

Attaching a processed customer document to the shared opportunity would expose its evidence to
other organizations. Downloading the same attachment on each request would also waste bandwidth
and repeat processing.

## Decision

ContractFit stores `resourceLinks` in each immutable SAM snapshot. The API derives the current
attachment list from the latest snapshot and gives each URL a stable SHA-256 identifier.

An authenticated user starts analysis for one attachment. The backend downloads the file from an
HTTPS `sam.gov` host, adds the API key on the server, enforces the upload size and file-type rules,
and stores the file as an organization-owned `SourceDocument`. A separate `document_origins`
association records every catalog opportunity, source URL, and snapshot that produced the document.
This preserves amendment history even when multiple snapshots contain identical bytes. A second
request from the same organization reuses the existing document and job. Another organization
receives its own document and processing history.

## Consequences

- Snapshots preserve attachment-list changes without storing API keys.
- Customer evidence stays inside the customer organization.
- ContractFit accepts PDF, DOCX, and TXT attachments in this phase. ZIP files need a separate
  extraction and archive-safety design.
- Organization, opportunity, source URL, and snapshot hash form the origin idempotency key; binary
  content remains deduplicated by organization and SHA-256.
