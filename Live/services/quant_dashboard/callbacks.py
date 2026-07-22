from __future__ import annotations

from time import perf_counter
from typing import Any

from dash import Input, Output, html

try:
    # Reuse existing callback registration
    from services.data_catalog.quant_dashboard_callbacks import (
        register_quant_dashboard_callbacks as _original_register,
    )
except Exception as exc:  # pragma: no cover
    _original_register = None  # type: ignore
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

try:
    from .queries import load_quant_dashboard
except Exception:  # pragma: no cover
    load_quant_dashboard = None  # type: ignore


def _status_panel_view(payload: Any, elapsed_ms: int) -> Any:
    rows_loaded = sum(len(v or []) for v in (getattr(payload, "sections", {}) or {}).values())
    warnings_n = len(getattr(payload, "errors", []) or [])
    items = [
        ("Backend", getattr(payload, "backend", "")),
        ("Status", getattr(payload, "status", "")),
        ("Rows Loaded", str(rows_loaded)),
        ("Execution Time", f"{elapsed_ms} ms"),
        ("Cache Status", "N/A"),
        ("Warnings", str(warnings_n)),
    ]
    rows = [html.Tr([html.Th(k), html.Td(v)]) for k, v in items]
    return html.Div(
        className="quant-native-card",
        children=[html.H4("Status Panel"), html.Table(html.Tbody(rows), className="quant-native-table")],
    )


def register_quant_dashboard_callbacks(app):
    """Canonical callback registration for the Quant Dashboard.

    Delegates to the existing implementation and adds a lightweight
    status panel renderer without duplicating SQL or business logic.
    """
    if _original_register is None:
        raise RuntimeError(f"Quant Dashboard callbacks unavailable: {_IMPORT_ERROR}")

    _original_register(app)

    if load_quant_dashboard is None:
        return

    @app.callback(
        Output("quant-dashboard-status-panel", "children"),
        Input("quant-dashboard-refresh", "n_clicks"),
        Input("quant-dashboard-backend", "value"),
        Input("quant-dashboard-limit", "value"),
        prevent_initial_call=False,
    )
    def _render_status_panel(_n, backend, limit):
        start = perf_counter()
        payload = load_quant_dashboard(backend=backend or "sqlite", limit=limit or 10)
        elapsed = int((perf_counter() - start) * 1000)
        return _status_panel_view(payload, elapsed)

    return None
