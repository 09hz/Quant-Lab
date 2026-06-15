# =============================================================================
# CALLBACK ORDER WARNING
# =============================================================================
# This app is sensitive to callback order because several callbacks share
# interval/store-trigger dependencies.
#
# Keep callback order as:
# 1. Global state/status
# 2. Dashboard state
# 3. Watch state
# 4. Watch replay load/control/clock
# 5. Paper trading state/panels
# 6. Dashboard render
# 7. Watch render
# 8. Quotes render
# 9. Charts render
#
# Render callbacks should not mutate replay/paper/live service state except for
# safe snapshot reads. State mutation should happen in control callbacks, then
# trigger render callbacks through dcc.Store values.
# =============================================================================
from __future__ import annotations
from core.RiskGuard import TradeIntent

from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, html, no_update, ctx

from config import DEFAULT_SYMBOL, DEFAULT_TIMEFRAME
from utils.chart_utils import create_candlestick_figure


RANGE_DAYS = {
    "1D": 1,
    "1W": 7,
    "1M": 30,
    "3M": 90,
    "1Y": 365,
    "5Y": 365 * 5,
}


def _build_metrics_strip(symbol: str, company: str, last, open_, updated_at, prefix: str = "USD"):
    if last is None:
        return [
            html.Div(f"{symbol} / {company}", className="metric-price"),
            html.Div("Waiting for data...", className="metric-muted"),
        ]

    last_f = float(last)
    open_f = float(open_) if open_ not in (None, 0) else last_f
    change = last_f - open_f
    pct = (change / open_f * 100) if open_f else 0.0
    cls = "metric-positive" if change >= 0 else "metric-negative"
    updated_text = updated_at.strftime("%A, %I:%M %p") if updated_at else "--"

    return [
        html.Div(f"{last_f:,.2f} {prefix}", className="metric-price"),
        html.Div(f"{change:+.2f} ({pct:+.2f}%)", className=cls),
        html.Div(f"{symbol} · {company}", className="metric-muted"),
        html.Div(f"Updated {updated_text}", className="metric-muted"),
    ]


def _build_stats_grid_from_bars(df):
    if df is None or df.empty:
        return [
            html.Div(
                className="stat-card",
                children=[html.Div("No data loaded", className="stat-label")],
            )
        ]

    first = df.iloc[0]
    last = df.iloc[-1]

    open_v = float(first["open"])
    high_v = float(df["high"].max())
    low_v = float(df["low"].min())
    close_v = float(last["close"])
    volume_v = float(df["volume"].sum())

    return [
        html.Div(
            className="stat-card",
            children=[
                html.Div(className="stat-row", children=[html.Div("Open", className="stat-label"), html.Div(f"{open_v:,.2f}", className="stat-value")]),
                html.Div(className="stat-row", children=[html.Div("High", className="stat-label"), html.Div(f"{high_v:,.2f}", className="stat-value")]),
                html.Div(className="stat-row", children=[html.Div("Low", className="stat-label"), html.Div(f"{low_v:,.2f}", className="stat-value")]),
            ],
        ),
        html.Div(
            className="stat-card",
            children=[
                html.Div(className="stat-row", children=[html.Div("Close", className="stat-label"), html.Div(f"{close_v:,.2f}", className="stat-value")]),
                html.Div(className="stat-row", children=[html.Div("Bars", className="stat-label"), html.Div(f"{len(df):,}", className="stat-value")]),
                html.Div(className="stat-row", children=[html.Div("Volume", className="stat-label"), html.Div(f"{volume_v:,.0f}", className="stat-value")]),
            ],
        ),
        html.Div(
            className="stat-card",
            children=[
                html.Div(className="stat-row", children=[html.Div("Range", className="stat-label"), html.Div(f"{high_v - low_v:,.2f}", className="stat-value")]),
                html.Div(className="stat-row", children=[html.Div("First Bar", className="stat-label"), html.Div(str(first["time"])[:16], className="stat-value")]),
                html.Div(className="stat-row", children=[html.Div("Last Bar", className="stat-label"), html.Div(str(last["time"])[:16], className="stat-value")]),
            ],
        ),
    ]


def _empty_figure(title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        title=title,
        template="plotly_dark",
        paper_bgcolor="#0d1b4f",
        plot_bgcolor="#0d1b4f",
        font={"color": "#e8f1ff"},
        dragmode="pan",
        hovermode="x unified",
    )
    fig.update_xaxes(fixedrange=False, rangeslider_visible=False)
    fig.update_yaxes(fixedrange=False)
    return fig


def _safe_range_key(value, default="1D") -> str:
    value = str(value or default).upper()
    if value in {"1D", "1W", "1M", "3M", "1Y", "5Y", "MAX"}:
        return value
    return default


def _range_key_from_button(trigger_id: str | None, prefix: str, default="1D") -> str:
    if not trigger_id:
        return default

    raw = trigger_id.replace(prefix, "").lower()
    mapping = {
        "1d": "1D",
        "1w": "1W",
        "1m": "1M",
        "3m": "3M",
        "1y": "1Y",
        "5y": "5Y",
        "max": "MAX",
    }
    return mapping.get(raw, default)


