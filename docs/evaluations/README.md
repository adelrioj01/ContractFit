# Versioned evaluation evidence

These artifacts record reproducible synthetic regression baselines. They are checked into the
repository so portfolio claims can be audited without running optional model infrastructure.

| Artifact | Command | Provider |
|---|---|---|
| `quality-baseline.json` | `uv run python -m contractfit.quality_cli --output quality-report.json` | Deterministic extraction and lexical ranking |
| `lexical-ranking-baseline.json` | `uv run python -m contractfit.ranking_cli --provider lexical` | Lexical fallback |

The checked-in values were reproduced on 2026-11-04. Wall-clock timings vary by machine and should
not be compared as service-level objectives. No Ollama artifact is included because a successful,
version-recorded model run was not performed for this documentation update.

When updating an artifact, record the date, Git commit, dataset size, provider/model, command, and
environment notes in this file. Never add customer data, private prompts, credentials, or production
traces.
