param(
    [string]$RepoRoot = "C:\Users\sunny\Documents\GitHub\AlgoTrader",
    [string]$PythonPath = "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe"
)

if (-not (Test-Path $PythonPath)) {
    Write-Error "Python path not found: $PythonPath"
    exit 1
}

& "$PSScriptRoot\set_postgres_env.ps1"

Push-Location "$RepoRoot\Live"
try {
    & $PythonPath -m services.database.status --repo-root $RepoRoot --backend postgres --migrate
    & $PythonPath -m services.data_catalog.postgres_status_service --repo-root $RepoRoot --migrate
}
finally {
    Pop-Location
}
