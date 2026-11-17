# Portfolio evaluation

ContractFit exposes a reproducible regression gate rather than claiming accuracy from screenshots
or anecdotal examples.

Run it from `backend/`:

```bash
uv run python -m contractfit.quality_cli --output quality-report.json
```

The command exits with status 1 if extraction, evidence alignment or instruction-text behavior is no
longer exact, if lexical ranking falls below its recorded baseline, or if a deterministic phase
exceeds its latency budget. CI uploads the same machine-readable report as a workflow artifact.

## Observed local baseline

Reproduced on 2026-11-04 in the development environment:

| Evaluation | Cases | Result | Observed latency |
|---|---:|---:|---:|
| Extraction, eligibility and citations | 4 | all six metrics `1.0` | 1.890 ms |
| Deterministic instruction-text corpus | 6 | all six metrics `1.0` | 0.842 ms |
| Lexical ranking | 30 | Top-1 `0.3667`, Recall@3 `0.4333`, MRR `0.5306` | 0.886 ms |

The per-phase CI budget is 500 ms. These observed timings are machine-specific. The deliberately
broad threshold detects blocking work and large regressions; it is not a hardware-neutral
performance claim.

Versioned copies of the reproducible results are under [`docs/evaluations/`](evaluations/README.md).

## What the tests demonstrate

- Exact structured values and citations are checked, not only requirement categories.
- Missing mandatory information remains `needs_review` rather than being inferred as satisfied.
- Instructions embedded in solicitation text do not invent fields, evidence or eligibility.
- Customer records remain scoped to the authenticated organization in API and repository tests.
- CI runs pgvector retrieval and concurrent amendment acknowledgement against PostgreSQL 17.

## Honest limitations

- All bundled labels are synthetic regression fixtures, not customer data.
- The four-case extraction corpus is useful for invariants but too small for an accuracy claim.
- The instruction-text corpus exercises the deterministic extractor, not LLM prompt injection,
  encoding attacks, role-boundary attacks or data exfiltration.
- The ranking corpus has 30 cases; the roadmap target is 100 human-reviewed cases.
- Latency excludes OCR, SAM.gov calls, SMTP, Redis queue time and optional Ollama inference.
- The PostgreSQL integration checks run in CI or only when `DATABASE_URL` names a migrated database
  ending in `_test` and `CONTRACTFIT_ALLOW_TEST_DB_RESET=1`. They are skipped by default.
