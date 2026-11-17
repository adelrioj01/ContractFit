# Contributing to ContractFit

ContractFit favors small, evidence-backed changes. Read `AGENTS.md` and the relevant architecture
decision before editing behavior.

## Development setup

```bash
cd backend
uv sync --dev
uv run ruff check .
uv run mypy src
uv run pytest
```

Docker-backed development starts from the repository root with `docker compose up --build`.

## Change requirements

- Keep deterministic business rules out of prompts and UI code.
- Preserve the organization boundary on customer-owned records.
- Preserve document, page or section, supporting text, and confidence for extracted requirements.
- Treat missing mandatory information as unknown and reviewable, never implicitly satisfied.
- Add labeled positive, negative, missing, ambiguous, or contradictory examples when changing
  extraction or matching behavior.
- Add an architecture decision before changing a shared schema or a major system boundary.
- Do not commit secrets, customer documents, private profiles, or production traces.

## Before opening a pull request

Run `./scripts/verify.ps1` on PowerShell or run the backend checks individually. Describe:

1. The problem and bounded scope.
2. Files and behavior changed.
3. Verification commands and observed results.
4. Data, security, migration, and organization-isolation implications.
5. Known limitations and follow-up work.

The CI PostgreSQL job verifies migrations, pgvector search, and concurrent amendment
acknowledgement against an isolated test database.
