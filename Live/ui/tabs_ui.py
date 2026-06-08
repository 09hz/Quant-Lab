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
                className="controls-row controls-row-top",
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
    className="controls-row controls-row-bottom",
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