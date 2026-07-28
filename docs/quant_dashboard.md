# DEPRECATED: Data Library Quant Dashboard

v24.7 adds a read-only dashboard to the Data Library tab.

## Shows

- Quant table counts
- Recent experiment runs
- Recent strategy runs
- Best backtests
- Walk-forward validation runs
- Universe runs
- Data quality events

## Backends

The dashboard can read:

- SQLite fallback
- PostgreSQL, when environment credentials are available

## Notes

The dashboard is read-only. It does not migrate tables, insert rows, update rows, delete rows, move files, place orders, or connect to brokers.

## PostgreSQL

Start Dash from a PowerShell session where PostgreSQL environment variables are set:

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader"

.\scripts\set_postgres_env.ps1

cd ".\Live"

$PY = "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe"
& $PY ".\app.py"
```

Then choose PostgreSQL in the dashboard backend dropdown.

Research/simulation only.
