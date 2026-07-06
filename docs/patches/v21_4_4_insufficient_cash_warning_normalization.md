# v21_4_4_insufficient_cash_warning_normalization

## Purpose

Normalize one confusing scoring issue seen in v21.4.2.

Some candidates produced usable simulated metrics, but were marked as engine failures because later buy signals could not be filled with available simulated cash. Example pattern:

```text
final_equity exists
total_return_pct exists
trade_count exists
fail_reasons:
- Insufficient cash for BUY ...
```

That should not always be treated as a broken engine. It is better represented as:

```text
engine_pass = True when usable metrics exist
execution_warning = skipped_buy_signal_insufficient_cash
research_pass = based on recovered metric score
```

This keeps the system honest while avoiding false "engine failed" labels.

## User-selected variables

```text
1. Patch: v21.4.4 insufficient-cash warning normalization.
2. Treat insufficient-cash skipped signals as warnings when usable metrics exist.
3. Keep hard failures as failures.
4. Recompute a deterministic recovered score from metrics.
5. Add execution_quality_report.md and execution_quality.json.
6. No UI changes yet.
7. No broker/live-trading changes.
```

## Files added

```text
Live/services/ai/auto_lab_orchestrator/execution_quality.py
Live/services/ai/auto_lab_orchestrator/execution_quality_from_run.py
Live/services/ai/auto_lab_orchestrator/execution_quality_self_test.py
```

## Files patched

```text
Live/services/ai/auto_lab_orchestrator/csv_mutation_retest_sized.py
```

The sized CSV runner now normalizes insufficient-cash signal skips before writing reports, mutation traces, and strategy build traces.

## Output files per run

```text
execution_quality_report.md
execution_quality.json
```

## What changes

Before:

```text
engine_pass = False
score = 0
fail_reasons = ["Insufficient cash for BUY ..."]
```

After, only when usable metrics exist and all hard fail reasons are insufficient-cash skipped entries:

```text
engine_pass = True
score = recovered from metrics
fail_reasons = []
warnings include insufficient-cash skipped-signal warnings
```

Hard script/data/engine failures remain failures.

## Run patch

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader"

& "C:\\Users\\sunny\\Documents\\GitHub\\StockVisualizer\\.venv\\Scripts\\python.exe" ".\\v21_4_4_insufficient_cash_warning_normalization.py" `
  --repo-root "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader" `
  --run-execution-quality-self-test `
  --generate-latest-quality-report
```

## Rerun sized AMD Auto Lab

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

## Inspect

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader\\Live"

$latest = Get-ChildItem ".\\data\\auto_lab_runs" -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1

notepad "$($latest.FullName)\\execution_quality_report.md"
notepad "$($latest.FullName)\\mutation_report.md"
notepad "$($latest.FullName)\\strategy_build_trace.md"
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
