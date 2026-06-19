# Refactor-ready file previews

These keep the current visual while preparing for the future split.

## `app.py`

```python
from __future__ import annotations

import sys
import asyncio
from datetime import datetime

import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dcc, html, no_update, ctx

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from core.RealTime import RealTimeIB, TIMEFRAME_MAP
from core.ReplayModule import ReplayEngine
from services.replay_service import ReplayService
from ui.tabs_ui import (
    build_dashboard_tab,
    build_watch_tab,
    build_quotes_tab,
    build_charts_tab,
)
from utils.chart_utils import create_candlestick_figure


DEFAULT_SYMBOL = "MSFT"
DEFAULT_TIMEFRAME = "1 min"

rt = RealTimeIB(host="127.0.0.1", port=4001)
rt.start(DEFAULT_SYMBOL, DEFAULT_TIMEFRAME)

replay_engine = ReplayEngine()
replay_service = ReplayService(rt, replay_engine)

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
                ),
                dcc.Tab(
                    label="Watch",
                    value="watch",
                    className="main-tab",
                    selected_className="main-tab-selected",
                ),
                dcc.Tab(
                    label="Quotes",
                    value="quotes",
                    className="main-tab",
                    selected_className="main-tab-selected",
                ),
                dcc.Tab(
                    label="Charts",
                    value="charts",
                    className="main-tab",
                    selected_className="main-tab-selected",
                ),
            ],
        ),
        html.Div(id="tab-content", className="tab-content"),
        dcc.Interval(id="ui-interval", interval=75, n_intervals=0),
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
                "replay_date": None,
                "replay_timeframe": "1 min",
            },
        ),
    ],
)


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
                html.Div(className="stat-row", children=[html.Div("First Bar", className="stat-label"), html.Div(str(first['time'])[:16], className="stat-value")]),
                html.Div(className="stat-row", children=[html.Div("Last Bar", className="stat-label"), html.Div(str(last['time'])[:16], className="stat-value")]),
            ],
        ),
    ]
    return cards


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


@app.callback(
    Output("tab-content", "children"),
    Input("main-tabs", "value"),
    State("dashboard-state", "data"),
    State("watch-state", "data"),
)
def render_tab_content(active_tab, dashboard_state, watch_state):
    dashboard_state = dashboard_state or {}
    watch_state = watch_state or {}

    dashboard_symbol = dashboard_state.get("symbol", DEFAULT_SYMBOL)
    dashboard_timeframe = dashboard_state.get("timeframe", DEFAULT_TIMEFRAME)

    watch_symbol = watch_state.get("symbol", "MSFT")
    watch_speed = watch_state.get("replay_speed", 1)
    watch_index = watch_state.get("replay_index", 100)
    watch_date = watch_state.get("replay_date")

    if active_tab == "watch":
        return build_watch_tab(
            symbol_options=SYMBOL_OPTIONS,
            default_symbol=watch_symbol,
            default_speed=watch_speed,
            default_index=watch_index,
            default_date=watch_date,
        )

    if active_tab == "quotes":
        return build_quotes_tab(
            symbol_options=SYMBOL_OPTIONS,
            default_symbol=dashboard_symbol,
        )

    if active_tab == "charts":
        return build_charts_tab(
            symbol_options=SYMBOL_OPTIONS,
            timeframe_map=TIMEFRAME_MAP,
            default_symbol=dashboard_symbol,
            default_timeframe=dashboard_timeframe,
        )

    return build_dashboard_tab(
        symbol_options=SYMBOL_OPTIONS,
        timeframe_map=TIMEFRAME_MAP,
        default_symbol=dashboard_symbol,
        default_timeframe=dashboard_timeframe,
    )


# =========================
# Dashboard callbacks
# =========================

@app.callback(
    Output("dashboard-state", "data"),
    Input("symbol-dropdown", "value"),
    Input("timeframe-dropdown", "value"),
    State("dashboard-state", "data"),
    State("symbol-dropdown", "search_value"),
    State("timeframe-dropdown", "search_value"),
    prevent_initial_call=True,
)
def save_dashboard_state(
    symbol,
    timeframe,
    current_state,
    symbol_search_value,
    timeframe_search_value,
):
    if symbol_search_value or timeframe_search_value:
        return no_update

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
    State("symbol-dropdown", "search_value"),
    State("active-symbol", "data"),
    prevent_initial_call=True,
)
def auto_load_symbol(symbol, symbol_search_value, current_active_symbol):
    if symbol_search_value:
        return no_update, no_update

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
    Output("load-status-text", "children"),
    Input("load-status", "data"),
    prevent_initial_call=True,
)
def show_load_status(status):
    return status


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
    State("symbol-dropdown", "search_value"),
    State("timeframe-dropdown", "search_value"),
    prevent_initial_call=True,
)
def render_dashboard_chart(
    _n,
    active_symbol,
    timeframe,
    active_tab,
    zoom_state,
    symbol_search_value,
    timeframe_search_value,
):
    if active_tab != "dashboard":
        return no_update, no_update, no_update, no_update

    if symbol_search_value or timeframe_search_value:
        return no_update, no_update, no_update, no_update

    try:
        symbol = active_symbol or DEFAULT_SYMBOL
        timeframe = timeframe or DEFAULT_TIMEFRAME
        company_name = rt.get_company_name(symbol)

        snap = rt.get_snapshot(symbol, timeframe)
        fig = create_candlestick_figure(snap.bars, symbol, timeframe)
        fig.update_layout(
            uirevision=f"dashboard-{symbol}-{timeframe}",
            dragmode="pan",
        )

        updated = snap.updated_at.strftime("%H:%M:%S") if snap.updated_at else "--:--:--"
        quote_text = f"LIVE · {company_name} ({symbol}) · Updated {updated}"

        if zoom_state:
            if "xaxis.range[0]" in zoom_state and "xaxis.range[1]" in zoom_state:
                fig.update_xaxes(
                    range=[zoom_state["xaxis.range[0]"], zoom_state["xaxis.range[1]"]]
                )
            if "yaxis.range[0]" in zoom_state and "yaxis.range[1]" in zoom_state:
                fig.update_yaxes(
                    range=[zoom_state["yaxis.range[0]"], zoom_state["yaxis.range[1]"]]
                )

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


# =========================
# Watch callbacks
# =========================

@app.callback(
    Output("watch-state", "data"),
    Input("watch-symbol-dropdown", "value"),
    Input("replay-speed", "value"),
    Input("replay-slider", "value"),
    Input("replay-date", "date"),
    State("watch-state", "data"),
    State("watch-symbol-dropdown", "search_value"),
    State("replay-speed", "search_value"),
    prevent_initial_call=True,
)
def save_watch_state(
    symbol,
    replay_speed,
    replay_index,
    replay_date,
    current_state,
    symbol_search_value,
    speed_search_value,
):
    if symbol_search_value or speed_search_value:
        return no_update

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
    Output("watch-status", "children"),
    Output("replay-slider", "max", allow_duplicate=True),
    Output("replay-slider", "value", allow_duplicate=True),
    Input("main-tabs", "value"),
    Input("watch-symbol-dropdown", "value"),
    Input("replay-date", "date"),
    Input("replay-speed", "value"),
    State("watch-symbol-dropdown", "search_value"),
    State("replay-speed", "search_value"),
    prevent_initial_call=True,
)
def load_watch_symbol(active_tab, symbol, replay_date, replay_speed, symbol_search_value, speed_search_value):
    if active_tab != "watch":
        return no_update, no_update, no_update

    if symbol_search_value or speed_search_value:
        return no_update, no_update, no_update

    try:
        status, info = replay_service.load_replay(
            symbol=symbol or "MSFT",
            timeframe="1 min",
            replay_date=replay_date,
            speed=replay_speed,
        )
        return status, max(1, info["max_index"]), max(1, info["current_index"])
    except Exception as exc:
        return f"Replay load error: {exc}", 100, 1


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
            return "Replay playing", max(1, replay_service.info()["current_index"])

        if trigger == "replay-pause":
            replay_service.pause()
            return "Replay paused", max(1, replay_service.info()["current_index"])

        if trigger == "replay-step":
            replay_service.forward(1)
            return f"Replay stepped to {replay_service.info()['current_index']}", max(1, replay_service.info()["current_index"])

        if trigger == "replay-rewind":
            replay_service.rewind(1)
            return f"Replay rewound to {replay_service.info()['current_index']}", max(1, replay_service.info()["current_index"])

        if trigger == "replay-slider":
            replay_service.set_index(slider_value or 1)
            return f"Replay moved to {replay_service.info()['current_index']}", max(1, replay_service.info()["current_index"])

        return no_update, no_update

    except Exception as exc:
        print(f"[REPLAY CONTROL ERROR] {exc}", flush=True)
        return f"Replay control error: {exc}", no_update


@app.callback(
    Output("watch-chart", "figure"),
    Output("replay-slider", "max", allow_duplicate=True),
    Output("replay-slider", "value", allow_duplicate=True),
    Output("watch-metrics-strip", "children"),
    Output("watch-stats-grid", "children"),
    Output("watch-loading-overlay", "className"),
    Input("ui-interval", "n_intervals"),
    State("main-tabs", "value"),
    State("watch-symbol-dropdown", "value"),
    State("watch-symbol-dropdown", "search_value"),
    State("replay-speed", "search_value"),
    prevent_initial_call=True,
)
def render_watch_tab(_n, active_tab, symbol, symbol_search_value, speed_search_value):
    if active_tab != "watch":
        return no_update, no_update, no_update, no_update, no_update, "watch-loading-overlay hidden"

    if symbol_search_value or speed_search_value:
        return no_update, no_update, no_update, no_update, no_update, no_update

    try:
        symbol = symbol or "MSFT"

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
            return fig, 100, 1, [], [], "watch-loading-overlay"

        info = replay_service.info()

        fig = create_candlestick_figure(visible, symbol, "1 min")
        fig.update_layout(
            uirevision=f"watch-{symbol}",
            dragmode="pan",
        )

        company = rt.get_company_name(symbol)
        last_close = float(visible.iloc[-1]["close"]) if not visible.empty else None
        open_val = float(visible.iloc[0]["open"]) if not visible.empty else None

        metrics = _build_metrics_strip(symbol, company, last_close, open_val, datetime.now())
        stats = _build_stats_grid_from_bars(visible)

        return (
            fig,
            max(1, info["max_index"]),
            max(1, info["current_index"]),
            metrics,
            stats,
            "watch-loading-overlay hidden",
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
            uirevision=f"watch-{symbol or 'MSFT'}",
            dragmode="pan",
        )
        return fig, 100, 1, [], [], "watch-loading-overlay"


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
        fig.update_layout(uirevision=f"charts-{symbol}-{timeframe}", dragmode="pan")

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

```

