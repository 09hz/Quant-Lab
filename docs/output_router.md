# Managed Output Router

The Managed Output Router scans existing `Live/data` outputs and routes them through the Central Artifact Writer.

It is a bridge for files produced before every module is fully patched to call `save_json`, `save_csv`, or `save_markdown` directly.

## Dry run

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader\Live"

$PY = "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe"

& $PY -m services.artifacts.route_existing_outputs `
  --repo-root "C:\Users\sunny\Documents\GitHub\AlgoTrader" `
  --dry-run `
  --limit 50
```

## Route without PostgreSQL ingestion

```powershell
& $PY -m services.artifacts.route_existing_outputs `
  --repo-root "C:\Users\sunny\Documents\GitHub\AlgoTrader" `
  --no-ingest
```

## Route and ingest into PostgreSQL

Start Dash or PowerShell with PostgreSQL credentials available, then run:

```powershell
& $PY -m services.artifacts.route_existing_outputs `
  --repo-root "C:\Users\sunny\Documents\GitHub\AlgoTrader"
```

## Route only recent files

```powershell
& $PY -m services.artifacts.route_existing_outputs `
  --repo-root "C:\Users\sunny\Documents\GitHub\AlgoTrader" `
  --since-minutes 120
```

## What it skips

- `Live/data/managed_artifacts`
- SQLite catalog databases
- raw SQLite/database files
- image/binary/archive files
- files above the configured max size

## Safety

The router does not move, delete, or rewrite existing files. It registers and optionally ingests them.
Research/simulation only.
