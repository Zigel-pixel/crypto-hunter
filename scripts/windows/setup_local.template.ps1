param([switch]$ConfirmSetup)
$ProductionDir = "C:\CryptoHunterProd"
$TemplateDir = Join-Path $PSScriptRoot "."
$Files = @{ "run_bot.template.ps1" = "run_bot.ps1"; "auto_deploy.template.ps1" = "auto_deploy.ps1"; "check_deployment.template.ps1" = "check_deployment.ps1"; "clear_failed_deployment.template.ps1" = "clear_failed_deployment.ps1" }
if (-not $ConfirmSetup) { throw "Review paths and rerun with -ConfirmSetup. Existing files will be backed up." }
foreach ($entry in $Files.GetEnumerator()) {
    $source = Join-Path $TemplateDir $entry.Key; $destination = Join-Path $ProductionDir $entry.Value
    if (-not (Test-Path -LiteralPath $source)) { throw "Template missing: $source" }
    if (Test-Path -LiteralPath $destination) { Copy-Item -LiteralPath $destination -Destination "$destination.$((Get-Date).ToString('yyyyMMdd-HHmmss')).bak" }
    Copy-Item -LiteralPath $source -Destination $destination
}
Write-Host "Local scripts created. Review configuration before installing tasks. Sensitive runtime files were not touched."
