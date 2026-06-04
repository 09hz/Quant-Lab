from __future__ import annotations

import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dcc, html, no_update, ctx

from RealTime import RealTimeIB, TIMEFRAME_MAP
from chart_utils import create_candlestick_figure
from tabs_ui import (
    build_dashboard_tab,
    build_watch_tab,
    build_quotes_tab,
    build_charts_tab,
)
from ReplayModule import ReplayEngine


DEFAULT_SYMBOL = "MSFT"
DEFAULT_TIMEFRAME = "1 min"

rt = RealTimeIB(host="127.0.0.1", port=4001)
rt.start(DEFAULT_SYMBOL, DEFAULT_TIMEFRAME)

replay = ReplayEngine()
SYMBOL_OPTIONS = rt.get_symbol_options()

app = Dash(__name__, suppress_callback_exceptions=True)
app.title = "Stock Visualizer"

app.layout = html.Div(
    className="app-shell",
    children=[
        html.Div(
            className="topbar",
            children=[
                html.Div(id="pair-title", className="pair-title"),
                html.Div(id="quote-strip", className="quote-strip"),
            ],
        ),

        dcc.Tabs(
            id="main-tabs",
            value="dashboard",
            className="main-tabs",
            children=[
                dcc.Tab(
                    label="Dashboard",
                    value="dashboard",
                    className="main-tab",
                    selected_className="main-tab-selected",
                    children=[
                        build_dashboard_tab(
                            symbol_options=SYMBOL_OPTIONS,
                            timeframe_map=TIMEFRAME_MAP,
                            default_symbol=DEFAULT_SYMBOL,
                            default_timeframe=DEFAULT_TIMEFRAME,
                        )
                    ],
                ),
                dcc.Tab(
                    label="Watch",
                    value="watch",
                    className="main-tab",
                    selected_className="main-tab-selected",
                    children=[
                        build_watch_tab(
                            symbol_options=SYMBOL_OPTIONS,
                            default_symbol="MSFT",
                            default_speed=1,
                            default_index=100,
                        )
                    ],
                ),
                dcc.Tab(
                    label="Quotes",
                    value="quotes",
                    className="main-tab",
                    selected_className="main-tab-selected",
                    children=[
                        build_quotes_tab(
                            symbol_options=SYMBOL_OPTIONS,
                            default_symbol=DEFAULT_SYMBOL,
                        )
                    ],
                ),
                dcc.Tab(
                    label="Charts",
                    value="charts",
                    className="main-tab",
                    selected_className="main-tab-selected",
                    children=[
                        build_charts_tab(
                            symbol_options=SYMBOL_OPTIONS,
                            timeframe_map=TIMEFRAME_MAP,
                            default_symbol=DEFAULT_SYMBOL,
                            default_timeframe=DEFAULT_TIMEFRAME,
                        )
                    ],
                ),
            ],
        ),

        dcc.Interval(id="ui-interval", interval=250, n_intervals=0),
        dcc.Store(id="zoom-state", data={}),
        dcc.Store(id="active-symbol", data=DEFAULT_SYMBOL),
        dcc.Store(id="load-status", data="Ready"),
        dcc.Store(
            id="dashboard-state",
            data={
                "symbol": DEFAULT_SYMBOL,
                "timeframe": DEFAULT_TIMEFRAME,
            },
        ),
        dcc.Store(
            id="watch-state",
            data={
                "symbol": "MSFT",
                "replay_speed": 1,
                "replay_index": 100,
            },
        ),
    ],
)


# =========================
# Shared callbacks
# =========================

@app.callback(
    Output("pair-title", "children"),
    Input("active-symbol", "data"),
    Input("main-tabs", "value"),
    State("watch-state", "data"),
    State("dashboard-state", "data"),
)
def update_pair_title(active_symbol, active_tab, watch_state, dashboard_state):
    if active_tab == "watch":
        symbol = (watch_state or {}).get("symbol", "MSFT")
    else:
        symbol = active_symbol or (dashboard_state or {}).get("symbol", DEFAULT_SYMBOL)

    company = rt.get_company_name(symbol)
    return f"{symbol} / {company}"


