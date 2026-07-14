param([switch]$ManualRetry)
$ErrorActionPreference = "Stop"

# Local configuration. Never place secrets in this file or Task Scheduler arguments.
$ProductionDir = "C:\CryptoHunterProd"
$RepositoryUrl = "https://github.com/Zigel-pixel/crypto-hunter.git"
$Branch = "feat/market-core"
$BotTaskName = "Crypto Hunter Bot"
$BasePythonExe = "py"
$QaWorkingDir = $ProductionDir
$WarmupSeconds = 15
$HealthSeconds = 15
$MaximumDeploymentSeconds = 900
$E2ESuite = "all"
$RollbackOnSmokeE2EFailure = $true
$RollbackOnFullE2EFailure = $false
$RuntimeDir = Join-Path $ProductionDir ".deployment"
$CandidateRoot = "C:\CryptoHunterDeployCandidate"
$VenvRoot = Join-Path $RuntimeDir "venvs"
$StatePath = Join-Path $RuntimeDir "state.json"
$LockPath = Join-Path $RuntimeDir "deployment.lock"
$ReportDir = Join-Path $RuntimeDir "reports"
$LogDir = Join-Path $ProductionDir "logs\deployment"
$BotLog = Join-Path $ProductionDir "logs\bot.log"

function Write-DeployLog([string]$Stage, [string]$Message) {
    $safe = $Message -replace '(?i)(token|api[_ -]?key|secret|password)\s*[:=]\s*\S+', '[REDACTED]'
    Add-Content -LiteralPath (Join-Path $LogDir "deployment-$((Get-Date).ToString('yyyyMMdd')).log") -Value "[$((Get-Date).ToString('s'))][$Stage] $safe"
}
function Invoke-Checked([string]$Stage, [scriptblock]$Command) {
    if ($script:deadline -and (Get-Date) -ge $script:deadline) { throw "Maximum deployment duration exceeded before $Stage." }
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Stage failed with exit code $LASTEXITCODE" }
    if ($script:deadline -and (Get-Date) -ge $script:deadline) { throw "Maximum deployment duration exceeded during $Stage." }
}
function Get-State {
    if (-not (Test-Path -LiteralPath $StatePath)) { return @{} }
    try { return Get-Content -Raw -LiteralPath $StatePath | ConvertFrom-Json -AsHashtable }
    catch { return @{} }
}
function Save-State([hashtable]$State) {
    $temporary = "$StatePath.tmp"
    $State | ConvertTo-Json | Set-Content -LiteralPath $temporary -Encoding UTF8
    Move-Item -Force -LiteralPath $temporary -Destination $StatePath
}
function Send-Notification([string]$Text) {
    if ($env:DEPLOYMENT_NOTIFICATIONS_ENABLED -eq 'false') { return }
    if (-not $env:QA_BOT_TOKEN -or -not $env:QA_ADMIN_TELEGRAM_ID) { return }
    $body = @{ chat_id = $env:QA_ADMIN_TELEGRAM_ID; text = $Text; disable_web_page_preview = $true } | ConvertTo-Json
    try { Invoke-RestMethod -Method Post -Uri "https://api.telegram.org/bot$($env:QA_BOT_TOKEN)/sendMessage" -ContentType 'application/json' -Body $body -TimeoutSec 10 | Out-Null }
    catch { Write-DeployLog "notify" "Administrator notification failed." }
}
function Save-DeploymentReport([string]$Status, [string]$SafeError = "") {
    if (-not $newCommit -or -not $oldCommit) { return }
    $stamp = (Get-Date).ToString('yyyyMMdd-HHmmss')
    $payload = [ordered]@{ branch=$Branch; old_commit=$oldCommit; new_commit=$newCommit; status=$Status; finished_at=(Get-Date).ToString('o'); smoke_e2e=$smokePassed; full_e2e=$fullPassed; error=($SafeError -replace '(?i)(token|api[_ -]?key|secret|password)\s*[:=]\s*\S+','[REDACTED]') }
    $payload | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $ReportDir "deployment-report-$stamp.json") -Encoding UTF8
    @("# Crypto Hunter Deployment Report","","- Branch: $Branch","- Old commit: $oldCommit","- New commit: $newCommit","- Status: $Status","- Smoke E2E: $smokePassed","- Full E2E: $fullPassed","","Safe error: $($payload.error)") | Set-Content -LiteralPath (Join-Path $ReportDir "deployment-report-$stamp.md") -Encoding UTF8
}
function Get-BotProcesses {
    $root = [IO.Path]::GetFullPath($ProductionDir)
    @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -and $_.CommandLine.Contains($root, [StringComparison]::OrdinalIgnoreCase) -and $_.CommandLine -match 'main\.py' })
}
function Test-BotHealth {
    Start-Sleep -Seconds $HealthSeconds
    $processes = @(Get-BotProcesses)
    if ($processes.Count -ne 1) { return $false }
    if (-not (Test-Path -LiteralPath $BotLog)) { return $false }
    $tail = (Get-Content -LiteralPath $BotLog -Tail 120) -join "`n"
    return $tail -match '(?i)polling|Starting Crypto Hunter' -and $tail -notmatch 'Traceback \(most recent call last\)'
}
function Stop-ProductionBot {
    Stop-ScheduledTask -TaskName $BotTaskName -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
    foreach ($process in @(Get-BotProcesses)) { Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop }
}
function Start-ProductionBot { Start-ScheduledTask -TaskName $BotTaskName; Start-Sleep -Seconds $WarmupSeconds }
function Restore-Production([string]$Commit, [string]$PythonPointer) {
    Stop-ProductionBot
    Push-Location $ProductionDir
    try { Invoke-Checked "rollback source" { git reset --keep $Commit } }
    finally { Pop-Location }
    if ($PythonPointer) { Set-Content -LiteralPath (Join-Path $RuntimeDir "active-python.txt") -Value $PythonPointer -Encoding UTF8 }
    Start-ProductionBot
    return Test-BotHealth
}

