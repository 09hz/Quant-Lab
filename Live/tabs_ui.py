from dash import dcc, html


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
                                options=[{"label": k, "value": k} for k in timeframe_map.keys()],
                                value=default_timeframe,
                                clearable=False,
                                className="black-dropdown",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(id="load-status-text", className="status-text"),
            html.Div(
                className="chart-card",
                children=[
                    dcc.Graph(
                        id="live-chart",
                        className="chart-graph",
                        config={
                            "displaylogo": False,
                            "modeBarButtonsToRemove": [
                                "lasso2d",
                                "select2d",
                                "autoScale2d",
                            ],
                        },
                    ),
                ],
            ),
        ],
    )

def build_watch_tab(symbol_options, default_symbol, default_speed=1, default_index=100):
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
                                searchable=True,
                                clearable=False,
                                className="black-dropdown",
                                placeholder="Search ticker or company...",
                            ),
                        ],
                    ),
                    html.Div(
                        className="control-box control-timeframe",
                        children=[
                            html.Label("Replay Speed"),
                            dcc.Dropdown(
                                id="replay-speed",
                                options=[
                                    {"label": "0.25x", "value": 0.25},
                                    {"label": "0.5x", "value": 0.5},
                                    {"label": "1x", "value": 1},
                                    {"label": "2x", "value": 2},
                                    {"label": "5x", "value": 5},
                                ],
                                value=default_speed,
                                clearable=False,
                                className="black-dropdown",
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
                                style={"display": "flex", "gap": "8px"},
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
            html.Div(
                className="chart-card",
                children=[
                    dcc.Graph(id="watch-chart", className="chart-graph"),
                ],
            ),
        ],
    )

def build_quotes_tab(symbol_options, default_symbol):
    return html.Div(
        className="tab-panel dashboard-tab-panel",
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
        className="tab-panel dashboard-tab-panel",
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
                                options=[{"label": k, "value": k} for k in timeframe_map.keys()],
                                value=default_timeframe,
                                clearable=False,
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
                        config={"displaylogo": False},
                    ),
                ],
            ),
        ],
    )