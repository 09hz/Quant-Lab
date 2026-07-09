# v24.9.3 — Real BackTestEngine Adapter

## Purpose

Upgrade the Research Loop so it can try the real project `BackTestEngine` before falling back to deterministic proxy scoring.

v24.9.0-v24.9.2 proved the strategy/backtest loop, report writing, Quant Schema storage, and dashboard controls. v24.9.3 adds a safe adapter boundary for real historical simulation.

## What this patch adds

- `Live/services/research_loop/backtest_engine_adapter.py`
- `Live/services/research_loop/evaluation_pipeline.py`
- `Live/services/research_loop/self_test_v24_9_3.py`
- `docs/research_loop_backtest_engine_adapter.md`
- `docs/patches/v24_9_3_real_backtest_engine_adapter.md`

## What this patch patches

- `Live/services/research_loop/models.py`
  - Adds `evaluation_mode = "hybrid_safe"`

- `Live/services/research_loop/orchestrator.py`
  - Uses the evaluation pipeline instead of direct proxy scoring.
  - Adds CLI option `--evaluation-mode`.

## Evaluation modes

```text
proxy
  Always use deterministic proxy scoring.

hybrid_safe
  Try the real BackTestEngine through a safe adapter.
  If the adapter cannot find/call/parse a compatible backtest function, fall back to proxy scoring.

real_required
  Try the real BackTestEngine.
  If real engine evaluation fails, do not silently treat proxy results as real.
```

## Safety

- Research/simulation only
- No broker calls
- No live trading
- No order placement
- Avoids callable names containing live/order/broker/execute/trade
- Calls only functions whose required arguments can be safely satisfied
- Passes `simulation_only=True` when supported
- Falls back to proxy if real engine shape is incompatible
- Does not touch Data Library or main app layout
