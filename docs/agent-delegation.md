# ContractFit agent delegation policy

This policy decides what the Codex orchestrator may delegate to the local OpenCode model. It is
based on the repository boundaries in `docs/architecture.md`: extraction and matching share core
domain objects, while API, persistence, review, and organization visibility cross security and
transaction boundaries.

The default delegated model is local `ollama/qwen2.5-coder:7b`, which keeps code on the machine but
has unreliable tool calling in the current OpenCode/Ollama setup. Use it only for self-contained
tasks with supplied context. `opencode/big-pickle` was verified to operate repository tools and
does not consume Codex, but it is an external provider that may receive repository content. It may
be selected only with explicit approval for that task and the script's `-AllowExternalProvider`
flag. Never send secrets, customer documents, private capability statements, or production traces.

## Decision rule

Classify every task before starting it.

### Green: delegate to OpenCode

Delegate when the interface and expected behavior already exist, the allowed files can be named
precisely, and failure is caught by deterministic checks.

- Add or expand tests for behavior already decided by an ADR or existing implementation.
- Add labeled evaluation fixtures without changing metric definitions or matching rules.
- Implement isolated frontend presentation changes against an unchanged API contract.
- Update documentation, examples, type annotations, formatting, or narrowly scoped dead-code
  analysis.
- Add adapters or parsers behind an existing interface when representative fixtures and exact
  acceptance tests are supplied.
- Investigate a bounded question read-only and return file-and-line evidence.
- Review a completed diff read-only for regressions, missing tests, evidence alignment, and tenant
  isolation.

Typical ContractFit examples:

- Add negative and ambiguous extraction examples to the evaluation dataset.
- Add API tests for an already-defined review or compliance endpoint.
- Add Excel fixture tests after the parser contract has been chosen.
- Improve dashboard accessibility or loading states without changing response models.
- Check documentation for commands or endpoint names that no longer match the source.

### Amber: split before delegation

These tasks are delegable only after Codex makes the design decision and freezes the interface.
OpenCode receives one implementation slice with non-overlapping files.

- A new document parser: Codex defines supported formats, evidence coordinates, error behavior,
  fixtures, and interface; OpenCode may implement the parser and focused tests.
- A new API endpoint: Codex defines authorization, organization visibility, request/response
  models, and store contract; OpenCode may implement tests or one layer at a time.
- Persistence behavior without a migration: Codex defines atomicity and isolation; OpenCode may
  implement one adapter after the protocol is fixed.
- Evaluation expansion: Codex defines labels and success thresholds; OpenCode may author cases and
  run the existing evaluator.
- Frontend workflow changes: Codex freezes the API and state transitions; OpenCode may implement
  the view in frontend-only files.

Do not assign an amber task as "implement feature X." First reduce it to an explicit file set and
acceptance contract.

### Red: keep with the Codex orchestrator

Do not delegate ownership of work that can silently change product truth, security, or shared
contracts.

- Architecture decisions, ADR acceptance, scope selection, and final integration.
- Database schema or migration changes and changes to shared Pydantic/API contracts.
- Deterministic eligibility gates, money/date/distance/set-aside logic, ranking weights, and match
  explanations.
- Evidence selection, citation provenance, conflict resolution, and rules that convert missing
  information into satisfied, failed, or unknown states.
- Authentication, authorization, organization visibility, public/private opportunity ownership,
  and cross-tenant behavior.
- Transactions, concurrency control, idempotency, retries, and recovery behavior spanning stores
  or processes.
- Secret handling, production configuration, dependency upgrades with security impact, deployment,
  pushes, merges, releases, and destructive cleanup.
- Final diff review, full verification, cherry-pick, and user handoff.

OpenCode may review or gather evidence about a red area, but it must not be the decision owner or
sole reviewer.

## Current delegation candidates

Use these as the preferred backlog for the local model, subject to a clean worktree and a fresh
task brief:

1. Expand extraction evaluation fixtures toward the roadmap target, one category per task, with
   positive, negative, missing, ambiguous, and contradictory examples. Codex approves labels.
2. Add PostgreSQL-only concurrency test scaffolding for conflicting-review resolution. Codex owns
   the transaction semantics and reviews the result; the test must skip clearly when PostgreSQL is
   unavailable.
3. Audit roadmap and architecture documentation against implemented routes, models, and commands;
   report drift first, then make documentation-only corrections in a separate task.
4. Add frontend accessibility and error-state tests for upload, evidence navigation, and the review
   queue without changing API contracts.
5. Prepare Excel solicitation fixtures and parser acceptance tests. Do not implement the parser
   until Codex defines how sheet/cell coordinates map to `Evidence`.
6. Expand tenant-isolation tests for existing endpoints using current contracts; no source changes
   unless Codex separately approves a verified defect.

## Required task brief

Every delegated task must contain all of the following:

```text
Objective:
Allowed files:
Prohibited changes:
Acceptance criteria:
Verification commands:
Expected handoff: changed files, observed results, limitations, commit hash.
```

If any field is missing, the orchestrator completes the brief before invoking
`tools/opencode/delegate.ps1`.

## Acceptance workflow

1. Codex classifies the task and writes the brief.
2. OpenCode works in `opencode/<task>` in its sibling worktree and commits locally.
3. `contractfit-reviewer` may perform a read-only review, but cannot approve the change alone.
4. Codex inspects the commit and surrounding code, rejects scope expansion, and cherry-picks only
   an acceptable commit.
5. Codex reruns proportional checks in the integration branch and records remaining risks.