## `services/replay_service.py`

```python
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from core.RealTime import RealTimeIB
from core.ReplayModule import ReplayEngine


class ReplayService:
    def __init__(self, rt: RealTimeIB, engine: ReplayEngine):
        self.rt = rt
        self.engine = engine
        self.cache: dict[tuple[str, str, str], pd.DataFrame] = {}

    def _make_cache_key(
        self,
        symbol: str,
        timeframe: str,
        replay_date: Optional[str],
    ) -> tuple[str, str, str]:
        symbol = self.rt._sanitize_symbol(symbol)
        return (symbol, timeframe or "1 min", replay_date or "latest")

    def clear_cache(self) -> None:
        self.cache.clear()

    def load_replay(
        self,
        symbol: str,
        timeframe: str = "1 min",
        replay_date: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> tuple[str, dict]:
        symbol = self.rt._sanitize_symbol(symbol)
        timeframe = timeframe or "1 min"
        cache_key = self._make_cache_key(symbol, timeframe, replay_date)

        if cache_key in self.cache:
            hist = self.cache[cache_key]
        else:
            if replay_date:
                start_dt = datetime.fromisoformat(replay_date)
                end_dt = start_dt + timedelta(days=1)
                hist = self.rt.load_history_range(symbol, timeframe, start_dt, end_dt)
            else:
                hist = self.rt.load_history(symbol, timeframe)
            self.cache[cache_key] = hist

        if hist is None or hist.empty:
            self.engine.reset()
            if speed is not None:
                self.engine.set_speed(speed)
            return f"No replay history returned for {symbol}", {
                "playing": False,
                "speed": self.engine.speed,
                "current_index": 1,
                "max_index": 0,
            }

        self.engine.reset()
        self.engine.load_from_df(hist)
        if speed is not None:
            self.engine.set_speed(speed)

        return f"Replay loaded for {symbol} ({len(hist)} bars)", self.engine.info()

    def play(self) -> None:
        self.engine.play()

    def pause(self) -> None:
        self.engine.pause()

    def rewind(self, steps: int = 1) -> None:
        self.engine.rewind(steps)

    def forward(self, steps: int = 1) -> None:
        self.engine.forward(steps)

    def set_index(self, index: int) -> None:
        self.engine.set_index(index)

    def set_speed(self, speed: float) -> None:
        self.engine.set_speed(speed)

    def tick(self) -> None:
        self.engine.tick()

    def visible_bars(self) -> pd.DataFrame:
        return self.engine.visible_bars()

    def current_bar(self):
        return self.engine.current_bar()

    def info(self) -> dict:
        return self.engine.info()

    def reset(self) -> None:
        self.engine.reset()

```

## `core/RealTime.py`

