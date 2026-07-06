# v21_1_core_engine_smoke_test_and_objective_scorecard

## Purpose

Upgrade the v21.0 Auto Lab foundation into a more useful product-grade experiment layer.

v21.0 proved the orchestration loop works:

```text
Goal → candidates → adapter → normalized results → scorecard → report bundle
```

But the first report exposed an important issue:

```text
Strategies could show Passed=True even when they did not reach the user's target objective.
```

v21.1 fixes that by splitting the result into separate labels:

```text
engine_pass
research_pass
objective_hit
objective_progress_pct
retest_recommendation
```

It also adds a real core-engine smoke-test path using the existing project engines:

```text
StrategyEngine.run(script, bars)
BackTestEngine.run(bars, signals, initial_cash, quantity)
```

## User-selected variables

```text
1. v21.1 focus: C — core engine smoke test + objective scorecard labels.
2. Data mode: A — synthetic bars with real StrategyEngine + BackTestEngine first.
3. Strategy scripts: C — built-in simple templates + scan existing strategy examples.
4. Pass/fail wording: B — split into engine_pass, research_pass, objective_hit.
5. Target behavior: C — objective_hit false and objective_progress percent shown.
6. Modify UI now: A — no UI changes; JSON/markdown reports only.
7. Safety: A — simulation-only hard guard; no broker/paper trading calls.
8. Patch name: v21_1_core_engine_smoke_test_and_objective_scorecard.py.
```

## Files changed / added

```text
Live/services/ai/auto_lab_orchestrator/models.py
Live/services/ai/auto_lab_orchestrator/scorecard.py
Live/services/ai/auto_lab_orchestrator/report_builder.py
Live/services/ai/auto_lab_orchestrator/adapters.py
Live/services/ai/auto_lab_orchestrator/sample_data.py
Live/services/ai/auto_lab_orchestrator/templates.py
Live/services/ai/auto_lab_orchestrator/core_engine_smoke_test.py
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

## What changes

### 1. Objective-aware scorecard

The scorecard now separates:

```text
engine_pass:
  Did the engine produce a usable result?

research_pass:
  Is the result worth further research based on deterministic gates?

objective_hit:
  Did the strategy actually reach the user's target equity?

objective_progress_pct:
  How far it got toward the target return.
```

Example:

```text
engine_pass=True
research_pass=True
objective_hit=False
objective_progress_pct=1.22
```

That means:

```text
The test ran and may be worth further study,
but it did not meet the user's 2x target.
```

### 2. Better report language

The report table now shows:

```text
Engine
Research
Objective
Progress
Retest recommendation
```

instead of one overloaded `Passed` flag.

### 3. Core engine smoke test

Adds:

```text
Live/services/ai/auto_lab_orchestrator/core_engine_smoke_test.py
```

It tries:

```text
CoreStrategyBacktestAdapter
→ StrategyEngine.run(...)
→ BackTestEngine.run(...)
→ normalized results
→ scorecards
→ report bundle
```

using synthetic bars first.

### 4. Example strategy scanning

The smoke test scans likely example folders and extracts scripts from `.txt`, `.md`, `.strategy`, `.strat`, and `.py` files when safe.

It still does not execute raw Python directly. Scripts are passed into your existing `StrategyEngine`, which is the controlled Strategy Lab path.

### 5. Toy adapter remains available

The toy adapter is still used for basic orchestrator self-test, but its report now uses the clearer objective labels.

## Run patch

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader"

& "C:\\Users\\sunny\\Documents\\GitHub\\StockVisualizer\\.venv\\Scripts\\python.exe" ".\\v21_1_core_engine_smoke_test_and_objective_scorecard.py" `
  --repo-root "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader" `
  --run-self-test `
  --run-core-smoke
```

Expected patch-level output:

```text
v21.1 core engine smoke test and objective scorecard complete.
- compile: PASS
- self_test: PASS
```

The core smoke test is non-blocking by default. If the real engine path fails because templates do not match the current Strategy Lab language, the patch still succeeds and prints the diagnostic. Use `--strict-core-smoke` only when you want core smoke failure to fail the patch command.

## Run self-test later

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader"

& "C:\\Users\\sunny\\Documents\\GitHub\\StockVisualizer\\.venv\\Scripts\\python.exe" ".\\Live\\services\\ai\\auto_lab_orchestrator\\self_test.py"
```

## Run core smoke later

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader"

& "C:\\Users\\sunny\\Documents\\GitHub\\StockVisualizer\\.venv\\Scripts\\python.exe" ".\\Live\\services\\ai\\auto_lab_orchestrator\\core_engine_smoke_test.py"
```

## Inspect latest reports

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader\\Live"

Get-ChildItem ".\\data\\auto_lab_runs" -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 5

$latest = Get-ChildItem ".\\data\\auto_lab_runs" -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
notepad "$($latest.FullName)\\report.md"
```

## Expected report improvement

Instead of:

```text
Passed=True even though target missed
```

you should now see:

```text
engine_pass=True
research_pass=True/False
objective_hit=False
objective_progress_pct=...
retest_recommendation=...
```

## v21.2 target

After the real core smoke test shows which scripts work, v21.2 should connect the orchestrator to real CSV/current-app bars and begin multi-run mutation/retest experiments.
