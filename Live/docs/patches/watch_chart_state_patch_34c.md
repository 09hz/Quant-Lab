# Patch 34c — Watch higher-timeframe replay chart state repair

This patch fixes a chart rendering issue after loading higher-timeframe replay
ranges such as `1 hour` and `1 day`.

## Problem

The replay loader can now request higher timeframes, but the Watch chart still
kept old viewport state from earlier `1 min` views. The stored range often stayed
at `1D`, which is too narrow for `1 hour` and especially `1 day` replay candles.

Symptoms:

- Candles appear missing or off-screen.
- Double-click/autorange returns to an unusable view.
- The current price marker/line updates while candles appear absent.
- Changing from 1-minute replay to 1-hour or 1-day replay leaves stale zoom state.

## Fix

The patch adds a Watch chart state normalizer that:

- Uses timeframe-aware default ranges.
- Promotes `1 hour` replay to a wider default range.
- Promotes `1 day` replay to a wider default range.
- Drops stale manual zoom ranges that do not overlap the currently loaded bars.
- Keeps the renderer path at `Live/renderers/watch_chart_renderer.py`.

## Files

- `Live/services/watch_chart_state.py`
- `Live/scripts/check_watch_chart_state.py`
- `Live/renderers/watch_chart_renderer.py`
- `Live/callbacks.py`
