from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, html, dcc, no_update, ctx

from config import DEFAULT_SYMBOL, DEFAULT_TIMEFRAME
from utils.chart_utils import create_candlestick_figure
from core.RiskGuard import TradeIntent


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

def _is_today_or_latest_replay_date(replay_date) -> bool:
    """
    Live market paper trading should only be available when the Watch tab
    is using today's date or no date/latest mode.
    """
    if not replay_date:
        return True

    try:
        selected = pd.to_datetime(replay_date, errors="coerce")
        if pd.isna(selected):
            return False

        return selected.date() == datetime.now().date()
    except Exception:
        return False

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

            return (
                status,
                max_idx,
                idx,
                "watch-loading-overlay hidden",
                int(render_trigger or 0) + 1,
            )

        except Exception as exc:
            print(f"[REPLAY LOAD ERROR] {exc}", flush=True)
            return (
                f"Replay load error: {exc}",
                100,
                1,
                "watch-loading-overlay hidden",
                int(render_trigger or 0) + 1,
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
        """
        User replay controls.

        This callback does not output replay-slider.value. It only changes the
        replay engine and bumps replay-render-trigger. That prevents programmatic
        slider updates from re-triggering "Replay moved to n" while Play is active.
        """
        if active_tab != "watch":
            return no_update, no_update

        trigger = ctx.triggered_id
        render_trigger = int(render_trigger or 0)

        try:
            info = replay_service.info()
            max_index = max(1, int(info.get("max_index", 1)))

            if max_index <= 1:
                return "No replay data loaded yet.", no_update

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
        """
        Dedicated replay heartbeat.

        The clock advances the engine and bumps the render trigger. It does not
        directly write to replay-slider.value.
        """
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

    @app.callback(
        Output("load-status", "data", allow_duplicate=True),
        Input("watch-symbol-dropdown", "value"),
        Input("paper-price-source", "value"),
        Input("replay-date", "date"),
        State("main-tabs", "value"),
        prevent_initial_call=True,
    )
    def request_watch_live_symbol(symbol, price_source, replay_date, active_tab):
        if active_tab != "watch":
            return no_update

        if not symbol:
            return no_update

        if price_source != "live":
            return no_update

        if not _is_today_or_latest_replay_date(replay_date):
            return no_update

        try:
            symbol = rt._sanitize_symbol(symbol)
            rt.request_symbol(symbol)
            return f"Requested live Watch data for {symbol}"
        except Exception as exc:
            print(f"[WATCH LIVE SYMBOL ERROR] {exc}", flush=True)
            return f"Watch live symbol error: {exc}"

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
    def render_dashboard_chart(
            _n,
            active_symbol,
            timeframe,
            dashboard_chart_state,
            active_tab,
    ):
        """
        Dashboard-only live renderer.

        This intentionally does NOT touch Watch/replay/paper callbacks.
        It uses a changing datarevision and avoids uirevision during the
        diagnostic period so Plotly cannot preserve a stale candlestick trace.
        """
        if active_tab != "dashboard":
            return no_update, no_update, no_update, no_update

        try:
            symbol = (active_symbol or DEFAULT_SYMBOL).upper().strip()
            timeframe = timeframe or DEFAULT_TIMEFRAME
            company_name = rt.get_company_name(symbol)

            # Make sure the dashboard symbol has an active live subscription.
            # This is cheap if already subscribed and prevents a stale symbol state.
            try:
                rt.request_symbol(symbol)
            except Exception as req_exc:
                print(f"[DASHBOARD REQUEST WARNING] {symbol}: {req_exc}", flush=True)

            snap = rt.get_snapshot(symbol, timeframe)

            bars = snap.bars.copy() if snap.bars is not None else pd.DataFrame()

            if bars is not None and not bars.empty:
                bars["time"] = pd.to_datetime(bars["time"], errors="coerce")
                bars = bars.dropna(subset=["time", "open", "high", "low", "close"]).copy()

            if bars is None or bars.empty:
                fig = _empty_figure(f"{symbol} | Waiting for live candles...")
                quote_text = f"LIVE · {company_name} ({symbol}) · Waiting for candles"
                return quote_text, fig, [], []

            latest_time = str(bars.iloc[-1]["time"])
            latest_open = float(bars.iloc[-1]["open"])
            latest_high = float(bars.iloc[-1]["high"])
            latest_low = float(bars.iloc[-1]["low"])
            latest_close = float(bars.iloc[-1]["close"])
            current_price = float(snap.last) if snap.last is not None else latest_close

            fig = create_candlestick_figure(
                bars,
                symbol,
                timeframe,
                current_price=current_price,
            )

            # Keep your dashboard range buttons and manual pan/zoom behavior.
            fig = _apply_chart_view(
                fig,
                bars,
                dashboard_chart_state,
                default_range="1D",
            )

            state = dashboard_chart_state or {}
            range_key = _safe_range_key(state.get("range_key"), "1D")
            mode = state.get("mode", "live")

            # Force trace arrays into plain Python lists. This avoids some cases
            # where the front end does not notice a DataFrame/Series-backed change.
            try:
                if fig.data:
                    for trace in fig.data:
                        if hasattr(trace, "x") and trace.x is not None:
                            trace.x = list(trace.x)
                        if hasattr(trace, "open") and trace.open is not None:
                            trace.open = [float(x) for x in trace.open]
                        if hasattr(trace, "high") and trace.high is not None:
                            trace.high = [float(x) for x in trace.high]
                        if hasattr(trace, "low") and trace.low is not None:
                            trace.low = [float(x) for x in trace.low]
                        if hasattr(trace, "close") and trace.close is not None:
                            trace.close = [float(x) for x in trace.close]
            except Exception as trace_exc:
                print(f"[DASHBOARD TRACE NORMALIZE WARNING] {trace_exc}", flush=True)

            # Diagnostic redraw key. Keep uirevision disabled for now.
            # Once confirmed working, we can re-enable a stable uirevision.
            redraw_key = (
                f"{symbol}-{timeframe}-{mode}-{range_key}-"
                f"{latest_time}-{latest_open}-{latest_high}-{latest_low}-{latest_close}-"
                f"{current_price}-{_n}"
            )

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

            updated = snap.updated_at.strftime("%H:%M:%S") if snap.updated_at else "--:--:--"
            quote_text = (
                f"LIVE · {company_name} ({symbol}) · Updated {updated} · "
                f"Last {current_price:,.2f}"
            )

            open_val = float(bars.iloc[0]["open"])

            metrics = _build_metrics_strip(
                symbol,
                company_name,
                current_price,
                open_val,
                snap.updated_at,
            )

            stats = _build_stats_grid_from_bars(bars)

            return quote_text, fig, metrics, stats

        except Exception as exc:
            print(f"[DASHBOARD RENDER ERROR] {exc}", flush=True)
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
        Input("paper-trade-trigger", "data"),
        Input("ui-interval", "n_intervals"),
        State("main-tabs", "value"),
        State("watch-symbol-dropdown", "value"),
        State("paper-price-source", "value"),
        State("replay-date", "date"),
        prevent_initial_call=True,
    )
    def render_watch_tab(
            _render_trigger,
            _load_request,
            watch_chart_state,
            _paper_trade_trigger,
            _ui_n,
            active_tab,
            symbol,
            price_source,
            replay_date,
    ):
        if active_tab != "watch":
            return no_update, no_update, no_update, no_update, no_update

        try:
            symbol = (symbol or DEFAULT_SYMBOL).upper().strip()
            price_source = str(price_source or "replay").lower().strip()

            use_live_watch_data = (
                    price_source == "live"
                    and _is_today_or_latest_replay_date(replay_date)
            )

            info = replay_service.info()
            max_idx = max(1, int(info.get("max_index", 1)))
            idx = max(1, int(info.get("current_index", 1)))

            if use_live_watch_data:
                try:
                    rt.request_symbol(symbol)
                except Exception:
                    pass

                snap = rt.get_snapshot(symbol, "1 min")
                visible = snap.bars.copy() if snap.bars is not None else pd.DataFrame()

                # Keep the chart dynamic by using the latest live tick price.
                current_price = snap.last
                updated_at = snap.updated_at or datetime.now()
                chart_label = "Live Market"

            else:
                visible = replay_service.visible_bars()

                current_price = (
                    float(visible.iloc[-1]["close"])
                    if visible is not None and not visible.empty
                    else None
                )
                updated_at = datetime.now()
                chart_label = "Replay Cursor"

            if visible is None or visible.empty:
                fig = _empty_figure(f"{symbol} | 1 min | Loading {chart_label} data...")
                fig.update_layout(uirevision=f"watch-{symbol}-empty")
                return fig, max_idx, idx, [], []

            # In live mode, prefer snap.last. If it is missing, fall back to
            # the latest candle close.
            if current_price is None:
                current_price = float(visible.iloc[-1]["close"])

            fig = create_candlestick_figure(
                visible,
                symbol,
                "1 min",
                current_price=current_price,
            )

            # Paper trade markers only belong on the Watch tab.
            if paper_trading_service is not None:
                try:
                    fills_df = paper_trading_service.fills_df()

                    if fills_df is not None and not fills_df.empty:
                        fills_df = fills_df[
                            fills_df["symbol"].astype(str).str.upper() == symbol.upper()
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

            source_label = "live" if use_live_watch_data else "replay"

            fig.update_layout(
                uirevision=f"watch-{symbol}-{source_label}-{mode}-{range_key}",
                dragmode="pan",
            )

            company = rt.get_company_name(symbol)
            open_val = float(visible.iloc[0]["open"]) if not visible.empty else None

            metrics = _build_metrics_strip(
                symbol,
                company,
                current_price,
                open_val,
                updated_at,
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
    # Paper trading
    # ------------------------------------------------------------
    def _paper_current_price_and_time(
            symbol: str,
            source: str = "replay",
            replay_date=None,
    ):
        symbol = (symbol or DEFAULT_SYMBOL).upper().strip()
        source = str(source or "replay").lower().strip()

        if source == "replay":
            try:
                bar = replay_service.current_bar()
                if bar is not None:
                    return float(bar["close"]), bar.get("time", datetime.now()), "Replay Cursor"
            except Exception:
                pass

            return None, datetime.now(), "Replay Cursor"

        if source == "live":
            if not _is_today_or_latest_replay_date(replay_date):
                return (
                    None,
                    datetime.now(),
                    "Live Market unavailable for historical dates",
                )

            try:
                rt.request_symbol(symbol)
            except Exception:
                pass

            snap = rt.get_snapshot(symbol, "1 min")

            if snap.last is None:
                return None, snap.updated_at or datetime.now(), "Live Market"

            return float(snap.last), snap.updated_at or datetime.now(), "Live Market"

        return None, datetime.now(), source

    @app.callback(
        Output("paper-trade-status", "children"),
        Output("paper-trade-trigger", "data"),
        Input("paper-buy", "n_clicks"),
        Input("paper-sell", "n_clicks"),
        Input("paper-reset", "n_clicks"),
        State("paper-order-qty", "value"),
        State("watch-symbol-dropdown", "value"),
        State("paper-price-source", "value"),
        State("paper-position-mode", "value"),
        State("replay-date", "date"),
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
            price_source,
            position_mode,
            replay_date,
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

            allow_short = str(position_mode or "long_only") == "allow_shorts"

            last_price, timestamp, source_label = _paper_current_price_and_time(
                symbol,
                source=price_source,
                replay_date=replay_date,
            )

            if last_price is None:
                return f"No price available from {source_label} for {symbol}.", no_update

            if trigger == "paper-buy":
                intent = TradeIntent(
                    symbol=symbol,
                    side="BUY",
                    quantity=quantity,
                    order_type="MARKET",
                    reason="Manual paper buy",
                    source=f"manual:{source_label}",
                )

            elif trigger == "paper-sell":
                intent = TradeIntent(
                    symbol=symbol,
                    side="SELL",
                    quantity=quantity,
                    order_type="MARKET",
                    reason="Manual paper sell",
                    source=f"manual:{source_label}",
                )

            else:
                return no_update, no_update

            print(
                f"[PAPER TRADE DEBUG] symbol={symbol} side={intent.side} "
                f"qty={quantity} price_source={price_source} "
                f"position_mode={position_mode} allow_short={allow_short}",
                flush=True,
            )

            decision, order = paper_trading_service.submit_intent(
                intent=intent,
                last_price=last_price,
                timestamp=timestamp,
                mode="simulated",
                allow_short=allow_short,
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

            mode_label = "Shorts allowed" if allow_short else "Long only"

            return (
                f"Paper order {order.status}: {fill_text} via {source_label} · {mode_label}",
                paper_trigger + 1,
            )

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
        Output("trade-analytics-drawer", "className"),
        Input("trade-analytics-open", "n_clicks"),
        Input("trade-analytics-close", "n_clicks"),
        State("main-tabs", "value"),
        prevent_initial_call=True,
    )
    def toggle_trade_analytics_drawer(open_clicks, close_clicks, active_tab):
        if active_tab != "watch":
            return no_update

        trigger = ctx.triggered_id

        if trigger == "trade-analytics-open":
            return "trade-analytics-drawer"

        if trigger == "trade-analytics-close":
            return "trade-analytics-drawer hidden"

        return no_update

    @app.callback(
        Output("trade-analytics-content", "children"),
        Input("trade-analytics-open", "n_clicks"),
        Input("paper-trade-trigger", "data"),
        Input("ui-interval", "n_intervals"),
        State("watch-symbol-dropdown", "value"),
        State("main-tabs", "value"),
        prevent_initial_call=False,
    )
    def render_trade_analytics_content(_open_clicks, _paper_trigger, _n, symbol, active_tab):
        if active_tab != "watch":
            return no_update

        symbol = (symbol or DEFAULT_SYMBOL).upper().strip()

        if paper_trading_service is None:
            return html.Div("Paper trading service is disabled.", className="paper-empty")

        try:
            positions = paper_trading_service.positions_df()
        except Exception:
            positions = pd.DataFrame()

        try:
            orders = paper_trading_service.orders_df()
        except Exception:
            orders = pd.DataFrame()

        try:
            fills = paper_trading_service.fills_df()
        except Exception:
            fills = pd.DataFrame()

        try:
            if paper_state_cache is not None:
                paper_state_cache.save_from_service(paper_trading_service)
        except Exception as cache_exc:
            print(f"[ANALYTICS CACHE SAVE ERROR] {cache_exc}", flush=True)

        if fills is None:
            fills = pd.DataFrame()

        if not fills.empty and "symbol" in fills.columns:
            fills = fills[fills["symbol"].astype(str).str.upper() == symbol]

        total_fills = int(len(fills)) if fills is not None else 0

        realized_pnl = 0.0
        if fills is not None and not fills.empty and "realized_pnl" in fills.columns:
            realized_pnl = float(
                pd.to_numeric(fills["realized_pnl"], errors="coerce")
                .fillna(0.0)
                .sum()
            )

        buy_count = 0
        sell_count = 0
        long_short_text = "No fills yet"

        if fills is not None and not fills.empty and "side" in fills.columns:
            sides = fills["side"].astype(str).str.upper()
            buy_count = int((sides == "BUY").sum())
            sell_count = int((sides == "SELL").sum())
            long_short_text = f"BUY fills: {buy_count} · SELL fills: {sell_count}"

        pnl_class = "analytics-value analytics-positive" if realized_pnl >= 0 else "analytics-value analytics-negative"

        cards = html.Div(
            className="analytics-card-grid",
            children=[
                html.Div(
                    className="analytics-card",
                    children=[
                        html.Div("Symbol", className="analytics-label"),
                        html.Div(symbol, className="analytics-value"),
                    ],
                ),
                html.Div(
                    className="analytics-card",
                    children=[
                        html.Div("Total Fills", className="analytics-label"),
                        html.Div(f"{total_fills}", className="analytics-value"),
                    ],
                ),
                html.Div(
                    className="analytics-card",
                    children=[
                        html.Div("Realized PnL", className="analytics-label"),
                        html.Div(f"${realized_pnl:,.2f}", className=pnl_class),
                    ],
                ),
                html.Div(
                    className="analytics-card",
                    children=[
                        html.Div("Fill Sides", className="analytics-label"),
                        html.Div(long_short_text, className="analytics-value"),
                    ],
                ),
            ],
        )

        fills_view = fills.tail(12).copy() if fills is not None and not fills.empty else pd.DataFrame()
        orders_view = orders.tail(12).copy() if orders is not None and not orders.empty else pd.DataFrame()
        positions_view = positions.copy() if positions is not None and not positions.empty else pd.DataFrame()

        def _pre_from_df(df, empty_text):
            if df is None or df.empty:
                return html.Div(empty_text, className="paper-empty")

            view = df.copy()

            for col in view.columns:
                if str(col).lower() in {"timestamp", "submitted_at", "filled_at"}:
                    try:
                        view[col] = pd.to_datetime(
                            view[col],
                            errors="coerce",
                            format="mixed",
                        ).dt.strftime("%Y-%m-%d %H:%M:%S")
                        view[col] = view[col].fillna("")
                    except Exception:
                        pass

            return html.Pre(view.to_string(index=False), className="analytics-table")

        return html.Div(
            children=[
                cards,

                html.Div("PnL Curve", className="analytics-section-title"),
                _build_pnl_chart(fills),

                html.Div("Open Positions", className="analytics-section-title"),
                _pre_from_df(positions_view, "No open positions."),

                html.Div("Recent Orders", className="analytics-section-title"),
                _pre_from_df(orders_view, "No orders yet."),

                html.Div("Recent Fills", className="analytics-section-title"),
                _pre_from_df(fills_view, "No fills yet."),
            ]
        )

    def _build_pnl_chart(fills_df):
        if fills_df is None or fills_df.empty:
            fig = go.Figure()
            fig.update_layout(
                title="Realized PnL",
                template="plotly_dark",
                paper_bgcolor="#0f172a",
                plot_bgcolor="#020617",
                font={"color": "#dbeafe"},
                height=260,
                margin=dict(l=35, r=20, t=45, b=35),
            )
            return dcc.Graph(
                figure=fig,
                config={"displayModeBar": False},
                className="analytics-pnl-chart",
            )

        if "realized_pnl" not in fills_df.columns:
            fig = go.Figure()
            fig.update_layout(
                title="Realized PnL unavailable",
                template="plotly_dark",
                paper_bgcolor="#0f172a",
                plot_bgcolor="#020617",
                font={"color": "#dbeafe"},
                height=260,
                margin=dict(l=35, r=20, t=45, b=35),
            )
            return dcc.Graph(
                figure=fig,
                config={"displayModeBar": False},
                className="analytics-pnl-chart",
            )

        df = fills_df.copy()

        time_col = None
        for candidate in ["timestamp", "filled_at", "submitted_at"]:
            if candidate in df.columns:
                time_col = candidate
                break

        if time_col is None:
            df["_time"] = range(len(df))
            time_col = "_time"
        else:
            df[time_col] = pd.to_datetime(
                df[time_col],
                errors="coerce",
                format="mixed",
            )
            df = df.dropna(subset=[time_col]).copy()

        if df.empty:
            fig = go.Figure()
            fig.update_layout(
                title="Realized PnL",
                template="plotly_dark",
                paper_bgcolor="#0f172a",
                plot_bgcolor="#020617",
                font={"color": "#dbeafe"},
                height=260,
                margin=dict(l=35, r=20, t=45, b=35),
            )
            return dcc.Graph(
                figure=fig,
                config={"displayModeBar": False},
                className="analytics-pnl-chart",
            )

        df["realized_pnl"] = pd.to_numeric(
            df["realized_pnl"],
            errors="coerce",
        ).fillna(0.0)

        df = df.sort_values(time_col).copy()
        df["cumulative_pnl"] = df["realized_pnl"].cumsum()

        final_pnl = float(df["cumulative_pnl"].iloc[-1])
        line_color = "#22c55e" if final_pnl >= 0 else "#ef4444"

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=df[time_col],
                y=df["cumulative_pnl"],
                mode="lines+markers",
                line=dict(width=3, color=line_color),
                marker=dict(size=6, color=line_color),
                name="Cumulative Realized PnL",
                hovertemplate=(
                    "Time: %{x}<br>"
                    "Cumulative PnL: $%{y:,.2f}"
                    "<extra></extra>"
                ),
            )
        )

        fig.add_hline(
            y=0,
            line_width=1,
            line_dash="dot",
            line_color="rgba(148, 163, 184, 0.7)",
        )

        fig.update_layout(
            title=f"Cumulative Realized PnL: ${final_pnl:,.2f}",
            template="plotly_dark",
            paper_bgcolor="#0f172a",
            plot_bgcolor="#020617",
            font={"color": "#dbeafe"},
            height=260,
            margin=dict(l=35, r=20, t=45, b=35),
            hovermode="x unified",
            showlegend=False,
        )

        fig.update_xaxes(
            showgrid=True,
            gridcolor="rgba(148, 163, 184, 0.12)",
        )

        fig.update_yaxes(
            title="PnL $",
            showgrid=True,
            gridcolor="rgba(148, 163, 184, 0.12)",
            zeroline=False,
        )

        return dcc.Graph(
            figure=fig,
            config={"displayModeBar": False, "responsive": True},
            className="analytics-pnl-chart",
        )

    @app.callback(
        Output("paper-trade-status", "children", allow_duplicate=True),
        Input("paper-price-source", "value"),
        Input("replay-date", "date"),
        State("main-tabs", "value"),
        prevent_initial_call=True,
    )
    def warn_live_source_for_historical_date(price_source, replay_date, active_tab):
        if active_tab != "watch":
            return no_update

        if price_source == "live" and not _is_today_or_latest_replay_date(replay_date):
            return "Live Market paper trading is only available for today's date or latest mode."

        if price_source == "live":
            return "Live Market paper trading enabled for today's/current data."

        return "Replay Cursor paper trading enabled."


    @app.callback(
        Output("paper-summary-panel", "children"),
        Output("paper-positions-panel", "children"),
        Output("paper-orders-panel", "children"),
        Output("paper-fills-panel", "children"),
        Input("paper-trade-trigger", "data"),
        Input("replay-render-trigger", "data"),
        Input("ui-interval", "n_intervals"),
        State("watch-symbol-dropdown", "value"),
        State("paper-price-source", "value"),
        State("replay-date", "date"),
        State("main-tabs", "value"),
        prevent_initial_call=False,
    )
    def render_paper_trading_panels(
            _paper_trigger,
            _replay_trigger,
            _ui_n,
            symbol,
            price_source,
            replay_date,
            active_tab,
    ):

        if active_tab != "watch":
            return no_update, no_update, no_update, no_update

        if paper_trading_service is None:
            disabled = html.Div("Paper trading service is disabled.", className="paper-empty")
            return disabled, disabled, disabled, disabled

        symbol = (symbol or DEFAULT_SYMBOL).upper().strip()

        prices = {}
        try:
            price, _timestamp, _source_label = _paper_current_price_and_time(
                symbol,
                source=price_source,
                replay_date=replay_date,
            )

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
        Add paper-trade fill markers to a candlestick chart.

        BUY markers appear above candles.
        SELL markers appear below candles.
        Multiple fills on the same candle/side are grouped into one marker.
        """
        if bars is None or bars.empty:
            return fig

        if fills_df is None or fills_df.empty:
            return fig

        required_fill_cols = {"symbol", "side", "quantity", "price", "timestamp", "order_id"}
        if not required_fill_cols.issubset(set(fills_df.columns)):
            return fig

        df_bars = bars.copy()
        df_bars["time"] = pd.to_datetime(df_bars["time"], errors="coerce")
        df_bars = df_bars.dropna(subset=["time"])

        if df_bars.empty:
            return fig

        fills = fills_df.copy()
        fills["timestamp"] = pd.to_datetime(fills["timestamp"], errors="coerce")
        fills = fills.dropna(subset=["timestamp"])

        if fills.empty:
            return fig

        fills["candle_time"] = fills["timestamp"].dt.floor("min")
        df_bars["candle_time"] = df_bars["time"].dt.floor("min")

        merged = fills.merge(
            df_bars[["candle_time", "high", "low", "close"]],
            on="candle_time",
            how="inner",
        )

        if merged.empty:
            return fig

        grouped_rows = []

        for (candle_time, side), group in merged.groupby(["candle_time", "side"]):
            side = str(side).upper()

            total_qty = float(group["quantity"].sum())
            if total_qty <= 0:
                continue

            avg_price = float((group["price"] * group["quantity"]).sum() / total_qty)
            order_ids = ", ".join(str(x) for x in group["order_id"].tolist())
            count = len(group)

            high = float(group["high"].iloc[0])
            low = float(group["low"].iloc[0])
            close = float(group["close"].iloc[0])

            candle_range = max(high - low, abs(close) * 0.002, 0.01)
            offset = candle_range * 0.35

            if side == "BUY":
                y = high + offset
                marker_symbol = "triangle-up"
                label = f"BUY x{count}" if count > 1 else "BUY"
            else:
                y = low - offset
                marker_symbol = "triangle-down"
                label = f"SELL x{count}" if count > 1 else "SELL"

            realized = 0.0
            if "realized_pnl" in group.columns:
                realized = float(
                    pd.to_numeric(group["realized_pnl"], errors="coerce")
                    .fillna(0)
                    .sum()
                )

            sources = []
            if "source" in group.columns:
                sources = [
                    str(s)
                    for s in group["source"].dropna().tolist()
                    if str(s).strip()
                ]

            reasons = []
            if "reason" in group.columns:
                reasons = [
                    str(r)
                    for r in group["reason"].dropna().tolist()
                    if str(r).strip()
                ]

            hover = (
                f"<b>{label}</b><br>"
                f"Time: {candle_time}<br>"
                f"Orders: {order_ids}<br>"
                f"Quantity: {total_qty:g}<br>"
                f"Avg Fill: ${avg_price:,.2f}<br>"
                f"Realized PnL: ${realized:,.2f}<br>"
                f"Source: {', '.join(sorted(set(sources))) if sources else 'manual'}<br>"
                f"Reason: {' | '.join(reasons) if reasons else '--'}"
            )

            grouped_rows.append(
                {
                    "time": candle_time,
                    "side": side,
                    "y": y,
                    "symbol": marker_symbol,
                    "label": label,
                    "hover": hover,
                }
            )

        if not grouped_rows:
            return fig

        marker_df = pd.DataFrame(grouped_rows)

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
                )
            )

        return fig

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