```python
from __future__ import annotations

import asyncio
import csv
import queue
import random
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd
from dash import html
from ib_async import IB, Stock, Ticker, util

from utils.chart_utils import apply_tick_to_bars, normalize_history_df, resample_bars


TIMEFRAME_MAP: Dict[str, Tuple[str, str]] = {
    "1 min": ("1 min", "1 D"),
    "5 mins": ("5 mins", "2 D"),
    "15 mins": ("15 mins", "5 D"),
    "1 hour": ("1 hour", "30 D"),
    "1 day": ("1 day", "1 Y"),
}


@dataclass
class SymbolState:
    symbol: str
    timeframe: str
    bars: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(
        columns=["time", "open", "high", "low", "close", "volume"]
    ))
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    last_size: float = 0.0
    updated_at: Optional[datetime] = None
    tick_count: int = 0


class RealTimeIB:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 4001,
        client_id: Optional[int] = None,
    ):
        self.host = host
        self.port = port
        self.client_id = client_id if client_id is not None else random.randint(1000, 999999)

        self.ib = IB()

        self._contracts: Dict[str, Stock] = {}
        self._tickers: Dict[str, Ticker] = {}
        self._states: Dict[Tuple[str, str], SymbolState] = {}

        self._lock = threading.RLock()
        self._runner_thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._startup_error: Optional[str] = None

        self._requests: queue.Queue[tuple[Any, ...]] = queue.Queue()

        project_root = Path(__file__).resolve().parent.parent
        data_dir = project_root / "data"

        self.nasdaq_file = data_dir / "nasdaq_tickers_simple.txt"
        self.nasdaq_symbols = self._load_nasdaq_symbols(self.nasdaq_file)

        self.company_file = data_dir / "nasdaq_symbol_names_filled.csv"
        self.company_names = self._load_company_names(self.company_file)

        print(f"[NASDAQ FILE] {self.nasdaq_file}", flush=True)
        print(f"[NASDAQ COUNT] {len(self.nasdaq_symbols)}", flush=True)
        print(f"[HAS MSFT] {'MSFT' in self.nasdaq_symbols}", flush=True)

        print(f"[COMPANY FILE] {self.company_file}", flush=True)
        print(f"[COMPANY COUNT] {len(self.company_names)}", flush=True)
        print(f"[MSFT NAME] {self.company_names.get('MSFT', 'MISSING')}", flush=True)

    def _load_nasdaq_symbols(self, file_path: Path) -> set[str]:
        if not file_path.exists():
            print(f"[WARN] NASDAQ file not found: {file_path}", flush=True)
            return set()

        with open(file_path, "r", encoding="utf-8") as f:
            return {
                line.strip().upper()
                for line in f
                if line.strip()
            }

    def _load_company_names(self, file_path: Path) -> dict[str, str]:
        if not file_path.exists():
            print(f"[WARN] Company file not found: {file_path}", flush=True)
            return {}

        company_map: dict[str, str] = {}

        with open(file_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                symbol = (row.get("symbol") or "").strip().upper()
                name = (row.get("name") or "").strip()
                if symbol:
                    company_map[symbol] = name

        return company_map

    def is_valid_nasdaq_symbol(self, symbol: str) -> bool:
        symbol = self._sanitize_symbol(symbol)
        return symbol in self.nasdaq_symbols

    def get_company_name(self, symbol: str) -> str:
        symbol = self._sanitize_symbol(symbol)
        return self.company_names.get(symbol) or symbol

    def get_symbol_options(self) -> list[dict[str, object]]:
        options: list[dict[str, object]] = []

        for symbol in sorted(self.nasdaq_symbols):
            company = self.company_names.get(symbol, "")
            label_text = f"{symbol} - {company}" if company else symbol
            search_text = f"{symbol} {company}".strip()

            options.append(
                {
                    "label": html.Span(label_text, style={"color": "black"}),
                    "value": symbol,
                    "search": search_text,
                }
            )

        return options

    def connect(self) -> None:
        if not self.ib.isConnected():
            self.ib.connect(self.host, self.port, clientId=self.client_id, timeout=30)

    def disconnect(self) -> None:
        if self.ib.isConnected():
            self.ib.disconnect()

    def start(self, symbol: str, timeframe: str) -> None:
        if self._runner_thread and self._runner_thread.is_alive():
            return

        symbol = self._sanitize_symbol(symbol)

        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                self.connect()
                self.ensure_symbol_ready(symbol, timeframe)
                self._ready.set()

                while True:
                    self._process_requests()
                    self.ib.sleep(0.25)

            except Exception as exc:
                self._startup_error = str(exc)
                self._ready.set()
                print(f"[IB LOOP ERROR] {exc}", flush=True)

        self._runner_thread = threading.Thread(target=_run, daemon=True)
        self._runner_thread.start()
        self._ready.wait(timeout=15)

        if self._startup_error:
            raise RuntimeError(self._startup_error)

    def request_symbol(self, symbol: str) -> None:
        symbol = self._sanitize_symbol(symbol)
        self._requests.put(("symbol", symbol))

    def _process_requests(self) -> None:
        while not self._requests.empty():
            req = self._requests.get()

            try:
                kind = req[0]

                if kind == "symbol":
                    symbol = str(req[1])
                    print(f"[REQUEST] loading live symbol {symbol}", flush=True)
                    self.ensure_symbol_ready(symbol, "1 min")
                    print(f"[REQUEST] loaded live symbol {symbol}", flush=True)

            except Exception as exc:
                print(f"[REQUEST ERROR] {req}: {exc}", flush=True)

    def get_contract(self, symbol: str) -> Stock:
        symbol = self._sanitize_symbol(symbol)

        if not self.is_valid_nasdaq_symbol(symbol):
            raise ValueError(f"{symbol} is not in NASDAQ symbol list")

        with self._lock:
            if symbol in self._contracts:
                return self._contracts[symbol]

        contract = Stock(symbol, "SMART", "USD", primaryExchange="NASDAQ")
        self.ib.qualifyContracts(contract)

        with self._lock:
            self._contracts[symbol] = contract

        return contract

    def load_history(self, symbol: str, timeframe: str) -> pd.DataFrame:
        symbol = self._sanitize_symbol(symbol)

        if timeframe not in TIMEFRAME_MAP:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        contract = self.get_contract(symbol)
        bar_size, duration = TIMEFRAME_MAP[timeframe]

        bars = self.ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow="TRADES",
            useRTH=True,
            formatDate=1,
        )

        df = util.df(bars)
        df = normalize_history_df(df)

        with self._lock:
            key = (symbol, timeframe)
            state = self._states.get(key, SymbolState(symbol=symbol, timeframe=timeframe))
            state.bars = df
            state.updated_at = datetime.now()
            self._states[key] = state

        return df

    def load_history_at(self, symbol: str, timeframe: str, end_dt: datetime) -> pd.DataFrame:
        symbol = self._sanitize_symbol(symbol)

        if timeframe not in TIMEFRAME_MAP:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        contract = self.get_contract(symbol)
        bar_size, duration = TIMEFRAME_MAP[timeframe]

        bars = self.ib.reqHistoricalData(
            contract,
            endDateTime=end_dt.strftime("%Y%m%d %H:%M:%S"),
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow="TRADES",
            useRTH=True,
            formatDate=1,
        )

        df = util.df(bars)
        df = normalize_history_df(df)
        return df

    def load_history_range(
        self,
        symbol: str,
        timeframe: str,
        start_dt: datetime,
        end_dt: datetime,
    ) -> pd.DataFrame:
        if start_dt >= end_dt:
            raise ValueError("start_dt must be before end_dt")

        pieces: list[pd.DataFrame] = []
        cursor = end_dt

        step_map = {
            "1 min": timedelta(days=1),
            "5 mins": timedelta(days=2),
            "15 mins": timedelta(days=5),
            "1 hour": timedelta(days=30),
            "1 day": timedelta(days=365),
        }

        if timeframe not in step_map:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        while cursor > start_dt:
            chunk = self.load_history_at(symbol, timeframe, cursor)

            if chunk is None or chunk.empty:
                break

            pieces.append(chunk)

            oldest = pd.to_datetime(chunk["time"].min()).to_pydatetime()
            if oldest <= start_dt:
                break

            cursor = oldest - timedelta(seconds=1)
            self.ib.sleep(0.25)

        if not pieces:
            return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

        out = pd.concat(pieces, ignore_index=True)
        out = out.drop_duplicates(subset="time").sort_values("time").reset_index(drop=True)
        out = out[(out["time"] >= start_dt) & (out["time"] <= end_dt)].reset_index(drop=True)
        return out

    def subscribe_live(self, symbol: str, timeframe: str = "1 min") -> None:
        symbol = self._sanitize_symbol(symbol)
        contract = self.get_contract(symbol)

        with self._lock:
            key = (symbol, "1 min")
            has_state = key in self._states and not self._states[key].bars.empty
            if symbol in self._tickers:
                return

        if not has_state:
            self.load_history(symbol, "1 min")

        ticker = self.ib.reqMktData(contract, "", False, False)
        ticker.updateEvent += self._make_tick_handler(symbol, "1 min")

        with self._lock:
            self._tickers[symbol] = ticker

    def _make_tick_handler(self, symbol: str, timeframe: str):
        def on_tick(ticker: Ticker, *args):
            price_raw = ticker.last if ticker.last is not None else ticker.marketPrice()

            if price_raw is None or pd.isna(price_raw):
                return

            price = float(price_raw)
            size = float(ticker.lastSize or 0)

            with self._lock:
                key = (symbol, timeframe)
                state = self._states.get(key)
                if state is None:
                    return

                state.bid = float(ticker.bid) if ticker.bid is not None else state.bid
                state.ask = float(ticker.ask) if ticker.ask is not None else state.ask
                state.last = price
                state.last_size = size
                state.updated_at = datetime.now()
                state.tick_count += 1
                state.bars = apply_tick_to_bars(
                    state.bars,
                    price=price,
                    size=size,
                    tick_time=datetime.now(),
                )
                self._states[key] = state

        return on_tick

    def get_snapshot(self, symbol: str, timeframe: str) -> SymbolState:
        symbol = self._sanitize_symbol(symbol)
        key = (symbol, "1 min")

        with self._lock:
            state = self._states.get(key)

        if state is None:
            raise ValueError(f"No loaded state for {symbol} 1 min")

        bars = state.bars.copy()
        if timeframe != "1 min":
            bars = resample_bars(bars, timeframe)

        return SymbolState(
            symbol=state.symbol,
            timeframe=timeframe,
            bars=bars,
            bid=state.bid,
            ask=state.ask,
            last=state.last,
            last_size=state.last_size,
            updated_at=state.updated_at,
            tick_count=state.tick_count,
        )

    def ensure_symbol_ready(self, symbol: str, timeframe: str) -> None:
        self.load_history(symbol, "1 min")
        self.subscribe_live(symbol, "1 min")

    @staticmethod
    def _sanitize_symbol(symbol: str) -> str:
        cleaned = "".join(
            ch for ch in symbol.upper().strip()
            if ch.isalnum() or ch in {".", "-"}
        )
        if not cleaned:
            raise ValueError("Invalid symbol.")
        return cleaned
```