def _clean_relayout_range(relayout_data):
    """
    Extract user-driven Plotly x/y ranges.

    Double-click reset/autorange returns live mode.
    Initial noise is ignored.
    """
    if not relayout_data:
        return no_update

    if (
        relayout_data.get("xaxis.autorange") is True
        or relayout_data.get("yaxis.autorange") is True
        or relayout_data.get("autosize") is True
    ):
        return {
            "mode": "live",
            "x_range": None,
            "y_range": None,
        }

    x0 = relayout_data.get("xaxis.range[0]")
    x1 = relayout_data.get("xaxis.range[1]")
    y0 = relayout_data.get("yaxis.range[0]")
    y1 = relayout_data.get("yaxis.range[1]")

    if x0 is not None and x1 is not None:
        return {
            "mode": "manual",
            "x_range": [x0, x1],
            "y_range": [y0, y1] if y0 is not None and y1 is not None else None,
        }

    if y0 is not None and y1 is not None:
        return {
            "mode": "manual",
            "x_range": None,
            "y_range": [y0, y1],
        }

    return no_update


def _clean_bars_for_view(bars: pd.DataFrame) -> pd.DataFrame:
    if bars is None or bars.empty:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

    df = bars.copy()
    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    df = df.dropna(subset=["time", "high", "low"])

    return df


def _visible_window_from_bars(bars: pd.DataFrame, range_key: str):
    df = _clean_bars_for_view(bars)
    if df.empty:
        return None

    range_key = _safe_range_key(range_key)
    end_time = df["time"].max()

    if range_key == "MAX":
        start_time = df["time"].min()
    else:
        days = RANGE_DAYS.get(range_key, 1)
        start_time = end_time - timedelta(days=days)
        start_time = max(start_time, df["time"].min())

    return [start_time, end_time]


def _fit_y_axis_to_visible_bars(fig, bars: pd.DataFrame, x_range=None):
    """
    Fit y-axis only to visible candles. This prevents candles from becoming
    long, flat, or unreadable when Plotly preserves a bad y-axis range.
    """
    df = _clean_bars_for_view(bars)
    if df.empty:
        return fig

    visible = df
    if x_range:
        x0 = pd.to_datetime(x_range[0], errors="coerce")
        x1 = pd.to_datetime(x_range[1], errors="coerce")

        if pd.notna(x0) and pd.notna(x1):
            visible = df[(df["time"] >= x0) & (df["time"] <= x1)]

    if visible.empty:
        visible = df.tail(100)

    high = float(visible["high"].max())
    low = float(visible["low"].min())

    if high <= low:
        pad = max(abs(high) * 0.005, 0.01)
    else:
        pad = (high - low) * 0.08

    fig.update_yaxes(range=[low - pad, high + pad], fixedrange=False)
    return fig


def _apply_chart_view(fig, bars: pd.DataFrame, chart_state: dict | None, default_range="1D"):
    state = chart_state or {}
    mode = state.get("mode", "live")
    range_key = _safe_range_key(state.get("range_key"), default_range)

    if bars is None or bars.empty:
        return fig

    if mode == "manual":
        x_range = state.get("x_range")
        y_range = state.get("y_range")

        if x_range:
            fig.update_xaxes(range=x_range, fixedrange=False)
            fig = _fit_y_axis_to_visible_bars(fig, bars, x_range)

        if y_range:
            fig.update_yaxes(range=y_range, fixedrange=False)

        return fig

    x_range = _visible_window_from_bars(bars, range_key)
    if x_range:
        fig.update_xaxes(range=x_range, fixedrange=False)

    fig = _fit_y_axis_to_visible_bars(fig, bars, x_range)
    return fig


def _default_chart_state(range_key="1D"):
    return {
        "mode": "live",
        "range_key": range_key,
        "x_range": None,
        "y_range": None,
    }

