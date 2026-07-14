$ProductionDir = "C:\CryptoHunterProd"
$StatePath = Join-Path $ProductionDir ".deployment\state.json"
$ReportDir = Join-Path $ProductionDir ".deployment\reports"
if (Test-Path -LiteralPath $StatePath) { Get-Content -Raw -LiteralPath $StatePath } else { Write-Host "No deployment state exists." }
Get-ChildItem -LiteralPath $ReportDir -Filter 'deployment-report-*' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 10 Name,LastWriteTime,Length
