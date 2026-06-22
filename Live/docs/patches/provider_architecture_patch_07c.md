# Provider Architecture Patch 07c — IB Gateway exporter start fix

## Purpose

Patch 07c fixes the IBKR historical CSV exporter for the current `RealTimeIB.start(...)`
signature.

The previous Patch 07b exporter tried `start()` without a symbol. Your local
`RealTimeIB` requires a symbol, so the exporter printed:

```text
RealTimeIB.start() missing 1 required positional argument: 'symbol'
```

Patch 07c updates:

```text
Live/scripts/export_ibkr_history_to_csv.py
Live/docs/patches/provider_architecture_patch_07c.md
```

## Changes

The exporter now tries symbol-aware startup calls first:

```text
start(symbol=...)
start(symbol=..., timeframe=...)
start(...)
```

It also adds a direct `ib.connect(...)` fallback for exporter-only usage when the
wrapper start method does not establish the low-level IB connection.

## Your IB Gateway command

If your Gateway API port is `4001`:

```powershell
python .\Live\scripts\export_ibkr_history_to_csv.py --symbol MSFT --timeframe "1 min" --start 2026-06-15 --end 2026-06-18 --port 4001 --client-id 31
```

Use a client ID that is not already used by the Dash app.

## Security notes

Do not commit:

```text
.env
IBKR credentials
account IDs
private account exports
```

Generated market-data CSV files can become large. Keep them out of Git unless you
intentionally want small test fixtures.
