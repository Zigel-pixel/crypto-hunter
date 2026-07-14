param()
$ErrorActionPreference = "Stop"

# Copy this template to the production clone as run_bot.ps1 and customize only these values.
$ProjectDir = "C:\CryptoHunterProd"
$DefaultPythonExe = Join-Path $ProjectDir ".venv\Scripts\python.exe"
$ActivePythonFile = Join-Path $ProjectDir ".deployment\active-python.txt"
$MainFile = Join-Path $ProjectDir "main.py"
$LogDir = Join-Path $ProjectDir "logs"
$RestartDelaySeconds = 15
$DuplicateInstanceExitCode = 1
$MaximumRapidRestarts = 3
$RapidRestartWindowSeconds = 60

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir "bot.log"
$StdoutLog = Join-Path $LogDir "bot.stdout.log"
$StderrLog = Join-Path $LogDir "bot.stderr.log"
$rapidRestarts = 0

while ($true) {
    $PythonExe = $DefaultPythonExe
    if (Test-Path -LiteralPath $ActivePythonFile) {
        $candidate = (Get-Content -Raw -LiteralPath $ActivePythonFile).Trim()
        if ($candidate -and (Test-Path -LiteralPath $candidate)) { $PythonExe = $candidate }
    }
    if (-not (Test-Path -LiteralPath $PythonExe)) { throw "Configured Python executable is unavailable." }

    $started = Get-Date
    Add-Content -LiteralPath $LogFile -Value "[$($started.ToString('s'))] Starting Crypto Hunter"
    # Start-Process avoids Windows PowerShell 5.1 converting ordinary native stderr
    # (including Python INFO logs) into terminating NativeCommandError records.
    $process = Start-Process -FilePath $PythonExe -ArgumentList @($MainFile) -WorkingDirectory $ProjectDir -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog -NoNewWindow -Wait -PassThru
    $code = $process.ExitCode
    if (Test-Path -LiteralPath $StdoutLog) { Get-Content -LiteralPath $StdoutLog | Add-Content -LiteralPath $LogFile }
    if (Test-Path -LiteralPath $StderrLog) { Get-Content -LiteralPath $StderrLog | Add-Content -LiteralPath $LogFile }
    $runtime = ((Get-Date) - $started).TotalSeconds
    Add-Content -LiteralPath $LogFile -Value "[$((Get-Date).ToString('s'))] Process exited with code $code after $([int]$runtime)s"

    if ($code -eq 0) { exit 0 }
    if ($code -eq $DuplicateInstanceExitCode -and $runtime -lt 10) {
        Add-Content -LiteralPath $LogFile -Value "Duplicate-instance rejection; launcher exits to avoid restart spam."
        exit $code
    }
    $rapidRestarts = if ($runtime -lt $RapidRestartWindowSeconds) { $rapidRestarts + 1 } else { 0 }
    if ($rapidRestarts -ge $MaximumRapidRestarts) {
        Add-Content -LiteralPath $LogFile -Value "Crash-loop protection activated."
        exit $code
    }
    Start-Sleep -Seconds $RestartDelaySeconds
}
