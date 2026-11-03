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

## Agent orchestration
- Use a single orchestrator as the owner of scope, context, integration, verification, and final
  handoff. The orchestrator must inspect repository state and relevant instructions before
  delegating work.
- Delegate only work that can be assigned with clear ownership and acceptance criteria. Prefer one
  worker for small changes; use multiple workers only for independent areas with non-overlapping
  files or explicitly coordinated interfaces.
- Give every worker an assigned directory or file set, a concrete deliverable, prohibited changes,
  and required verification. Use separate Git worktrees for concurrent implementation when
  workers would otherwise share a working tree.
- Keep business-rule decisions, schema changes, and final integration with the orchestrator. Do not
  let agents silently expand scope or introduce a shared-schema change without an architecture
  decision.
- Use independent reviewers for evidence correctness, deterministic rules, organization isolation,
  tests, and regression risk. Reviewers start read-only and must report findings with file and line
  evidence; they do not approve work with a generic summary.
- An agent must not be the sole reviewer of its own implementation. Reviewer output is advisory;
  deterministic checks, labeled evaluations, observed command output, and final diff review are
  the acceptance authority.
- Integrate worker changes sequentially. Resolve overlaps deliberately, rerun relevant checks after
  integration, and have the orchestrator inspect the complete diff before handoff.
- For extraction or matching work, assign or perform a dedicated evaluation review. New behavior
  must include labeled positive, negative, missing, ambiguous, and contradictory examples as
  applicable.

## Orchestrator context lifecycle
- The orchestrator owns context accounting. At roughly 30 percent context consumption, or sooner
  when large outputs reduce reliability, replace verbose history with a compact working summary.
- A compact summary must preserve the objective, user requirements, orchestration decisions,
  verified facts, repository path, branch, assigned agents and their status, modified and untracked
  files, observed verification results, blockers, risks, and exact next actions.
- After compaction, use targeted graph queries, searches, and file reads. Do not repeat completed
  investigation or reload large outputs unless the compact evidence is insufficient.
- Create a successor chat only when another compaction would no longer preserve reliable execution
  or when the current chat is approaching its practical context limit. Before creating it, recheck
  Git state, agent status, diffs, and verification results, then prepare the same compact handoff.
- The successor chat must continue from the handoff rather than restart investigation. It must
  confirm the repository, branch, worktree, outstanding changes, and exact next action before
  making edits.
- Chat creation and compaction depend on host support. If the host cannot create a successor chat
  automatically, prepare the complete handoff and ask the user to open the new chat with that
  handoff; never claim that a chat was created when it was not.

## OpenCode delegation
- Prefer `tools/opencode/delegate.ps1` when delegating bounded implementation or test work to the
  local OpenCode model. The script must run only from a clean orchestrator worktree.
- Give OpenCode explicit allowed files, prohibited changes, acceptance criteria, and verification
  commands. Keep architecture decisions, schema changes, integration, and final acceptance with
  the Codex orchestrator.
- OpenCode works in its own `opencode/<task>` branch and sibling worktree. It must commit locally,
  report its commit hash, and never push or merge. The orchestrator reviews the diff and
  cherry-picks only accepted commits.
- Use `contractfit-reviewer` for an independent read-only pass. A local-model review is advisory;
  observed tests, deterministic evaluations, and orchestrator diff review remain authoritative.

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