# =========================
# Dashboard callbacks
# =========================

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
    Output("active-symbol", "data"),
    Output("load-status", "data"),
    Input("symbol-dropdown", "value"),
    prevent_initial_call=True,
)
def auto_load_symbol(symbol):
    if not symbol:
        return no_update, "No symbol selected"

    try:
        symbol = rt._sanitize_symbol(symbol)
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
    Output("load-status-text", "children"),
    Input("load-status", "data"),
    prevent_initial_call=True,
)
def show_load_status(status):
    return status


@app.callback(
    Output("quote-strip", "children"),
    Output("live-chart", "figure"),
    Input("ui-interval", "n_intervals"),
    Input("active-symbol", "data"),
    Input("timeframe-dropdown", "value"),
    State("main-tabs", "value"),
    State("zoom-state", "data"),
    prevent_initial_call=True,
)
def render_dashboard_chart(_n, active_symbol, timeframe, active_tab, zoom_state):
    if active_tab != "dashboard":
        return no_update, no_update

    try:
        symbol = active_symbol or DEFAULT_SYMBOL
        timeframe = timeframe or DEFAULT_TIMEFRAME
        company_name = rt.get_company_name(symbol)

        snap = rt.get_snapshot(symbol, timeframe)
        fig = create_candlestick_figure(snap.bars, symbol, timeframe)

        bid = f"{snap.bid:.2f}" if snap.bid is not None else "--"
        ask = f"{snap.ask:.2f}" if snap.ask is not None else "--"
        last = f"{snap.last:.2f}" if snap.last is not None else "--"
        size = f"{snap.last_size:.0f}" if snap.last_size is not None else "--"
        updated = snap.updated_at.strftime("%H:%M:%S") if snap.updated_at else "--:--:--"

        quote_text = (
            f"[LIVE] {symbol} ({company_name}) | "
            f"Last: {last} | Bid: {bid} | Ask: {ask} | "
            f"Size: {size} | Ticks: {snap.tick_count} | Updated: {updated}"
        )

        if zoom_state:
            if "xaxis.range[0]" in zoom_state and "xaxis.range[1]" in zoom_state:
                fig.update_xaxes(
                    range=[zoom_state["xaxis.range[0]"], zoom_state["xaxis.range[1]"]],
                    row=1,
                    col=1,
                )
            if "yaxis.range[0]" in zoom_state and "yaxis.range[1]" in zoom_state:
                fig.update_yaxes(
                    range=[zoom_state["yaxis.range[0]"], zoom_state["yaxis.range[1]"]],
                    row=1,
                    col=1,
                )

        return quote_text, fig

    except Exception as exc:
        fig = go.Figure()
        fig.update_layout(
            title="Loading dashboard...",
            template="plotly_dark",
            paper_bgcolor="#0d1b4f",
            plot_bgcolor="#0d1b4f",
            font={"color": "#e8f1ff"},
        )
        return f"Loading dashboard... {exc}", fig


# =========================
# Watch callbacks
# =========================

@app.callback(
    Output("watch-state", "data"),
    Input("watch-symbol-dropdown", "value"),
    Input("replay-speed", "value"),
    Input("replay-slider", "value"),
    State("watch-state", "data"),
    prevent_initial_call=True,
)
def save_watch_state(symbol, replay_speed, replay_index, current_state):
    state = dict(current_state or {})
    if symbol:
        state["symbol"] = symbol
    if replay_speed is not None:
        state["replay_speed"] = replay_speed
    if replay_index is not None:
        state["replay_index"] = replay_index
    return state


