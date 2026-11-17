[CmdletBinding()]
param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $repoRoot "backend"
$report = Join-Path $backend "quality-report.json"

function Invoke-Checked {
    param(
        [Parameter(Mandatory)] [string]$Label,
        [Parameter(Mandatory)] [scriptblock]$Command
    )

    Write-Host "`n==> $Label" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

function Test-LocalMarkdownLinks {
    Write-Host "`n==> Documentation links" -ForegroundColor Cyan
    $missing = [System.Collections.Generic.List[string]]::new()
    $markdownFiles = Get-ChildItem -Path $repoRoot -Recurse -File -Filter "*.md" |
        Where-Object { $_.FullName -notmatch '[\\/](\.venv|graphify-out)[\\/]' }

    foreach ($file in $markdownFiles) {
        $content = Get-Content -Raw -LiteralPath $file.FullName
        foreach ($match in [regex]::Matches($content, '!?(?:\[[^\]]*\])\(([^)]+)\)')) {
            $target = $match.Groups[1].Value.Trim()
            if (-not $target -or $target.StartsWith('#') -or $target -match '^[a-z]+://') {
                continue
            }
            $pathPart = [Uri]::UnescapeDataString(($target -split '#', 2)[0]).Trim('<', '>')
            if (-not $pathPart) {
                continue
            }
            $resolved = Join-Path $file.DirectoryName $pathPart
            if (-not (Test-Path -LiteralPath $resolved)) {
                $relativeFile = [IO.Path]::GetRelativePath($repoRoot, $file.FullName)
                $missing.Add("${relativeFile}: $target")
            }
        }
    }

    if ($missing.Count -gt 0) {
        throw "Broken local Markdown links:`n$($missing -join "`n")"
    }
    Write-Host "Local Markdown links are valid."
}

function Test-RepositorySecrets {
    Write-Host "`n==> Tracked and untracked repository secret patterns" -ForegroundColor Cyan
    $patterns = '(?i)(sk-[a-z0-9]{20,}|ghp_[a-z0-9]{20,}|github_pat_[a-z0-9_]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)'
    $matches = [System.Collections.Generic.List[string]]::new()
    $tracked = & git -C $repoRoot ls-files --cached --others --exclude-standard
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to enumerate repository files."
    }
    foreach ($relative in $tracked) {
        $path = Join-Path $repoRoot $relative
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            continue
        }
        $content = Get-Content -Raw -LiteralPath $path -ErrorAction SilentlyContinue
        if ($content -and $content -match $patterns) {
            $matches.Add($relative)
        }
    }
    if ($matches.Count -gt 0) {
        throw "Potential live secret patterns found in repository files: $($matches -join ', ')"
    }
    Write-Host "No high-confidence live secret patterns found."
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required. Install it from https://docs.astral.sh/uv/."
}

Push-Location $backend
try {
    Invoke-Checked "Ruff" { uv run ruff check . }
    Invoke-Checked "Mypy" { uv run mypy src }
    if (-not $SkipTests) {
        Invoke-Checked "Pytest" { uv run pytest }
    }
    Invoke-Checked "Portfolio quality gate" {
        uv run python -m contractfit.quality_cli --output $report
    }
}
finally {
    Pop-Location
}

Test-LocalMarkdownLinks
Test-RepositorySecrets

Write-Host "`nContractFit verification passed." -ForegroundColor Green
