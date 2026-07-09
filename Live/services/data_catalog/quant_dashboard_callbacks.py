from __future__ import annotations

from typing import Any

from dash import Input, Output, html

from services.data_catalog.quant_dashboard_queries import load_quant_dashboard


COLUMN_PREFERENCES = {
    "recent_experiments": ["created_at", "experiment_id", "module", "experiment_name", "status", "artifact_id"],
    "recent_strategies": ["created_at", "strategy_run_id", "strategy_name", "strategy_family", "symbol", "timeframe", "status"],
    "best_backtests": ["created_at", "backtest_run_id", "symbol", "strategy_name", "timeframe", "sharpe", "total_return", "max_drawdown", "win_rate", "profit_factor", "trade_count"],
    "walk_forward_runs": ["created_at", "walk_forward_run_id", "symbol", "strategy_name", "timeframe", "window_count", "avg_sharpe", "max_drawdown", "pass_rate", "stability_score", "status"],
    "universe_runs": ["created_at", "universe_run_id", "universe_name", "theme", "selected_count", "status"],
    "data_quality_events": ["created_at", "event_id", "symbol", "dataset_name", "severity", "event_type", "message"],
}


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4f}"
    text = str(value)
    return text if len(text) <= 120 else text[:117] + "..."


def _section_table(title: str, rows: list[dict[str, Any]], key: str):
    if not rows:
        return html.Div(
            className="quant-dashboard-table-card",
            children=[
                html.H4(title),
                html.Div("No rows yet.", className="data-library-muted"),
            ],
        )

    preferred = [col for col in COLUMN_PREFERENCES.get(key, []) if any(col in row for row in rows)]
    extras = []
    for row in rows:
        for col in row.keys():
            if col not in preferred and col not in extras:
                extras.append(col)
    columns = (preferred + extras)[:10]

    return html.Div(
        className="quant-dashboard-table-card",
        children=[
            html.H4(title),
            html.Table(
                className="quant-dashboard-table",
                children=[
                    html.Thead(html.Tr([html.Th(col) for col in columns])),
                    html.Tbody([
                        html.Tr([html.Td(_fmt(row.get(col))) for col in columns])
                        for row in rows
                    ]),
                ],
            ),
        ],
    )


def _counts_view(counts: dict[str, int]):
    if not counts:
        return html.Div("No quant counts available.", className="data-library-muted")

    items = [
        html.Div(
            className="quant-dashboard-count-tile",
            children=[
                html.Div(table.replace("_", " ").title(), className="quant-dashboard-count-label"),
                html.Div(str(count), className="quant-dashboard-count-value"),
            ],
        )
        for table, count in counts.items()
    ]
    return html.Div(className="quant-dashboard-count-grid", children=items)


def _status_view(payload):
    status_class = "quant-dashboard-status-pass" if payload.status == "PASS" else "quant-dashboard-status-warn" if payload.status == "WARN" else "quant-dashboard-status-fail"
    children = [
        html.Div(f"Status: {payload.status}", className=status_class),
        html.Div(f"Backend: {payload.backend}", className="data-library-muted"),
        html.Div(payload.message, className="data-library-muted"),
    ]
    if payload.errors:
        children.append(
            html.Details(
                children=[
                    html.Summary("Warnings / errors"),
                    html.Pre("\n".join(payload.errors[:10]), className="quant-dashboard-error-pre"),
                ]
            )
        )
    return html.Div(children=children)


def register_quant_dashboard_callbacks(app):
    @app.callback(
        Output("quant-dashboard-status", "children"),
        Output("quant-dashboard-counts", "children"),
        Output("quant-dashboard-experiments", "children"),
        Output("quant-dashboard-strategies", "children"),
        Output("quant-dashboard-backtests", "children"),
        Output("quant-dashboard-walk-forward", "children"),
        Output("quant-dashboard-universe", "children"),
        Output("quant-dashboard-data-quality", "children"),
        Input("quant-dashboard-refresh", "n_clicks"),
        Input("quant-dashboard-backend", "value"),
        Input("quant-dashboard-limit", "value"),
        prevent_initial_call=False,
    )
    def refresh_quant_dashboard(_n_clicks, backend, limit):
        payload = load_quant_dashboard(backend=backend or "sqlite", limit=limit or 10)
        sections = payload.sections
        return (
            _status_view(payload),
            _counts_view(payload.counts),
            _section_table("Recent Experiments", sections.get("recent_experiments", []), "recent_experiments"),
            _section_table("Recent Strategies", sections.get("recent_strategies", []), "recent_strategies"),
            _section_table("Best Backtests", sections.get("best_backtests", []), "best_backtests"),
            _section_table("Walk-Forward Runs", sections.get("walk_forward_runs", []), "walk_forward_runs"),
            _section_table("Universe Runs", sections.get("universe_runs", []), "universe_runs"),
            _section_table("Data Quality Events", sections.get("data_quality_events", []), "data_quality_events"),
        )
