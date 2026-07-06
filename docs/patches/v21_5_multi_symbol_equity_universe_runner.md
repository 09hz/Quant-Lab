# v21_5_multi_symbol_equity_universe_runner

## Purpose

Extend AI Auto Lab from one-symbol research to multi-symbol / multi-equity universe research.

Current proven loop:

```text
single symbol
→ bootstrap bars
→ same-data parent baseline
→ simulation sizing
→ mutation retest
→ execution-quality normalization
→ strategy trace
→ reports
```

v21.5 adds:

```text
symbol universe
→ run the same pipeline per symbol
→ compare symbols
→ compare strategy families
→ detect single-symbol overfit risk
→ create universe-level reports
```

## User-selected variables

```text
1. Patch: v21.5 multi-symbol equity universe runner.
2. Symbols: passed from CLI, e.g. AMD,NVDA,MSFT,AAPL,TSLA.
3. Data: local cache first, yfinance fallback; optional --yfinance-first.
4. Sizing: percent_cash_exposure, default 95%.
5. Per-symbol same-data baseline: yes.
6. Per-symbol mutation retest: yes.
7. Universe reports: markdown + JSON.
8. UI changes: no UI yet.
9. Safety: research/simulation only.
```

## Files added

```text
Live/services/ai/auto_lab_orchestrator/universe_reporter.py
Live/services/ai/auto_lab_orchestrator/universe_runner.py
Live/services/ai/auto_lab_orchestrator/universe_self_test.py
```

## Outputs

Universe-level folder:

```text
Live/data/auto_lab_universe_runs/<universe_run_id>/
  universe_results.json
  universe_report.md
  symbol_leaderboard.md
  strategy_robustness_report.md
  top_universe_strategy_algorithm.md
```

Each symbol also gets a normal run folder under:

```text
Live/data/auto_lab_runs/<run_id>/
```

## Main command

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader"

& "C:\\Users\\sunny\\Documents\\GitHub\\StockVisualizer\\.venv\\Scripts\\python.exe" ".\\Live\\services\\ai\\auto_lab_orchestrator\\universe_runner.py" `
  --symbols AMD,NVDA,MSFT,AAPL,TSLA `
  --start 2020-01-01 `
  --end 2025-12-31 `
  --yfinance-first `
  --sizing-mode percent_cash_exposure `
  --cash-exposure-pct 95 `
  --max-total-runs-per-symbol 20 `
  --max-mutations-per-parent 4
```

## Run patch

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader"

& "C:\\Users\\sunny\\Documents\\GitHub\\StockVisualizer\\.venv\\Scripts\\python.exe" ".\\v21_5_multi_symbol_equity_universe_runner.py" `
  --repo-root "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader" `
  --run-universe-self-test
```

## Inspect

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader\\Live"

$latest = Get-ChildItem ".\\data\\auto_lab_universe_runs" -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1

notepad "$($latest.FullName)\\universe_report.md"
notepad "$($latest.FullName)\\symbol_leaderboard.md"
notepad "$($latest.FullName)\\strategy_robustness_report.md"
notepad "$($latest.FullName)\\top_universe_strategy_algorithm.md"
notepad "$($latest.FullName)\\universe_results.json"
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

## Previous request note

The previous request was to inspect the winner details from the single-symbol AMD run:

```text
top_strategy_algorithm.md
strategy_build_trace.md
execution_quality_report.md
real_data_report.md
```

The terminal output already proved the important part: yfinance data loaded and the in-sample objective was hit. The report snippets are still useful for reviewing exact metrics, but they are no longer blocking v21.5.
