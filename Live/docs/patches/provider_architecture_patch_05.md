# Provider Architecture Patch 05 — Provider Diagnostics

## Purpose

This patch adds a small provider-health diagnostic layer so market-data setup can be checked without launching the full Dash app.

It helps verify:

- which provider is active,
- whether provider imports work,
- whether symbols can be sanitized,
- whether symbol options can be loaded,
- whether history returns normalized OHLCV columns,
- whether snapshots can be created.

## Files Added

```text
Live/.env.example
Live/scripts/check_market_data_provider.py
Live/services/market_data/provider_health.py
Live/docs/patches/provider_architecture_patch_05.md
```

## No Backup Files

This patch intentionally does not create `.bak` files. Rollback should be handled through Git.

## Usage

From the repository root:

```powershell
python .\Live\scripts\check_market_data_provider.py
```

CSV mode:

```powershell
$env:MARKET_DATA_PROVIDER="csv"
$env:CSV_MARKET_DATA_ROOT="cache/replay"
python .\Live\scripts\check_market_data_provider.py --provider csv --symbol MSFT
```

IBKR wrapper import check without requesting history:

```powershell
python .\Live\scripts\check_market_data_provider.py --provider ibkr --skip-history
```

IBKR history check, only when TWS or IB Gateway is running:

```powershell
python .\Live\scripts\check_market_data_provider.py --provider ibkr --symbol MSFT --timeframe "1 min"
```

## Test Commands

```powershell
python -m py_compile .\Live\services\market_data\provider_health.py
python -m py_compile .\Live\scripts\check_market_data_provider.py
python .\Live\scripts\check_market_data_provider.py --provider ibkr --skip-history
```

## Commit

```powershell
git add .\Live\.env.example
git add .\Live\scripts\check_market_data_provider.py
git add .\Live\services\market_data\provider_health.py
git add .\Live\docs\patches\provider_architecture_patch_05.md
git commit -m "Add market data provider diagnostics"
```
