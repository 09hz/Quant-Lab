# Replay Date Range Full Patch

This bundle fully implements the replay date-range loader and restores the backtest UI.

## Files

- `Live/core/ReplayModule.py`
- `Live/services/replay_service.py`
- `Live/ui/tabs_ui.py`
- `Live/callbacks.py`
- `Live/assets/style.css`

## What changed

- Replay range loading now loads raw `1 min` bars for every weekday in the selected range.
- Weekends are skipped.
- Multi-day bars are stitched into one DataFrame and installed into `ReplayEngine`.
- The replay slider max becomes the full stitched bar count.
- Watch interval selection no longer causes an IB reload; it only resamples chart display.
- Single-day replay also loads raw `1 min` bars and displays the selected interval via resampling.
- Strategy backtest controls are restored inside the Strategy Lab tab.
- `ReplayEngine` and `ReplayService` expose `all_bars()` so backtests can use the full loaded dataset.

## Test

```bash
python -m py_compile Live/core/ReplayModule.py
python -m py_compile Live/services/replay_service.py
python -m py_compile Live/ui/tabs_ui.py
python -m py_compile Live/callbacks.py
python Live/app.py
```

Then test:

- Start Monday → End Tuesday → Load Range
- Start Friday → End Monday → Load Range
- Select 15 min interval; it should resample without `Unsupported timeframe`.
- Run Strategy Lab backtest; the backtest section should be visible.
