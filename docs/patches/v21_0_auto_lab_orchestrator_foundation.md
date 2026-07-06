# v21_0_auto_lab_orchestrator_foundation

## Purpose

Create the first clean AI Auto Lab orchestration layer above the existing strategy/backtest engines.

This does not rebuild the current backtester or strategy engine. It creates a new layer that can later call them through adapters.

## User-selected variables

```text
1. Integration style: A — create new Auto Lab orchestrator beside existing research_autolab.
2. First engine adapter: C — support both core StrategyEngine/BackTestEngine and a self-test toy adapter.
3. First data mode: A — fake sample bars self-test only for v21.0, then CSV/current app bars later.
4. Scoring: A — deterministic scorecard now.
5. Strategy generation: A — schema + templates only, no AI generation yet.
6. Safety: A — simulation-only hard guard.
7. Output files: A — write Auto Lab run JSON + markdown report.
8. Patch name: v21_0_auto_lab_orchestrator_foundation.py.
```

## Why this patch is needed

The diagnostic found the existing project already has:

```text
Live/core/StrategyEngine.py
StrategyEngine.run(script, bars) -> StrategyScriptResult

Live/core/BackTestEngine.py
BackTestEngine.run(bars, signals, initial_cash, quantity) -> BacktestResult

Live/services/ai/research_autolab/
Existing AutoLab planner/csv runner/reporter/ui callbacks

Live/callbacks.py
Existing manual strategy backtest callback
```

v21.0 creates the missing orchestration layer:

```text
Goal
→ candidate strategy specs
→ adapter
→ backtest result normalization
→ deterministic scorecard
→ experiment run memory
→ markdown/json report
```

## Files added

```text
Live/services/ai/auto_lab_orchestrator/__init__.py
Live/services/ai/auto_lab_orchestrator/models.py
Live/services/ai/auto_lab_orchestrator/safety.py
Live/services/ai/auto_lab_orchestrator/sample_data.py
Live/services/ai/auto_lab_orchestrator/templates.py
Live/services/ai/auto_lab_orchestrator/scorecard.py
Live/services/ai/auto_lab_orchestrator/adapters.py
Live/services/ai/auto_lab_orchestrator/report_builder.py
Live/services/ai/auto_lab_orchestrator/orchestrator.py
Live/services/ai/auto_lab_orchestrator/self_test.py
```

## Files intentionally not modified

```text
Live/core/BackTestEngine.py
Live/core/StrategyEngine.py
Live/callbacks.py
Live/services/ai/research_autolab/*
Live/ui/*
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

## New architecture

```text
AI / user goal
→ ExperimentGoal
→ StrategyCandidate list
→ AutoLabOrchestrator
→ EngineAdapter
   - ToyBacktestAdapter for self-test
   - CoreStrategyBacktestAdapter for future connection
→ NormalizedBacktestResult
→ StrategyScorecard
→ AutoLabReport
→ JSON + markdown run bundle
```

## Output folders

Self-test writes to:

```text
Live/data/auto_lab_runs/<run_id>/
  experiment_run.json
  report.md
  scorecards.json
  results.json
```

## Run patch

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader"

& "C:\\Users\\sunny\\Documents\\GitHub\\StockVisualizer\\.venv\\Scripts\\python.exe" ".\\v21_0_auto_lab_orchestrator_foundation.py" `
  --repo-root "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader" `
  --run-self-test
```

Expected:

```text
v21.0 Auto Lab orchestrator foundation complete.
- compile: PASS
- self_test: PASS
```

## Run self-test later

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader"

& "C:\\Users\\sunny\\Documents\\GitHub\\StockVisualizer\\.venv\\Scripts\\python.exe" ".\\Live\\services\\ai\\auto_lab_orchestrator\\self_test.py"
```

Expected:

```text
AI Auto Lab Orchestrator self-test: PASS
```

## Inspect outputs

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader\\Live"

Get-ChildItem ".\\data\\auto_lab_runs" -Recurse | Select-Object -First 40

Get-ChildItem ".\\data\\auto_lab_runs" -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
```

Open latest report:

```powershell
$latest = Get-ChildItem ".\\data\\auto_lab_runs" -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
notepad "$($latest.FullName)\\report.md"
```

## v21.1 target

Connect the orchestrator to the existing real engine paths:

```text
StrategyEngine.run(script, bars)
BackTestEngine.run(bars, signals, initial_cash, quantity)
research_autolab.csv_runner.run_backtest_request_from_csv(...)
```

v21.0 keeps this as an adapter foundation only so we do not break current UI behavior.
