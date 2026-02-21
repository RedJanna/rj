[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "Medium")]
param(
    [string]$RepoPath = "C:\KassandraOpenAI",
    [string]$Remote = "origin",
    [string]$Branch = "main",
    [string]$CommitMessage = "chore: auto checkpoint",
    [string[]]$IncludePath,
    [string[]]$ExcludePath,
    [switch]$NoCommit,
    [switch]$Amend,
    [switch]$AllowEmpty,
    [switch]$DryRun,
    [switch]$SkipSecretScan,
    [int]$RetryCount = 3,
    [int]$RetryDelaySec = 2,
    [int]$NetworkTimeoutSec = 60,
    [string]$LogDir = "logs"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $RepoPath)) {
    Write-Error "Repo path not found: $RepoPath"
}

$resolvedRepoPath = (Resolve-Path -LiteralPath $RepoPath).Path
$resolvedLogDir = Join-Path $resolvedRepoPath $LogDir
New-Item -ItemType Directory -Path $resolvedLogDir -Force | Out-Null
$logPath = Join-Path $resolvedLogDir ("auto_commit_push-{0}.log" -f (Get-Date -Format "yyyyMMdd-HHmmss"))

function Write-Log {
    param(
        [string]$Message,
        [ValidateSet("INFO", "WARN", "ERROR")]
        [string]$Level = "INFO"
    )
    $entry = "[{0}] [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Level, $Message
    Write-Host $entry
    Add-Content -Path $logPath -Value $entry
}

function Invoke-Git {
    param(
        [string[]]$CmdArgs,
        [int]$TimeoutSec = 30
    )

    $stdoutFile = [System.IO.Path]::GetTempFileName()
    $stderrFile = [System.IO.Path]::GetTempFileName()
    try {
        $argList = @("-C", $resolvedRepoPath) + $CmdArgs
        $proc = Start-Process -FilePath "git" -ArgumentList $argList -PassThru -NoNewWindow -RedirectStandardOutput $stdoutFile -RedirectStandardError $stderrFile

        if (-not $proc.WaitForExit($TimeoutSec * 1000)) {
            try { $proc.Kill() } catch {}
            throw "git timed out after ${TimeoutSec}s: git $($CmdArgs -join ' ')"
        }

        $stdoutRaw = Get-Content -Path $stdoutFile -Raw -ErrorAction SilentlyContinue
        $stderrRaw = Get-Content -Path $stderrFile -Raw -ErrorAction SilentlyContinue
        $stdout = if ($null -eq $stdoutRaw) { "" } else { ([string]$stdoutRaw).Trim() }
        $stderr = if ($null -eq $stderrRaw) { "" } else { ([string]$stderrRaw).Trim() }

        $exitCode = if ($null -eq $proc.ExitCode) { 0 } else { [int]$proc.ExitCode }

        if ($exitCode -ne 0) {
            if ([string]::IsNullOrWhiteSpace($stderr)) {
                throw "git exited with code ${exitCode}: git $($CmdArgs -join ' ')"
            }
            throw "git exited with code ${exitCode}: git $($CmdArgs -join ' ')`n$stderr"
        }
        return $stdout
    }
    finally {
        Remove-Item -Path $stdoutFile, $stderrFile -ErrorAction SilentlyContinue
    }
}

function Invoke-GitWithRetry {
    param(
        [string]$OperationName,
        [string[]]$CmdArgs
    )
    for ($attempt = 1; $attempt -le $RetryCount; $attempt++) {
        try {
            return Invoke-Git -CmdArgs $CmdArgs -TimeoutSec $NetworkTimeoutSec
        }
        catch {
            if ($attempt -ge $RetryCount) {
                throw
            }
            Write-Log "$OperationName failed (attempt $attempt/$RetryCount): $($_.Exception.Message). Retrying in $RetryDelaySec sec..." "WARN"
            Start-Sleep -Seconds $RetryDelaySec
        }
    }
}

function Invoke-Step {
    param(
        [string]$Description,
        [scriptblock]$Action
    )
    if ($DryRun) {
        Write-Log "DRY-RUN: $Description"
        return
    }
    if ($PSCmdlet.ShouldProcess($resolvedRepoPath, $Description)) {
        & $Action
    }
}

