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

## Verification and context discipline
- Inspect repository state, source files, diffs, and relevant external documentation before making
  technical claims or choosing an implementation.
- Treat command output, tests, source code, and primary documentation as evidence. Distinguish
  verified facts from inferences, and label any unverified assumption.
- Review every changed diff before handoff. Run checks proportional to the risk of the change and
  never claim that a check passed unless its successful output was observed.
- Recheck branch, working-tree, and test state before reporting completion. State remaining risks,
  skipped checks, and blockers explicitly.
- When roughly 30 percent of the available context has been consumed, or earlier when large outputs
  would waste tokens or memory, replace verbose working history with a compact state summary. Keep
  the objective, user requirements, decisions, verified facts, paths, branch, uncommitted changes,
  test results, blockers, and next actions.
- Use targeted searches and file reads after compaction. Do not repeat completed investigation or
  reload large outputs unless the saved evidence is insufficient.
- If compaction no longer keeps the work reliable, prepare a handoff summary before moving to a new
  chat. Include the objective, branch, repository path, decisions, modified and untracked files,
  verification results, known risks, and the exact next action. Recheck this information against
  Git before creating the successor chat.
- Create a successor chat only when continued work in the current chat risks losing requirements or
  evidence. Carry the compact handoff into the new chat and continue from it instead of restarting
  the investigation.

## Project health reviews
- At sprint boundaries and during scheduled maintenance reviews, inspect Git state, CI or local
  checks, migrations, dependencies, security-sensitive configuration, documentation drift, and the
  main user workflows.
- Search for dead code, obsolete files, duplicated implementations, stale generated artifacts, and
  tests that no longer protect current behavior. Confirm references and ownership before proposing
  removal.
- Do not delete a file because it appears unused from its name or location. Verify imports,
  runtime loading, build configuration, documentation links, and deployment references first.
- Separate safe cleanup from behavior changes. Report evidence, expected impact, and recovery path
  before any destructive cleanup.
- Keep maintenance findings prioritized. Fix verified regressions in scope; record larger product or
  architecture changes as follow-up work instead of expanding the active sprint silently.

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
