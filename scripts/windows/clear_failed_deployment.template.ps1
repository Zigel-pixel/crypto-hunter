param([switch]$ConfirmClear)
$ErrorActionPreference = "Stop"
$ProductionDir = "C:\CryptoHunterProd"
$StatePath = Join-Path $ProductionDir ".deployment\state.json"
if (-not $ConfirmClear) { throw "Rerun with -ConfirmClear to clear only the failed-commit retry block." }
if (-not (Test-Path -LiteralPath $StatePath)) { Write-Host "No deployment state exists."; exit 0 }
try {
    try { $state = Get-Content -Raw -LiteralPath $StatePath | ConvertFrom-Json }
    catch { $state = [pscustomobject]@{} }
    if ($state.PSObject.Properties['failed_commit']) { $state.failed_commit = '' }
    else { $state | Add-Member -NotePropertyName failed_commit -NotePropertyValue '' }
    $temporary = "$StatePath.tmp"
    try {
        [IO.File]::WriteAllText($temporary, ($state | ConvertTo-Json -Depth 6), (New-Object Text.UTF8Encoding($false)))
        if (Test-Path -LiteralPath $StatePath) { [IO.File]::Replace($temporary, $StatePath, $null) }
        else { [IO.File]::Move($temporary, $StatePath) }
    } catch { Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue; throw }
    Write-Host "Failed deployment retry block cleared."
} catch {
    Write-Error "Failed deployment retry block was not cleared." -ErrorAction Continue
    exit 1
}
