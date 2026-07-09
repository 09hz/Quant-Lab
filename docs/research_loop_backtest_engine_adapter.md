# Real BackTestEngine Adapter

v24.9.3 adds a safe adapter between the Research Loop and the project `BackTestEngine`.

## Why this exists

The Research Loop should be the research manager. It should not hard-code one backtest implementation. It should call a safe adapter that can:

1. Find the available `BackTestEngine`.
2. Call only compatible simulation/backtest functions.
3. Extract metrics from returned results.
4. Fall back to proxy scoring if the engine API is incompatible.
5. Store/report the source of the evaluation.

## Modes

```text
proxy
  Use deterministic proxy scoring only.

hybrid_safe
  Try real BackTestEngine first.
  Fall back to proxy scoring if the adapter cannot safely run.

real_required
  Require the real BackTestEngine.
  If it cannot run, report failure for the candidate instead of pretending proxy results are real.
```

## Recommended first run

Use hybrid mode first:

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader\Live"

$PY = "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe"

& $PY -m services.research_loop.orchestrator `
  --repo-root "C:\Users\sunny\Documents\GitHub\AlgoTrader" `
  --theme "AI infrastructure semiconductors" `
  --symbols "AMD,NVDA,SMH" `
  --max-candidates 10 `
  --max-loops 1 `
  --backend sqlite `
  --evaluation-mode hybrid_safe
```

## How the adapter stays safe

The adapter skips callable names containing:

```text
live
order
broker
execute
trade
place
submit
send
```

It only calls functions/methods whose required arguments it can supply from:

```text
symbol
symbols
strategy_name
candidate
parameters
timeframe
repo_root
simulation_only
```

It passes `simulation_only=True` and broker-disable environment variables when possible.

## Still not live trading

The adapter is for historical simulation only. It does not place orders, route orders, connect to a broker for trading, or produce trade recommendations.
