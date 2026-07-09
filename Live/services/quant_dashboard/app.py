
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from dash import Dash, Input, Output, dcc, html
from services.quant_dashboard.queries import load_quant_dashboard

SECTION_TITLES = {
    "recent_experiments": "Recent Experiments",
    "recent_strategies": "Recent Strategies",
    "best_backtests": "Best Backtests",
    "walk_forward_runs": "Walk-Forward Runs",
    "universe_runs": "Universe Runs",
    "data_quality_events": "Data Quality Events",
}
COLUMN_PREFERENCES = {
    "recent_experiments": ["created_at", "experiment_id", "module", "experiment_name", "status"],
    "recent_strategies": ["created_at", "strategy_run_id", "strategy_name", "strategy_family", "symbol", "status"],
    "best_backtests": ["created_at", "backtest_run_id", "symbol", "strategy_name", "sharpe", "total_return", "max_drawdown", "win_rate", "trade_count"],
    "walk_forward_runs": ["created_at", "walk_forward_run_id", "symbol", "strategy_name", "avg_sharpe", "pass_rate", "status"],
    "universe_runs": ["created_at", "universe_run_id", "universe_name", "theme", "selected_count", "status"],
    "data_quality_events": ["created_at", "event_id", "symbol", "severity", "event_type", "message"],
}

def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4f}"
    text = str(value)
    return text if len(text) <= 140 else text[:137] + "..."

def _status_banner(payload):
    cls = "status-pass" if payload.status == "PASS" else "status-warn" if payload.status == "WARN" else "status-fail"
    children = [html.Div(f"Status: {payload.status}", className=cls), html.Div(f"Backend: {payload.backend}"), html.Div(payload.message), html.Div(f"Repo: {payload.repo_root}", className="muted")]
    if payload.errors:
        children.append(html.Details([html.Summary("Warnings / errors"), html.Pre("\n".join(payload.errors[:15]))]))
    return html.Div(children, className="card")

def _counts_view(counts: dict[str, int]):
    return html.Div([html.Div([html.Div(k.replace("_", " ").title(), className="count-label"), html.Div(str(v), className="count-value")], className="count-tile") for k, v in counts.items()], className="count-grid")

def _section_table(section_key: str, rows: list[dict[str, Any]]):
    title = SECTION_TITLES.get(section_key, section_key.replace("_", " ").title())
    if not rows:
        return html.Div([html.H3(title), html.Div("No rows yet.", className="muted")], className="card")
    preferred = [col for col in COLUMN_PREFERENCES.get(section_key, []) if any(col in row for row in rows)]
    extras = []
    for row in rows:
        for col in row:
            if col not in preferred and col not in extras:
                extras.append(col)
    cols = (preferred + extras)[:10]
    return html.Div([html.H3(title), html.Table([html.Thead(html.Tr([html.Th(c) for c in cols])), html.Tbody([html.Tr([html.Td(_fmt(row.get(c))) for c in cols]) for row in rows])])], className="card table-card")

def build_layout(repo_root: str, backend: str, limit: int):
    return html.Div([
        html.H1("Quant Research Dashboard"),
        html.Div("Read-only dashboard for typed quant research results. Research/simulation only. No broker calls or live orders.", className="muted"),
        html.Div([
            html.Label("Backend"),
            dcc.Dropdown(id="backend", value=backend, clearable=False, options=[{"label": "SQLite fallback", "value": "sqlite"}, {"label": "PostgreSQL", "value": "postgres"}]),
            html.Label("Rows per section"),
            dcc.Input(id="limit", type="number", min=1, max=100, step=1, value=limit, debounce=True),
            html.Button("Refresh", id="refresh", n_clicks=0),
            dcc.Store(id="repo-root", data=repo_root),
        ], className="controls card"),
        html.Div(id="status"),
        html.Div(id="counts"),
        html.Div(id="sections", className="sections"),
    ], className="page")

def create_app(*, repo_root: str, backend: str = "sqlite", limit: int = 10) -> Dash:
    app = Dash(__name__)
    app.title = "Quant Research Dashboard"
    app.layout = build_layout(repo_root, backend, limit)
    app.index_string = """<!DOCTYPE html><html><head>{%metas%}<title>{%title%}</title>{%favicon%}{%css%}<style>
body{font-family:Arial,sans-serif;margin:0;background:#111;color:#eee}.page{padding:24px}.muted{opacity:.75}.card{border:1px solid rgba(255,255,255,.14);border-radius:10px;padding:14px;margin:14px 0;background:rgba(255,255,255,.04)}.controls{display:grid;grid-template-columns:120px minmax(220px,340px) 130px 90px 110px 1fr;gap:10px;align-items:center}.count-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}.count-tile{border:1px solid rgba(255,255,255,.14);border-radius:10px;padding:12px;background:rgba(255,255,255,.04)}.count-label{opacity:.75;font-size:.86rem}.count-value{font-size:1.5rem;font-weight:700;margin-top:4px}.table-card{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:.88rem}th,td{border-bottom:1px solid rgba(255,255,255,.12);padding:7px 9px;text-align:left;vertical-align:top}pre{white-space:pre-wrap;max-height:260px;overflow:auto}.status-pass{font-weight:700;color:#7ce38b}.status-warn{font-weight:700;color:#ffd166}.status-fail{font-weight:700;color:#ff6b6b}
</style></head><body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body></html>"""

    @app.callback(Output("status", "children"), Output("counts", "children"), Output("sections", "children"), Input("refresh", "n_clicks"), Input("backend", "value"), Input("limit", "value"), Input("repo-root", "data"), prevent_initial_call=False)
    def refresh_dashboard(_n, selected_backend, selected_limit, selected_repo_root):
        payload = load_quant_dashboard(repo_root=selected_repo_root, backend=selected_backend or "sqlite", limit=selected_limit or 10)
        return _status_banner(payload), _counts_view(payload.counts), [_section_table(k, v) for k, v in payload.sections.items()]

    return app

def main() -> int:
    parser = argparse.ArgumentParser(description="Launch standalone read-only Quant Research Dashboard.")
    parser.add_argument("--repo-root", type=str, default=str(Path.cwd().parent if Path.cwd().name.lower() == "live" else Path.cwd()))
    parser.add_argument("--backend", choices=["sqlite", "postgres"], default="sqlite")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8061)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    app = create_app(repo_root=args.repo_root, backend=args.backend, limit=10)
    print("Quant Research Dashboard starting.")
    print("Research/simulation only. No broker calls. No live orders.")
    print(f"Open: http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