## `core/ReplayModule.py`

```python
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


@dataclass
class ReplayEngine:
    bars: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(
        columns=["time", "open", "high", "low", "close", "volume"]
    ))
    current_index: int = 1
    playing: bool = False
    speed: float = 1.0
    progress: float = 0.0
    last_tick_time: Optional[float] = None

    def reset(self) -> None:
        self.bars = pd.DataFrame(
            columns=["time", "open", "high", "low", "close", "volume"]
        )
        self.current_index = 1
        self.playing = False
        self.speed = 1.0
        self.progress = 0.0
        self.last_tick_time = None

    def load_from_csv(self, path: str) -> None:
        df = pd.read_csv(path)
        self.load_from_df(df)

    def load_from_df(self, df: pd.DataFrame) -> None:
        if df is None or df.empty:
            raise ValueError("Replay data is empty.")

        out = df.copy()

        if "time" not in out.columns:
            if "date" in out.columns:
                out = out.rename(columns={"date": "time"})
            elif "Date" in out.columns:
                out = out.rename(columns={"Date": "time"})
            elif "datetime" in out.columns:
                out = out.rename(columns={"datetime": "time"})
            elif "Datetime" in out.columns:
                out = out.rename(columns={"Datetime": "time"})

        required = ["time", "open", "high", "low", "close", "volume"]
        missing = [c for c in required if c not in out.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        out = out[required].copy()
        out["time"] = pd.to_datetime(out["time"], errors="coerce")
        out = out.dropna(subset=["time"]).sort_values("time").drop_duplicates(subset="time")

        out["open"] = pd.to_numeric(out["open"], errors="coerce")
        out["high"] = pd.to_numeric(out["high"], errors="coerce")
        out["low"] = pd.to_numeric(out["low"], errors="coerce")
        out["close"] = pd.to_numeric(out["close"], errors="coerce")
        out["volume"] = pd.to_numeric(out["volume"], errors="coerce").fillna(0)

        out = out.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)

        if out.empty:
            raise ValueError("Replay data became empty after cleaning.")

        self.bars = out
        self.current_index = max(1, min(100, len(out)))
        self.playing = False
        self.speed = 1.0
        self.progress = 0.0
        self.last_tick_time = None

    def play(self) -> None:
        self.playing = True
        self.last_tick_time = time.perf_counter()

    def pause(self) -> None:
        self.playing = False
        self.last_tick_time = None

    def rewind(self, steps: int = 1) -> None:
        self.current_index = max(1, self.current_index - max(1, steps))
        self.last_tick_time = time.perf_counter() if self.playing else None

    def forward(self, steps: int = 1) -> None:
        self.current_index = min(len(self.bars), self.current_index + max(1, steps))
        self.last_tick_time = time.perf_counter() if self.playing else None

    def set_index(self, index: int) -> None:
        if self.bars.empty:
            return
        self.current_index = max(1, min(int(index), len(self.bars)))
        self.last_tick_time = time.perf_counter() if self.playing else None

    def set_speed(self, speed: float) -> None:
        self.speed = max(0.25, float(speed))

    def tick(self) -> None:
        if not self.playing or self.bars.empty:
            return

        now = time.perf_counter()

        if self.last_tick_time is None:
            self.last_tick_time = now
            return

        elapsed = now - self.last_tick_time
        self.last_tick_time = now

        base_bars_per_second = 4.0
        bars_to_advance = elapsed * self.speed * base_bars_per_second
        self.progress += bars_to_advance

        step = int(self.progress)
        if step < 1:
            return

        self.progress -= step
        self.current_index = min(len(self.bars), self.current_index + step)

        if self.current_index >= len(self.bars):
            self.playing = False
            self.last_tick_time = None

    def visible_bars(self) -> pd.DataFrame:
        if self.bars.empty:
            return self.bars.copy()
        return self.bars.iloc[:self.current_index].copy()

    def current_bar(self) -> Optional[pd.Series]:
        visible = self.visible_bars()
        if visible.empty:
            return None
        return visible.iloc[-1]

    def info(self) -> dict:
        return {
            "playing": self.playing,
            "speed": self.speed,
            "current_index": self.current_index,
            "max_index": len(self.bars),
        }
```

