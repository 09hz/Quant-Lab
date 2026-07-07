param(
    [string]$HostName = "localhost",
    [string]$Port = "5432",
    [string]$Database = "algotrader",
    [string]$User = "algotrader_app",
    [string]$Schema = "algotrader"
)

$env:ALGOTRADER_DB_BACKEND = "postgres"
$env:ALGOTRADER_DB_HOST = $HostName
$env:ALGOTRADER_DB_PORT = $Port
$env:ALGOTRADER_DB_NAME = $Database
$env:ALGOTRADER_DB_USER = $User
$env:ALGOTRADER_DB_SCHEMA = $Schema
$env:ALGOTRADER_DB_PASSWORD = Read-Host "Enter PostgreSQL password for $User"
Remove-Item Env:ALGOTRADER_DATABASE_URL -ErrorAction SilentlyContinue

Write-Host "PostgreSQL environment variables set for this PowerShell process."
Write-Host "Password is stored only in this terminal process environment."
Write-Host "Start Dash from this same PowerShell window if you want the UI to use PostgreSQL."
