# Watch Live Guard Patch 29

Adds a UI safety guard for the Watch tab so live-specific Watch controls are disabled on weekends and approximate U.S. equity-market holidays.

## Files

- `Live/services/market_calendar/live_trading_day.py`
- `Live/services/watch/live_guard_callbacks.py`
- `Live/assets/zz_watch_live_guard.css`
- `Live/ui/tabs_ui.py`
- `Live/app.py`

## Behavior

When the live guard is enabled and the current New York date is not an open live trading day:

- Watch symbol dropdown is disabled.
- Watch timeframe dropdown is disabled.
- A banner tells the user to use Replay or CSV/local data.

Replay controls are intentionally not disabled.

## Environment variables

```env
WATCH_LIVE_GUARD_ENABLED=true
WATCH_LIVE_MANUAL_OVERRIDE=false
WATCH_MARKET_TIMEZONE=America/New_York
```

## Notes

The market calendar is an offline approximation. It covers common weekends and major U.S. equity-market holidays, but it does not model every special closure or early close.
