from __future__ import annotations

from dash import html, dcc

try:
    # Reuse existing, proven UI builder
    from services.data_catalog.quant_dashboard_ui import (
        build_quant_dashboard_panel as _original_build_panel,
    )
except Exception as exc:  # pragma: no cover
    _original_build_panel = None  # type: ignore
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


_MODULE_TITLES = [
    "Market Overview",
    "Screening Results",
    "Factor Analysis",
    "Momentum",
    "Value",
    "Growth",
    "Quality",
    "Volatility",
    "Liquidity",
    "Risk",
    "Correlation",
    "Sector Analysis",
    "Market Breadth",
    "Data Quality",
    "Research Notes",
]


def _placeholder_card(title: str):
    return html.Div(
        className="quant-native-card quant-native-table-card",
        children=[
            html.H4(title),
            html.Div("Placeholder — wired when module queries are available.", className="quant-native-muted"),
        ],
    )


def build_quant_dashboard_layout():
    """Canonical Quant Dashboard layout.

    Wraps the reused Quant Dashboard panel in a quant-native page container
    and appends placeholder research modules. No new CSS; uses existing
    quant-native-* classes.
    """
    if _original_build_panel is None:
        raise RuntimeError(f"Quant Dashboard UI unavailable: {_IMPORT_ERROR}")

    header = html.Div(
        className="quant-native-header",
        children=[
            html.Div(children=[html.H2("Quant Dashboard"), html.Div("Quantitative Research Workspace", className="quant-native-muted")]),
            html.Div("Research-only", className="quant-native-safety-pill"),
        ],
    )

    modules = html.Div(
        className="quant-native-controls",
        children=[_placeholder_card(title) for title in _MODULE_TITLES],
    )

    controls = html.Div(
        className="quant-native-controls",
        children=[
            html.Div([
                html.Label("Dataset"),
                dcc.Dropdown(id="quant-dataset", options=[], value=None, placeholder="Select dataset...", disabled=True),
            ]),
            html.Div([
                html.Label("Universe"),
                dcc.Dropdown(id="quant-universe", options=[], value=None, placeholder="Select universe...", disabled=True),
            ]),
            html.Div([
                html.Label("Market"),
                dcc.Dropdown(id="quant-market", options=[], value=None, placeholder="Select market...", disabled=True),
            ]),
            html.Div([
                html.Label("Date Range"),
                dcc.DatePickerRange(id="quant-date-range", disabled=True),
            ]),
            html.Button("Reset", id="quant-dashboard-reset", n_clicks=0, className="data-library-button"),
            html.Button("Export", id="quant-dashboard-export", n_clicks=0, className="data-library-button"),
            dcc.Download(id="quant-dashboard-download"),
        ],
    )

    results_controls = html.Div(
        className="quant-native-controls",
        children=[
            html.Div([
                html.Label("Results Section"),
                dcc.Dropdown(
                    id="quant-results-section",
                    options=[
                        {"label": "Recent Experiments", "value": "recent_experiments"},
                        {"label": "Recent Strategies", "value": "recent_strategies"},
                        {"label": "Best Backtests", "value": "best_backtests"},
                        {"label": "Walk-Forward Runs", "value": "walk_forward_runs"},
                        {"label": "Universe Runs", "value": "universe_runs"},
                        {"label": "Data Quality Events", "value": "data_quality_events"},
                    ],
                    value="recent_experiments",
                    clearable=False,
                ),
            ]),
            html.Div([
                html.Label("Sort By"),
                dcc.Dropdown(id="quant-results-sort", options=[], value=None, clearable=False),
            ]),
            html.Div([
                html.Label("Direction"),
                dcc.Dropdown(
                    id="quant-results-direction",
                    options=[{"label": "Descending", "value": "desc"}, {"label": "Ascending", "value": "asc"}],
                    value="desc",
                    clearable=False,
                ),
            ]),
        ],
    )

    results_table = html.Div(id="quant-dashboard-results-table", className="quant-dashboard-table-card")

    return html.Div(
        className="quant-native-page",
        children=[
            header,
            controls,
            _original_build_panel(),
            html.Div(id="quant-dashboard-status-panel", className="quant-native-card"),
            results_controls,
            results_table,
            modules,
        ],
    )
