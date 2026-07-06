# v21_4_1_data_bootstrap_and_generation_control

## Purpose

Add a market-bars bootstrap step and stop accidental chained mutation parents in the new bootstrap workflow.

v21.4 proved the CSV pipeline works, but the user does not have a CSV file yet. v21.4 also showed that using the latest run blindly can mutate prior mutations.

v21.4.1 adds a command that does this:

```text
local cached CSV search
→ yfinance fallback if available
→ save Live/data/market_bars/<SYMBOL>_1d.csv
→ run csv_mutation_retest.py
→ default parent run = latest gen0/original seed run
```

## User-selected variables

```text
1. Data bootstrap source: A — local app/cache first, then yfinance fallback.
2. If yfinance missing: A — show install/config hint.
3. Output CSV path: A — Live/data/market_bars/<SYMBOL>_1d.csv.
4. Parent generation: A — default to gen0/original seeds only in bootstrap workflow.
5. Chained mutations: A — disabled by default; enable with --allow-chained-mutations.
6. UI changes: A — no UI yet, command line only.
7. Patch name: v21_4_1_data_bootstrap_and_generation_control.py.
```

## Files added

```text
Live/services/ai/auto_lab_orchestrator/generation_control.py
Live/services/ai/auto_lab_orchestrator/bars_bootstrapper.py
Live/services/ai/auto_lab_orchestrator/bootstrap_bars_and_run.py
Live/services/ai/auto_lab_orchestrator/bootstrap_self_test.py
```

## Files intentionally not modified

```text
Live/core/BackTestEngine.py
Live/core/StrategyEngine.py
Live/callbacks.py
Live/services/ai/research_autolab/*
Live/ui/*
```

## Main command

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader"

& "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe" ".\Live\services\ai\auto_lab_orchestrator\bootstrap_bars_and_run.py" `
  --symbol AMD `
  --start 2020-01-01 `
  --end 2025-12-31 `
  --max-total-runs 20 `
  --max-mutations-per-parent 4
```

## yfinance note

If no local data exists, the bootstrapper tries yfinance if installed. If yfinance is missing, install it inside the same venv:

```powershell
& "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe" -m pip install yfinance
```

## Chained mutation behavior

Default:

```text
Uses latest gen0/original-seed parent run when available.
If none exists, forces csv_mutation_retest.py to create a fresh CSV baseline first.
```

Optional chained mode:

```powershell
--allow-chained-mutations
```

## Run patch

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader"

& "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe" ".\v21_4_1_data_bootstrap_and_generation_control.py" `
  --repo-root "C:\Users\sunny\Documents\GitHub\AlgoTrader" `
  --run-bootstrap-self-test
```

Expected:

```text
v21.4.1 data bootstrap and generation control complete.
- compile: PASS
- bootstrap_self_test: PASS
```

## Inspect outputs

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader\Live"

Get-ChildItem ".\data\market_bars"

$latest = Get-ChildItem ".\data\auto_lab_runs" -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1

notepad "$($latest.FullName)\real_data_report.md"
notepad "$($latest.FullName)\mutation_report.md"
notepad "$($latest.FullName)\experiment_memory.json"
```

## Safety

```text
Simulation/research only.
No broker execution.
No live orders.
No PaperBroker calls.
No account credentials.
No secrets.
```
