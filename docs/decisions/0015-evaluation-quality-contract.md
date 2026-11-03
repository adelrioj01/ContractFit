# ADR 0015: Evaluate structured values, gates, and citation alignment

## Status

Accepted

## Context

The end-to-end evaluation dataset records expected requirement categories and overall eligibility.
Its extraction metric therefore treats an incorrect value as correct when the category exists, and
its citation metric only checks that cited text occurs somewhere in the document. It does not
verify individual gate outcomes or that a gate cites the text supporting the value it evaluated.

Expanding this weak contract to one hundred cases would increase case count without protecting the
product invariants around unknown mandatory information and evidence-grounded decisions.

## Decision

- Label expected extracted requirements with category, exact extracted value, and exact supporting
  text. Compare labels as multisets so missing, duplicated, and unexpected requirements reduce the
  score.
- Label every deterministic gate exercised by a case with its expected status and expected
  supporting text, including an explicit null citation for unknown values.
- Preserve the existing extraction-recall, citation-validity, and overall-eligibility metrics for
  compatibility.
- Add structured-value accuracy, gate accuracy, and gate-citation alignment to the evaluation
  report.
- Treat labels as product decisions. Agents may propose cases, but the orchestrator approves their
  expected values, statuses, and citations before integration.

## Consequences

Evaluation cases require more careful labeling, but failures identify whether extraction,
deterministic matching, or evidence selection regressed. The dataset should reach the roadmap's
one-hundred-case target only after this richer contract is stable.