## `ui/tabs_ui.py`

```python
from dash import dcc, html


def make_timeframe_options(timeframe_map):
    return [
        {
            "label": html.Span(k, style={"color": "#f4f7ff"}),
            "value": k,
            "search": k,
        }
        for k in timeframe_map.keys()
    ]


def make_replay_speed_options():
    return [
        {"label": html.Span("0.25x", style={"color": "#f4f7ff"}), "value": 0.25, "search": "0.25x quarter slow"},
        {"label": html.Span("0.5x", style={"color": "#f4f7ff"}), "value": 0.5, "search": "0.5x half slow"},
        {"label": html.Span("1x", style={"color": "#f4f7ff"}), "value": 1, "search": "1x normal default"},
        {"label": html.Span("2x", style={"color": "#f4f7ff"}), "value": 2, "search": "2x double fast"},
        {"label": html.Span("5x", style={"color": "#f4f7ff"}), "value": 5, "search": "5x very fast"},
    ]


def build_dashboard_tab(symbol_options, timeframe_map, default_symbol, default_timeframe):
    return html.Div(
        className="tab-panel dashboard-tab-panel",
        children=[
            html.Div(
                className="controls-row",
                children=[
                    html.Div(
                        className="control-box control-symbol",
                        children=[
                            html.Label("Symbol / Company"),
                            dcc.Dropdown(
                                id="symbol-dropdown",
                                options=symbol_options,
                                value=default_symbol,
                                placeholder="Search ticker or company...",
                                searchable=True,
                                clearable=False,
                                className="black-dropdown",
                            ),
                        ],
                    ),
                    html.Div(
                        className="control-box control-timeframe",
                        children=[
                            html.Label("Timeframe"),
                            dcc.Dropdown(
                                id="timeframe-dropdown",
                                options=make_timeframe_options(timeframe_map),
                                value=default_timeframe,
                                clearable=False,
                                searchable=True,
                                className="black-dropdown",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(id="load-status-text", className="status-text"),
            html.Div(id="dashboard-metrics-strip", className="metrics-strip"),
            html.Div(
                className="range-row",
                children=[
                    html.Button("1 Day", id="dashboard-range-1d", n_clicks=0, className="range-btn"),
                    html.Button("5 Days", id="dashboard-range-5d", n_clicks=0, className="range-btn"),
                    html.Button("1 Month", id="dashboard-range-1m", n_clicks=0, className="range-btn"),
                    html.Button("YTD", id="dashboard-range-ytd", n_clicks=0, className="range-btn"),
                    html.Button("1 Year", id="dashboard-range-1y", n_clicks=0, className="range-btn"),
                    html.Button("5 Years", id="dashboard-range-5y", n_clicks=0, className="range-btn"),
                    html.Button("Max", id="dashboard-range-max", n_clicks=0, className="range-btn"),
                ],
            ),
            html.Div(
                className="chart-card",
                children=[
                    dcc.Graph(
                        id="live-chart",
                        className="chart-graph",
                        config={
                            "displaylogo": False,
                            "scrollZoom": True,
                            "modeBarButtonsToRemove": [
                                "lasso2d",
                                "select2d",
                                "autoScale2d",
                            ],
                        },
                    ),
                ],
            ),
            html.Div(id="dashboard-stats-grid", className="stats-grid"),
        ],
    )


def build_watch_tab(symbol_options, default_symbol, default_speed=1, default_index=100, default_date=None):
    return html.Div(
        className="tab-panel watch-tab-panel",
        children=[
            html.Div(
                className="controls-row",
                children=[
                    html.Div(
                        className="control-box control-symbol",
                        children=[
                            html.Label("Replay Symbol / Company"),
                            dcc.Dropdown(
                                id="watch-symbol-dropdown",
                                options=symbol_options,
                                value=default_symbol,
                                placeholder="Search ticker or company...",
                                searchable=True,
                                clearable=False,
                                className="black-dropdown",
                            )
                        ],
                    ),
                    html.Div(
                        className="control-box control-timeframe",
                        children=[
                            html.Label("Replay Speed"),
                            dcc.Dropdown(
                                id="replay-speed",
                                options=make_replay_speed_options(),
                                value=default_speed,
                                clearable=False,
                                searchable=True,
                                className="black-dropdown",
                            ),
                        ],
                    ),
                    html.Div(
                        className="control-box control-timeframe",
                        children=[
                            html.Label("Replay Start Date"),
                            dcc.DatePickerSingle(
                                id="replay-date",
                                date=default_date,
                                display_format="MM/DD/YYYY",
                                className="date-picker-dark",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="controls-row",
                children=[
                    html.Div(
                        className="control-box",
                        children=[
                            html.Label("Replay Controls"),
                            html.Div(
                                [
                                    html.Button("Play", id="replay-play", n_clicks=0),
                                    html.Button("Pause", id="replay-pause", n_clicks=0),
                                    html.Button("Step", id="replay-step", n_clicks=0),
                                    html.Button("Rewind", id="replay-rewind", n_clicks=0),
                                ],
                                style={"display": "flex", "gap": "8px", "flexWrap": "wrap"},
                            ),
                        ],
                    ),
                    html.Div(
                        className="control-box control-symbol",
                        children=[
                            html.Label("Replay Position"),
                            dcc.Slider(
                                id="replay-slider",
                                min=1,
                                max=100,
                                step=1,
                                value=default_index,
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(id="watch-status", className="status-text"),
            html.Div(id="watch-metrics-strip", className="metrics-strip"),
            html.Div(
                className="range-row",
                children=[
                    html.Button("1 Day", id="watch-range-1d", n_clicks=0, className="range-btn"),
                    html.Button("5 Days", id="watch-range-5d", n_clicks=0, className="range-btn"),
                    html.Button("1 Month", id="watch-range-1m", n_clicks=0, className="range-btn"),
                    html.Button("YTD", id="watch-range-ytd", n_clicks=0, className="range-btn"),
                    html.Button("1 Year", id="watch-range-1y", n_clicks=0, className="range-btn"),
                    html.Button("5 Years", id="watch-range-5y", n_clicks=0, className="range-btn active"),
                    html.Button("Max", id="watch-range-max", n_clicks=0, className="range-btn"),
                ],
            ),
            html.Div(
                className="chart-card watch-chart-wrap",
                children=[
                    html.Div(
                        id="watch-loading-overlay",
                        className="watch-loading-overlay hidden",
                        children=[
                            html.Div("Loading replay data...", className="watch-loading-text"),
                        ],
                    ),
                    dcc.Graph(
                        id="watch-chart",
                        className="chart-graph",
                        config={
                            "displaylogo": False,
                            "scrollZoom": True,
                        },
                    ),
                ],
            ),
            html.Div(id="watch-stats-grid", className="stats-grid"),
        ],
    )


def build_quotes_tab(symbol_options, default_symbol):
    return html.Div(
        className="tab-panel quotes-tab-panel",
        children=[
            html.Div(
                className="controls-row",
                children=[
                    html.Div(
                        className="control-box control-symbol",
                        children=[
                            html.Label("Quote Symbol / Company"),
                            dcc.Dropdown(
                                id="quotes-symbol-dropdown",
                                options=symbol_options,
                                value=default_symbol,
                                placeholder="Search ticker or company...",
                                searchable=True,
                                clearable=False,
                                className="black-dropdown",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(id="quotes-status", className="status-text"),
            html.Div(
                className="chart-card",
                children=[
                    html.Div(
                        id="quotes-panel",
                        className="quote-strip",
                        children="Quotes tab ready",
                    ),
                ],
            ),
        ],
    )


def build_charts_tab(symbol_options, timeframe_map, default_symbol, default_timeframe):
    return html.Div(
        className="tab-panel charts-tab-panel",
        children=[
            html.Div(
                className="controls-row",
                children=[
                    html.Div(
                        className="control-box control-symbol",
                        children=[
                            html.Label("Charts Symbol / Company"),
                            dcc.Dropdown(
                                id="charts-symbol-dropdown",
                                options=symbol_options,
                                value=default_symbol,
                                placeholder="Search ticker or company...",
                                searchable=True,
                                clearable=False,
                                className="black-dropdown",
                            ),
                        ],
                    ),
                    html.Div(
                        className="control-box control-timeframe",
                        children=[
                            html.Label("Charts Timeframe"),
                            dcc.Dropdown(
                                id="charts-timeframe-dropdown",
                                options=make_timeframe_options(timeframe_map),
                                value=default_timeframe,
                                clearable=False,
                                searchable=True,
                                className="black-dropdown",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(id="charts-status", className="status-text"),
            html.Div(
                className="chart-card",
                children=[
                    dcc.Graph(
                        id="charts-main-graph",
                        className="chart-graph",
                        config={
                            "displaylogo": False,
                            "scrollZoom": True,
                        },
                    ),
                ],
            ),
        ],
    )
```

