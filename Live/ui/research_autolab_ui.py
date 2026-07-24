from __future__ import annotations

from dash import dcc, html


DEFAULT_SERIES_IDS = (
    "CPIAUCSL,CPILFESL,PCEPI,PCEPILFE,DGS2,DGS10,FEDFUNDS,T10Y2Y,"
    "VIXCLS,SP500,NASDAQCOM,PAYEMS,UNRATE,UMCSENT,IPMAN,INDPRO,"
    "DGORDER,AMTMNO,DCOILWTICO"
)


def build_research_autolab_panel(*args, **kwargs):
    return html.Div(
        className="research-autolab-page",
        children=[
            html.Div(
                className="research-autolab-hero",
                children=[
                    html.Div("Research Autolab", className="labelColor"),
                    html.Div(
                        "Simulation-only macro hypothesis testing from approved research evidence. "
                        "No broker access. No order placement.",
                        className="research-autolab-subtitle",
                    ),
                ],
            ),
            html.Div(
                className="research-autolab-controls",
                children=[
                    html.Div(
                        className="control-box",
                        children=[
                            html.Label("Bars directory"),
                            dcc.Input(
                                id="autolab-bars-dir",
                                value="data/autolab_bars",
                                type="text",
                                debounce=True,
                                className="research-autolab-input",
                            ),
                        ],
                    ),
                    html.Div(
                        className="control-box",
                        children=[
                            html.Label("Macro directory"),
                            dcc.Input(
                                id="autolab-macro-dir",
                                value="data/autolab_macro",
                                type="text",
                                debounce=True,
                                className="research-autolab-input",
                            ),
                        ],
                    ),
                    html.Div(
                        className="control-box",
                        children=[
                            html.Label("Symbols"),
                            dcc.Input(
                                id="autolab-symbols",
                                value="SPY,QQQ,XLK,SMH,XLI,IWM",
                                type="text",
                                debounce=True,
                                className="research-autolab-input",
                            ),
                        ],
                    ),
                    html.Div(
                        className="control-box research-autolab-series-box",
                        children=[
                            html.Label("FRED series IDs"),
                            dcc.Textarea(
                                id="autolab-series-ids",
                                value=DEFAULT_SERIES_IDS,
                                className="research-autolab-textarea",
                            ),
                        ],
                    ),
                    html.Div(
                        className="research-autolab-button-row",
                        children=[
                            html.Button(
                                "Refresh FRED macro CSVs",
                                id="autolab-refresh-macro",
                                n_clicks=0,
                                className="newsroom-btn",
                                title="Download/update local FRED CSVs into the macro directory.",
                            ),
                            html.Button(
                                "Run baseline vs macro overlay",
                                id="autolab-run-comparison",
                                n_clicks=0,
                                className="newsroom-btn primary",
                            ),
                            html.Button(
                                "Clear",
                                id="autolab-clear",
                                n_clicks=0,
                                className="newsroom-btn danger",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                id="autolab-safety-status",
                className="research-autolab-safety",
                children="Simulation-only. Results are research artifacts, not trade instructions.",
            ),
            dcc.Loading(
                type="default",
                children=[
                    html.Div(id="autolab-status", className="research-autolab-status"),
                    html.Div(id="autolab-artifacts", className="research-autolab-artifacts"),
                    html.Div(id="autolab-top-table", className="research-autolab-table-wrap"),
                    dcc.Markdown(id="autolab-summary", className="research-autolab-summary"),
                ],
            ),
            dcc.Store(id="autolab-last-results", storage_type="session"),
        ],
    )


def build_research_autolab_tab(*args, **kwargs):
    return build_research_autolab_panel(*args, **kwargs)
