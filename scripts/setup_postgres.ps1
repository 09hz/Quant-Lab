param(
    [string]$PsqlPath = "",
    [string]$HostName = "localhost",
    [string]$Port = "5432",
    [string]$Database = "algotrader",
    [string]$AppUser = "algotrader_app",
    [string]$Schema = "algotrader"
)

function Find-Psql {
    if ($PsqlPath -and (Test-Path $PsqlPath)) {
        return $PsqlPath
    }

    $candidates = @(
        "C:\Program Files\PostgreSQL\18\bin\psql.exe",
        "C:\Program Files\PostgreSQL\17\bin\psql.exe",
        "C:\Program Files\PostgreSQL\16\bin\psql.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    $found = Get-ChildItem "C:\Program Files\PostgreSQL" -Recurse -Filter "psql.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) {
        return $found.FullName
    }

    throw "Could not find psql.exe. Install PostgreSQL or pass -PsqlPath."
}

$PSQL = Find-Psql
Write-Host "Using psql: $PSQL"

$adminPassword = Read-Host "Enter postgres admin password"
$appPassword = Read-Host "Enter password to set for $AppUser"

$env:PGPASSWORD = $adminPassword

try {
    $dbExists = & $PSQL -h $HostName -p $Port -U postgres -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$Database';"
    if ($dbExists.Trim() -ne "1") {
        & $PSQL -h $HostName -p $Port -U postgres -d postgres -c "CREATE DATABASE $Database;"
    } else {
        Write-Host "Database already exists: $Database"
    }

    $escapedPassword = $appPassword.Replace("'", "''")
    $roleSql = @"
DO `$`$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '$AppUser') THEN
        CREATE ROLE $AppUser LOGIN PASSWORD '$escapedPassword';
    ELSE
        ALTER ROLE $AppUser WITH LOGIN PASSWORD '$escapedPassword';
    END IF;
END
`$`$;
"@

    $roleFile = New-TemporaryFile
    Set-Content -Path $roleFile -Value $roleSql -Encoding UTF8

    & $PSQL -h $HostName -p $Port -U postgres -d postgres -f $roleFile
    Remove-Item $roleFile -Force -ErrorAction SilentlyContinue

    & $PSQL -h $HostName -p $Port -U postgres -d $Database -c "CREATE SCHEMA IF NOT EXISTS $Schema AUTHORIZATION $AppUser;"
    & $PSQL -h $HostName -p $Port -U postgres -d $Database -c "ALTER SCHEMA $Schema OWNER TO $AppUser;"
    & $PSQL -h $HostName -p $Port -U postgres -d $Database -c "GRANT CONNECT ON DATABASE $Database TO $AppUser;"
    & $PSQL -h $HostName -p $Port -U postgres -d $Database -c "GRANT CREATE ON DATABASE $Database TO $AppUser;"
    & $PSQL -h $HostName -p $Port -U postgres -d $Database -c "GRANT USAGE, CREATE ON SCHEMA $Schema TO $AppUser;"
    & $PSQL -h $HostName -p $Port -U postgres -d $Database -c "ALTER DEFAULT PRIVILEGES IN SCHEMA $Schema GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO $AppUser;"
    & $PSQL -h $HostName -p $Port -U postgres -d $Database -c "ALTER ROLE $AppUser SET search_path TO $Schema, public;"

    $env:PGPASSWORD = $appPassword
    & $PSQL -h $HostName -p $Port -U $AppUser -d $Database -c "SELECT current_database(), current_user, current_schema();"

    Write-Host "PostgreSQL setup complete."
    Write-Host "To set env vars for Dash, run:"
    Write-Host ".\scripts\set_postgres_env.ps1"
}
finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}
