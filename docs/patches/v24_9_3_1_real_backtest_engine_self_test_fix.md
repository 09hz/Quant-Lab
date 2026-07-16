# v24.9.3.1 — Real BackTestEngine Self-Test Fix

## Purpose

Fix the v24.9.3 self-test syntax error and remove the fake temporary BackTestEngine from the self-test.

The broken self-test error was:

```text
NameError: name 'r' is not defined
```

## Why the fake engine existed

The fake engine was intended only as an isolated adapter unit test, not as a replacement for the project BackTestEngine. That was a poor fit here because this project already has:

```text
Live/core/BackTestEngine.py
```

## What this patch changes

- Rewrites `self_test_v24_9_3.py` to probe the actual project `Live/core/BackTestEngine.py`.
- Improves the adapter loader so it tries a normal project import first:
  - `core.BackTestEngine`
- Falls back to file loading only if normal import fails.
- Keeps hybrid-safe behavior:
  - try real BackTestEngine first
  - if incompatible, fall back to proxy and report the reason

## Files patched

- `Live/services/research_loop/backtest_engine_adapter.py`
- `Live/services/research_loop/self_test_v24_9_3.py`
- `docs/patches/v24_9_3_1_real_backtest_engine_self_test_fix.md`

## Safety

- No Data Library edits
- No main app layout edits
- No broker calls
- No live trading
- No order placement
- No credentials written
- No file moves or deletes
