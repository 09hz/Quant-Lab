from __future__ import annotations

import sys
import asyncio

from dash import Dash, dcc, html

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from callbacks import register_callbacks
from config import (
    APP_TITLE,
    DEFAULT_REPLAY_INDEX,
    DEFAULT_REPLAY_SPEED,
    DEFAULT_SYMBOL,
    DEFAULT_TIMEFRAME,
    UI_INTERVAL_MS,
)
from core.RealTime import RealTimeIB, TIMEFRAME_MAP
from core.ReplayModule import ReplayEngine
from services.replay_service import ReplayService
from ui.tabs_ui import (
    build_dashboard_tab,
    build_watch_tab,
    build_quotes_tab,
    build_charts_tab,
)


rt = RealTimeIB(host="127.0.0.1", port=4001)
rt.start(DEFAULT_SYMBOL, DEFAULT_TIMEFRAME)

replay_engine = ReplayEngine()
replay_service = ReplayService(rt, replay_engine)

SYMBOL_OPTIONS = rt.get_symbol_options()

app = Dash(__name__, suppress_callback_exceptions=True)
app.title = APP_TITLE

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
                            default_symbol=DEFAULT_SYMBOL,
                            default_speed=DEFAULT_REPLAY_SPEED,
                            default_index=DEFAULT_REPLAY_INDEX,
                            default_date=None,
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

        # Keep this interval always enabled. Individual callbacks decide whether
        # they should update for the active tab.
        dcc.Interval(id="ui-interval", interval=UI_INTERVAL_MS, n_intervals=0),

        # Legacy/loading state store. Kept so older references do not break.
        dcc.Store(id="watch-loading-state", data=False),

        # New two-step replay load request store:
        # 1) clientside callback shows overlay and writes this request
        # 2) server callback loads replay data and hides overlay
        dcc.Store(
            id="watch-load-request",
            data={
                "nonce": 0,
                "symbol": DEFAULT_SYMBOL,
                "replay_date": None,
                "timeframe": "1 min",
            },
        ),

        dcc.Store(
            id="dashboard-chart-state",
            data={
                "mode": "live",
                "range_key": "1D",
                "x_range": None,
                "y_range": None,
            },
        ),
        dcc.Store(
            id="watch-chart-state",
            data={
                "mode": "live",
                "range_key": "1D",
                "x_range": None,
                "y_range": None,
            },
        ),

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
                "symbol": DEFAULT_SYMBOL,
                "replay_speed": DEFAULT_REPLAY_SPEED,
                "replay_index": DEFAULT_REPLAY_INDEX,
                "replay_date": None,
            },
        ),
    ],
)

register_callbacks(app, rt, replay_service, SYMBOL_OPTIONS, TIMEFRAME_MAP)

if __name__ == "__main__":
    app.run(debug=False)
