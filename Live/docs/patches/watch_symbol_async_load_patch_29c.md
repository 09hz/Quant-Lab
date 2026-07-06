# Patch 29c — Watch symbol async load guard

## Purpose

Fix Watch tab freezes when selecting a live symbol that has not been loaded yet.

Previously, `BarViewService.build_watch_view()` called `request_symbol()` directly from the Dash chart render path. For unloaded IBKR symbols this can block the callback and make the app appear frozen.

## Changes

Added:

- `Live/services/watch/symbol_load_guard.py`

Updated:

- `Live/services/bar_view_service.py`

## Behavior

When Watch is using live data:

1. The symbol request is started in a daemon background thread.
2. The render callback immediately returns a loading chart if no snapshot exists yet.
3. Duplicate loads for the same symbol/timeframe are throttled.
4. Previously loaded/cached symbols still render normally.

## Environment

Optional:

```env
WATCH_SYMBOL_LOAD_COOLDOWN_SECONDS=20
```

## Safety

This patch does not change broker/order logic, paper trading, strategy execution, Newsroom, AI, or data-provider configuration.
