# Patch 34j — Replay native timeframe cache routing

This patch fixes the Watch replay range path where the UI/callbacks send
`1 hour` or `1 day`, but `ReplayService.load_date_range()` still loads every
day as `1 min`.

## Changes

- `ReplayService.load_date_range()` now uses the selected native timeframe.
- `1 min` keeps the existing regular-session/full-session validation.
- Higher timeframes use native cache keys such as `1_hour` and `1_day`.
- Daily bars no longer get dropped by the one-minute 09:30–16:00 filter.
- Replay status text no longer says `raw 1-min bars` for higher timeframe loads.
- Adds a checker script.

## Expected logs

For a daily replay range:

```text
[WATCH LOAD REQUEST] symbol=NVDA timeframe=1 day load_mode=range ...
[REPLAY RANGE TIMEFRAME] symbol=NVDA selected=1 day load_timeframe=1 day
[REPLAY CACHE] provider load ('NVDA', '1 day', '2025-08-01')
[REPLAY SOURCE] requesting symbol=NVDA, timeframe=1 day, date=2025-08-01
```

The key should not be `('NVDA', '1 min', 'YYYY-MM-DD')` when the selected
Watch timeframe is `1 day`.
