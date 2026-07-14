param([switch]$ConfirmUninstall)
$BotTaskName = "Crypto Hunter Bot"
$DeployTaskName = "Crypto Hunter Auto Deploy"
if (-not $ConfirmUninstall) { throw "Rerun with -ConfirmUninstall to remove only the two configured tasks." }
schtasks.exe /Delete /TN $DeployTaskName /F
schtasks.exe /Delete /TN $BotTaskName /F
