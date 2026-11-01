param(
    [ValidateSet("prepare", "collect", "full")]
    [string]$Stage = "full",
    [switch]$RunChecks
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..")
$helper = Join-Path $scriptDir "manual_retest_helper.py"

if (-not (Test-Path $helper)) {
    Write-Error "helper not found: $helper"
}

Push-Location $repoRoot
try {
    if ($Stage -eq "prepare") {
        $args = @($helper, "prepare")
        if ($RunChecks) { $args += "--run-checks" }
        & python @args
        exit $LASTEXITCODE
    }

    if ($Stage -eq "collect") {
        & python $helper collect
        exit $LASTEXITCODE
    }

    $args = @($helper, "prepare")
    if ($RunChecks) { $args += "--run-checks" }
    & python @args
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host ""
    Write-Host "请完成 GUI 手工复测（A + B）后按回车继续采集证据..."
    Read-Host | Out-Null

    & python $helper collect
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