## `utils/chart_utils.py`

```python
from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd
import plotly.graph_objects as go


def normalize_history_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

    out = df.copy()

    rename_map = {}
    for src, dst in [
        ("date", "time"),
        ("Date", "time"),
        ("datetime", "time"),
        ("Datetime", "time"),
    ]:
        if src in out.columns and dst not in out.columns:
            rename_map[src] = dst

    if rename_map:
        out = out.rename(columns=rename_map)

    required = ["time", "open", "high", "low", "close", "volume"]
    for col in required:
        if col not in out.columns:
            if col == "volume":
                out[col] = 0
            else:
                raise ValueError(f"Missing required column: {col}")

    out = out[required].copy()
    out["time"] = pd.to_datetime(out["time"], errors="coerce")
    out["open"] = pd.to_numeric(out["open"], errors="coerce")
    out["high"] = pd.to_numeric(out["high"], errors="coerce")
    out["low"] = pd.to_numeric(out["low"], errors="coerce")
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out["volume"] = pd.to_numeric(out["volume"], errors="coerce").fillna(0)

    out = out.dropna(subset=["time", "open", "high", "low", "close"])
    out = out.drop_duplicates(subset="time").sort_values("time").reset_index(drop=True)

    return out


def _floor_time_to_minute(ts: datetime) -> pd.Timestamp:
    return pd.Timestamp(ts).floor("min")


def apply_tick_to_bars(
    bars: pd.DataFrame,
    price: float,
    size: float,
    tick_time: Optional[datetime] = None,
) -> pd.DataFrame:
    if tick_time is None:
        tick_time = datetime.now()

    out = normalize_history_df(bars)
    bar_time = _floor_time_to_minute(tick_time)

    if out.empty:
        return pd.DataFrame(
            [
                {
                    "time": bar_time,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": size,
                }
            ]
        )

    last_idx = out.index[-1]
    last_bar_time = pd.Timestamp(out.loc[last_idx, "time"]).floor("min")

    if bar_time > last_bar_time:
        new_row = {
            "time": bar_time,
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": size,
        }
        out = pd.concat([out, pd.DataFrame([new_row])], ignore_index=True)
        return out

    if bar_time == last_bar_time:
        out.loc[last_idx, "high"] = max(float(out.loc[last_idx, "high"]), price)
        out.loc[last_idx, "low"] = min(float(out.loc[last_idx, "low"]), price)
        out.loc[last_idx, "close"] = price
        out.loc[last_idx, "volume"] = float(out.loc[last_idx, "volume"]) + size
        return out

    return out


def resample_bars(bars: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    out = normalize_history_df(bars)
    if out.empty or timeframe == "1 min":
        return out

    rule_map = {
        "5 mins": "5min",
        "15 mins": "15min",
        "1 hour": "1h",
        "1 day": "1D",
    }

    if timeframe not in rule_map:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    out = out.set_index("time")
    resampled = out.resample(rule_map[timeframe]).agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )
    resampled = resampled.dropna(subset=["open", "high", "low", "close"]).reset_index()
    return resampled


def create_candlestick_figure(bars: pd.DataFrame, symbol: str, timeframe: str) -> go.Figure:
    df = normalize_history_df(bars)

    fig = go.Figure()

    if not df.empty:
        fig.add_trace(
            go.Candlestick(
                x=df["time"],
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name=f"{symbol} {timeframe}",
                increasing_line_color="#22c55e",
                increasing_fillcolor="#22c55e",
                decreasing_line_color="#ef4444",
                decreasing_fillcolor="#ef4444",
                whiskerwidth=0.4,
            )
        )

        last_price = float(df.iloc[-1]["close"])

        fig.add_hline(
            y=last_price,
            line_width=1.2,
            line_dash="dot",
            line_color="#60a5fa",
            opacity=0.95,
            annotation_text=f"{last_price:,.2f}",
            annotation_position="right",
            annotation_font=dict(color="white", size=12),
            annotation_bgcolor="#2563eb",
            annotation_bordercolor="#60a5fa",
        )

    fig.update_layout(
        title=dict(
            text=f"{symbol} · {timeframe}",
            x=0.02,
            xanchor="left",
            font=dict(size=18, color="#f8fbff"),
        ),
        template="plotly_dark",
        paper_bgcolor="#071224",
        plot_bgcolor="#071224",
        font={"color": "#dbe7ff"},
        margin=dict(l=16, r=56, t=44, b=16),
        xaxis_rangeslider_visible=False,
        dragmode="pan",
        hovermode="x unified",
    )

    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.05)",
        zeroline=False,
        showline=False,
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.05)",
        zeroline=False,
        showline=False,
        side="right",
    )

    return fig
```

