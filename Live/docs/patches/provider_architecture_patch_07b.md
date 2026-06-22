# Provider Architecture Patch 07b — IB Gateway export connection handling

## Purpose

Patch 07b improves the local CSV export helper for IB Gateway users.

It updates:

```text
Live/scripts/export_ibkr_history_to_csv.py
Live/docs/patches/provider_architecture_patch_07b.md
```

## Why

The original exporter defaulted to a TWS-style port and could fail with a full traceback:

```text
ConnectionError("Not connected")
```

Patch 07b adds:

```text
--port
--gateway-live
--gateway-paper
--tws-live
--tws-paper
--client-id
friendly connection error output
```

## Your IB Gateway example

If your IB Gateway socket port is `4001`:

```powershell
python .\Live\scripts\export_ibkr_history_to_csv.py --symbol MSFT --timeframe "1 min" --start 2026-06-15 --end 2026-06-18 --port 4001
```

Equivalent shortcut:

```powershell
python .\Live\scripts\export_ibkr_history_to_csv.py --symbol MSFT --timeframe "1 min" --start 2026-06-15 --end 2026-06-18 --gateway-live
```

## Common local ports

```text
IB Gateway live:  4001
IB Gateway paper: 4002
TWS live:         7496
TWS paper:        7497
```

Use the actual port configured in your IB Gateway API settings if it differs.

## Security notes

Do not commit:

```text
.env
account IDs
IBKR credentials
generated files containing private account data
```

Market data CSV files are usually less sensitive than account data, but inspect generated files before adding them to Git.
