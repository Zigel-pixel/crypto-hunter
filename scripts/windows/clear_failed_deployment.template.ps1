param([switch]$ConfirmClear)
$ProductionDir = "C:\CryptoHunterProd"
$StatePath = Join-Path $ProductionDir ".deployment\state.json"
if (-not $ConfirmClear) { throw "Rerun with -ConfirmClear to clear only the failed-commit retry block." }
if (-not (Test-Path -LiteralPath $StatePath)) { Write-Host "No deployment state exists."; exit 0 }
$state = Get-Content -Raw -LiteralPath $StatePath | ConvertFrom-Json -AsHashtable
$state.failed_commit = ""
$temporary = "$StatePath.tmp"; $state | ConvertTo-Json | Set-Content -LiteralPath $temporary -Encoding UTF8
Move-Item -Force -LiteralPath $temporary -Destination $StatePath
Write-Host "Failed deployment retry block cleared."
