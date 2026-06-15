# update-vendor.ps1 - Windows wrapper around scripts/update-vendor.sh.
#
# The sync logic lives in the bash script (single source of truth). This wrapper
# just finds a bash (Git for Windows ships one) and forwards any arguments.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\update-vendor.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\update-vendor.ps1 <ref-or-sha>
[CmdletBinding()]
param([Parameter(ValueFromRemainingArguments = $true)] [string[]] $Args)

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$shScript  = Join-Path $scriptDir 'update-vendor.sh'

$bash = (Get-Command bash -ErrorAction SilentlyContinue).Source
if (-not $bash) {
    foreach ($candidate in @("$env:ProgramFiles\Git\bin\bash.exe", "$env:ProgramFiles\Git\usr\bin\bash.exe")) {
        if (Test-Path $candidate) { $bash = $candidate; break }
    }
}
if (-not $bash) {
    Write-Error "bash not found. Install Git for Windows (it ships bash), or run scripts/update-vendor.sh from WSL / Git Bash."
    exit 1
}

& $bash $shScript @Args
exit $LASTEXITCODE
