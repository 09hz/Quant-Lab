# PostgreSQL Setup for AlgoTrader

This project keeps SQLite as the local/default catalog and uses PostgreSQL as an optional research database for JSON/CSV ingestion.

## Install

Recommended local Windows stack:

- PostgreSQL
- DBeaver or pgAdmin
- Python package: `psycopg[binary]`

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader"

$PY = "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe"
& $PY -m pip install "psycopg[binary]"
```

## Create database, user, and schema

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader"
.\scripts\setup_postgres.ps1
```

The script prompts for:

- postgres admin password
- algotrader_app password

Passwords are not written to the repo.

## Set runtime environment variables

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader"
.\scripts\set_postgres_env.ps1
```

Then start Dash from the same PowerShell window:

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader\Live"
& "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe" ".\app.py"
```

## Verify from CLI

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader"
.\scripts\check_postgres.ps1
```

## Data Library UI

Open the Data Library tab and use:

- Check PostgreSQL
- Ingest JSON/CSV to PostgreSQL

The UI displays:

- connection status
- table counts
- latest ingestion run
- skipped/status summary

## Security

Do not commit real passwords. `.env`, `.env.local`, and `.env.*.local` are ignored.

## Browser setup wizard

The Data Library tab includes a local PostgreSQL setup wizard.

Use it for local development:

1. Open Data Library.
2. Expand **Connection settings**.
3. Enter host, port, database, schema, app user, and app password.
4. Click **Test Typed Credentials**.
5. If the database/user/schema are not created yet, expand **Local setup / repair database**.
6. Enter the postgres admin user/password.
7. Click **Set up / repair PostgreSQL database**.
8. Click **Ingest JSON/CSV to PostgreSQL**.

Passwords typed into the browser are used for the current Dash callback request only. They are not saved to the repo, not saved in `.env`, and not stored in Dash `dcc.Store`.

For shared or hosted deployments, disable admin setup controls and use environment variables or a secrets manager instead.
