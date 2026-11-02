# ADR 0010: Organization-owned compliance workspace

## Status

Accepted

## Context

Requirements extracted from a solicitation are source facts, but each company makes its own
coverage decision, assigns its own staff, and supplies its own evidence. Storing those decisions on
the shared opportunity or extracted requirement would expose private bid work across organizations.
Generating company claims from solicitation text would also violate ContractFit's evidence-first
boundary.

## Decision

Persist one editable compliance item per organization and extracted requirement. The item copies
the requirement description and original document citation for audit stability, while status,
mandatory/recommended priority, responsible user, due date, notes, and explicit business-evidence
references remain organization-owned. Initialization is deterministic and is allowed only after
the organization marks the opportunity `pursue` or advances it further in the pipeline.

The source citation is immutable through the compliance API. Business evidence is supplied by the
user as an explicit reference; ContractFit does not infer that the company satisfies a requirement.

## Consequences

- Two organizations can pursue the same catalog opportunity without sharing compliance decisions.
- Every matrix row remains traceable to the extracted requirement, document, page or section, and
  supporting text.
- A source document referenced by a compliance item cannot be deleted while the item exists.
- Compliance export and the later read-only amendment comparison use stable opportunity,
  requirement, document, and snapshot identifiers without mutating existing decisions.
- This first UI supports one explicit business-evidence description per row; richer selection from
  profiles, past performance, and uploaded company documents remains follow-up work.
