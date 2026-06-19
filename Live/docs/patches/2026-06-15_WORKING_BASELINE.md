
# Working Baseline Saved

Date saved: 2026-06-15

This bundle preserves the code state/features that were confirmed or intended as working during the debugging session.

## Do not touch for now

- Dashboard working baseline lives in `callbacks_dashboard_diagnostic_only_WORKING.py`.
- The important working Dashboard behavior:
  - Dashboard renderer only was changed.
  - Watch/replay/paper callbacks were left untouched.
  - `rt.request_symbol(symbol)` is called in Dashboard renderer to avoid stale subscription state.
  - Candle dataframe is copied and normalized.
  - Candlestick trace arrays are converted to plain Python lists.
  - `uirevision=None` during diagnostic mode.
  - `datarevision` includes symbol, timeframe, mode, range, latest OHLC, current price, and tick.
  - Title includes symbol/timeframe/last/tick.

## Dashboard baseline key block

```python
fig.update_layout(
    uirevision=None,
    datarevision=redraw_key,
    dragmode="pan",
    title={
        "text": f"{symbol} · {timeframe} · Last {current_price:,.2f} · tick {_n}",
        "x": 0.02,
        "xanchor": "left",
    },
)
```

## PaperBroker short-margin fix

Saved file:
- `PaperBroker_short_margin_fixed.py`

Purpose:
- Short sell should not make visible cash jump up.
- Opening a short reserves collateral and reduces cash.
- Covering a short releases collateral and applies realized PnL.
- Negative `PaperPosition.quantity` still represents a short position.

## UI/callback changes planned/applied manually

### Short buttons

Add to Paper Trading button group in `tabs_ui.py`:

```python
html.Button(
    "SHORT BUY",
    id="paper-short-buy",
    n_clicks=0,
    className="paper-btn paper-short-btn hidden",
),

html.Button(
    "SHORT SELL",
    id="paper-short-sell",
    n_clicks=0,
    className="paper-btn paper-short-btn hidden",
),
```

CSS:

```css
.paper-short-btn {
    border: 1px solid rgba(248, 113, 113, 0.75);
    color: #fecaca;
    background: rgba(127, 29, 29, 0.22);
}

.paper-short-btn:hover {
    border-color: rgba(248, 113, 113, 1);
    background: rgba(127, 29, 29, 0.42);
}

.paper-short-btn.hidden {
    display: none !important;
}
```

Callback inside `register_callbacks(...)` near paper trading callbacks:

```python
@app.callback(
    Output("paper-short-buy", "className"),
    Output("paper-short-sell", "className"),
    Input("paper-position-mode", "value"),
    State("main-tabs", "value"),
    prevent_initial_call=False,
)
def toggle_short_trade_buttons(position_mode, active_tab):
    if active_tab != "watch":
        return no_update, no_update

    allow_short = str(position_mode or "long_only") == "allow_shorts"

    if allow_short:
        return (
            "paper-btn paper-short-btn",
            "paper-btn paper-short-btn",
        )

    return (
        "paper-btn paper-short-btn hidden",
        "paper-btn paper-short-btn hidden",
    )
```

### Update paper trade callback inputs

Decorator inputs should include:

```python
Input("paper-buy", "n_clicks"),
Input("paper-sell", "n_clicks"),
Input("paper-short-buy", "n_clicks"),
Input("paper-short-sell", "n_clicks"),
Input("paper-reset", "n_clicks"),
```

Function signature should include:

```python
def handle_manual_paper_trade(
        buy_clicks,
        sell_clicks,
        short_buy_clicks,
        short_sell_clicks,
        reset_clicks,
        quantity,
        symbol,
        price_source,
        position_mode,
        replay_date,
        paper_trigger,
        active_tab,
):
```

Short intent cases:

```python
elif trigger == "paper-short-sell":
    if not allow_short:
        return "Short selling is disabled. Select Allow Shorts first.", no_update

    intent = TradeIntent(
        symbol=symbol,
        side="SELL",
        quantity=quantity,
        order_type="MARKET",
        reason="Manual short sell",
        source=f"manual_short:{source_label}",
    )

elif trigger == "paper-short-buy":
    if not allow_short:
        return "Short buying/covering is disabled. Select Allow Shorts first.", no_update

    intent = TradeIntent(
        symbol=symbol,
        side="BUY",
        quantity=quantity,
        order_type="MARKET",
        reason="Manual short cover",
        source=f"manual_short_cover:{source_label}",
    )
```

## Analytics drawer

Added/desired:
- `trade-analytics-open`
- `trade-analytics-close`
- `trade-analytics-drawer`
- `trade-analytics-content`
- PnL curve via `dcc.Graph`

Important import for analytics PnL chart:

```python
from dash import Input, Output, State, html, dcc, no_update, ctx
```

## Paper cache

New service file planned:
- `Live/services/paper_cache.py`

Purpose:
- Save paper summary/positions/orders/fills under `cache/paper/`
- Save after each trade and reset.
- Later restore account state on startup after inspecting `PaperBroker.py`/`paper_trading_service.py`.

## Current debugging focus

User is debugging a minor candle issue. Use the Dashboard diagnostic baseline as the rollback point before changing anything else.
