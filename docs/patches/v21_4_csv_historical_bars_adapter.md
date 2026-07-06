# v21_4_csv_historical_bars_adapter

## Purpose

Connect the Auto Lab mutation/retest loop to CSV historical bars.

v21.3 proved the mutation loop works on synthetic bars:

```text
valid parent strategy
→ mutate parameter
→ run real StrategyEngine + BackTestEngine
→ score result
→ compare against parent
→ save experiment memory
```

v21.4 moves the loop toward product reality by adding a CSV bars adapter.

## User-selected variables

```text
1. Data source: A — CSV bars first.
2. CSV input format: A — auto-detect columns date/open/high/low/close/volume.
3. Symbols: A — single symbol per run.
4. Date range: A — optional start/end filter.
5. Output: B — same mutation report + separate real_data_report.md.
6. Scoring: B — add synthetic_vs_real_data label.
7. UI changes: A — no UI yet, command-line/report only.
8. Patch name: v21_4_csv_historical_bars_adapter.py.
```

## Files added

```text
Live/services/ai/auto_lab_orchestrator/data_adapters.py
Live/services/ai/auto_lab_orchestrator/real_data_reporter.py
Live/services/ai/auto_lab_orchestrator/csv_mutation_retest.py
Live/services/ai/auto_lab_orchestrator/csv_data_self_test.py
```

## Files intentionally not modified

```text
Live/core/BackTestEngine.py
Live/core/StrategyEngine.py
Live/callbacks.py
Live/services/ai/research_autolab/*
Live/ui/*
```

## What v21.4 does

```text
CSV historical bars
→ auto-detect OHLCV/date columns
→ optional start/end filter
→ load bars into DataFrame
→ select parent strategies from latest core/mutation run
→ generate mutations
→ run CoreStrategyBacktestAdapter
→ score
→ write normal report.md
→ write mutation_report.md
→ write experiment_memory.json
→ write real_data_report.md
```

## CSV column support

Auto-detects common forms:

```text
date: date, datetime, timestamp, time
open: open, o
high: high, h
low: low, l
close: close, c, adj close, adjusted close
volume: volume, vol, v
```

If volume is missing, it fills volume with zero.

## Main command

Use one CSV:

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader"

& "C:\\Users\\sunny\\Documents\\GitHub\\StockVisualizer\\.venv\\Scripts\\python.exe" ".\\Live\\services\\ai\\auto_lab_orchestrator\\csv_mutation_retest.py" `
  --symbol AMD `
  --csv-path "C:\\path\\to\\AMD.csv" `
  --start 2020-01-01 `
  --end 2025-12-31 `
  --max-total-runs 20 `
  --max-mutations-per-parent 4
```

Or use a bars directory:

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader"

& "C:\\Users\\sunny\\Documents\\GitHub\\StockVisualizer\\.venv\\Scripts\\python.exe" ".\\Live\\services\\ai\\auto_lab_orchestrator\\csv_mutation_retest.py" `
  --symbol AMD `
  --bars-dir "C:\\path\\to\\bars" `
  --start 2020-01-01 `
  --end 2025-12-31 `
  --max-total-runs 20 `
  --max-mutations-per-parent 4
```

## Run patch with self-test

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader"

& "C:\\Users\\sunny\\Documents\\GitHub\\StockVisualizer\\.venv\\Scripts\\python.exe" ".\\v21_4_csv_historical_bars_adapter.py" `
  --repo-root "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader" `
  --run-csv-self-test
```

Expected:

```text
v21.4 CSV historical bars adapter complete.
- compile: PASS
- csv_self_test: PASS
```

## Inspect latest report

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader\\Live"

$latest = Get-ChildItem ".\\data\\auto_lab_runs" -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1

notepad "$($latest.FullName)\\real_data_report.md"
notepad "$($latest.FullName)\\mutation_report.md"
notepad "$($latest.FullName)\\experiment_memory.json"
```

## Safety

```text
Simulation/research only.
No broker execution.
No live orders.
No PaperBroker calls.
No account credentials.
No external API calls.
No secrets.
```

## v21.5 target

Add walk-forward validation:

```text
CSV bars
→ split train/test windows
→ mutate on train
→ validate on unseen test
→ reject overfit candidates
```
