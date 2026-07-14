param([switch]$ConfirmInstall)
$ErrorActionPreference = "Stop"
$ProductionDir = "C:\CryptoHunterProd"
$BotTaskName = "Crypto Hunter Bot"
$DeployTaskName = "Crypto Hunter Auto Deploy"
$BotScript = Join-Path $ProductionDir "run_bot.ps1"
$DeployScript = Join-Path $ProductionDir "auto_deploy.ps1"
$PowerShellExe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

if (-not $ConfirmInstall) { throw "Review local paths, then rerun with -ConfirmInstall." }
foreach ($path in ($BotScript,$DeployScript)) { if (-not (Test-Path -LiteralPath $path)) { throw "Required local script is missing: $path" } }
$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$escaped = [Security.SecurityElement]::Escape($ProductionDir)
$botXml = @"
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"><Triggers><LogonTrigger><Enabled>true</Enabled><UserId>$user</UserId></LogonTrigger></Triggers><Principals><Principal id="Author"><UserId>$user</UserId><LogonType>InteractiveToken</LogonType><RunLevel>HighestAvailable</RunLevel></Principal></Principals><Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><StartWhenAvailable>true</StartWhenAvailable><ExecutionTimeLimit>PT0S</ExecutionTimeLimit></Settings><Actions Context="Author"><Exec><Command>$PowerShellExe</Command><Arguments>-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File &quot;$BotScript&quot;</Arguments><WorkingDirectory>$escaped</WorkingDirectory></Exec></Actions></Task>
"@
$deployXml = @"
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"><Triggers><CalendarTrigger><StartBoundary>$((Get-Date).AddMinutes(1).ToString('s'))</StartBoundary><Enabled>true</Enabled><ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay><Repetition><Interval>PT5M</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition></CalendarTrigger></Triggers><Principals><Principal id="Author"><UserId>$user</UserId><LogonType>InteractiveToken</LogonType><RunLevel>HighestAvailable</RunLevel></Principal></Principals><Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><StartWhenAvailable>true</StartWhenAvailable><ExecutionTimeLimit>PT15M</ExecutionTimeLimit></Settings><Actions Context="Author"><Exec><Command>$PowerShellExe</Command><Arguments>-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File &quot;$DeployScript&quot;</Arguments><WorkingDirectory>$escaped</WorkingDirectory></Exec></Actions></Task>
"@
$botFile = Join-Path $env:TEMP "crypto-hunter-bot-task.xml"; $deployFile = Join-Path $env:TEMP "crypto-hunter-deploy-task.xml"
try {
    Set-Content -LiteralPath $botFile -Value $botXml -Encoding Unicode; Set-Content -LiteralPath $deployFile -Value $deployXml -Encoding Unicode
    schtasks.exe /Create /TN $BotTaskName /XML $botFile /F | Out-Host
    schtasks.exe /Create /TN $DeployTaskName /XML $deployFile /F | Out-Host
} finally { Remove-Item -LiteralPath $botFile,$deployFile -Force -ErrorAction SilentlyContinue }
Write-Host "Installed/updated '$BotTaskName' and '$DeployTaskName'."
