# v24.6.1 — Direct Producer Wiring Self-Test + Category Inference Fix

## Purpose

Fix the v24.6 self-test failure:

```text
AssertionError: {'status': 'wired', 'module': 'core.BackTestEngine', 'wrapped': 0, 'members': []}
```

## Cause

The direct producer wrapper intentionally avoids wrapping imported functions that do not belong to the target module. The self-test created fake functions inside the self-test module, so the safety check rejected them.

There was also a category inference weakness: module name could dominate method name. For example, inside `core.BackTestEngine`, a function named `run_universe` could be classified as `backtest` because the module name contained `BackTestEngine`.

## Fix

- Update `infer_category()` to prioritize the function/method name before the module name.
- Update the self-test to mark synthetic functions/classes as belonging to the simulated producer module.

## Safety

Research/simulation only.

- No broker calls
- No live trading
- No order placement
- No file moves
- No file deletes
- No credentials written
