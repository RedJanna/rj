param(
    [string]$RepoPath = "C:\KassandraOpenAI",
    [string]$Branch = "main",
    [string]$CommitMessage = "chore: auto checkpoint",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Run-Git {
    param([string[]]$CmdArgs)
    git -C $RepoPath @CmdArgs
}

if (-not (Test-Path $RepoPath)) {
    Write-Error "Repo path not found: $RepoPath"
}

if (-not (Test-Path (Join-Path $RepoPath ".git"))) {
    Write-Error "Not a git repository: $RepoPath"
}

$currentBranch = (Run-Git -CmdArgs @("rev-parse", "--abbrev-ref", "HEAD")).Trim()
if ($currentBranch -ne $Branch) {
    Write-Host "Switching branch: $currentBranch -> $Branch"
    if (-not $DryRun) {
        Run-Git -CmdArgs @("checkout", $Branch) | Out-Null
    }
}

Write-Host "Fetching origin/$Branch..."
if (-not $DryRun) {
    Run-Git -CmdArgs @("fetch", "origin", $Branch) | Out-Null
}

Write-Host "Staging changes..."
if (-not $DryRun) {
    Run-Git -CmdArgs @("add", "-A") | Out-Null
}

if (-not $DryRun) {
    & git -C $RepoPath diff --cached --quiet
    if ($LASTEXITCODE -eq 0) {
        Write-Host "No changes to commit."
        exit 0
    }
}

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$finalMessage = "$CommitMessage ($timestamp)"

Write-Host "Committing: $finalMessage"
if (-not $DryRun) {
    Run-Git -CmdArgs @("commit", "-m", $finalMessage) | Out-Null
}

Write-Host "Rebasing on origin/$Branch..."
if (-not $DryRun) {
    Run-Git -CmdArgs @("pull", "--rebase", "origin", $Branch) | Out-Null
}

Write-Host "Pushing to origin/$Branch..."
if (-not $DryRun) {
    Run-Git -CmdArgs @("push", "origin", $Branch) | Out-Null
}

Write-Host "Done."
