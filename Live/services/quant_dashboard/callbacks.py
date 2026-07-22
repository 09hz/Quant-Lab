from __future__ import annotations

from time import perf_counter
from typing import Any
import json

from dash import Input, Output, State, html, dcc, no_update

try:
    # Reuse existing callback registration and column preferences
    from services.data_catalog.quant_dashboard_callbacks import (
        register_quant_dashboard_callbacks as _original_register,
        COLUMN_PREFERENCES as _COLUMN_PREFS,
    )
except Exception as exc:  # pragma: no cover
    _original_register = None  # type: ignore
    _COLUMN_PREFS = {}
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

try:
    from .queries import load_quant_dashboard
except Exception:  # pragma: no cover
    load_quant_dashboard = None  # type: ignore


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4f}"
    text = str(value)
    return text if len(text) <= 120 else text[:117] + "..."


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
    status panel renderer and research modules without duplicating SQL.
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

    # Research modules (subset) from existing payload
    def _count_tile(label: str, value: Any):
        return html.Div(
            className="quant-native-count-tile",
            children=[
                html.Div(label, className="quant-native-count-label"),
                html.Div(str(value), className="quant-native-count-value"),
            ],
        )

    def _count_grid(items: list[tuple[str, Any]]):
        return html.Div(
            className="quant-native-count-grid",
            children=[_count_tile(k, v) for k, v in items],
        )

    def _mini_table(title: str, rows: list[dict], cols: list[str]):
        return html.Div(
            className="quant-native-card quant-native-table-card",
            children=[
                html.H4(title),
                html.Table(
                    className="quant-dashboard-table",
                    children=[
                        html.Thead(html.Tr([html.Th(c) for c in cols])),
                        html.Tbody([html.Tr([html.Td(_fmt(r.get(c))) for c in cols]) for r in rows[:10]]),
                    ],
                ),
            ],
        )

    @app.callback(
        Output("quant-module-market-overview", "children"),
        Output("quant-module-data-quality", "children"),
        Output("quant-module-screening", "children"),
        Input("quant-dashboard-refresh", "n_clicks"),
        Input("quant-dashboard-backend", "value"),
        Input("quant-dashboard-limit", "value"),
        State("quant-universe", "value"),
        State("quant-date-range", "start_date"),
        State("quant-date-range", "end_date"),
        prevent_initial_call=False,
    )
    def _render_modules(_n, backend, limit, universe, start_date, end_date):
        payload = load_quant_dashboard(backend=backend or "sqlite", limit=limit or 10)
        s = payload.sections or {}
        # Filters applied to section copies
        def filter_rows(rows: list[dict]):
            out = rows
            if start_date or end_date:
                def in_range(r):
                    ts = r.get("created_at")
                    if not ts:
                        return False
                    d = str(ts)[:10]
                    if start_date and d < str(start_date):
                        return False
                    if end_date and d > str(end_date):
                        return False
                    return True
                out = [r for r in out if in_range(r)]
            return out

        experiments = filter_rows(list(s.get("recent_experiments", [])))
        strategies = filter_rows(list(s.get("recent_strategies", [])))
        backtests = filter_rows(list(s.get("best_backtests", [])))
        universes = list(s.get("universe_runs", []))
        dq = filter_rows(list(s.get("data_quality_events", [])))
        if universe:
            universes = [r for r in universes if r.get("universe_name") == universe]

        market_overview = html.Div(
            children=[
                html.H4("Market Overview"),
                _count_grid([
                    ("Experiments", len(experiments)),
                    ("Strategies", len(strategies)),
                    ("Backtests", len(backtests)),
                    ("Universe Runs", len(universes)),
                    ("Data Quality", len(dq)),
                ]),
            ],
        )

        dq_cols = _COLUMN_PREFS.get("data_quality_events", ["created_at", "symbol", "dataset_name", "severity", "event_type"])[:6]
        dq_view = _mini_table("Data Quality", dq, dq_cols)

        screening_cols = _COLUMN_PREFS.get("recent_strategies", ["created_at", "strategy_name", "symbol", "timeframe", "status"])[:6]
        screening = _mini_table("Screening Results", strategies, screening_cols)

        return market_overview, dq_view, screening

    # Reset control values to defaults without duplicating logic
    @app.callback(
        Output("quant-dashboard-backend", "value"),
        Output("quant-dashboard-limit", "value"),
        Output("quant-dataset", "value"),
        Output("quant-universe", "value"),
        Output("quant-market", "value"),
        Output("quant-date-range", "start_date"),
        Output("quant-date-range", "end_date"),
        Input("quant-dashboard-reset", "n_clicks"),
        prevent_initial_call=True,
    )
    def _reset_controls(n):
        if not n:
            return no_update, no_update, no_update, no_update, no_update, no_update, no_update
        return "sqlite", 10, None, None, None, None, None

    # Export current dashboard payload as JSON
    @app.callback(
        Output("quant-dashboard-download", "data"),
        Input("quant-dashboard-export", "n_clicks"),
        State("quant-dashboard-backend", "value"),
        State("quant-dashboard-limit", "value"),
        prevent_initial_call=True,
    )
    def _export_payload(n, backend, limit):
        if not n:
            return no_update
        payload = load_quant_dashboard(backend=backend or "sqlite", limit=limit or 10)
        try:
            data = json.dumps(getattr(payload, "to_dict", lambda: payload)(), indent=2)
        except Exception:
            data = json.dumps(payload.__dict__, indent=2)
        return dcc.send_string(data, "quant_dashboard.json")

    # Results table: sort and render using payload sections (no new SQL), with optional universe/date filters
    @app.callback(
        Output("quant-results-sort", "options"),
        Output("quant-results-sort", "value"),
        Output("quant-dashboard-results-table", "children"),
        Input("quant-results-section", "value"),
        Input("quant-results-direction", "value"),
        Input("quant-dashboard-refresh", "n_clicks"),
        Input("quant-dashboard-backend", "value"),
        Input("quant-dashboard-limit", "value"),
        State("quant-results-sort", "value"),
        State("quant-universe", "value"),
        State("quant-date-range", "start_date"),
        State("quant-date-range", "end_date"),
        prevent_initial_call=False,
    )
    def _render_results(section, direction, _n, backend, limit, sort_col, universe, start_date, end_date):
        payload = load_quant_dashboard(backend=backend or "sqlite", limit=limit or 10)
        rows = list((payload.sections or {}).get(section or "recent_experiments", []))

        # Optional filters
        if universe and section == "universe_runs":
            rows = [r for r in rows if r.get("universe_name") == universe]
        if start_date or end_date:
            def in_range(r):
                ts = r.get("created_at")
                if not ts:
                    return False
                s = str(ts)[:10]
                if start_date and s < str(start_date):
                    return False
                if end_date and s > str(end_date):
                    return False
                return True
            rows = [r for r in rows if in_range(r)]

        # Columns preference reuse
        preferred = [c for c in _COLUMN_PREFS.get(section or "", []) if any(c in r for r in rows)]
        extras: list[str] = []
        for r in rows:
            for c in r.keys():
                if c not in preferred and c not in extras:
                    extras.append(c)
        columns = (preferred + extras)[:12]
        options = [{"label": c, "value": c} for c in columns]
        if not columns:
            return options, sort_col, html.Div("No rows yet.", className="data-library-muted")
        if sort_col not in columns or sort_col is None:
            sort_col = columns[0]
        def key_fn(v):
            val = v.get(sort_col)
            try:
                return float(val)
            except Exception:
                return ("" if val is None else str(val))
        rows_sorted = sorted(rows, key=key_fn, reverse=(str(direction or "desc") == "desc"))
        table = html.Table(
            className="quant-dashboard-table",
            children=[
                html.Thead(html.Tr([html.Th(c) for c in columns])),
                html.Tbody([html.Tr([html.Td(_fmt(r.get(c))) for c in columns]) for r in rows_sorted]),
            ],
        )
        card = html.Div(className="quant-dashboard-table-card", children=[html.H4("Results"), table])
        return options, sort_col, card

    return None
