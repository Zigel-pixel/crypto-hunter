$ErrorActionPreference = "Stop"

function Replace-FileAtomic {
    param(
        [Parameter(Mandatory=$true)][string]$TemporaryPath,
        [Parameter(Mandatory=$true)][string]$DestinationPath
    )

    $temporary = [IO.Path]::GetFullPath($TemporaryPath)
    $destination = [IO.Path]::GetFullPath($DestinationPath)
    $temporaryDirectory = [IO.Path]::GetDirectoryName($temporary)
    $destinationDirectory = [IO.Path]::GetDirectoryName($destination)
    $backup = $destination + ".atomic-backup"
    $replacementSucceeded = $false

    if (-not [string]::Equals($temporaryDirectory, $destinationDirectory, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Atomic replacement requires temporary and destination files in the same directory."
    }
    if (-not [IO.File]::Exists($temporary)) {
        throw "Atomic replacement temporary file is missing."
    }

    try {
        if ([IO.File]::Exists($backup)) {
            [IO.File]::Delete($backup)
        }
        if ([IO.File]::Exists($destination)) {
            [IO.File]::Replace($temporary, $destination, $backup)
        } else {
            [IO.File]::Move($temporary, $destination)
        }
        if (-not [IO.File]::Exists($destination)) {
            throw "Atomic replacement destination verification failed."
        }
        $replacementSucceeded = $true
        if ([IO.File]::Exists($backup)) {
            [IO.File]::Delete($backup)
        }
    } catch {
        if ([IO.File]::Exists($backup)) {
            try {
                if ([IO.File]::Exists($destination)) { [IO.File]::Delete($destination) }
                [IO.File]::Move($backup, $destination)
            } catch {
                throw "Atomic replacement failed and the original remains at the operation backup path."
            }
        }
        throw
    } finally {
        if (-not $replacementSucceeded -and [IO.File]::Exists($temporary)) {
            [IO.File]::Delete($temporary)
        }
    }
}
