# v21_4_2_same_data_baseline_and_sizing_modes

## Purpose

Make the CSV mutation loop more realistic and easier to trust.

The previous CSV run proved real AMD bars can load:

```text
Data rows: 1507
Data first_date: 2020-01-02
Data last_date: 2025-12-30
```

But two issues remained:

```text
1. Parent score comparison used old synthetic parent scorecards.
2. Backtests used fixed quantity, usually around 10 shares, so a $12,000 account was under-deployed.
```

v21.4.2 adds:

```text
same-data baseline
simulation sizing modes
same-data mutation delta
real-data report improvements
```

## User-selected variables

```text
1. Default sizing: C — percent_cash_exposure.
2. Default exposure: C — 95%.
3. Same-data baseline: A — always run before CSV mutation.
4. Parent comparison: B — compare mutation vs same-data CSV parent baseline.
5. Quantity mutation: B — keep but secondary to sizing mode.
6. UI changes: A — no UI, command-line/report only.
7. Patch name: v21_4_2_same_data_baseline_and_sizing_modes.py.
```

## Files added

```text
Live/services/ai/auto_lab_orchestrator/sizing.py
Live/services/ai/auto_lab_orchestrator/csv_mutation_retest_sized.py
Live/services/ai/auto_lab_orchestrator/sizing_self_test.py
```

## Files overwritten

```text
Live/services/ai/auto_lab_orchestrator/bootstrap_bars_and_run.py
```

The bootstrap command now calls `csv_mutation_retest_sized.py`.

## Files intentionally not modified

```text
Live/core/BackTestEngine.py
Live/core/StrategyEngine.py
Live/callbacks.py
Live/services/ai/research_autolab/*
Live/ui/*
```

## Sizing modes

```text
fixed_quantity
max_affordable_shares
percent_cash_exposure
```

Default:

```text
sizing_mode = percent_cash_exposure
cash_exposure_pct = 95
```

This is still simulation-only. It does not place orders or provide live sizing advice.

## Main command

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader"

& "C:\\Users\\sunny\\Documents\\GitHub\\StockVisualizer\\.venv\\Scripts\\python.exe" ".\\Live\\services\\ai\\auto_lab_orchestrator\\bootstrap_bars_and_run.py" `
  --symbol AMD `
  --start 2020-01-01 `
  --end 2025-12-31 `
  --sizing-mode percent_cash_exposure `
  --cash-exposure-pct 95 `
  --max-total-runs 20 `
  --max-mutations-per-parent 4
```

## Direct CSV command

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader"

& "C:\\Users\\sunny\\Documents\\GitHub\\StockVisualizer\\.venv\\Scripts\\python.exe" ".\\Live\\services\\ai\\auto_lab_orchestrator\\csv_mutation_retest_sized.py" `
  --symbol AMD `
  --csv-path "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader\\Live\\data\\market_bars\\AMD_1d.csv" `
  --start 2020-01-01 `
  --end 2025-12-31 `
  --run-id autolab_2026-07-02T160607Z0000 `
  --sizing-mode percent_cash_exposure `
  --cash-exposure-pct 95 `
  --max-total-runs 20 `
  --max-mutations-per-parent 4
```

## Outputs

```text
report.md
mutation_report.md
real_data_report.md
experiment_memory.json
same_data_baseline_report.md
same_data_baseline.json
```

## Run patch

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader"

& "C:\\Users\\sunny\\Documents\\GitHub\\StockVisualizer\\.venv\\Scripts\\python.exe" ".\\v21_4_2_same_data_baseline_and_sizing_modes.py" `
  --repo-root "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader" `
  --run-sizing-self-test
```

Expected:

```text
v21.4.2 same-data baseline and sizing modes complete.
- compile: PASS
- sizing_self_test: PASS
```

## UI readiness note

After v21.4.2, the backend is close enough for a first UI integration:

```text
v22.0: Auto Lab UI launcher and report viewer
v22.1: progress/status polling
v22.2: results tables and equity charts
v22.3: AI explanation layer
```

Production-quality research needs v21.5 walk-forward validation before treating results as strong.
