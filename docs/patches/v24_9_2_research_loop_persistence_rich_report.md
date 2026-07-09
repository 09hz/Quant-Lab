# v24.9.2 — Research Loop Persistence + Rich Report Fix

## Purpose

Fix the first Research Loop output being too basic and fix Quant Schema persistence compatibility.

The first browser-run loop produced a useful scaffold report, but it also showed:

```text
Quant persist: WARN: quant schema persist skipped: OperationalError: table experiment_runs has no column named experiment_id
```

That happens when an older `experiment_runs` table already exists with a different schema. The v24.9.0 loop expected the newer typed Quant Schema columns.

## What this patch improves

1. Adds schema-compatible persistence.
   - Detects which columns actually exist.
   - Inserts only columns supported by the local table.
   - Avoids crashing on old `experiment_runs` layouts.
   - Keeps PostgreSQL/SQLite support best-effort.

2. Upgrades Research Loop reports.
   - Adds clear explanation of Research Loop vs Auto Lab.
   - Adds per-symbol results.
   - Adds strategy parameters.
   - Adds pass/fail gates.
   - Adds walk-forward proxy details.
   - Adds universe robustness details.
   - Adds next-action recommendations.

3. Adds adapter hooks.
   - `BacktestAdapter`
   - `AutoLabAdapter`
   - `WalkForwardAdapter`
   - `UniverseAdapter`

These are intentionally interfaces/placeholders for the next real integration patch.

## Safety

- Simulation/research only
- No broker calls
- No live trading
- No order placement
- No credentials written
- No file moves or deletes
- No Data Library edits
- No main app layout edits
