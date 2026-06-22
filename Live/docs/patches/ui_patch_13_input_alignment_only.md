# UI Patch 13 — Input Alignment Only

This patch is intentionally narrow.

## Fixes

- Backtest `Initial Cash` input values no longer sit off to the right.
- Backtest `Quantity` input values no longer sit off to the right.
- Replay Start / Replay End date controls are styled through Dash `DatePickerSingle` wrappers instead of broad global form styling.
- Date boxes are given enough width for `MM/DD/YYYY`.

## Safety boundary

This patch does **not** target:

- Plotly
- `dcc.Graph`
- candle charts
- PnL charts
- SVG
- canvas
- graph containers
- JavaScript resize behavior

## File added

```text
Live/assets/zz_input_alignment_only.css
```

## Older UI patch assets removed if present

```text
Live/assets/ui_backtest_replay_polish.css
Live/assets/plotly_resize_stabilizer.js
Live/assets/backtest_layout_fix.css
Live/assets/replay_controls_polish.css
Live/assets/zz_backtest_replay_ui_safe.css
Live/assets/zz_replay_date_controls_only.css
Live/assets/zz_date_cash_quantity_only.css
```

## Browser cache note

After applying, restart Dash and press `Ctrl + F5` in the browser.
