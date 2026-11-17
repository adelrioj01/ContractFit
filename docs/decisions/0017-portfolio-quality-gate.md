# ADR 0017: Portfolio quality and latency gate

## Status

Accepted

## Context

ContractFit had separate extraction and ranking tests, but no single command that produced a
machine-readable quality report or failed when measured behavior fell below the documented
baseline. Robustness to instruction-like solicitation text was an assertion in one validation test
rather than a versioned corpus. The PostgreSQL-specific amendment race was reviewed in code but only
exercised with SQLite locally.

## Decision

- Add a deterministic `contractfit.quality_cli` command that evaluates extraction, exact values,
  citations, eligibility, gate decisions, gate-to-citation alignment, lexical ranking and local
  wall-clock latency.
- Require perfect results on the small deterministic extraction and instruction-text corpora. Preserve
  the measured 30-case lexical ranking floor rather than presenting it as production accuracy.
- Use generous 500 ms CI budgets for each local phase. They detect accidental blocking or major
  regressions without treating shared-runner timing as a microbenchmark.
- Keep instruction-like text fixtures separate and explicitly synthetic. In the deterministic
  extractor, such text cannot replace structured fields or evidence. This is not an LLM prompt
  injection or exfiltration test.
- Run the amendment idempotency race against the CI PostgreSQL service, where row locks and unique
  constraint waiting have the production semantics that SQLite cannot reproduce.

## Consequences

- One command produces a JSON report, CI uploads it as an artifact, and regressions return non-zero.
- CI covers a real PostgreSQL concurrency path in addition to SQLite repository tests.
- The latency figures exclude OCR, network access and optional Ollama inference.
- The corpus remains too small for external accuracy claims: extraction has four labeled cases,
  instruction-text robustness has six and ranking has thirty. Expansion to one hundred reviewed ranking
  cases remains roadmap work.
