param(
    [string]$RepoRoot = "",
    [string]$PythonPath = ""
)

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}
elseif (-not (Test-Path -LiteralPath $RepoRoot -PathType Container)) {
    Write-Error "Repository root not found: $RepoRoot"
    exit 1
}
else {
    $RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
}
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $PythonPath = Join-Path $RepoRoot ".venv\Scripts\python.exe"
}

if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    Write-Error "Python path not found: $PythonPath"
    exit 1
}
$PythonPath = (Resolve-Path -LiteralPath $PythonPath).Path

& "$PSScriptRoot\set_postgres_env.ps1"

Push-Location "$RepoRoot\Live"
$exitCode = 0
try {
    & $PythonPath -m services.database.status --repo-root $RepoRoot --backend postgres --migrate
    if ($LASTEXITCODE -ne 0) {
        $exitCode = $LASTEXITCODE
    }
    else {
        & $PythonPath -m services.data_catalog.postgres_status_service --repo-root $RepoRoot --migrate
        if ($LASTEXITCODE -ne 0) {
            $exitCode = $LASTEXITCODE
        }
    }
}
finally {
    Pop-Location
}

if ($exitCode -ne 0) {
    exit $exitCode
}
