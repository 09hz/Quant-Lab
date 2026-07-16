# Provider Architecture Patch 08 — IBKR Batch CSV Export

## Purpose

Patch 08 adds a local-only batch export helper for the CSV/cache workflow.

It does not add broker order routing, Tradier logic, FastAPI, Plotly/JS behavior, or UI changes.

## Files added

```text
Live/scripts/batch_export_ibkr_history_to_csv.py
Live/docs/patches/provider_architecture_patch_08.md
```

## Why this exists

After the single-symbol exporter works, it is useful to export several symbols into `cache/replay` without manually repeating the same command.

The batch exporter intentionally calls:

```text
Live/scripts/export_ibkr_history_to_csv.py
```

once per symbol, so it reuses the known-good single-symbol export path.

## Example

Gateway live port 4001:

```powershell
python .\Live\scripts\batch_export_ibkr_history_to_csv.py --symbols MSFT,AAPL,NVDA --timeframe "1 min" --start 2026-06-15 --end 2026-06-19 --port 4001 --client-id 31
```

Gateway paper port 4002:

```powershell
python .\Live\scripts\batch_export_ibkr_history_to_csv.py --symbols MSFT,AAPL,NVDA --timeframe "1 min" --start 2026-06-15 --end 2026-06-19 --port 4002 --client-id 31
```

Using a symbols file:

```powershell
python .\Live\scripts\batch_export_ibkr_history_to_csv.py --symbols-file .\symbols.txt --timeframe "1 min" --start 2026-06-15 --end 2026-06-19 --port 4001 --client-id 31
```

## Notes

For full-day regular-session bars, the end date is usually best supplied as the next calendar day.

Example:

```text
Wanted sessions: 2026-06-15 through 2026-06-18
Use: --start 2026-06-15 --end 2026-06-19
```

## Safety

- Does not place orders.
- Does not read balances.
- Does not require Tradier.
- Does not commit exported CSV files.
- Uses separate client IDs per symbol by default.

Keep local cache files out of Git:

```gitignore
cache/replay/
```
