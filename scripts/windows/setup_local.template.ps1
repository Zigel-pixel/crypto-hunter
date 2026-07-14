param([switch]$ConfirmSetup)
$ErrorActionPreference = "Stop"
$ProductionDir = "C:\CryptoHunterProd"
$TemplateDir = Join-Path $PSScriptRoot "."
$Files = @{ "run_bot.template.ps1" = "run_bot.ps1"; "auto_deploy.template.ps1" = "auto_deploy.ps1"; "atomic_files.template.ps1" = "atomic_files.ps1"; "check_deployment.template.ps1" = "check_deployment.ps1"; "clear_failed_deployment.template.ps1" = "clear_failed_deployment.ps1" }
$replacements = @($Files.Values | ForEach-Object { Join-Path $ProductionDir $_ })
Write-Host "The following generated files will replace local edits after timestamped backups:"
$replacements | ForEach-Object { Write-Host " - $_" }
if (-not $ConfirmSetup) { throw "Review the replacement list and rerun with -ConfirmSetup." }
foreach ($entry in $Files.GetEnumerator()) {
    $source = Join-Path $TemplateDir $entry.Key; $destination = Join-Path $ProductionDir $entry.Value
    if (-not (Test-Path -LiteralPath $source)) { throw "Template missing: $source" }
    if (Test-Path -LiteralPath $destination) { Copy-Item -LiteralPath $destination -Destination "$destination.$((Get-Date).ToString('yyyyMMdd-HHmmss')).bak" -ErrorAction Stop }
    Copy-Item -LiteralPath $source -Destination $destination -ErrorAction Stop
}
Write-Host "Local scripts created. Review configuration before installing tasks. Sensitive runtime files were not touched."
