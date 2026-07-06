# v21_3_first_mutation_retest_loop

## Purpose

Start the first real Auto Lab mutation/retest loop.

v21.2 proved the clean core-engine seed path works:

```text
candidate_count: 8
passed_count: 6
engine_pass/research_pass seeds:
- example_boolean_crossover
- example_ema_crossover
- seed_ema_crossover
- example_rsi_mean_reversion
- seed_boolean_crossover
- seed_rsi_mean_reversion
```

All passing candidates missed the 2x target, so the next correct step is mutation/retesting.

## User-selected variables

```text
1. Mutation scope: B — mutate all engine_pass=True candidates from latest smoke run.
2. Quantity mutation: B — keep quantity fixed for cleaner signal testing.
3. Profit factor handling: C — show no_loss_trades label and cap score.
4. Parent selection: A — all research_pass=True.
5. Run size: A — small, max 20 mutations.
6. Data mode: A — synthetic bars still.
7. UI changes: A — no UI, reports only.
8. Patch name: v21_3_first_mutation_retest_loop.py.
```

## Files added / changed

```text
Live/services/ai/auto_lab_orchestrator/mutator.py
Live/services/ai/auto_lab_orchestrator/mutation_reporter.py
Live/services/ai/auto_lab_orchestrator/mutation_retest_loop.py
```

Also patches future report/metric display behavior:

```text
Live/services/ai/auto_lab_orchestrator/adapters.py
Live/services/ai/auto_lab_orchestrator/report_builder.py
```

## Files intentionally not modified

```text
Live/core/BackTestEngine.py
Live/core/StrategyEngine.py
Live/callbacks.py
Live/services/ai/research_autolab/*
Live/ui/*
```

## What v21.3 does

```text
latest core smoke run
→ select parent candidates with engine_pass=True and research_pass=True
→ generate safe parameter mutations
→ run each mutation through CoreStrategyBacktestAdapter
→ score each mutation
→ write mutation report and experiment memory
```

## Mutation types

```text
EMA/SMA fast/slow windows
RSI length
RSI buy threshold
RSI sell threshold
```

Quantity is intentionally fixed in v21.3.

## Output files

Each mutation run writes the normal run bundle:

```text
Live/data/auto_lab_runs/<run_id>/
  experiment_run.json
  results.json
  scorecards.json
  report.md
```

and v21.3 adds:

```text
  mutation_results.json
  mutation_report.md
  experiment_memory.json
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

## Run patch

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader"

& "C:\\Users\\sunny\\Documents\\GitHub\\StockVisualizer\\.venv\\Scripts\\python.exe" ".\\v21_3_first_mutation_retest_loop.py" `
  --repo-root "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader" `
  --run-mutation-smoke
```

Expected patch-level output:

```text
v21.3 first mutation retest loop complete.
- compile: PASS
- mutation_smoke: PASS
```

The mutation smoke is non-blocking unless `--strict-mutation-smoke` is used.

## Run mutation loop later

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader"

& "C:\\Users\\sunny\\Documents\\GitHub\\StockVisualizer\\.venv\\Scripts\\python.exe" ".\\Live\\services\\ai\\auto_lab_orchestrator\\mutation_retest_loop.py" `
  --max-total-runs 20 `
  --max-mutations-per-parent 4
```

## Inspect latest mutation report

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader\\Live"

$latest = Get-ChildItem ".\\data\\auto_lab_runs" -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1

notepad "$($latest.FullName)\\mutation_report.md"
notepad "$($latest.FullName)\\experiment_memory.json"
```

## v21.4 target

Connect the loop to real CSV/current-app bars:

```text
clean parent seeds
→ mutation loop
→ CSV/current app bars
→ score
→ experiment memory
→ AI report/explanation
```
