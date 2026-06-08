from __future__ import annotations

from datetime import datetime

import plotly.graph_objects as go
from dash import Input, Output, State, html, no_update, ctx

from config import DEFAULT_SYMBOL, DEFAULT_TIMEFRAME
from ui.tabs_ui import (
    build_dashboard_tab,
    build_watch_tab,
    build_quotes_tab,
    build_charts_tab,
)
from utils.chart_utils import create_candlestick_figure


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

    cards = [
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
    return cards


def register_callbacks(app, rt, replay_service, symbol_options, timeframe_map):
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
        Output("watch-loading-overlay", "className"),
        Input("watch-loading-state", "data"),
        State("main-tabs", "value"),
    )
    def toggle_watch_loading_overlay(is_loading, active_tab):
        if active_tab != "watch":
            return "watch-loading-overlay hidden"
        return "watch-loading-overlay" if is_loading else "watch-loading-overlay hidden"

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

    @app.callback(
        Output("zoom-state", "data"),
        Input("live-chart", "relayoutData"),
        State("zoom-state", "data"),
        prevent_initial_call=True,
    )
    def capture_zoom(relayout_data, current_state):
        if relayout_data is None:
            return current_state
        return relayout_data

    @app.callback(
        Output("watch-loading-state", "data", allow_duplicate=True),
        Input("main-tabs", "value"),
        Input("watch-symbol-dropdown", "value"),
        Input("replay-date", "date"),
        prevent_initial_call=True,
    )
    def start_watch_loading(active_tab, symbol, replay_date):
        if active_tab != "watch":
            return no_update
        if not symbol:
            return no_update
        return True

    @app.callback(
        Output("watch-status", "children"),
        Output("replay-slider", "max", allow_duplicate=True),
        Output("replay-slider", "value", allow_duplicate=True),
        Output("watch-loading-state", "data"),
        Input("main-tabs", "value"),
        Input("watch-symbol-dropdown", "value"),
        Input("replay-date", "date"),
        Input("replay-speed", "value"),
        prevent_initial_call=True,
    )
    def load_watch_symbol(active_tab, symbol, replay_date, replay_speed):
        if active_tab != "watch":
            return no_update, no_update, no_update, no_update

        try:
            status, info = replay_service.load_replay(
                symbol=symbol or DEFAULT_SYMBOL,
                timeframe="1 min",
                replay_date=replay_date,
                speed=replay_speed,
            )
            return status, max(1, info["max_index"]), max(1, info["current_index"]), False
        except Exception as exc:
            return f"Replay load error: {exc}", 100, 1, False

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

    @app.callback(
        Output("quote-strip", "children"),
        Output("live-chart", "figure"),
        Output("dashboard-metrics-strip", "children"),
        Output("dashboard-stats-grid", "children"),
        Input("ui-interval", "n_intervals"),
        Input("active-symbol", "data"),
        Input("timeframe-dropdown", "value"),
        State("main-tabs", "value"),
        State("zoom-state", "data"),
        prevent_initial_call=True,
    )
    def render_dashboard_chart(_n, active_symbol, timeframe, active_tab, zoom_state):
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
                current_price=snap.last,)

            fig.update_layout(
                uirevision=f"dashboard-{symbol}-{timeframe}",
                dragmode="pan",
            )

            updated = snap.updated_at.strftime("%H:%M:%S") if snap.updated_at else "--:--:--"
            quote_text = f"LIVE · {company_name} ({symbol}) · Updated {updated}"

            if zoom_state:
                if "xaxis.range[0]" in zoom_state and "xaxis.range[1]" in zoom_state:
                    fig.update_xaxes(range=[zoom_state["xaxis.range[0]"], zoom_state["xaxis.range[1]"]])
                if "yaxis.range[0]" in zoom_state and "yaxis.range[1]" in zoom_state:
                    fig.update_yaxes(range=[zoom_state["yaxis.range[0]"], zoom_state["yaxis.range[1]"]])

            open_val = None if snap.bars.empty else float(snap.bars.iloc[0]["open"])
            metrics = _build_metrics_strip(symbol, company_name, snap.last, open_val, snap.updated_at)
            stats = _build_stats_grid_from_bars(snap.bars)

            return quote_text, fig, metrics, stats

        except Exception as exc:
            fig = go.Figure()
            fig.update_layout(
                title="Loading dashboard...",
                template="plotly_dark",
                paper_bgcolor="#0d1b4f",
                plot_bgcolor="#0d1b4f",
                font={"color": "#e8f1ff"},
            )
            return f"Loading dashboard... {exc}", fig, [], []

    @app.callback(
        Output("watch-chart", "figure"),
        Output("replay-slider", "max", allow_duplicate=True),
        Output("replay-slider", "value", allow_duplicate=True),
        Output("watch-metrics-strip", "children"),
        Output("watch-stats-grid", "children"),
        State("main-tabs", "value"),
        Input("ui-interval", "n_intervals"),
        State("watch-symbol-dropdown", "value"),
        prevent_initial_call=True,
    )
    def render_watch_tab(active_tab, _n, symbol):
        if active_tab != "watch":
            return no_update, no_update, no_update, no_update, no_update

        try:
            symbol = symbol or DEFAULT_SYMBOL

            replay_service.tick()
            visible = replay_service.visible_bars()

            if visible.empty:
                fig = go.Figure()
                fig.update_layout(
                    title=f"{symbol} | 1 min | No replay data loaded yet",
                    template="plotly_dark",
                    paper_bgcolor="#0d1b4f",
                    plot_bgcolor="#0d1b4f",
                    font={"color": "#e8f1ff"},
                    uirevision=f"watch-{symbol}",
                    dragmode="pan",
                )
                return fig, 100, 1, [], []

            info = replay_service.info()
            current_price = float(visible.iloc[-1]["close"]) if not visible.empty else None

            fig = create_candlestick_figure(
                visible,
                symbol,
                "1 min",
                current_price=current_price,
            )
            fig.update_layout(
                uirevision=f"watch-{symbol}",
                dragmode="pan",
            )

            company = rt.get_company_name(symbol)
            open_val = float(visible.iloc[0]["open"]) if not visible.empty else None

            metrics = _build_metrics_strip(symbol, company, current_price, open_val, datetime.now())
            stats = _build_stats_grid_from_bars(visible)

            return (
                fig,
                max(1, info["max_index"]),
                max(1, info["current_index"]),
                metrics,
                stats,
            )

        except Exception as exc:
            print(f"[WATCH RENDER ERROR] {exc}", flush=True)
            fig = go.Figure()
            fig.update_layout(
                title=f"Replay loading... {exc}",
                template="plotly_dark",
                paper_bgcolor="#0d1b4f",
                plot_bgcolor="#0d1b4f",
                font={"color": "#e8f1ff"},
                uirevision=f"watch-{symbol or DEFAULT_SYMBOL}",
                dragmode="pan",
            )
            return fig, 100, 1, [], []

    @app.callback(
        Output("quotes-status", "children"),
        Output("quotes-panel", "children"),
        Input("ui-interval", "n_intervals"),
        Input("quotes-symbol-dropdown", "value"),
        State("main-tabs", "value"),
        prevent_initial_call=True,
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

    @app.callback(
        Output("charts-status", "children"),
        Output("charts-main-graph", "figure"),
        Input("ui-interval", "n_intervals"),
        Input("charts-symbol-dropdown", "value"),
        Input("charts-timeframe-dropdown", "value"),
        State("main-tabs", "value"),
        prevent_initial_call=True,
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
            fig.update_layout(uirevision=f"charts-{symbol}-{timeframe}", dragmode="pan")

            return f"Charts loaded for {symbol}", fig

        except Exception as exc:
            fig = go.Figure()
            fig.update_layout(
                title=f"Charts tab error: {exc}",
                template="plotly_dark",
            )
            return f"Charts error: {exc}", fig
