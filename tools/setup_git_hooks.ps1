Param()

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")

Write-Host "[hooks] Repo root: $repoRoot"
Push-Location $repoRoot
try {
    git config core.hooksPath .githooks
    Write-Host "[hooks] Configured core.hooksPath=.githooks"
    Write-Host "[hooks] Done. Pre-commit will run text encoding integrity checks."
}
finally {
    Pop-Location
}
