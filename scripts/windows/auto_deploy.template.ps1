param([switch]$ManualRetry)
$ErrorActionPreference = "Stop"

# Local configuration. Never place secrets in this file or Task Scheduler arguments.
$ProductionDir = "C:\CryptoHunterProd"
$RepositoryUrl = "https://github.com/Zigel-pixel/crypto-hunter.git"
$Branch = "feat/market-core"
$BotTaskName = "Crypto Hunter Bot"
# Optional full bootstrap interpreter path. Empty means: valid production venv
# first, then the full path resolved from `py` without a minor-version selector.
$BasePythonExe = ""
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
$AtomicHelper = Join-Path $PSScriptRoot "atomic_files.ps1"
if (-not (Test-Path -LiteralPath $AtomicHelper)) { throw "Atomic file helper is missing." }
. $AtomicHelper

function Write-DeployLog([string]$Stage, [string]$Message) {
    $safe = $Message -replace '(?i)(token|api[_ -]?key|secret|password)\s*[:=]\s*\S+', '[REDACTED]'
    Add-Content -LiteralPath (Join-Path $LogDir "deployment-$((Get-Date).ToString('yyyyMMdd')).log") -Value "[$((Get-Date).ToString('s'))][$Stage] $safe"
}
function Invoke-Checked([string]$Stage, [scriptblock]$Command) {
    if ($script:deadline -and (Get-Date) -ge $script:deadline) { throw "Maximum deployment duration exceeded before $Stage." }
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $Command
        $nativeExitCode = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previousPreference }
    if ($nativeExitCode -ne 0) { throw "$Stage failed with exit code $nativeExitCode" }
    if ($script:deadline -and (Get-Date) -ge $script:deadline) { throw "Maximum deployment duration exceeded during $Stage." }
}
function Invoke-NativeCode([scriptblock]$Command) {
    $previousPreference = $ErrorActionPreference
    try { $ErrorActionPreference = 'Continue'; & $Command | Out-Host; return $LASTEXITCODE }
    finally { $ErrorActionPreference = $previousPreference }
}
function Resolve-BootstrapPython {
    $candidates = @()
    $default = Join-Path $ProductionDir '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $default) { $candidates += $default }
    if ($BasePythonExe) { $candidates += $BasePythonExe }
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) { $candidates += $launcher.Source }
    foreach ($candidate in $candidates) {
        if (-not (Test-Path -LiteralPath $candidate)) { continue }
        $stdout = Join-Path $env:TEMP ("crypto-hunter-python-" + [guid]::NewGuid().ToString('N') + '.out')
        $stderr = "$stdout.err"
        try {
            $probe = Start-Process -FilePath $candidate -ArgumentList @('--version') -RedirectStandardOutput $stdout -RedirectStandardError $stderr -NoNewWindow -Wait -PassThru
            $output = @((Get-Content -LiteralPath $stdout -ErrorAction SilentlyContinue), (Get-Content -LiteralPath $stderr -ErrorAction SilentlyContinue)) -join ' '
            if ($probe.ExitCode -eq 0 -and $output.Trim() -match '^Python \d+\.\d+\.\d+') {
                return [pscustomobject]@{ Path=[IO.Path]::GetFullPath($candidate); Version=$output.Trim() }
            }
        } finally { Remove-Item -LiteralPath $stdout,$stderr -Force -ErrorAction SilentlyContinue }
    }
    throw 'No valid Python interpreter was found. Configure BasePythonExe with a full executable path.'
}
function Get-State {
    if (-not (Test-Path -LiteralPath $StatePath)) { return [pscustomobject]@{} }
    try { return Get-Content -Raw -LiteralPath $StatePath | ConvertFrom-Json }
    catch { return [pscustomobject]@{} }
}
function Set-StateValue([object]$State, [string]$Name, [object]$Value) {
    if ($State.PSObject.Properties[$Name]) { $State.$Name = $Value }
    else { $State | Add-Member -NotePropertyName $Name -NotePropertyValue $Value }
}
function Save-State([object]$State) {
    $temporary = "$StatePath.tmp"
    try {
        $json = $State | ConvertTo-Json -Depth 6
        [IO.File]::WriteAllText($temporary, $json, (New-Object Text.UTF8Encoding($false)))
        Replace-FileAtomic -TemporaryPath $temporary -DestinationPath $StatePath
    } catch {
        Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
        throw
    }
}
function Set-ActivePython([string]$PythonPath) {
    if (-not $PythonPath -or -not (Test-Path -LiteralPath $PythonPath)) { throw 'Active Python executable does not exist.' }
    $pointer = Join-Path $RuntimeDir 'active-python.txt'; $temporary = "$pointer.tmp"
    try {
        [IO.File]::WriteAllText($temporary, [IO.Path]::GetFullPath($PythonPath), (New-Object Text.UTF8Encoding($false)))
        Replace-FileAtomic -TemporaryPath $temporary -DestinationPath $pointer
    } catch { Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue; throw }
}
function Get-RestorePython {
    $default = Join-Path $ProductionDir '.venv\Scripts\python.exe'
    $pointer = Join-Path $RuntimeDir 'active-python.txt'
    if (Test-Path -LiteralPath $pointer) {
        $existing = (Get-Content -Raw -LiteralPath $pointer).Trim()
        if ($existing -and (Test-Path -LiteralPath $existing)) { return [IO.Path]::GetFullPath($existing) }
    }
    if (Test-Path -LiteralPath $default) { return [IO.Path]::GetFullPath($default) }
    throw 'Neither the previous active Python nor the default production Python is valid.'
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
    $payload = [ordered]@{ branch=$Branch; old_commit=$oldCommit; new_commit=$newCommit; status=$Status; finished_at=(Get-Date).ToString('o'); smoke_e2e=$smokePassed; full_e2e=$fullPassed; rollback=$script:rollbackDetails; error=($SafeError -replace '(?i)(token|api[_ -]?key|secret|password)\s*[:=]\s*\S+','[REDACTED]') }
    $payload | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $ReportDir "deployment-report-$stamp.json") -Encoding UTF8
    @("# Crypto Hunter Deployment Report","","- Branch: $Branch","- Old commit: $oldCommit","- New commit: $newCommit","- Status: $Status","- Smoke E2E: $smokePassed","- Full E2E: $fullPassed","- Rollback stages: $($script:rollbackDetails)","","Safe error: $($payload.error)") | Set-Content -LiteralPath (Join-Path $ReportDir "deployment-report-$stamp.md") -Encoding UTF8
}
function Get-BotProcesses {
    $main = [IO.Path]::GetFullPath((Join-Path $ProductionDir 'main.py')).ToLowerInvariant()
    @(Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" | Where-Object {
        if (-not $_.CommandLine) { return $false }
        $command = $_.CommandLine.Replace('/', '\').ToLowerInvariant()
        $quoted = '"' + $main.Replace('/', '\') + '"'
        $command.Contains($quoted) -or $command -match ('(^|\s)' + [regex]::Escape($main.Replace('/', '\')) + '(\s|$)')
    })
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
    foreach ($process in @(Get-BotProcesses)) { Write-DeployLog 'process' "Stopping production PID $($process.ProcessId)."; Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop }
    $limit = (Get-Date).AddSeconds(15)
    while (@(Get-BotProcesses).Count -gt 0 -and (Get-Date) -lt $limit) { Start-Sleep -Milliseconds 250 }
    if (@(Get-BotProcesses).Count -ne 0) { throw 'Exact production processes did not exit before start.' }
}
function Start-ProductionBot {
    Stop-ProductionBot
    Start-ScheduledTask -TaskName $BotTaskName
    Start-Sleep -Seconds $WarmupSeconds
    if (@(Get-BotProcesses).Count -ne 1) { throw 'Production start did not create exactly one matching process.' }
}
function Restore-Production([string]$Commit, [string]$RestorePython) {
    $result = [ordered]@{ source_restored=$false; pointer_restored=$false; processes_cleared=$false; health_restored=$false; success=$false }
    try {
        Stop-ProductionBot; $result.processes_cleared = $true
        Push-Location $ProductionDir
        try { Invoke-Checked "rollback source" { git reset --keep $Commit }; $result.source_restored = ((git rev-parse HEAD).Trim() -eq $Commit) }
        finally { Pop-Location }
        if (-not $result.source_restored) { throw 'Rollback source verification failed.' }
        Set-ActivePython $RestorePython; $result.pointer_restored = $true
        Start-ProductionBot
        $result.health_restored = Test-BotHealth
        $result.success = $result.source_restored -and $result.pointer_restored -and $result.processes_cleared -and $result.health_restored
    } catch { Write-DeployLog 'rollback' $_.Exception.Message }
    $script:rollbackDetails = ($result | ConvertTo-Json -Compress)
    Write-DeployLog 'rollback' $script:rollbackDetails
    return [pscustomobject]$result
}

New-Item -ItemType Directory -Force -Path $RuntimeDir,$VenvRoot,$ReportDir,$LogDir | Out-Null
$productionFull = [IO.Path]::GetFullPath($ProductionDir).TrimEnd('\')
$candidateFull = [IO.Path]::GetFullPath($CandidateRoot).TrimEnd('\')
if ($candidateFull -eq $productionFull -or $candidateFull.StartsWith($productionFull + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "Candidate directory must be outside the production worktree." }
if ([IO.Path]::GetFileName($candidateFull) -ne 'CryptoHunterDeployCandidate') { throw "Candidate directory name failed its safety allowlist." }
$lock = [IO.File]::Open($LockPath, 'OpenOrCreate', 'ReadWrite', 'None')
$deploymentStatus = 'blocked'; $smokePassed = $null; $fullPassed = $null; $rollbackDetails = 'not_required'
try {
    $deadline = (Get-Date).AddSeconds($MaximumDeploymentSeconds)
    $bootstrap = Resolve-BootstrapPython
    $bootstrapPython = $bootstrap.Path
    Write-DeployLog 'python' "Interpreter: $($bootstrap.Path); version: $($bootstrap.Version)"
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
    if (-not (Test-Path -LiteralPath (Join-Path $candidateVenv 'Scripts\python.exe'))) { Invoke-Checked "candidate venv" { & $bootstrapPython -m venv $candidateVenv } }
    $candidatePython = Join-Path $candidateVenv 'Scripts\python.exe'
    Invoke-Checked "dependencies" { & $candidatePython -m pip install --disable-pip-version-check -r (Join-Path $CandidateRoot 'requirements.txt') -r (Join-Path $CandidateRoot 'requirements-dev.txt') }
    Invoke-Checked "compile" { & $candidatePython -m compileall -q (Join-Path $CandidateRoot 'app') (Join-Path $CandidateRoot 'qa_bot') (Join-Path $CandidateRoot 'qa') (Join-Path $CandidateRoot 'qa_e2e') (Join-Path $CandidateRoot 'deployment') (Join-Path $CandidateRoot 'tests') (Join-Path $CandidateRoot 'main.py') }
    Push-Location $CandidateRoot
    try { Invoke-Checked "pytest" { & $candidatePython -m pytest -q } }
    finally { Pop-Location }

    $previousPython = Get-RestorePython
    Stop-ProductionBot
    Push-Location $ProductionDir
    try { Invoke-Checked "fast-forward" { git merge --ff-only "origin/$Branch" } }
    finally { Pop-Location }
    Set-ActivePython $candidatePython
    Start-ProductionBot
    if (-not (Test-BotHealth)) {
        $rollback = Restore-Production $oldCommit $previousPython
        Set-StateValue $state 'failed_commit' $newCommit; Save-State $state
        Save-DeploymentReport $(if ($rollback.success) { 'rolled_back' } else { 'rollback_failed' }) 'Production health check failed.'
        if (-not $rollback.success) { throw "Rollback failed to restore source, pointer, processes, or bot health." }
        Send-Notification "⏪ Deployment rolled back after failed process health. Old commit restored: $($oldCommit.Substring(0,7))"
        exit 1
    }

    Push-Location $QaWorkingDir
    try {
        $statusCode = Invoke-NativeCode { & $candidatePython -m qa_e2e status *> $null }
        if ($statusCode -ne 0) { throw "Authorized E2E session is unavailable." }
        $smokeCode = Invoke-NativeCode { & $candidatePython -m qa_e2e run smoke }; $smokePassed = $smokeCode -eq 0
        if (-not $smokePassed -and $RollbackOnSmokeE2EFailure) {
            $rollback = Restore-Production $oldCommit $previousPython
            Set-StateValue $state 'failed_commit' $newCommit; Save-State $state
            Save-DeploymentReport $(if ($rollback.success) { 'rolled_back' } else { 'rollback_failed' }) 'Smoke E2E failed.'
            if (-not $rollback.success) { throw "Rollback failed after smoke E2E failure." }
            Send-Notification "⏪ Deployment rolled back after smoke E2E failure."
            exit 1
        }
        $fullPassed = $false
        if ($smokePassed) { $fullCode = Invoke-NativeCode { & $candidatePython -m qa_e2e run $E2ESuite }; $fullPassed = $fullCode -eq 0 }
        if (-not $fullPassed -and $RollbackOnFullE2EFailure) { $rollback = Restore-Production $oldCommit $previousPython; Save-DeploymentReport $(if ($rollback.success) { 'rolled_back' } else { 'rollback_failed' }) 'Full E2E failed.'; if (-not $rollback.success) { throw 'Rollback failed after full E2E failure.' }; exit 1 }
    } finally { Pop-Location }
    Set-StateValue $state 'last_successfully_deployed_commit' $newCommit; Set-StateValue $state 'previous_working_commit' $oldCommit; Set-StateValue $state 'failed_commit' ''; $deploymentStatus = if ($fullPassed) { 'deployed' } else { 'deployed_with_e2e_failures' }; Set-StateValue $state 'last_deployment_status' $deploymentStatus; Save-State $state
    Save-DeploymentReport $deploymentStatus
    Send-Notification "✅ Deployment complete`nCommit: $($newCommit.Substring(0,7))`nHealth: healthy`nSmoke E2E: $smokePassed`nFull E2E: $fullPassed"
}
catch {
    Write-DeployLog "blocked" $_.Exception.Message
    $state = Get-State
    if ($newCommit) { Set-StateValue $state 'failed_commit' $newCommit }; Set-StateValue $state 'last_deployment_status' 'blocked'; Save-State $state
    Save-DeploymentReport 'blocked' $_.Exception.Message
    Send-Notification "⛔ Deployment blocked. The existing production version was preserved. See the local deployment log."
    exit 1
}
finally {
    if (Test-Path -LiteralPath $CandidateRoot) { $previousPreference=$ErrorActionPreference; try { $ErrorActionPreference='Continue'; git -C $ProductionDir worktree remove --force $CandidateRoot 2>$null } finally { $ErrorActionPreference=$previousPreference } }
    $lock.Dispose()
}