function Test-RemoteExists {
    param([string]$RemoteName)
    & git -C $resolvedRepoPath remote get-url $RemoteName *> $null
    return ($LASTEXITCODE -eq 0)
}

function Test-LocalBranchExists {
    param([string]$BranchName)
    try {
        Invoke-Git -CmdArgs @("show-ref", "--verify", "--quiet", "refs/heads/$BranchName") -TimeoutSec 15 | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Test-RemoteBranchExists {
    param([string]$RemoteName, [string]$BranchName)
    $result = & git -C $resolvedRepoPath ls-remote --heads $RemoteName "refs/heads/$BranchName" 2>$null
    return ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace(($result | Out-String)))
}

function Get-RemoteDefaultBranch {
    param([string]$RemoteName)
    $symref = & git -C $resolvedRepoPath ls-remote --symref $RemoteName HEAD 2>$null
    if ($LASTEXITCODE -ne 0) {
        return $null
    }
    $match = [regex]::Match(($symref | Out-String), 'ref:\s+refs/heads/([^\s]+)\s+HEAD')
    if ($match.Success) {
        return $match.Groups[1].Value
    }
    return $null
}

function Run-SecretScan {
    $stagedFilesRaw = Invoke-Git -CmdArgs @("diff", "--cached", "--name-only")
    if ([string]::IsNullOrWhiteSpace($stagedFilesRaw)) {
        return
    }

    $stagedFiles = $stagedFilesRaw -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    $sensitiveNamePattern = '(?i)(^|[\\/])(\.env(\..+)?|id_rsa|id_dsa|.*\.(pem|p12|pfx|key))$'
    $contentPatterns = @(
        'AKIA[0-9A-Z]{16}',
        '(?i)-----BEGIN [A-Z ]*PRIVATE KEY-----',
        '(?i)(api[_-]?key|access[_-]?token|secret[_-]?key|password)\s*[:=]\s*[''"][^''"]{8,}[''"]'
    )

    $findings = New-Object System.Collections.Generic.List[string]

    foreach ($file in $stagedFiles) {
        if ($file -match $sensitiveNamePattern) {
            $findings.Add("Sensitive filename pattern detected: $file")
        }
        $fullPath = Join-Path $resolvedRepoPath $file
        if (-not (Test-Path -LiteralPath $fullPath)) {
            continue
        }

        foreach ($pattern in $contentPatterns) {
            try {
                $match = Select-String -Path $fullPath -Pattern $pattern -SimpleMatch:$false -ErrorAction Stop
                if ($match) {
                    $findings.Add("Sensitive content pattern detected in: $file")
                    break
                }
            }
            catch {
                # Skip unreadable/binary files.
            }
        }
    }

    if ($findings.Count -gt 0) {
        $message = "Secret scan blocked commit:`n - " + ($findings -join "`n - ")
        throw $message
    }
}

if (-not (Test-Path (Join-Path $resolvedRepoPath ".git"))) {
    Write-Error "Not a git repository: $resolvedRepoPath"
}

Write-Log "Starting auto commit/push for $resolvedRepoPath"

if (-not (Test-RemoteExists -RemoteName $Remote)) {
    Write-Error "Remote '$Remote' not found in repository."
}

$remoteBranchExists = Test-RemoteBranchExists -RemoteName $Remote -BranchName $Branch
$localBranchExists = Test-LocalBranchExists -BranchName $Branch

if (-not $remoteBranchExists -and -not $localBranchExists) {
    $fallbackBranch = Get-RemoteDefaultBranch -RemoteName $Remote
    if (-not [string]::IsNullOrWhiteSpace($fallbackBranch)) {
        Write-Log "Branch '$Branch' not found. Falling back to remote default branch '$fallbackBranch'." "WARN"
        $Branch = $fallbackBranch
        $remoteBranchExists = Test-RemoteBranchExists -RemoteName $Remote -BranchName $Branch
        $localBranchExists = Test-LocalBranchExists -BranchName $Branch
    }
}

if (-not $remoteBranchExists -and -not $localBranchExists) {
    Write-Error "Branch '$Branch' does not exist locally or on '$Remote', and remote default branch could not be resolved."
}

$currentBranch = (Invoke-Git -CmdArgs @("rev-parse", "--abbrev-ref", "HEAD") -TimeoutSec 15).Trim()
if ($currentBranch -ne $Branch) {
    Invoke-Step -Description "Switch branch $currentBranch -> $Branch" -Action {
        if ($localBranchExists) {
            Invoke-Git -CmdArgs @("checkout", $Branch) -TimeoutSec 20 | Out-Null
        }
        elseif ($remoteBranchExists) {
            Invoke-Git -CmdArgs @("checkout", "-b", $Branch, "--track", "$Remote/$Branch") -TimeoutSec 20 | Out-Null
        }
        else {
            throw "Unable to switch to branch '$Branch'."
        }
    }
}

Invoke-Step -Description "Fetch $Remote/$Branch" -Action {
    Write-Log "Fetching $Remote/$Branch..."
    Invoke-GitWithRetry -OperationName "Fetch" -CmdArgs @("fetch", $Remote, $Branch) | Out-Null
}

Invoke-Step -Description "Stage files" -Action {
    Write-Log "Staging changes..."
    if ($IncludePath -and $IncludePath.Count -gt 0) {
        foreach ($path in $IncludePath) {
            Invoke-Git -CmdArgs @("add", "--", $path) -TimeoutSec 20 | Out-Null
        }
    }
    else {
        Invoke-Git -CmdArgs @("add", "-A") -TimeoutSec 20 | Out-Null
    }

    if ($ExcludePath -and $ExcludePath.Count -gt 0) {
        foreach ($path in $ExcludePath) {
            try {
                Invoke-Git -CmdArgs @("reset", "HEAD", "--", $path) -TimeoutSec 20 | Out-Null
                Write-Log "Excluded from staging: $path"
            }
            catch {
                Write-Log "Exclude path not staged or missing: $path" "WARN"
            }
        }
    }
}

$hasStagedChanges = $false
try {
    Invoke-Git -CmdArgs @("diff", "--cached", "--quiet") -TimeoutSec 10 | Out-Null
}
catch {
    if ($_.Exception.Message -match "exited with code 1") {
        $hasStagedChanges = $true
    }
    else {
        throw
    }
}
if (-not $hasStagedChanges -and -not $AllowEmpty) {
    Write-Log "No changes to commit."
    exit 0
}

if (-not $NoCommit -and -not $SkipSecretScan) {
    Invoke-Step -Description "Run secret scan on staged files" -Action {
        Write-Log "Running staged secret scan..."
        Run-SecretScan
        Write-Log "Secret scan passed."
    }
}

if (-not $NoCommit) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $finalMessage = "$CommitMessage ($timestamp)"

    Invoke-Step -Description "Create git commit" -Action {
        $commitArgs = @("commit")
        if ($Amend) {
            $commitArgs += "--amend"
        }
        if ($AllowEmpty) {
            $commitArgs += "--allow-empty"
        }
        $commitArgs += @("-m", $finalMessage)
        Write-Log "Committing: $finalMessage"
        Invoke-Git -CmdArgs $commitArgs -TimeoutSec 30 | Out-Null
    }
}
else {
    Write-Log "NoCommit set: commit step skipped." "WARN"
}

Invoke-Step -Description "Rebase on $Remote/$Branch" -Action {
    Write-Log "Rebasing on $Remote/$Branch..."
    try {
        Invoke-GitWithRetry -OperationName "Pull --rebase" -CmdArgs @("pull", "--rebase", $Remote, $Branch) | Out-Null
    }
    catch {
        Write-Log "Rebase failed. Attempting rebase --abort..." "WARN"
        try {
            Invoke-Git -CmdArgs @("rebase", "--abort") -TimeoutSec 15 | Out-Null
            Write-Log "Rebase aborted successfully." "WARN"
        }
        catch {
            Write-Log "No active rebase to abort or abort failed." "WARN"
        }
        throw
    }
}

Invoke-Step -Description "Push to $Remote/$Branch" -Action {
    Write-Log "Pushing to $Remote/$Branch..."
    Invoke-GitWithRetry -OperationName "Push" -CmdArgs @("push", $Remote, $Branch) | Out-Null
}

Write-Log "Done."