## `assets/style.css`

```css
/* =========================
   Global dark theme
========================= */
body {
    margin: 0;
    background: linear-gradient(135deg, #07111f 0%, #0a1630 45%, #130f2c 100%);
    font-family: Arial, Helvetica, sans-serif;
    color: #e6eefc;
}

.app-shell {
    min-height: 100vh;
    padding: 18px;
}


/* =========================
   Top header card
========================= */
.topbar {
    background: rgba(7, 17, 40, 0.92);
    border: 1px solid rgba(108, 92, 231, 0.22);
    border-radius: 16px;
    padding: 16px 18px;
    margin-bottom: 16px;
    box-shadow: 0 12px 28px rgba(0, 0, 0, 0.34);
}

.pair-title {
    font-size: 30px;
    font-weight: 700;
    color: #f4f7ff;
    margin-bottom: 10px;
}

.quote-strip {
    font-family: Consolas, "Courier New", monospace;
    font-size: 14px;
    color: #9ce6d1;
    line-height: 1.5;
    word-break: break-word;
}


/* =========================
   Main tabs
========================= */
.main-tabs {
    margin: 12px 0 16px 0;
}

.main-tab {
    min-width: 120px;
    text-align: center;
    background: rgba(10, 28, 80, 0.78) !important;
    color: #eaf2ff !important;
    border: 1px solid rgba(119, 170, 255, 0.18) !important;
    padding: 12px 18px !important;
    border-radius: 12px 12px 0 0 !important;
    font-weight: 600 !important;
}

.main-tab:hover {
    background: rgba(30, 58, 138, 0.88) !important;
    color: #ffffff !important;
}

.main-tab-selected {
    background: rgba(24, 34, 78, 0.98) !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    border-top: 3px solid #38bdf8 !important;
    box-shadow: 0 8px 20px rgba(56, 189, 248, 0.16) !important;
}


/* =========================
   Tab containers
========================= */
.tab-panel {
    width: 100%;
}

.dashboard-tab-panel,
.watch-tab-panel,
.quotes-tab-panel,
.charts-tab-panel {
    background: linear-gradient(180deg, rgba(49, 19, 80, 0.22), rgba(9, 16, 46, 0.04));
    border-radius: 14px;
    padding-top: 4px;
}

.dashboard-tab-panel .status-text,
.watch-tab-panel .status-text,
.quotes-tab-panel .status-text,
.charts-tab-panel .status-text {
    color: #f7b1d9;
}

.dashboard-tab-panel .control-box,
.watch-tab-panel .control-box,
.quotes-tab-panel .control-box,
.charts-tab-panel .control-box {
    border: 1px solid rgba(236, 72, 153, 0.18);
    box-shadow: 0 10px 22px rgba(41, 10, 44, 0.28);
}

.dashboard-tab-panel .chart-card,
.watch-tab-panel .chart-card,
.quotes-tab-panel .chart-card,
.charts-tab-panel .chart-card {
    border: 1px solid rgba(236, 72, 153, 0.20);
    box-shadow: 0 14px 30px rgba(22, 7, 36, 0.30);
}


/* =========================
   Controls
========================= */
.controls-row {
    display: flex;
    gap: 14px;
    align-items: flex-end;
    flex-wrap: wrap;
    margin-bottom: 10px;
}

.control-box {
    background: rgba(11, 20, 48, 0.92);
    border: 1px solid rgba(108, 92, 231, 0.16);
    border-radius: 14px;
    padding: 12px 14px;
    box-shadow: 0 10px 22px rgba(0, 0, 0, 0.26);
}

.control-symbol {
    min-width: 420px;
}

.control-timeframe {
    min-width: 220px;
}

.control-box label {
    display: block;
    margin-bottom: 8px;
    font-size: 13px;
    color: #f4f7ff;
}


/* =========================
   Buttons
========================= */
button {
    min-width: 90px;
    height: 40px;
    border: none;
    border-radius: 10px;
    background: linear-gradient(90deg, #7c3aed, #ec4899);
    color: #f8f5ff;
    font-weight: 700;
    font-size: 14px;
    cursor: pointer;
    transition: transform 0.12s ease, filter 0.12s ease;
    box-shadow: 0 8px 16px rgba(30, 10, 40, 0.30);
}

button:hover {
    filter: brightness(1.08);
    transform: translateY(-1px);
}


/* =========================
   Status text
========================= */
.status-text {
    min-height: 20px;
    margin: 8px 0 14px 2px;
    color: #9fc3ff;
    font-size: 13px;
}


/* =========================
   Chart card - darker revert
========================= */
.chart-card {
    background: linear-gradient(180deg, rgba(9, 16, 30, 0.96), rgba(6, 12, 24, 0.96));
    border: 1px solid rgba(96, 165, 250, 0.12);
    border-radius: 18px;
    padding: 12px;
    box-shadow: 0 16px 34px rgba(0, 0, 0, 0.34);
}

.chart-graph {
    border-radius: 12px;
    overflow: hidden;
}

.js-plotly-plot {
    border-radius: 10px;
    overflow: hidden;
}


/* =========================
   Dropdown styling - dark background
========================= */
.black-dropdown {
    color: #f4f7ff !important;
}

.black-dropdown .Select,
.black-dropdown .select__control,
.black-dropdown [class*="control"] {
    background: rgba(8, 22, 70, 0.95) !important;
    color: #f4f7ff !important;
    border: 1px solid rgba(119, 170, 255, 0.28) !important;
    border-radius: 10px !important;
    box-shadow: none !important;
}

.black-dropdown .Select-value,
.black-dropdown .Select-value-label,
.black-dropdown .select__single-value,
.black-dropdown [class*="singleValue"],
.black-dropdown [class*="ValueContainer"] * {
    color: #f4f7ff !important;
}

.black-dropdown .Select-placeholder,
.black-dropdown .select__placeholder,
.black-dropdown [class*="placeholder"] {
    color: #cbd5e1 !important;
    opacity: 1 !important;
}

.black-dropdown .Select-input > input,
.black-dropdown .select__input-container,
.black-dropdown .select__input-container input,
.black-dropdown input {
    color: #f4f7ff !important;
    background: transparent !important;
}

.black-dropdown .Select-menu-outer,
.black-dropdown .Select-menu,
.black-dropdown .select__menu,
.black-dropdown .select__menu-list,
.black-dropdown [class*="menu"] {
    background: rgba(8, 22, 70, 0.98) !important;
    color: #f4f7ff !important;
    border: 1px solid rgba(119, 170, 255, 0.24) !important;
}

.black-dropdown .VirtualizedSelectOption,
.black-dropdown .VirtualizedSelectFocusedOption,
.black-dropdown .Select-option,
.black-dropdown .select__option,
.black-dropdown [class*="option"] {
    background: rgba(8, 22, 70, 0.98) !important;
    color: #f4f7ff !important;
}

.black-dropdown .VirtualizedSelectFocusedOption,
.black-dropdown .Select-option.is-focused,
.black-dropdown .select__option--is-focused,
.black-dropdown [class*="option"]:hover {
    background: rgba(30, 58, 138, 0.95) !important;
    color: #ffffff !important;
}

.black-dropdown .Select-option.is-selected,
.black-dropdown .select__option--is-selected {
    background: #4c1d95 !important;
    color: #ffffff !important;
}

.black-dropdown .Select-arrow,
.black-dropdown .select__indicator,
.black-dropdown .select__dropdown-indicator,
.black-dropdown [class*="indicator"] {
    color: #f4f7ff !important;
    border-top-color: #f4f7ff !important;
}

.black-dropdown .Select-clear-zone,
.black-dropdown .Select-clear,
.black-dropdown .select__clear-indicator {
    color: #f4f7ff !important;
}

.black-dropdown .select__indicator-separator {
    background-color: rgba(255, 255, 255, 0.18) !important;
}


/* =========================
   Slider styling
========================= */
.rc-slider-rail {
    background-color: rgba(255, 255, 255, 0.22) !important;
}

.rc-slider-track {
    background-color: #a855f7 !important;
}

.rc-slider-handle {
    border: 2px solid #f472b6 !important;
    background-color: #f472b6 !important;
    box-shadow: 0 0 0 4px rgba(244, 114, 182, 0.16) !important;
    opacity: 1 !important;
}

.rc-slider-handle:hover,
.rc-slider-handle:focus,
.rc-slider-handle:active {
    border-color: #f472b6 !important;
    background-color: #f472b6 !important;
    box-shadow: 0 0 0 6px rgba(244, 114, 182, 0.22) !important;
}

.rc-slider-dot {
    border-color: rgba(255, 255, 255, 0.35) !important;
    background-color: transparent !important;
}

.rc-slider-dot-active {
    border-color: #f472b6 !important;
}

.rc-slider-mark-text {
    color: #dbe6ff !important;
}


/* =========================
   Date picker dark styling
========================= */
.date-picker-dark .DateInput_input {
    background: #0f172a !important;
    color: #f4f7ff !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    border: 1px solid rgba(236, 72, 153, 0.24) !important;
}

.date-picker-dark .DateInput {
    background: transparent !important;
}

.date-picker-dark .SingleDatePickerInput {
    background: #0f172a !important;
    border-radius: 10px !important;
    overflow: hidden;
    border: 1px solid rgba(236, 72, 153, 0.22) !important;
}

.date-picker-dark .SingleDatePicker_picker {
    background: #0b1226 !important;
}

.DateRangePicker_picker,
.SingleDatePicker_picker,
.DayPicker,
.CalendarMonth,
.CalendarMonthGrid,
.DayPicker_transitionContainer {
    background: #0b1226 !important;
    color: #f4f7ff !important;
}

.CalendarDay {
    background: #0f172a !important;
    color: #f4f7ff !important;
    border: 1px solid rgba(255, 255, 255, 0.04) !important;
}

.CalendarDay:hover {
    background: #251a52 !important;
    color: #ffffff !important;
}

.CalendarDay__selected,
.CalendarDay__selected:hover {
    background: #4c1d95 !important;
    border: 1px solid #a855f7 !important;
    color: #ffffff !important;
}

.DayPickerNavigation_button {
    background: #0f172a !important;
    border: 1px solid rgba(236, 72, 153, 0.22) !important;
    color: #f4f7ff !important;
}


/* =========================
   Market-style metrics + range + stats
========================= */
.metrics-strip {
    display: flex;
    gap: 18px;
    flex-wrap: wrap;
    align-items: center;
    margin: 6px 0 12px 0;
    padding: 12px 14px;
    border-radius: 14px;
    background: rgba(8, 14, 30, 0.82);
    border: 1px solid rgba(255, 255, 255, 0.06);
}

.metric-price {
    font-size: 30px;
    font-weight: 800;
    color: #f8fbff;
}

.metric-positive {
    color: #22c55e;
    font-weight: 700;
    font-size: 24px;
}

.metric-negative {
    color: #ef4444;
    font-weight: 700;
    font-size: 24px;
}

.metric-muted {
    color: #94a3b8;
    font-size: 13px;
}

.range-row {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin: 0 0 12px 0;
}

.range-btn {
    min-width: auto;
    height: 34px;
    padding: 0 14px;
    background: rgba(22, 28, 45, 0.95);
    color: #dbe6ff;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    font-size: 13px;
    font-weight: 700;
    box-shadow: none;
}

.range-btn:hover {
    background: rgba(35, 42, 70, 0.98);
    color: #ffffff;
    transform: none;
}

.range-btn.active {
    background: rgba(80, 64, 130, 0.95);
    color: #ffffff;
    border-color: rgba(244, 114, 182, 0.40);
}

.stats-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(220px, 1fr));
    gap: 14px;
    margin-top: 16px;
}

.stat-card {
    background: linear-gradient(180deg, rgba(10, 18, 34, 0.96), rgba(7, 13, 26, 0.96));
    border: 1px solid rgba(96, 165, 250, 0.12);
    border-radius: 18px;
    padding: 16px 18px;
    box-shadow:
        0 10px 24px rgba(0, 0, 0, 0.28),
        inset 0 1px 0 rgba(255, 255, 255, 0.03);
}

.stat-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    padding: 9px 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.stat-row:last-child {
    border-bottom: none;
    padding-bottom: 0;
}

.stat-label {
    color: #94a3b8;
    font-size: 13px;
    font-weight: 500;
}

.stat-value {
    color: #f8fbff;
    font-weight: 700;
    font-size: 14px;
}

/* =========================
   Watch chart loading overlay
========================= */
.watch-chart-wrap {
    position: relative;
}

.watch-loading-overlay {
    position: absolute;
    inset: 12px;
    z-index: 20;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(5, 10, 25, 0.82);
    border-radius: 12px;
    backdrop-filter: blur(4px);
}

.watch-loading-overlay.hidden {
    display: none;
}

.watch-loading-text {
    color: #f4f7ff;
    font-size: 18px;
    font-weight: 700;
    padding: 14px 18px;
    border-radius: 12px;
    background: rgba(38, 18, 72, 0.90);
    border: 1px solid rgba(236, 72, 153, 0.28);
    box-shadow: 0 12px 28px rgba(0, 0, 0, 0.30);
}


/* =========================
   Responsive layout
========================= */
@media (max-width: 1100px) {
    .control-symbol {
        min-width: 300px;
    }

    .stats-grid {
        grid-template-columns: repeat(2, minmax(180px, 1fr));
    }
}

@media (max-width: 820px) {
    .pair-title {
        font-size: 24px;
    }

    .control-symbol,
    .control-timeframe {
        min-width: 100%;
    }

    .stats-grid {
        grid-template-columns: 1fr;
    }

    .app-shell {
        padding: 12px;
    }
}
```

## `config.py`

```python
DEFAULT_SYMBOL = "MSFT"
DEFAULT_TIMEFRAME = "1 min"
APP_TITLE = "Stock Visualizer"
UI_INTERVAL_MS = 250
DEFAULT_REPLAY_SPEED = 1
DEFAULT_REPLAY_INDEX = 100

```