@app.callback(
    Output("watch-status", "children"),
    Input("main-tabs", "value"),
    Input("watch-symbol-dropdown", "value"),
    prevent_initial_call=True,
)
def load_watch_symbol(active_tab, symbol):
    print(f"[CALLBACK] load_watch_symbol active_tab={active_tab} symbol={symbol}", flush=True)

    if active_tab != "watch":
        return no_update

    symbol = symbol or "MSFT"

    try:
        symbol = rt._sanitize_symbol(symbol)
        hist = rt.load_history(symbol, "1 min")

        if hist is None or hist.empty:
            print(f"[WATCH LOAD] no history for {symbol}", flush=True)
            return f"Replay load error: no history returned for {symbol}"

        replay.load_from_df(hist)
        print(f"[WATCH LOAD] symbol={symbol} rows={len(hist)}", flush=True)
        print(f"[WATCH LOAD] replay_info={replay.info()}", flush=True)
        return f"Replay loaded for {symbol} ({len(hist)} bars)"
    except Exception as exc:
        print(f"[WATCH LOAD ERROR] {exc}", flush=True)
        return f"Replay load error: {exc}"


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
    print(f"[CALLBACK] control_replay trigger={ctx.triggered_id} active_tab={active_tab}", flush=True)

    if active_tab != "watch":
        return no_update, no_update

    trigger = ctx.triggered_id

    try:
        if trigger == "replay-play":
            replay.play()
            return "Replay playing", max(1, replay.current_index)

        if trigger == "replay-pause":
            replay.pause()
            return "Replay paused", max(1, replay.current_index)

        if trigger == "replay-step":
            replay.forward(1)
            return f"Replay stepped to {replay.current_index}", max(1, replay.current_index)

        if trigger == "replay-rewind":
            replay.rewind(1)
            return f"Replay rewound to {replay.current_index}", max(1, replay.current_index)

        if trigger == "replay-slider":
            replay.set_index(slider_value or 1)
            return f"Replay moved to {replay.current_index}", max(1, replay.current_index)

        return no_update, no_update

    except Exception as exc:
        print(f"[REPLAY CONTROL ERROR] {exc}", flush=True)
        return f"Replay control error: {exc}", no_update


@app.callback(
    Output("watch-chart", "figure"),
    Output("replay-slider", "max"),
    Output("replay-slider", "value"),
    Input("ui-interval", "n_intervals"),
    Input("watch-symbol-dropdown", "value"),
    State("main-tabs", "value"),
    prevent_initial_call=True,
)
def render_watch_tab(_n, symbol, active_tab):
    print(f"[CALLBACK] render_watch_tab active_tab={active_tab} symbol={symbol}", flush=True)

    if active_tab != "watch":
        return no_update, no_update, no_update

    try:
        symbol = symbol or "MSFT"

        if replay.bars.empty:
            hist = rt.load_history(symbol, "1 min")
            replay.load_from_df(hist)
            print(f"[WATCH FALLBACK LOAD] symbol={symbol} rows={len(hist)}", flush=True)

        replay.tick()
        visible = replay.visible_bars()

        if visible.empty:
            print("[WATCH RENDER] visible empty", flush=True)
            fig = go.Figure()
            fig.update_layout(
                title=f"{symbol} | 1 min | No replay data loaded yet",
                template="plotly_dark",
                paper_bgcolor="#0d1b4f",
                plot_bgcolor="#0d1b4f",
                font={"color": "#e8f1ff"},
            )
            return fig, 100, 1

        info = replay.info()
        print(f"[WATCH RENDER] visible_rows={len(visible)} info={info}", flush=True)

        fig = create_candlestick_figure(visible, symbol, "1 min")
        return fig, max(1, info["max_index"]), max(1, info["current_index"])

    except Exception as exc:
        print(f"[WATCH RENDER ERROR] {exc}", flush=True)
        fig = go.Figure()
        fig.update_layout(
            title=f"Replay loading... {exc}",
            template="plotly_dark",
            paper_bgcolor="#0d1b4f",
            plot_bgcolor="#0d1b4f",
            font={"color": "#e8f1ff"},
        )
        return fig, 100, 1


# =========================
# Quotes callbacks
# =========================

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


# =========================
# Charts callbacks
# =========================

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
        fig = create_candlestick_figure(snap.bars, symbol, timeframe)

        return f"Charts loaded for {symbol}", fig

    except Exception as exc:
        fig = go.Figure()
        fig.update_layout(
            title=f"Charts tab error: {exc}",
            template="plotly_dark",
        )
        return f"Charts error: {exc}", fig


if __name__ == "__main__":
    app.run(debug=False)