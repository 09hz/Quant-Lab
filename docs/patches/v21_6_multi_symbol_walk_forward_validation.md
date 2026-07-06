# v21_6_multi_symbol_walk_forward_validation

## Purpose

Add multi-symbol walk-forward validation.

v21.5 proved the Auto Lab can run a multi-equity universe:

```text
AMD,NVDA,MSFT,AAPL,TSLA
→ per-symbol baseline
→ per-symbol mutation retest
→ universe leaderboard
```

But those results are still in-sample. v21.6 adds a validation layer:

```text
train window
→ discover/mutate candidates
→ pick top candidates

test window
→ retest top train candidates on unseen bars
→ compare train vs test
→ compare against buy-and-hold
→ flag overfit risk
```

## User-selected variables

```text
1. Validation mode: A — single train/test split first.
2. Train window: A — 2020-01-01 to 2023-12-31.
3. Test window: A — 2024-01-01 to 2025-12-31.
4. Candidates to validate: B — top 3 per symbol.
5. Benchmark: B — compare against buy-and-hold return per symbol.
6. UI changes: A — no UI yet.
7. Patch name: v21_6_multi_symbol_walk_forward_validation.py.
```

## Files added

```text
Live/services/ai/auto_lab_orchestrator/walk_forward_reporter.py
Live/services/ai/auto_lab_orchestrator/walk_forward_runner.py
Live/services/ai/auto_lab_orchestrator/walk_forward_self_test.py
```

## Outputs

```text
Live/data/auto_lab_walk_forward_runs/<walk_forward_run_id>/
  walk_forward_universe_results.json
  walk_forward_universe_report.md
  walk_forward_symbol_leaderboard.md
  overfit_warning_report.md
  top_walk_forward_strategy_algorithm.md
```

## Main command

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader"

& "C:\\Users\\sunny\\Documents\\GitHub\\StockVisualizer\\.venv\\Scripts\\python.exe" ".\\Live\\services\\ai\\auto_lab_orchestrator\\walk_forward_runner.py" `
  --symbols AMD,NVDA,MSFT,AAPL,TSLA `
  --train-start 2020-01-01 `
  --train-end 2023-12-31 `
  --test-start 2024-01-01 `
  --test-end 2025-12-31 `
  --yfinance-first `
  --sizing-mode percent_cash_exposure `
  --cash-exposure-pct 95 `
  --top-n-per-symbol 3 `
  --max-total-runs-per-symbol 20 `
  --max-mutations-per-parent 4 `
  --continue-on-error
```

## Run patch

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader"

& "C:\\Users\\sunny\\Documents\\GitHub\\StockVisualizer\\.venv\\Scripts\\python.exe" ".\\v21_6_multi_symbol_walk_forward_validation.py" `
  --repo-root "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader" `
  --run-walk-forward-self-test
```

## Inspect

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader\\Live"

$latest = Get-ChildItem ".\\data\\auto_lab_walk_forward_runs" -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1

notepad "$($latest.FullName)\\walk_forward_universe_report.md"
notepad "$($latest.FullName)\\walk_forward_symbol_leaderboard.md"
notepad "$($latest.FullName)\\overfit_warning_report.md"
notepad "$($latest.FullName)\\top_walk_forward_strategy_algorithm.md"
notepad "$($latest.FullName)\\walk_forward_universe_results.json"
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
