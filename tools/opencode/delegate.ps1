[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-z0-9][a-z0-9-]*$')]
    [string]$Name,

    [Parameter(Mandatory = $true)]
    [string]$Task,

    [string]$Model = 'ollama/qwen2.5-coder:7b',

    [switch]$AllowExternalProvider,

    [switch]$NoRun
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$repositoryName = Split-Path $repositoryRoot -Leaf
$worktreePath = Join-Path (Split-Path $repositoryRoot -Parent) "$repositoryName-opencode-$Name"
$branchName = "opencode/$Name"

if ($Model.StartsWith('opencode/') -and -not $AllowExternalProvider) {
    throw 'OpenCode-hosted models may receive repository content. Pass -AllowExternalProvider only after explicit approval.'
}

$status = git -C $repositoryRoot status --porcelain
if ($LASTEXITCODE -ne 0) {
    throw 'Unable to inspect the ContractFit repository.'
}
if ($status) {
    throw 'The orchestrator worktree must be clean before delegation.'
}
if (Test-Path -LiteralPath $worktreePath) {
    throw "Worktree path already exists: $worktreePath"
}

git -C $repositoryRoot worktree add -b $branchName $worktreePath HEAD
if ($LASTEXITCODE -ne 0) {
    throw 'Unable to create the OpenCode worktree.'
}

$prompt = @"
Read AGENTS.md first. You are working in the isolated branch $branchName.

$Task

Do not push or merge. Commit the completed, verified change locally and report the commit hash.
"@

Write-Host "Worktree: $worktreePath"
Write-Host "Branch:   $branchName"

if ($NoRun) {
    Write-Host 'OpenCode was not started because -NoRun was supplied.'
    exit 0
}

Push-Location $worktreePath
try {
    opencode run --model $Model --agent contractfit-worker --title "ContractFit: $Name" $prompt
    if ($LASTEXITCODE -ne 0) {
        throw "OpenCode exited with code $LASTEXITCODE. The worktree was preserved."
    }
}
finally {
    Pop-Location
}

Write-Host "Review the result, then integrate it with: git cherry-pick <commit-hash>"
