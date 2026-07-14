param([switch]$ConfirmUninstall)
$ErrorActionPreference = "Stop"
$BotTaskName = "Crypto Hunter Bot"
$DeployTaskName = "Crypto Hunter Auto Deploy"
if (-not $ConfirmUninstall) { throw "Rerun with -ConfirmUninstall to remove only the two configured tasks." }
schtasks.exe /Delete /TN $DeployTaskName /F
if ($LASTEXITCODE -ne 0) { Write-Error "Auto deploy task removal failed."; exit 1 }
schtasks.exe /Delete /TN $BotTaskName /F
if ($LASTEXITCODE -ne 0) { Write-Error "Main bot task removal failed."; exit 1 }
Write-Host "Configured Crypto Hunter tasks were removed."
