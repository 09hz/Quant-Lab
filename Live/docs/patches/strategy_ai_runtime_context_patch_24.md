# Patch 24 — Strategy AI Runtime Context Framework

This patch adds a backend framework for making the AI Advisor aware of the user's current Strategy Lab state.

## Goal

When the user asks the AI about a strategy, the AI should receive a sanitized snapshot of:

- current strategy editor text
- current symbol
- current timeframe
- selected start/end range
- initial cash and quantity
- compact OHLCV bars summary
- latest backtest summary, if available
- validation messages, if available
- the user's question

## Backtest auto-run policy

If the user asks AI and no backtest has run yet, the app may run a local backtest first only when the UI explicitly allows it.

Recommended UI wording:

> Include latest backtest result. If no result exists, run a local backtest first.

The auto-run must remain local, broker-free, and advisory-only.

## Safety rules

The framework intentionally does not include:

- broker account data
- open orders
- positions
- API keys
- raw full bar history by default
- autonomous trading permissions

The AI receives a compact context block, not unrestricted application access.

## Files added

- `Live/services/ai/current_strategy_context.py`
- `Live/scripts/check_current_strategy_context.py`

## Test

```powershell
python -m py_compile .\Live\services\ai\current_strategy_context.py
python -m py_compile .\Live\scripts\check_current_strategy_context.py
python .\Live\scripts\check_current_strategy_context.py
```

## Next patch

Wire this into Strategy Lab callbacks:

- Attach Current Strategy Context
- Include Backtest Result
- Auto-run Backtest if missing
- Attach Bars Summary
- Ask AI with attached context
