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