New-Item -ItemType Directory -Force -Path $RuntimeDir,$VenvRoot,$ReportDir,$LogDir | Out-Null
$productionFull = [IO.Path]::GetFullPath($ProductionDir).TrimEnd('\')
$candidateFull = [IO.Path]::GetFullPath($CandidateRoot).TrimEnd('\')
if ($candidateFull -eq $productionFull -or $candidateFull.StartsWith($productionFull + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "Candidate directory must be outside the production worktree." }
if ([IO.Path]::GetFileName($candidateFull) -ne 'CryptoHunterDeployCandidate') { throw "Candidate directory name failed its safety allowlist." }
$lock = [IO.File]::Open($LockPath, 'OpenOrCreate', 'ReadWrite', 'None')
$deploymentStatus = 'blocked'; $smokePassed = $null; $fullPassed = $null
try {
    $deadline = (Get-Date).AddSeconds($MaximumDeploymentSeconds)
    if (-not (Test-Path -LiteralPath (Join-Path $ProductionDir '.git'))) { throw "Production repository is missing." }
    Push-Location $ProductionDir
    try {
        $currentBranch = (git branch --show-current).Trim()
        $origin = (git remote get-url origin).Trim()
        $dirty = git status --porcelain --untracked-files=no
        if ($currentBranch -ne $Branch) { throw "Unexpected production branch." }
        if ($origin.TrimEnd('/') -ne $RepositoryUrl.TrimEnd('/')) { throw "Unexpected origin repository." }
        if ($dirty) { throw "Tracked production working tree changes block deployment." }
        Invoke-Checked "fetch" { git fetch --prune origin $Branch }
        $oldCommit = (git rev-parse HEAD).Trim(); $newCommit = (git rev-parse "origin/$Branch").Trim()
        if ($oldCommit -eq $newCommit) { exit 0 }
        Invoke-Checked "ancestry" { git merge-base --is-ancestor $oldCommit $newCommit }
    } finally { Pop-Location }

    $state = Get-State
    if (-not $ManualRetry -and $state.failed_commit -eq $newCommit) { exit 0 }
    Send-Notification "🚀 Deployment started`nBranch: $Branch`nOld: $($oldCommit.Substring(0,7))`nNew: $($newCommit.Substring(0,7))"

    if (Test-Path -LiteralPath $CandidateRoot) { git -C $ProductionDir worktree remove --force $CandidateRoot }
    Invoke-Checked "candidate worktree" { git -C $ProductionDir worktree add --detach $CandidateRoot $newCommit }
    $candidateVenv = Join-Path $VenvRoot $newCommit
    if (-not (Test-Path -LiteralPath (Join-Path $candidateVenv 'Scripts\python.exe'))) { Invoke-Checked "candidate venv" { & $BasePythonExe -3.13 -m venv $candidateVenv } }
    $candidatePython = Join-Path $candidateVenv 'Scripts\python.exe'
    Invoke-Checked "dependencies" { & $candidatePython -m pip install --disable-pip-version-check -r (Join-Path $CandidateRoot 'requirements.txt') -r (Join-Path $CandidateRoot 'requirements-dev.txt') }
    Invoke-Checked "compile" { & $candidatePython -m compileall -q (Join-Path $CandidateRoot 'app') (Join-Path $CandidateRoot 'qa_bot') (Join-Path $CandidateRoot 'qa') (Join-Path $CandidateRoot 'qa_e2e') (Join-Path $CandidateRoot 'deployment') (Join-Path $CandidateRoot 'tests') (Join-Path $CandidateRoot 'main.py') }
    Push-Location $CandidateRoot
    try { Invoke-Checked "pytest" { & $candidatePython -m pytest -q } }
    finally { Pop-Location }

    $previousPython = if (Test-Path -LiteralPath (Join-Path $RuntimeDir 'active-python.txt')) { (Get-Content -Raw -LiteralPath (Join-Path $RuntimeDir 'active-python.txt')).Trim() } else { "" }
    Stop-ProductionBot
    Push-Location $ProductionDir
    try { Invoke-Checked "fast-forward" { git merge --ff-only "origin/$Branch" } }
    finally { Pop-Location }
    Set-Content -LiteralPath (Join-Path $RuntimeDir 'active-python.txt') -Value $candidatePython -Encoding UTF8
    Start-ProductionBot
    if (-not (Test-BotHealth)) {
        $restored = Restore-Production $oldCommit $previousPython
        $state.failed_commit = $newCommit; Save-State $state
        Save-DeploymentReport $(if ($restored) { 'rolled_back' } else { 'rollback_failed' }) 'Production health check failed.'
        Send-Notification "⏪ Deployment rolled back after failed process health. Old commit restored: $($oldCommit.Substring(0,7))"
        if (-not $restored) { throw "Rollback failed to restore bot health." }
        exit 1
    }

    Push-Location $QaWorkingDir
    try {
        & $candidatePython -m qa_e2e status *> $null
        if ($LASTEXITCODE -ne 0) { throw "Authorized E2E session is unavailable." }
        & $candidatePython -m qa_e2e run smoke; $smokePassed = $LASTEXITCODE -eq 0
        if (-not $smokePassed -and $RollbackOnSmokeE2EFailure) {
            $restored = Restore-Production $oldCommit $previousPython
            $state.failed_commit = $newCommit; Save-State $state
            Save-DeploymentReport $(if ($restored) { 'rolled_back' } else { 'rollback_failed' }) 'Smoke E2E failed.'
            Send-Notification "⏪ Deployment rolled back after smoke E2E failure."
            if (-not $restored) { throw "Rollback failed after smoke E2E failure." }
            exit 1
        }
        $fullPassed = $false
        if ($smokePassed) { & $candidatePython -m qa_e2e run $E2ESuite; $fullPassed = $LASTEXITCODE -eq 0 }
        if (-not $fullPassed -and $RollbackOnFullE2EFailure) { $restored = Restore-Production $oldCommit $previousPython; Save-DeploymentReport $(if ($restored) { 'rolled_back' } else { 'rollback_failed' }) 'Full E2E failed.'; exit 1 }
    } finally { Pop-Location }
    $state.last_successfully_deployed_commit = $newCommit; $state.previous_working_commit = $oldCommit; $state.failed_commit = ""; $state.last_deployment_status = if ($fullPassed) { 'deployed' } else { 'deployed_with_e2e_failures' }; Save-State $state
    $deploymentStatus = $state.last_deployment_status
    Save-DeploymentReport $deploymentStatus
    Send-Notification "✅ Deployment complete`nCommit: $($newCommit.Substring(0,7))`nHealth: healthy`nSmoke E2E: $smokePassed`nFull E2E: $fullPassed"
}
catch {
    Write-DeployLog "blocked" $_.Exception.Message
    $state = Get-State
    if ($newCommit) { $state.failed_commit = $newCommit }; $state.last_deployment_status = 'blocked'; Save-State $state
    Save-DeploymentReport 'blocked' $_.Exception.Message
    Send-Notification "⛔ Deployment blocked. The existing production version was preserved. See the local deployment log."
    exit 1
}
finally {
    if (Test-Path -LiteralPath $CandidateRoot) { git -C $ProductionDir worktree remove --force $CandidateRoot 2>$null }
    $lock.Dispose()
}
