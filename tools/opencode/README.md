# OpenCode delegation

This project defaults to the local `ollama/qwen2.5-coder:7b` model, so repository content stays on
the machine and the task does not consume Codex. OpenCode loads the root `AGENTS.md` automatically.
Classify the task with `docs/agent-delegation.md` before creating a worktree.

The local model is suitable mainly for tightly scoped prompts with supplied context: its tool calls
were emitted as text during validation instead of being executed. The free
`opencode/big-pickle` model operated repository tools correctly, but it is an external provider and
may receive repository content. It therefore requires explicit approval per delegated task.

From the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\opencode\delegate.ps1 `
  -Name add-review-tests `
  -Task "Add the specified review tests. Allowed files: backend/tests/test_review.py. Do not edit src. Run the targeted Ruff and pytest commands."
```

To use the external free model after approving that task's code exposure:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\opencode\delegate.ps1 `
  -Name external-task `
  -Model opencode/big-pickle `
  -AllowExternalProvider `
  -Task "..."
```

The script requires a clean orchestrator worktree, creates a sibling worktree and branch named
`opencode/<name>`, and starts the `contractfit-worker` agent. It never merges or pushes. Give the
reported commit hash to the orchestrator for review and cherry-pick.

Use `-NoRun` to create the isolated worktree without starting OpenCode. For a read-only review in
an existing worktree, run:

```powershell
opencode run --agent contractfit-reviewer "Review HEAD~1..HEAD and report prioritized findings."
```
