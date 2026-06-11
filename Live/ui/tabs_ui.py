from datetime import date

from dash import dcc, html


CHART_CONFIG = {
    "displaylogo": False,
    "scrollZoom": False,
    "doubleClick": "reset",
    "modeBarButtonsToRemove": [
        "lasso2d",
        "select2d",
        "autoScale2d",
    ],
}


def make_timeframe_options(timeframe_map):
    return [
        {
            "label": k,
            "value": k,
            "search": k,
        }
        for k in timeframe_map.keys()
    ]


def make_replay_speed_options():
    return [
        {"label": "0.25x", "value": 0.25, "search": "0.25x quarter slow"},
        {"label": "0.5x", "value": 0.5, "search": "0.5x half slow"},
        {"label": "1x", "value": 1, "search": "1x normal default"},
        {"label": "2x", "value": 2, "search": "2x double fast"},
        {"label": "5x", "value": 5, "search": "5x very fast"},
    ]


def make_chart_control_buttons(prefix: str):
    return [
        html.Button("Live", id=f"{prefix}-live-mode", n_clicks=0, className="range-btn active"),
        html.Button("1D", id=f"{prefix}-range-1d", n_clicks=0, className="range-btn"),
        html.Button("1W", id=f"{prefix}-range-1w", n_clicks=0, className="range-btn"),
        html.Button("1M", id=f"{prefix}-range-1m", n_clicks=0, className="range-btn"),
        html.Button("3M", id=f"{prefix}-range-3m", n_clicks=0, className="range-btn"),
        html.Button("1Y", id=f"{prefix}-range-1y", n_clicks=0, className="range-btn"),
        html.Button("5Y", id=f"{prefix}-range-5y", n_clicks=0, className="range-btn"),
        html.Button("Max", id=f"{prefix}-range-max", n_clicks=0, className="range-btn"),
        html.Button("Reset", id=f"{prefix}-reset-view", n_clicks=0, className="range-btn"),
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
                            html.Label("Instrument"),
                            dcc.Dropdown(
                                id="symbol-dropdown",
                                options=symbol_options,
                                value=default_symbol,
                                placeholder="Search ticker, symbol, or company...",
                                searchable=True,
                                clearable=False,
                                className="black-dropdown",
                            ),
                        ],
                    ),
                    html.Div(
                        className="control-box control-timeframe",
                        children=[
                            html.Label("Interval"),
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
                className="range-row chart-control-row",
                children=make_chart_control_buttons("dashboard"),
            ),
            html.Div(
                className="chart-card",
                children=[
                    dcc.Graph(
                        id="live-chart",
                        className="chart-graph",
                        config=CHART_CONFIG,
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
                className="controls-row controls-row-top",
                children=[
                    html.Div(
                        className="control-box control-symbol",
                        children=[
                            html.Label("Replay Symbol"),
                            dcc.Dropdown(
                                id="watch-symbol-dropdown",
                                options=symbol_options,
                                value=default_symbol,
                                placeholder="Search ticker, symbol, or company...",
                                searchable=True,
                                clearable=False,
                                className="black-dropdown",
                            ),
                        ],
                    ),
                    html.Div(
                        className="control-box control-timeframe control-speed",
                        children=[
                            html.Label("Speed"),
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
                            html.Label("Start Date"),
                            dcc.DatePickerSingle(
                                id="replay-date",
                                date=default_date,
                                display_format="MM/DD/YYYY",
                                max_date_allowed=date.today(),
                                className="date-picker-dark",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="controls-row controls-row-bottom",
                children=[
                    html.Div(
                        className="control-box",
                        children=[
                            html.Label("Playback"),
                            html.Div(
                                [
                                    html.Button("▶ Play", id="replay-play", n_clicks=0),
                                    html.Button("⏸ Pause", id="replay-pause", n_clicks=0),
                                    html.Button("→ Step", id="replay-step", n_clicks=0),
                                    html.Button("← Rewind", id="replay-rewind", n_clicks=0),
                                ],
                                style={"display": "flex", "gap": "8px", "flexWrap": "wrap"},
                            ),
                        ],
                    ),
                    html.Div(
                        className="control-box control-symbol",
                        children=[
                            html.Label("Position"),
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
                className="range-row chart-control-row",
                children=make_chart_control_buttons("watch"),
            ),
            html.Div(
                className="chart-card watch-chart-wrap",
                children=[
                    html.Div(
                        id="watch-loading-overlay",
                        className="watch-loading-overlay",
                        children=[
                            html.Div("Preparing replay data...", className="watch-loading-text"),
                        ],
                    ),
                    dcc.Graph(
                        id="watch-chart",
                        className="chart-graph",
                        config=CHART_CONFIG,
                    ),
                ],
            ),
            html.Div(id="watch-stats-grid", className="stats-grid"),
            html.Div(
                className="paper-trading-panel",
                children=[
                    html.Div(
                        className="paper-panel-header",
                        children=[
                            html.Div("Paper Trading", className="paper-panel-title"),
                            html.Div(
                                "Simulated only · No IBKR live orders",
                                className="paper-panel-subtitle",
                            ),
                        ],
                    ),
                    html.Button(
                        "Trade Analytics",
                        id="trade-analytics-open",
                        n_clicks=0,
                        className="analytics-open-button",
                    ),
                    html.Div(
                        className="paper-controls-row",
                        children=[
                            html.Div(
                                className="control-box control-timeframe",
                                children=[
                                    html.Label("Price Source"),
                                    dcc.Dropdown(
                                        id="paper-price-source",
                                        options=[
                                            {"label": "Replay Cursor", "value": "replay", "search": "replay historical cursor"},
                                            {"label": "Live Market", "value": "live", "search": "live realtime market"},
                                        ],
                                        value="replay",
                                        clearable=False,
                                        searchable=False,
                                        className="black-dropdown",
                                    ),
                                ],
                            ),
                            html.Div(
                                className="control-box control-timeframe",
                                children=[
                                    html.Label("Position Mode"),
                                    dcc.Dropdown(
                                        id="paper-position-mode",
                                        options=[
                                            {"label": "Long Only", "value": "long_only", "search": "long only no shorts"},
                                            {"label": "Allow Shorts", "value": "allow_shorts", "search": "short selling bearish"},
                                        ],
                                        value="long_only",
                                        clearable=False,
                                        searchable=False,
                                        className="black-dropdown",
                                    ),
                                ],
                            ),
                            html.Div(
                                className="control-box control-qty",
                                children=[
                                    html.Label("Quantity"),
                                    dcc.Input(
                                        id="paper-order-qty",
                                        type="number",
                                        min=1,
                                        step=1,
                                        value=1,
                                        className="paper-input",
                                        debounce=True,
                                    ),
                                ],
                            ),
                            html.Div(
                                className="paper-button-group",
                                children=[
                                    html.Button("Buy", id="paper-buy", n_clicks=0, className="paper-buy-btn"),
                                    html.Button("Sell", id="paper-sell", n_clicks=0, className="paper-sell-btn"),
                                    html.Button("Reset Paper", id="paper-reset", n_clicks=0, className="paper-reset-btn"),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        id="paper-trade-status",
                        className="paper-trade-status",
                        children="Paper account ready.",
                    ),
                    html.Div(
                        className="paper-summary-grid",
                        children=[
                            html.Div(id="paper-summary-panel", className="paper-summary-panel"),
                        ],
                    ),
                    html.Div(
                        className="paper-table-grid",
                        children=[
                            html.Div(
                                className="paper-table-card",
                                children=[
                                    html.Div("Positions", className="paper-table-title"),
                                    html.Div(id="paper-positions-panel"),
                                ],
                            ),
                            html.Div(
                                className="paper-table-card",
                                children=[
                                    html.Div("Orders", className="paper-table-title"),
                                    html.Div(id="paper-orders-panel"),
                                ],
                            ),
                            html.Div(
                                className="paper-table-card",
                                children=[
                                    html.Div("Fills", className="paper-table-title"),
                                    html.Div(id="paper-fills-panel"),
                                ],
                            ),
                        ],
                    ),html.Div(
    id="trade-analytics-drawer",
    className="trade-analytics-drawer hidden",
    children=[
        html.Div(
            className="trade-analytics-header",
            children=[
                html.Div("Trade Analytics", className="trade-analytics-title"),
                html.Button("×", id="trade-analytics-close", n_clicks=0, className="trade-analytics-close"),
            ],
        ),
        html.Div(
            id="trade-analytics-content",
            className="trade-analytics-content",
            children=[
                html.Div("No analytics loaded yet.", className="paper-empty")
            ],
        ),
    ],
)
                ],
            ),
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
                            html.Label("Instrument"),
                            dcc.Dropdown(
                                id="quotes-symbol-dropdown",
                                options=symbol_options,
                                value=default_symbol,
                                placeholder="Search ticker, symbol, or company...",
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
                        children="Ready for quotes",
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
                            html.Label("Instrument"),
                            dcc.Dropdown(
                                id="charts-symbol-dropdown",
                                options=symbol_options,
                                value=default_symbol,
                                placeholder="Search ticker, symbol, or company...",
                                searchable=True,
                                clearable=False,
                                className="black-dropdown",
                            ),
                        ],
                    ),
                    html.Div(
                        className="control-box control-timeframe",
                        children=[
                            html.Label("Interval"),
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
                        config=CHART_CONFIG,
                    ),
                ],
            ),
        ],
    )
