# Research Loop Orchestrator

v24.9.0 adds the first strategy/backtest improvement loop.

This is a research/simulation system. It does not place orders or connect to brokers.

## Goal

The goal is to make the AI research process smarter by turning every strategy attempt into structured feedback:

```text
Generate strategy candidates
Test them
Score them
Store the results
Remember what worked and failed
Use that memory in the next loop
```

## Current v24.9.0 behavior

The first version uses a deterministic local proxy evaluator. That means it creates stable, repeatable simulated metrics for strategy candidates so the loop, Quant Schema storage, dashboard visibility, and feedback path can be tested safely.

Later versions can replace the proxy evaluator with direct adapters to your real `BackTestEngine`, walk-forward runner, and universe runner.

## Loop steps

```text
1. Read loop config
2. Generate strategy candidates from theme and symbols
3. Evaluate each candidate with deterministic proxy backtest metrics
4. Apply risk/data-quality filters
5. Score candidates
6. Select survivors
7. Persist experiment/strategy/backtest/walk-forward/universe rows to Quant Schema
8. Write loop report JSON/Markdown
9. Write Market Memory feedback note
10. Refresh Quant Dashboard to review results
```

## Recommended command

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader\Live"

$PY = "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe"

& $PY -m services.research_loop.orchestrator `
  --repo-root "C:\Users\sunny\Documents\GitHub\AlgoTrader" `
  --theme "AI infrastructure semiconductors" `
  --symbols "AMD,NVDA,SMH" `
  --max-candidates 10 `
  --max-loops 1 `
  --backend sqlite
```

## What to look for in Quant Dashboard

After the loop runs, refresh Quant Dashboard and check:

- `experiment_runs`
- `strategy_runs`
- `backtest_runs`
- `walk_forward_runs`
- `universe_runs`
- `data_quality_events`

## Next patch

Recommended next:

```text
v24.9.1 — Native Quant Dashboard Tab
```

Then:

```text
v24.9.2 — Real BackTestEngine Adapter
```

The adapter should call your existing historical simulation engine behind a safe interface, while keeping all broker/live execution disabled.
