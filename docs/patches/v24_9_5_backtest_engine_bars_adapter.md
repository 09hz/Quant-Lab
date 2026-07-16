# v24.9.5 — BackTestEngine Bars Adapter

## Purpose

Wire the Research Loop to the real project `BackTestEngine.run(bars=...)` path by building a safe historical bars payload first.

v24.9.3 proved the real engine could be imported. The probe showed the blocker is a required `bars` argument that the adapter could not yet supply.

## What this patch adds

- `Live/services/research_loop/bars_adapter.py`
- `Live/services/research_loop/self_test_v24_9_5.py`
- `docs/research_loop_bars_adapter.md`
- `docs/patches/v24_9_5_backtest_engine_bars_adapter.md`

## What this patch patches

- `Live/services/research_loop/backtest_engine_adapter.py`
  - Adds safe support for required `bars` parameters.
  - Builds a historical bars payload from repo data when possible.
  - Falls back to a synthetic simulation-only bars series if no real bars file can be found.

## Behavior

The adapter will now try, in order:

1. Load `Live/core/BackTestEngine.py`
2. Build a safe `bars` payload for each symbol
3. Call the engine with:
   - `symbol`
   - `strategy_name`
   - `parameters`
   - `timeframe`
   - `simulation_only=True`
   - `bars=...`
4. Parse results into the Research Loop evaluation pipeline
5. Fall back to proxy scoring only if the real engine still cannot be called or parsed

## Safety

- Research/simulation only
- No broker calls
- No live trading
- No order placement
- No credentials written
- No file moves or deletes
- Skips dangerous callable names:
  - live
  - order
  - broker
  - execute
  - trade
  - place
  - submit
  - send
