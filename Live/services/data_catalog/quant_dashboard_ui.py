from __future__ import annotations

from dash import dcc, html


def build_quant_dashboard_panel():
    return html.Div(
        className="data-library-card quant-dashboard-card",
        children=[
            html.Div(
                className="data-library-card-header",
                children=[
                    html.H3("Quant Research Dashboard", className="data-library-card-title"),
                    html.Div("Read-only typed research results", className="data-library-card-subtitle"),
                ],
            ),
            html.P(
                "Shows rows from the typed Quant Research Schema. Research/simulation only; no broker calls or live orders.",
                className="data-library-muted",
            ),
            html.Div(
                className="quant-dashboard-controls",
                children=[
                    html.Label("Backend", className="data-library-label"),
                    dcc.Dropdown(
                        id="quant-dashboard-backend",
                        options=[
                            {"label": "SQLite fallback", "value": "sqlite"},
                            {"label": "PostgreSQL", "value": "postgres"},
                        ],
                        value="sqlite",
                        clearable=False,
                        className="quant-dashboard-dropdown",
                    ),
                    html.Label("Rows per section", className="data-library-label"),
                    dcc.Input(
                        id="quant-dashboard-limit",
                        type="number",
                        value=10,
                        min=1,
                        max=100,
                        step=1,
                        debounce=True,
                        className="quant-dashboard-limit",
                    ),
                    html.Button(
                        "Refresh Quant Dashboard",
                        id="quant-dashboard-refresh",
                        n_clicks=0,
                        className="data-library-button quant-dashboard-refresh",
                    ),
                ],
            ),
            html.Div(id="quant-dashboard-status", className="quant-dashboard-status"),
            html.Div(id="quant-dashboard-counts", className="quant-dashboard-counts"),
            html.Div(
                className="quant-dashboard-grid",
                children=[
                    html.Div(id="quant-dashboard-experiments", className="quant-dashboard-section"),
                    html.Div(id="quant-dashboard-strategies", className="quant-dashboard-section"),
                    html.Div(id="quant-dashboard-backtests", className="quant-dashboard-section"),
                    html.Div(id="quant-dashboard-walk-forward", className="quant-dashboard-section"),
                    html.Div(id="quant-dashboard-universe", className="quant-dashboard-section"),
                    html.Div(id="quant-dashboard-data-quality", className="quant-dashboard-section"),
                ],
            ),
        ],
    )
