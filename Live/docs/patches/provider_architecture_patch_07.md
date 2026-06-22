# Provider Architecture Patch 07 — Local CSV/cache hardening

## Purpose

Patch 07 adds local tools so the app can keep moving while Tradier is not active.

It adds:

```text
Live/scripts/inspect_market_data_cache.py
Live/scripts/export_ibkr_history_to_csv.py
Live/docs/patches/provider_architecture_patch_07.md
```

## Inspect local files

```powershell
python .\Live\scripts\inspect_market_data_cache.py
```

Use an explicit cache root:

```powershell
python .\Live\scripts\inspect_market_data_cache.py --root cache/replay
```

Filter by symbol:

```powershell
python .\Live\scripts\inspect_market_data_cache.py --symbol MSFT
```

## Export IBKR history to CSV

Use this only when IBKR/TWS/Gateway is available:

```powershell
python .\Live\scripts\export_ibkr_history_to_csv.py --symbol MSFT --timeframe "1 min" --start 2026-06-18 --end 2026-06-19
```

The script writes normalized CSV bars with:

```text
time,open,high,low,close,volume
```

## Test CSV provider mode

```powershell
$env:MARKET_DATA_PROVIDER="csv"
$env:CSV_MARKET_DATA_ROOT="cache/replay"
python .\Live\scripts\check_market_data_provider.py --provider csv --symbol MSFT --timeframe "1 min"
```

Then:

```powershell
$env:MARKET_DATA_PROVIDER="csv"
$env:CSV_MARKET_DATA_ROOT="cache/replay"
python .\Live\app.py
```

## Security notes

Do not commit:

```text
.env
API tokens
IBKR credentials
account IDs
large private data exports
```

CSV market data is usually safer than account data, but review generated files before committing.
