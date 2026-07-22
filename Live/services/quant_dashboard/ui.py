from __future__ import annotations

from dash import html

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

    return html.Div(
        className="quant-native-page",
        children=[
            header,
            _original_build_panel(),
            modules,
        ],
    )