def register_callbacks(
        app,
        rt,
        replay_service,
        symbol_options,
        timeframe_map,
        paper_trading_service=None,
        paper_state_cache=None,
):
    @app.callback(
        Output("pair-title", "children"),
        Input("active-symbol", "data"),
        Input("main-tabs", "value"),
        Input("watch-symbol-dropdown", "value"),
        Input("symbol-dropdown", "value"),
        State("watch-state", "data"),
        State("dashboard-state", "data"),
    )
    def update_pair_title(
            active_symbol,
            active_tab,
            watch_symbol,
            dashboard_symbol_dropdown,
            watch_state,
            dashboard_state,
    ):
        if active_tab == "watch":
            symbol = (
                    watch_symbol
                    or (watch_state or {}).get("symbol")
                    or DEFAULT_SYMBOL
            )
        else:
            symbol = (
                    active_symbol
                    or dashboard_symbol_dropdown
                    or (dashboard_state or {}).get("symbol")
                    or DEFAULT_SYMBOL
            )

        symbol = str(symbol).upper().strip()
        company = rt.get_company_name(symbol)

        return f"{symbol} / {company}"

    @app.callback(
        Output("load-status-text", "children"),
        Input("load-status", "data"),
    )
    def show_load_status(status):
        return status

    @app.callback(
        Output("dashboard-state", "data"),
        Input("symbol-dropdown", "value"),
        Input("timeframe-dropdown", "value"),
        State("dashboard-state", "data"),
        prevent_initial_call=True,
    )
    def save_dashboard_state(symbol, timeframe, current_state):
        state = dict(current_state or {})
        if symbol:
            state["symbol"] = symbol
        if timeframe:
            state["timeframe"] = timeframe
        return state

    @app.callback(
        Output("watch-state", "data"),
        Input("watch-symbol-dropdown", "value"),
        Input("replay-speed", "value"),
        Input("replay-slider", "value"),
        Input("replay-date", "date"),
        State("watch-state", "data"),
        prevent_initial_call=True,
    )
    def save_watch_state(symbol, replay_speed, replay_index, replay_date, current_state):
        state = dict(current_state or {})
        if symbol:
            state["symbol"] = symbol
        if replay_speed is not None:
            state["replay_speed"] = replay_speed
        if replay_index is not None:
            state["replay_index"] = replay_index
        state["replay_date"] = replay_date
        return state

    @app.callback(
        Output("active-symbol", "data"),
        Output("load-status", "data"),
        Input("symbol-dropdown", "value"),
        State("active-symbol", "data"),
        prevent_initial_call=True,
    )
    def auto_load_symbol(symbol, current_active_symbol):
        if not symbol:
            return no_update, "No symbol selected"

        try:
            symbol = rt._sanitize_symbol(symbol)

            if symbol == current_active_symbol:
                return no_update, no_update

            rt.request_symbol(symbol)
            return symbol, f"Loading live data for {symbol}"
        except Exception as exc:
            return no_update, f"Error: {exc}"


    # ------------------------------------------------------------
    # Dashboard chart interaction state
    # ------------------------------------------------------------
    @app.callback(
        Output("dashboard-chart-state", "data"),
        Input("dashboard-live-mode", "n_clicks"),
        Input("dashboard-reset-view", "n_clicks"),
        Input("dashboard-range-1d", "n_clicks"),
        Input("dashboard-range-1w", "n_clicks"),
        Input("dashboard-range-1m", "n_clicks"),
        Input("dashboard-range-3m", "n_clicks"),
        Input("dashboard-range-1y", "n_clicks"),
        Input("dashboard-range-5y", "n_clicks"),
        Input("dashboard-range-max", "n_clicks"),
        Input("live-chart", "relayoutData"),
        State("dashboard-chart-state", "data"),
        prevent_initial_call=True,
    )
    def update_dashboard_chart_state(*args):
        current_state = dict(args[-1] or _default_chart_state())
        relayout_data = args[-2]
        trigger_id = ctx.triggered_id

        if trigger_id in {"dashboard-live-mode", "dashboard-reset-view"}:
            return _default_chart_state(current_state.get("range_key", "1D"))

        if isinstance(trigger_id, str) and trigger_id.startswith("dashboard-range-"):
            range_key = _range_key_from_button(trigger_id, "dashboard-range-", "1D")
            return _default_chart_state(range_key)

        if trigger_id == "live-chart":
            parsed = _clean_relayout_range(relayout_data)
            if parsed is no_update:
                return no_update

            new_state = dict(current_state)
            new_state.update(parsed)
            new_state["range_key"] = current_state.get("range_key", "1D")
            return new_state

        return no_update

    # ------------------------------------------------------------
    # Watch chart interaction state
    # ------------------------------------------------------------
    @app.callback(
        Output("watch-chart-state", "data"),
        Input("watch-live-mode", "n_clicks"),
        Input("watch-reset-view", "n_clicks"),
        Input("watch-range-1d", "n_clicks"),
        Input("watch-range-1w", "n_clicks"),
        Input("watch-range-1m", "n_clicks"),
        Input("watch-range-3m", "n_clicks"),
        Input("watch-range-1y", "n_clicks"),
        Input("watch-range-5y", "n_clicks"),
        Input("watch-range-max", "n_clicks"),
        Input("watch-chart", "relayoutData"),
        State("watch-chart-state", "data"),
        prevent_initial_call=True,
    )
    def update_watch_chart_state(*args):
        current_state = dict(args[-1] or _default_chart_state())
        relayout_data = args[-2]
        trigger_id = ctx.triggered_id

        if trigger_id in {"watch-live-mode", "watch-reset-view"}:
            return _default_chart_state(current_state.get("range_key", "1D"))

        if isinstance(trigger_id, str) and trigger_id.startswith("watch-range-"):
            range_key = _range_key_from_button(trigger_id, "watch-range-", "1D")
            return _default_chart_state(range_key)

        if trigger_id == "watch-chart":
            parsed = _clean_relayout_range(relayout_data)
            if parsed is no_update:
                return no_update

            new_state = dict(current_state)
            new_state.update(parsed)
            new_state["range_key"] = current_state.get("range_key", "1D")
            return new_state

        return no_update

    # ------------------------------------------------------------
    # Watch replay loading overlay
    # ------------------------------------------------------------
    app.clientside_callback(
        """
        function(activeTab, symbol, replayDate, currentRequest) {
            if (activeTab !== "watch") {
                return [
                    dash_clientside.no_update,
                    dash_clientside.no_update
                ];
            }

            const req = currentRequest || {};
            const nonce = (req.nonce || 0) + 1;

            return [
                "watch-loading-overlay",
                {
                    nonce: nonce,
                    symbol: symbol || "MSFT",
                    replay_date: replayDate || null,
                    timeframe: "1 min"
                }
            ];
        }
        """,
        Output("watch-loading-overlay", "className", allow_duplicate=True),
        Output("watch-load-request", "data", allow_duplicate=True),
        Input("main-tabs", "value"),
        Input("watch-symbol-dropdown", "value"),
        Input("replay-date", "date"),
        State("watch-load-request", "data"),
        prevent_initial_call=True,
    )

    @app.callback(
        Output("watch-status", "children", allow_duplicate=True),
        Output("replay-slider", "max", allow_duplicate=True),
        Output("replay-slider", "value", allow_duplicate=True),
        Output("watch-loading-overlay", "className", allow_duplicate=True),
        Output("replay-render-trigger", "data", allow_duplicate=True),
        Input("watch-load-request", "data"),
        State("replay-speed", "value"),
        State("main-tabs", "value"),
        State("replay-render-trigger", "data"),
        prevent_initial_call=True,
    )
    def load_watch_symbol_from_request(load_request, replay_speed, active_tab, render_trigger):
        if active_tab != "watch":
            return no_update, no_update, no_update, no_update, no_update

        if not load_request:
            return no_update, no_update, no_update, no_update, no_update

        symbol = load_request.get("symbol") or DEFAULT_SYMBOL
        replay_date = load_request.get("replay_date")
        timeframe = load_request.get("timeframe") or "1 min"

        try:
            status, info = replay_service.load_replay(
                symbol=symbol,
                timeframe=timeframe,
                replay_date=replay_date,
                speed=replay_speed or 1,
            )

            max_idx = max(1, int(info.get("max_index", 1)))
            idx = max(1, int(info.get("current_index", 1)))
            render_trigger = int(render_trigger or 0) + 1

            return (
                status,
                max_idx,
                idx,
                "watch-loading-overlay hidden",
                render_trigger,
            )

        except Exception as exc:
            print(f"[REPLAY LOAD ERROR] {exc}", flush=True)
            render_trigger = int(render_trigger or 0) + 1

            return (
                f"Replay load error: {exc}",
                100,
                1,
                "watch-loading-overlay hidden",
                render_trigger,
            )

    @app.callback(
        Output("watch-status", "children", allow_duplicate=True),
        Input("replay-speed", "value"),
        State("main-tabs", "value"),
        prevent_initial_call=True,
    )
    def update_replay_speed(speed, active_tab):
        if active_tab != "watch":
            return no_update

        try:
            replay_service.set_speed(speed or 1)
            return f"Replay speed set to {speed or 1}x"
        except Exception as exc:
            return f"Replay speed error: {exc}"

    @app.callback(
        Output("watch-status", "children", allow_duplicate=True),
        Output("replay-render-trigger", "data", allow_duplicate=True),
        Input("replay-play", "n_clicks"),
        Input("replay-pause", "n_clicks"),
        Input("replay-step", "n_clicks"),
        Input("replay-rewind", "n_clicks"),
        Input("replay-slider", "value"),
        State("replay-render-trigger", "data"),
        State("main-tabs", "value"),
        prevent_initial_call=True,
    )
    def control_replay(
            play_clicks,
            pause_clicks,
            step_clicks,
            rewind_clicks,
            slider_value,
            render_trigger,
            active_tab,
    ):
        if active_tab != "watch":
            return no_update, no_update

        trigger = ctx.triggered_id
        render_trigger = int(render_trigger or 0)

        try:
            info = replay_service.info()
            max_index = max(1, int(info.get("max_index", 1)))

            if max_index <= 1:
                return "No replay data loaded.", no_update

            if trigger == "replay-play":
                replay_service.play()
                return "Replay playing", render_trigger + 1

            if trigger == "replay-pause":
                replay_service.pause()
                return "Replay paused", render_trigger + 1

            if trigger == "replay-step":
                replay_service.forward(1)
                idx = max(1, int(replay_service.info().get("current_index", 1)))
                return f"Replay stepped to {idx}", render_trigger + 1

            if trigger == "replay-rewind":
                replay_service.rewind(1)
                idx = max(1, int(replay_service.info().get("current_index", 1)))
                return f"Replay rewound to {idx}", render_trigger + 1

            if trigger == "replay-slider":
                idx = max(1, min(int(slider_value or 1), max_index))
                current_idx = max(1, int(replay_service.info().get("current_index", 1)))

                # Ignore programmatic slider updates from render_watch_tab.
                # Only treat it as user input when the value actually changes.
                if idx == current_idx:
                    return no_update, no_update

                replay_service.set_index(idx)
                return f"Replay moved to {idx}", render_trigger + 1

            return no_update, no_update

        except Exception as exc:
            print(f"[REPLAY CONTROL ERROR] {exc}", flush=True)
            return f"Replay control error: {exc}", no_update

    @app.callback(
        Output("replay-render-trigger", "data", allow_duplicate=True),
        Input("replay-clock", "n_intervals"),
        State("replay-render-trigger", "data"),
        State("main-tabs", "value"),
        prevent_initial_call=True,
    )
    def advance_replay_clock(_n, render_trigger, active_tab):
        if active_tab != "watch":
            return no_update

        try:
            info_before = replay_service.info()

            if not info_before.get("playing"):
                return no_update

            before_idx = int(info_before.get("current_index", 1))

            replay_service.tick()

            info_after = replay_service.info()
            after_idx = int(info_after.get("current_index", 1))

            if after_idx != before_idx:
                return int(render_trigger or 0) + 1

            return no_update

        except Exception as exc:
            print(f"[REPLAY CLOCK ERROR] {exc}", flush=True)
            return no_update
    def _paper_current_price_and_time(symbol: str):
        """
        Prefer replay cursor price on Watch tab.
        Fallback to live snapshot if replay is empty.
        """
        symbol = symbol or DEFAULT_SYMBOL

        try:
            bar = replay_service.current_bar()
            if bar is not None:
                return float(bar["close"]), bar.get("time", datetime.now())
        except Exception:
            pass

        snap = rt.get_snapshot(symbol, "1 min")
        if snap.last is None:
            return None, datetime.now()

        return float(snap.last), snap.updated_at or datetime.now()

    @app.callback(
        Output("paper-trade-status", "children"),
        Output("paper-trade-trigger", "data"),
        Input("paper-buy", "n_clicks"),
        Input("paper-sell", "n_clicks"),
        Input("paper-reset", "n_clicks"),
        State("paper-order-qty", "value"),
        State("watch-symbol-dropdown", "value"),
        State("paper-trade-trigger", "data"),
        State("main-tabs", "value"),
        prevent_initial_call=True,
    )
    def handle_manual_paper_trade(
        buy_clicks,
        sell_clicks,
        reset_clicks,
        quantity,
        symbol,
        paper_trigger,
        active_tab,
    ):
        if active_tab != "watch":
            return no_update, no_update

        if paper_trading_service is None:
            return "Paper trading service is not enabled.", no_update

        trigger = ctx.triggered_id
        paper_trigger = int(paper_trigger or 0)

        try:
            if trigger == "paper-reset":
                paper_trading_service.reset()

                try:
                    if paper_state_cache is not None:
                        paper_state_cache.clear()
                        paper_state_cache.save_from_service(paper_trading_service)
                except Exception as cache_exc:
                    print(f"[PAPER CACHE RESET ERROR] {cache_exc}", flush=True)

                return "Paper account reset to starting cash.", paper_trigger + 1

            symbol = (symbol or DEFAULT_SYMBOL).upper().strip()

            try:
                quantity = float(quantity or 0)
            except Exception:
                return "Quantity must be numeric.", no_update

            if quantity <= 0:
                return "Quantity must be greater than zero.", no_update

            last_price, timestamp = _paper_current_price_and_time(symbol)

            if last_price is None:
                return f"No current price available for {symbol}.", no_update

            if trigger == "paper-buy":
                intent = TradeIntent(
                    symbol=symbol,
                    side="BUY",
                    quantity=quantity,
                    order_type="MARKET",
                    reason="Manual paper buy",
                    source="manual",
                )

            elif trigger == "paper-sell":
                intent = TradeIntent(
                    symbol=symbol,
                    side="SELL",
                    quantity=quantity,
                    order_type="MARKET",
                    reason="Manual paper sell",
                    source="manual",
                )

            else:
                return no_update, no_update

            decision, order = paper_trading_service.submit_intent(
                intent=intent,
                last_price=last_price,
                timestamp=timestamp,
                mode="simulated",
            )

            try:
                if paper_state_cache is not None:
                    paper_state_cache.save_from_service(
                        paper_trading_service,
                        prices={symbol: float(last_price)},
                    )
            except Exception as cache_exc:
                print(f"[PAPER CACHE SAVE ERROR] {cache_exc}", flush=True)


            if not decision.approved:
                return f"Risk rejected: {decision.message}", paper_trigger + 1

            if order is None:
                return "Order was approved but no order object was returned.", paper_trigger + 1

            fill_text = (
                f"{order.side} {order.quantity:g} {order.symbol} "
                f"@ {order.fill_price:,.2f}"
                if order.fill_price is not None
                else f"{order.side} {order.quantity:g} {order.symbol}"
            )

            return f"Paper order {order.status}: {fill_text}", paper_trigger + 1

        except Exception as exc:
            print(f"[PAPER TRADE ERROR] {exc}", flush=True)
            return f"Paper trade error: {exc}", paper_trigger + 1

    def _paper_df_view(df, empty_message: str, max_rows: int = 8):
        if df is None or df.empty:
            return html.Div(empty_message, className="paper-empty")

        view = df.tail(max_rows).copy()

        datetime_cols = {
            "submitted_at",
            "filled_at",
            "timestamp",
        }

        for col in view.columns:
            col_lower = str(col).lower()

            if col_lower in datetime_cols:
                try:
                    view[col] = pd.to_datetime(
                        view[col],
                        errors="coerce",
                        format="mixed",
                    ).dt.strftime("%Y-%m-%d %H:%M:%S")

                    view[col] = view[col].fillna("")
                except Exception:
                    pass

        return html.Pre(
            view.to_string(index=False),
            className="paper-table",
        )

    @app.callback(
        Output("paper-summary-panel", "children"),
        Output("paper-positions-panel", "children"),
        Output("paper-orders-panel", "children"),
        Output("paper-fills-panel", "children"),
        Input("paper-trade-trigger", "data"),
        Input("replay-render-trigger", "data"),
        State("watch-symbol-dropdown", "value"),
        State("main-tabs", "value"),
        prevent_initial_call=False,
    )
    def render_paper_trading_panels(_paper_trigger, _replay_trigger, symbol, active_tab):
        if active_tab != "watch":
            return no_update, no_update, no_update, no_update

        if paper_trading_service is None:
            disabled = html.Div("Paper trading service is disabled.", className="paper-empty")
            return disabled, disabled, disabled, disabled

        symbol = (symbol or DEFAULT_SYMBOL).upper().strip()

        prices = {}
        try:
            price, _timestamp = _paper_current_price_and_time(symbol)
            if price is not None:
                prices[symbol] = float(price)
        except Exception:
            pass

        summary = paper_trading_service.summary(prices=prices)

        summary_cards = html.Div(
            className="paper-summary-cards",
            children=[
                html.Div(
                    className="paper-summary-card",
                    children=[
                        html.Div("Cash", className="paper-summary-label"),
                        html.Div(f"${summary.get('cash', 0):,.2f}", className="paper-summary-value"),
                    ],
                ),
                html.Div(
                    className="paper-summary-card",
                    children=[
                        html.Div("Equity", className="paper-summary-label"),
                        html.Div(f"${summary.get('equity', 0):,.2f}", className="paper-summary-value"),
                    ],
                ),
                html.Div(
                    className="paper-summary-card",
                    children=[
                        html.Div("Open Positions", className="paper-summary-label"),
                        html.Div(f"{summary.get('open_positions', 0)}", className="paper-summary-value"),
                    ],
                ),
                html.Div(
                    className="paper-summary-card",
                    children=[
                        html.Div("Orders / Fills", className="paper-summary-label"),
                        html.Div(
                            f"{summary.get('orders', 0)} / {summary.get('fills', 0)}",
                            className="paper-summary-value",
                        ),
                    ],
                ),
            ],
        )

        positions = _paper_df_view(
            paper_trading_service.positions_df(),
            "No open positions.",
        )

        orders = _paper_df_view(
            paper_trading_service.orders_df(),
            "No orders yet.",
        )

        fills = _paper_df_view(
            paper_trading_service.fills_df(),
            "No fills yet.",
        )

        return summary_cards, positions, orders, fills

    def _add_trade_markers_to_fig(fig, bars, fills_df):
        """
        Add paper-trade fill markers to the Watch candlestick chart only.

        BUY markers appear above candles.
        SELL markers appear below candles.
        Multiple fills on the same candle/side are grouped.
        """
        if bars is None or bars.empty:
            return fig

        if fills_df is None or fills_df.empty:
            return fig

        required_cols = {"symbol", "side", "quantity", "price", "timestamp", "order_id"}
        if not required_cols.issubset(set(fills_df.columns)):
            return fig

        df_bars = bars.copy()
        df_bars["time"] = pd.to_datetime(df_bars["time"], errors="coerce", format="mixed")
        df_bars = df_bars.dropna(subset=["time"]).copy()

        if df_bars.empty:
            return fig

        fills = fills_df.copy()
        fills["timestamp"] = pd.to_datetime(
            fills["timestamp"],
            errors="coerce",
            format="mixed",
        )
        fills = fills.dropna(subset=["timestamp"]).copy()

        if fills.empty:
            return fig

        fills["side"] = fills["side"].astype(str).str.upper()
        fills["quantity"] = pd.to_numeric(fills["quantity"], errors="coerce").fillna(0.0)
        fills["price"] = pd.to_numeric(fills["price"], errors="coerce").fillna(0.0)

        fills["candle_time"] = fills["timestamp"].dt.floor("min")
        df_bars["candle_time"] = df_bars["time"].dt.floor("min")

        merged = fills.merge(
            df_bars[["candle_time", "high", "low", "close"]],
            on="candle_time",
            how="inner",
        )

        if merged.empty:
            return fig

        marker_rows = []

        for (candle_time, side), group in merged.groupby(["candle_time", "side"]):
            side = str(side).upper()

            total_qty = float(group["quantity"].sum())
            if total_qty <= 0:
                continue

            avg_price = float((group["price"] * group["quantity"]).sum() / total_qty)

            high = float(group["high"].iloc[0])
            low = float(group["low"].iloc[0])
            close = float(group["close"].iloc[0])

            candle_range = max(high - low, abs(close) * 0.002, 0.01)
            offset = candle_range * 0.35

            order_ids = ", ".join(str(x) for x in group["order_id"].tolist())
            fill_count = len(group)

            realized = 0.0
            if "realized_pnl" in group.columns:
                realized = float(
                    pd.to_numeric(group["realized_pnl"], errors="coerce")
                    .fillna(0.0)
                    .sum()
                )

            if side == "BUY":
                marker_rows.append(
                    {
                        "time": candle_time,
                        "y": high + offset,
                        "side": "BUY",
                        "label": f"BUY x{fill_count}" if fill_count > 1 else "BUY",
                        "symbol": "triangle-up",
                        "hover": (
                            f"<b>BUY</b><br>"
                            f"Time: {candle_time}<br>"
                            f"Orders: {order_ids}<br>"
                            f"Quantity: {total_qty:g}<br>"
                            f"Avg Fill: ${avg_price:,.2f}<br>"
                            f"Realized PnL: ${realized:,.2f}"
                        ),
                    }
                )
            else:
                marker_rows.append(
                    {
                        "time": candle_time,
                        "y": low - offset,
                        "side": "SELL",
                        "label": f"SELL x{fill_count}" if fill_count > 1 else "SELL",
                        "symbol": "triangle-down",
                        "hover": (
                            f"<b>SELL</b><br>"
                            f"Time: {candle_time}<br>"
                            f"Orders: {order_ids}<br>"
                            f"Quantity: {total_qty:g}<br>"
                            f"Avg Fill: ${avg_price:,.2f}<br>"
                            f"Realized PnL: ${realized:,.2f}"
                        ),
                    }
                )

        if not marker_rows:
            return fig

        marker_df = pd.DataFrame(marker_rows)

        buys = marker_df[marker_df["side"] == "BUY"]
        sells = marker_df[marker_df["side"] == "SELL"]

        if not buys.empty:
            fig.add_trace(
                go.Scatter(
                    x=buys["time"],
                    y=buys["y"],
                    mode="markers+text",
                    marker=dict(
                        symbol="triangle-up",
                        size=14,
                        color="#22c55e",
                        line=dict(width=1, color="#ffffff"),
                    ),
                    text=buys["label"],
                    textposition="top center",
                    hovertext=buys["hover"],
                    hoverinfo="text",
                    name="Paper Buys",
                    showlegend=False,
                )
            )

        if not sells.empty:
            fig.add_trace(
                go.Scatter(
                    x=sells["time"],
                    y=sells["y"],
                    mode="markers+text",
                    marker=dict(
                        symbol="triangle-down",
                        size=14,
                        color="#ef4444",
                        line=dict(width=1, color="#ffffff"),
                    ),
                    text=sells["label"],
                    textposition="bottom center",
                    hovertext=sells["hover"],
                    hoverinfo="text",
                    name="Paper Sells",
                    showlegend=False,
                )
            )

        return fig


    # ------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------
    @app.callback(
        Output("quote-strip", "children"),
        Output("live-chart", "figure"),
        Output("dashboard-metrics-strip", "children"),
        Output("dashboard-stats-grid", "children"),
        Input("ui-interval", "n_intervals"),
        Input("active-symbol", "data"),
        Input("timeframe-dropdown", "value"),
        Input("dashboard-chart-state", "data"),
        State("main-tabs", "value"),
        prevent_initial_call=False,
    )
    def render_dashboard_chart(_n, active_symbol, timeframe, dashboard_chart_state, active_tab):
        if active_tab != "dashboard":
            return no_update, no_update, no_update, no_update

        try:
            symbol = active_symbol or DEFAULT_SYMBOL
            timeframe = timeframe or DEFAULT_TIMEFRAME
            company_name = rt.get_company_name(symbol)

            snap = rt.get_snapshot(symbol, timeframe)
            fig = create_candlestick_figure(
                snap.bars,
                symbol,
                timeframe,
                current_price=snap.last,
            )

            fig = _apply_chart_view(
                fig,
                snap.bars,
                dashboard_chart_state,
                default_range="1D",
            )

            state = dashboard_chart_state or {}
            range_key = _safe_range_key(state.get("range_key"), "1D")
            mode = state.get("mode", "live")
            fig.update_layout(
                uirevision=f"dashboard-{symbol}-{timeframe}-{mode}-{range_key}",
                dragmode="pan",
            )

            updated = snap.updated_at.strftime("%H:%M:%S") if snap.updated_at else "--:--:--"
            quote_text = f"LIVE · {company_name} ({symbol}) · Updated {updated}"

            open_val = None if snap.bars.empty else float(snap.bars.iloc[0]["open"])
            metrics = _build_metrics_strip(symbol, company_name, snap.last, open_val, snap.updated_at)
            stats = _build_stats_grid_from_bars(snap.bars)

            return quote_text, fig, metrics, stats

        except Exception as exc:
            fig = _empty_figure(f"Loading dashboard... {exc}")
            return f"Loading dashboard... {exc}", fig, [], []

    # ------------------------------------------------------------
    # Watch chart render
    # ------------------------------------------------------------
    @app.callback(
        Output("watch-chart", "figure"),
        Output("replay-slider", "max", allow_duplicate=True),
        Output("replay-slider", "value", allow_duplicate=True),
        Output("watch-metrics-strip", "children"),
        Output("watch-stats-grid", "children"),
        Input("replay-render-trigger", "data"),
        Input("watch-load-request", "data"),
        Input("watch-chart-state", "data"),
        State("main-tabs", "value"),
        State("watch-symbol-dropdown", "value"),
        prevent_initial_call=True,
    )
    def render_watch_tab(_render_trigger, _load_request, watch_chart_state, active_tab, symbol):
        if active_tab != "watch":
            return no_update, no_update, no_update, no_update, no_update

        try:
            symbol = symbol or DEFAULT_SYMBOL

            # Do NOT call replay_service.tick() here.
            # The dedicated replay-clock callback owns playback ticking.
            visible = replay_service.visible_bars()

            if visible.empty:
                fig = _empty_figure(f"{symbol} | 1 min | Loading replay data...")
                fig.update_layout(uirevision=f"watch-{symbol}-empty")
                return fig, 100, 1, [], []

            info = replay_service.info()
            max_idx = max(1, int(info.get("max_index", 1)))
            idx = max(1, int(info.get("current_index", 1)))

            current_price = float(visible.iloc[-1]["close"]) if not visible.empty else None

            fig = create_candlestick_figure(
                visible,
                symbol,
                "1 min",
                current_price=current_price,
            )

            if paper_trading_service is not None:
                try:
                    fills_df = paper_trading_service.fills_df()

                    if fills_df is not None and not fills_df.empty:
                        fills_df = fills_df[
                            fills_df["symbol"].astype(str).str.upper() == str(symbol).upper()
                            ]

                    fig = _add_trade_markers_to_fig(fig, visible, fills_df)

                except Exception as exc:
                    print(f"[WATCH TRADE MARKER ERROR] {exc}", flush=True)

            fig = _apply_chart_view(
                fig,
                visible,
                watch_chart_state,
                default_range="1D",
            )

            state = watch_chart_state or {}
            range_key = _safe_range_key(state.get("range_key"), "1D")
            mode = state.get("mode", "live")

            fig.update_layout(
                uirevision=f"watch-{symbol}-{mode}-{range_key}",
                dragmode="pan",
            )

            company = rt.get_company_name(symbol)
            open_val = float(visible.iloc[0]["open"]) if not visible.empty else None

            metrics = _build_metrics_strip(
                symbol,
                company,
                current_price,
                open_val,
                datetime.now(),
            )

            stats = _build_stats_grid_from_bars(visible)

            return (
                fig,
                max_idx,
                idx,
                metrics,
                stats,
            )

        except Exception as exc:
            print(f"[WATCH RENDER ERROR] {exc}", flush=True)
            fig = _empty_figure(f"Replay loading... {exc}")
            fig.update_layout(uirevision=f"watch-{symbol or DEFAULT_SYMBOL}-error")
            return fig, 100, 1, [], []
    # ------------------------------------------------------------
    # Quotes
    # ------------------------------------------------------------
    @app.callback(
        Output("quotes-status", "children"),
        Output("quotes-panel", "children"),
        Input("ui-interval", "n_intervals"),
        Input("quotes-symbol-dropdown", "value"),
        State("main-tabs", "value"),
        prevent_initial_call=False,
    )
    def render_quotes_tab(_n, symbol, active_tab):
        if active_tab != "quotes":
            return no_update, no_update

        try:
            symbol = symbol or DEFAULT_SYMBOL
            snap = rt.get_snapshot(symbol, "1 min")
            company = rt.get_company_name(symbol)

            bid = f"{snap.bid:.2f}" if snap.bid is not None else "--"
            ask = f"{snap.ask:.2f}" if snap.ask is not None else "--"
            last = f"{snap.last:.2f}" if snap.last is not None else "--"
            size = f"{snap.last_size:.0f}" if snap.last_size is not None else "--"
            updated = snap.updated_at.strftime("%H:%M:%S") if snap.updated_at else "--:--:--"

            quote_text = [
                html.Div(f"Company: {company}"),
                html.Div(f"Symbol: {symbol}"),
                html.Div(f"Last: {last}"),
                html.Div(f"Bid: {bid}"),
                html.Div(f"Ask: {ask}"),
                html.Div(f"Last Size: {size}"),
                html.Div(f"Updated: {updated}"),
            ]

            return f"Quotes loaded for {symbol}", quote_text

        except Exception as exc:
            return f"Quotes error: {exc}", f"Unable to load quotes for {symbol or DEFAULT_SYMBOL}"

    # ------------------------------------------------------------
    # Charts
    # ------------------------------------------------------------
    @app.callback(
        Output("charts-status", "children"),
        Output("charts-main-graph", "figure"),
        Input("ui-interval", "n_intervals"),
        Input("charts-symbol-dropdown", "value"),
        Input("charts-timeframe-dropdown", "value"),
        State("main-tabs", "value"),
        prevent_initial_call=False,
    )
    def render_charts_tab(_n, symbol, timeframe, active_tab):
        if active_tab != "charts":
            return no_update, no_update

        try:
            symbol = symbol or DEFAULT_SYMBOL
            timeframe = timeframe or DEFAULT_TIMEFRAME

            snap = rt.get_snapshot(symbol, timeframe)
            fig = create_candlestick_figure(
                snap.bars,
                symbol,
                timeframe,
                current_price=snap.last,
            )
            fig = _apply_chart_view(fig, snap.bars, {"mode": "live", "range_key": "1D"}, default_range="1D")
            fig.update_layout(uirevision=f"charts-{symbol}-{timeframe}", dragmode="pan")

            return f"Charts loaded for {symbol}", fig

        except Exception as exc:
            fig = go.Figure()
            fig.update_layout(
                title=f"Charts tab error: {exc}",
                template="plotly_dark",
            )
            return f"Charts error: {exc}", fig
