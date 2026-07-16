# Provider Architecture Patch 05b — Lenient Provider Diagnostics

## Purpose

Patch 05 reported IBKR diagnostics as failed when `get_snapshot()` raised:

```text
No loaded state for MSFT 1 min
```

That is not necessarily a broken provider. It usually means the diagnostic
script created the IBKR wrapper but did not start/subscribe the IBKR real-time
state in that process.

This patch makes snapshot errors non-fatal by default.

## Files Changed

- `Live/services/market_data/provider_health.py`
- `Live/scripts/check_market_data_provider.py`

## New Behavior

`get_snapshot()` failures are warnings unless the command uses:

```powershell
python .\Live\scripts\check_market_data_provider.py --provider ibkr --require-snapshot
```

For basic wrapper/import checks, use:

```powershell
python .\Live\scripts\check_market_data_provider.py --provider ibkr --skip-history
```

For an even lighter check:

```powershell
python .\Live\scripts\check_market_data_provider.py --provider ibkr --skip-history --skip-snapshot
```

## Why This Matters

The diagnostic script should distinguish between:

- provider import/factory failures
- symbol metadata failures
- required history failures
- optional live snapshot state not being initialized

IBKR can have valid symbol metadata and provider wrapping even when no live
snapshot state has been loaded yet.
