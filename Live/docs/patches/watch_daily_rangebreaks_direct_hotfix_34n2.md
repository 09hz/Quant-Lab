# Watch Daily Rangebreaks Direct Hotfix 34n2

## Purpose

Patch 34n failed to locate the exact `create_candlestick_figure(...)` return block in
`Live/renderers/watch_chart_renderer.py`.

This direct hotfix replaces the `WatchChartRenderer.base_candles()` method with a
daily-safe version instead of matching one exact return statement.

## Behavior

For `1 day` Watch replay charts:

- clears intraday Plotly x-axis rangebreaks;
- keeps the x-axis as a date axis;
- pads the x-axis by one calendar day on each side;
- logs `[WATCH DAILY RENDER] ... rangebreaks=off`.

This is needed because native daily IBKR bars are timestamped at midnight. Intraday
rangebreaks can hide those candles entirely.
