# ContractFit agent instructions

## Product objective
ContractFit helps facilities-service contractors identify government opportunities they can realistically pursue. It extracts solicitation requirements with citations, applies deterministic eligibility rules, and produces explainable match rankings.

## Architecture boundaries
- Keep business rules in `backend/src/contractfit/`, not in prompts or UI code.
- Use deterministic code for dates, distances, money, set-aside rules, insurance limits, and hard eligibility gates.
- Use models for structured extraction, semantic comparison, ambiguity detection, and evidence-based explanations.
- Every extracted requirement must preserve document, page or section, supporting text, and confidence.
- Missing mandatory information is `unknown`, never implicitly satisfied.
- All customer-owned records must carry an organization boundary.
- New extraction or matching behavior requires labeled evaluation examples.

## Work rules
- Work only in the directories assigned by the issue.
- Do not commit secrets, customer documents, private capability statements, or production traces.
- Keep pull requests small and independently testable.
- Do not change shared schemas without an architecture decision.
- Run the relevant tests, linting, and type checks before handoff.
- Report files changed, verification commands, limitations, and follow-up work.

## Commands
From `backend/`:

```bash
uv sync --dev
uv run ruff check .
uv run mypy src
uv run pytest
uv run uvicorn contractfit.main:app --reload
```

From the repository root:

```bash
docker compose up --build
```
