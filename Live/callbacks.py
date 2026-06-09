from __future__ import annotations

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
    """
    Chart view controller.

    live mode:
        follows the latest bars and auto-fits y-axis to visible candles

    manual mode:
        preserves user pan/zoom ranges until Live or Reset is clicked
    """
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
):
    @app.callback(
        Output("pair-title", "children"),
        Input("active-symbol", "data"),
        Input("main-tabs", "value"),
        State("watch-state", "data"),
        State("dashboard-state", "data"),
    )
    def update_pair_title(active_symbol, active_tab, watch_state, dashboard_state):
        if active_tab == "watch":
            symbol = (watch_state or {}).get("symbol", DEFAULT_SYMBOL)
        else:
            symbol = active_symbol or (dashboard_state or {}).get("symbol", DEFAULT_SYMBOL)

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
        Input("watch-load-request", "data"),
        State("replay-speed", "value"),
        State("main-tabs", "value"),
        prevent_initial_call=True,
    )
    def load_watch_symbol_from_request(load_request, replay_speed, active_tab):
        if active_tab != "watch":
            return no_update, no_update, no_update, no_update

        if not load_request:
            return no_update, no_update, no_update, no_update

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

            return (
                status,
                max(1, int(info.get("max_index", 1))),
                max(1, int(info.get("current_index", 1))),
                "watch-loading-overlay hidden",
            )

        except Exception as exc:
            print(f"[REPLAY LOAD ERROR] {exc}", flush=True)
            return (
                f"Replay load error: {exc}",
                100,
                1,
                "watch-loading-overlay hidden",
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
        Output("replay-slider", "value", allow_duplicate=True),
        Input("replay-play", "n_clicks"),
        Input("replay-pause", "n_clicks"),
        Input("replay-step", "n_clicks"),
        Input("replay-rewind", "n_clicks"),
        Input("replay-slider", "value"),
        State("main-tabs", "value"),
        prevent_initial_call=True,
    )
    def control_replay(play_clicks, pause_clicks, step_clicks, rewind_clicks, slider_value, active_tab):
        if active_tab != "watch":
            return no_update, no_update

        trigger = ctx.triggered_id

        try:
            if trigger == "replay-play":
                replay_service.play()
                idx = replay_service.info()["current_index"]
                return "Replay playing", max(1, idx)

            if trigger == "replay-pause":
                replay_service.pause()
                idx = replay_service.info()["current_index"]
                return "Replay paused", max(1, idx)

            if trigger == "replay-step":
                replay_service.forward(1)
                idx = replay_service.info()["current_index"]
                return f"Replay stepped to {idx}", max(1, idx)

            if trigger == "replay-rewind":
                replay_service.rewind(1)
                idx = replay_service.info()["current_index"]
                return f"Replay rewound to {idx}", max(1, idx)

            if trigger == "replay-slider":
                replay_service.set_index(slider_value or 1)
                idx = replay_service.info()["current_index"]
                return f"Replay moved to {idx}", max(1, idx)

            return no_update, no_update

        except Exception as exc:
            print(f"[REPLAY CONTROL ERROR] {exc}", flush=True)
            return f"Replay control error: {exc}", no_update

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
        Input("ui-interval", "n_intervals"),
        Input("watch-load-request", "data"),
        Input("watch-chart-state", "data"),
        State("main-tabs", "value"),
        State("watch-symbol-dropdown", "value"),
        prevent_initial_call=True,
    )
    def render_watch_tab(_n, _load_request, watch_chart_state, active_tab, symbol):
        if active_tab != "watch":
            return no_update, no_update, no_update, no_update, no_update

        try:
            symbol = symbol or DEFAULT_SYMBOL

            replay_service.tick()
            visible = replay_service.visible_bars()

            if visible.empty:
                fig = _empty_figure(f"{symbol} | 1 min | Loading replay data...")
                fig.update_layout(uirevision=f"watch-{symbol}-empty")
                return fig, 100, 1, [], []

            info = replay_service.info()
            current_price = float(visible.iloc[-1]["close"]) if not visible.empty else None

            fig = create_candlestick_figure(
                visible,
                symbol,
                "1 min",
                current_price=current_price,
            )

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

            metrics = _build_metrics_strip(symbol, company, current_price, open_val, datetime.now())
            stats = _build_stats_grid_from_bars(visible)

            return (
                fig,
                max(1, int(info["max_index"])),
                max(1, int(info["current_index"])),
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
