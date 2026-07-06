from __future__ import annotations

from dash import dcc, html


def _date_input(component_id: str, label: str, value: str):
    return html.Div(
        [
            html.Label(label, className="autolab-label"),
            dcc.Input(id=component_id, value=value, className="autolab-input", debounce=True),
        ]
    )


def _number_input(component_id: str, label: str, value, min_value=None, max_value=None, step=1):
    return html.Div(
        [
            html.Label(label, className="autolab-label"),
            dcc.Input(
                id=component_id,
                type="number",
                value=value,
                min=min_value,
                max=max_value,
                step=step,
                debounce=False,
                className="autolab-input",
            ),
        ]
    )


def build_auto_lab_tab() -> html.Div:
    """Build the main-app AI Auto Lab tab.

    Research/simulation only. This layout does not create broker/order controls.
    """
    return html.Div(
        className="autolab-shell",
        children=[
            html.Div(
                className="autolab-header",
                children=[
                    html.Div(
                        [
                            html.H2("AI Auto Lab", className="autolab-title"),
                            html.P(
                                "Multi-symbol research, AI symbol discovery, walk-forward validation, overfit warnings, capital assumptions, and strategy scripts.",
                                className="autolab-subtitle",
                            ),
                        ]
                    ),
                    html.Div("Research / simulation only", className="autolab-pill autolab-pill-warning"),
                ],
            ),
            html.Div(
                className="autolab-safety-banner",
                children=[
                    html.Strong("Safety: "),
                    "No live orders, no broker connection, no PaperBroker calls, no account credentials, and no financial advice. "
                    "Capital values and symbol suggestions are simulation/research assumptions only.",
                ],
            ),
            html.Div(
                className="autolab-grid autolab-grid-controls",
                children=[
                    html.Div(
                        className="autolab-card",
                        children=[
                            html.H3("Universe settings"),
                            html.Label("Symbols", className="autolab-label"),
                            dcc.Input(
                                id="main-autolab-symbols",
                                value="AMD,NVDA,MSFT,AAPL,TSLA",
                                className="autolab-input",
                                debounce=True,
                            ),
                            html.Div(
                                "Comma-separated symbols. AI Symbol Discovery can replace/expand this list before you run tests.",
                                className="autolab-help",
                            ),
                            html.Div(
                                className="autolab-two-col",
                                children=[
                                    _date_input("main-autolab-universe-start", "Universe start", "2020-01-01"),
                                    _date_input("main-autolab-universe-end", "Universe end", "2025-12-31"),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="autolab-card",
                        children=[
                            html.H3("AI Symbol Discovery"),
                            html.Label("Theme / focus", className="autolab-label"),
                            dcc.Input(
                                id="main-autolab-discovery-theme",
                                value="semiconductors, AI infrastructure, liquid large caps",
                                className="autolab-input",
                                debounce=True,
                            ),
                            html.Div(
                                className="autolab-two-col",
                                children=[
                                    _number_input("main-autolab-discovery-max-symbols", "Max symbols", 10, 1, 30, 1),
                                    html.Div(
                                        [
                                            html.Label("Action", className="autolab-label"),
                                            html.Button(
                                                "Suggest Symbols",
                                                id="main-autolab-suggest-symbols",
                                                n_clicks=0,
                                                className="autolab-button autolab-button-secondary autolab-full-width",
                                            ),
                                        ]
                                    ),
                                ],
                            ),
                            html.Div(
                                "Suggests symbols to test; it does not recommend trades.",
                                className="autolab-help",
                            ),
                        ],
                    ),
                    html.Div(
                        className="autolab-card",
                        children=[
                            html.H3("Walk-forward settings"),
                            html.Div(
                                className="autolab-two-col",
                                children=[
                                    _date_input("main-autolab-train-start", "Train start", "2020-01-01"),
                                    _date_input("main-autolab-train-end", "Train end", "2023-12-31"),
                                    _date_input("main-autolab-test-start", "Test start", "2024-01-01"),
                                    _date_input("main-autolab-test-end", "Test end", "2025-12-31"),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="autolab-card",
                        children=[
                            html.H3("Capital assumptions"),
                            html.Div(
                                className="autolab-two-col",
                                children=[
                                    _number_input("main-autolab-initial-cash", "Starting cash", 12000, 1, None, 100),
                                    _number_input("main-autolab-target-cash", "Target cash", 24000, 1, None, 100),
                                ],
                            ),
                            html.Div(
                                className="autolab-two-col",
                                children=[
                                    _number_input("main-autolab-cash-exposure", "Cash exposure %", 95, 1, 100, 1),
                                    _number_input("main-autolab-top-n", "Top N validation", 3, 1, 20, 1),
                                ],
                            ),
                            html.Label("Sizing mode", className="autolab-label"),
                            dcc.Dropdown(
                                id="main-autolab-sizing-mode",
                                options=[
                                    {"label": "Percent cash exposure", "value": "percent_cash_exposure"},
                                    {"label": "Fixed quantity", "value": "fixed_quantity"},
                                    {"label": "Max affordable shares", "value": "max_affordable_shares"},
                                ],
                                value="percent_cash_exposure",
                                clearable=False,
                                className="autolab-dropdown",
                            ),
                            html.Div(
                                "Starting/target cash are simulated research assumptions, not real account values.",
                                className="autolab-help",
                            ),
                        ],
                    ),
                    html.Div(
                        className="autolab-card",
                        children=[
                            html.H3("Run limits"),
                            html.Div(
                                className="autolab-two-col",
                                children=[
                                    _number_input("main-autolab-max-runs", "Max runs / symbol", 20, 1, 200, 1),
                                    _number_input("main-autolab-max-mutations", "Max mutations", 4, 1, 50, 1),
                                ],
                            ),
                            html.Div(
                                "Keep these low for fast UI tests. Increase only when you want deeper research runs.",
                                className="autolab-help",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="autolab-action-row",
                children=[
                    html.Button(
                        "Run Universe Auto Lab",
                        id="main-autolab-run-universe",
                        n_clicks=0,
                        className="autolab-button autolab-button-primary",
                    ),
                    html.Button(
                        "Run Walk-Forward Validation",
                        id="main-autolab-run-walk-forward",
                        n_clicks=0,
                        className="autolab-button autolab-button-primary",
                    ),
                    html.Button(
                        "Refresh Latest Reports",
                        id="main-autolab-refresh",
                        n_clicks=0,
                        className="autolab-button",
                    ),
                ],
            ),
            html.Div(
                className="autolab-card autolab-capital-card",
                children=[
                    html.H3("Current capital assumptions"),
                    html.Div(
                        id="main-autolab-capital-summary",
                        className="autolab-capital-summary-html",
                        children=[
                            html.H4("Simulated capital assumptions"),
                            html.Ul(
                                [
                                    html.Li("Starting cash: $12,000.00"),
                                    html.Li("Target cash: $24,000.00"),
                                    html.Li("Target return needed: 100.00%"),
                                    html.Li("Cash exposure: 95.00%"),
                                    html.Li("Sizing mode: percent_cash_exposure"),
                                ]
                            ),
                            html.Strong("Research/simulation only. These are not real account balances."),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="autolab-card",
                children=[
                    html.H3("AI Symbol Discovery Report"),
                    dcc.Markdown(
                        id="main-autolab-discovery-report",
                        children="No symbol discovery run yet. Enter seed symbols/theme and click **Suggest Symbols**.",
                        className="autolab-markdown autolab-markdown-small",
                    ),
                    html.Pre(
                        id="main-autolab-discovery-paths",
                        children="No symbol discovery paths yet.",
                        className="autolab-path-box autolab-path-box-secondary",
                    ),
                ],
            ),
            html.Div(
                className="autolab-card",
                children=[
                    html.H3("Command output"),
                    dcc.Textarea(
                        id="main-autolab-command-output",
                        value="Ready. Refresh reports or start a research run.",
                        className="autolab-output",
                    ),
                ],
            ),
            html.Div(
                className="autolab-report-grid",
                children=[
                    html.Div(
                        className="autolab-card autolab-report-card",
                        children=[
                            html.H3("Latest Universe Report"),
                            dcc.Markdown(
                                id="main-autolab-universe-report",
                                children="No universe report loaded yet.",
                                className="autolab-markdown",
                            ),
                        ],
                    ),
                    html.Div(
                        className="autolab-card autolab-report-card",
                        children=[
                            html.H3("Latest Walk-Forward Report"),
                            dcc.Markdown(
                                id="main-autolab-walk-forward-report",
                                children="No walk-forward report loaded yet.",
                                className="autolab-markdown",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="autolab-report-grid",
                children=[
                    html.Div(
                        className="autolab-card autolab-report-card",
                        children=[
                            html.H3("Universe Strategy Script / Algorithm"),
                            dcc.Markdown(
                                id="main-autolab-universe-script",
                                children="No universe strategy script loaded yet.",
                                className="autolab-markdown autolab-script-markdown",
                            ),
                        ],
                    ),
                    html.Div(
                        className="autolab-card autolab-report-card",
                        children=[
                            html.H3("Walk-Forward Strategy Script / Algorithm"),
                            dcc.Markdown(
                                id="main-autolab-walk-forward-script",
                                children="No walk-forward strategy script loaded yet.",
                                className="autolab-markdown autolab-script-markdown",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="autolab-card",
                children=[
                    html.H3("Report and script paths"),
                    html.Pre(
                        id="main-autolab-report-paths",
                        children="No report paths loaded yet.",
                        className="autolab-path-box",
                    ),
                    html.Pre(
                        id="main-autolab-script-paths",
                        children="No script paths loaded yet.",
                        className="autolab-path-box autolab-path-box-secondary",
                    ),
                ],
            ),
        ],
    )
