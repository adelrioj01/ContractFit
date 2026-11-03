# OpenCode delegation

This project uses the local `ollama/qwen2.5-coder:7b` model for bounded delegated work. OpenCode
loads the root `AGENTS.md` automatically.

From the repository root:

```powershell
.\tools\opencode\delegate.ps1 `
  -Name add-review-tests `
  -Task "Add the specified review tests. Allowed files: backend/tests/test_review.py. Do not edit src. Run the targeted Ruff and pytest commands."
```

The script requires a clean orchestrator worktree, creates a sibling worktree and branch named
`opencode/<name>`, and starts the `contractfit-worker` agent. It never merges or pushes. Give the
reported commit hash to the orchestrator for review and cherry-pick.

Use `-NoRun` to create the isolated worktree without starting OpenCode. For a read-only review in
an existing worktree, run:

```powershell
opencode run --agent contractfit-reviewer "Review HEAD~1..HEAD and report prioritized findings."
```
