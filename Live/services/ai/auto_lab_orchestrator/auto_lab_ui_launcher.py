from __future__ import annotations

from pathlib import Path
import argparse
import subprocess
import sys
import time


def _bootstrap_import_path() -> Path:
    here = Path(__file__).resolve()
    live_root = here.parents[3]
    repo_root = here.parents[4]
    for path in (str(live_root), str(repo_root)):
        if path not in sys.path:
            sys.path.insert(0, path)
    return live_root


LIVE_ROOT = _bootstrap_import_path()
PACKAGE_DIR = Path(__file__).resolve().parent
PYTHON_EXE = sys.executable


def _safe_symbols(value: str) -> str:
    cleaned = []
    for part in (value or "").replace(";", ",").split(","):
        token = part.strip().upper()
        if token and token.replace(".", "").replace("-", "").isalnum():
            cleaned.append(token)
    return ",".join(dict.fromkeys(cleaned))


def _run_command(cmd: list[str], cwd: Path) -> str:
    started = time.strftime("%Y-%m-%d %H:%M:%S")
    result = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)
    ended = time.strftime("%Y-%m-%d %H:%M:%S")
    parts = [
        f"Started: {started}",
        f"Ended: {ended}",
        f"Return code: {result.returncode}",
        "",
        "Command:",
        " ".join(f'"{x}"' if " " in str(x) else str(x) for x in cmd),
        "",
        "STDOUT:",
        result.stdout or "",
        "",
        "STDERR:",
        result.stderr or "",
    ]
    return "\n".join(parts)


def create_app():
    try:
        from dash import Dash, Input, Output, State, dcc, html
    except Exception as exc:
        raise RuntimeError(
            "Dash is required for the Auto Lab UI launcher. Install with: python -m pip install dash"
        ) from exc

    from services.ai.auto_lab_orchestrator.ui_report_loader import (
        load_latest_universe_report,
        load_latest_walk_forward_report,
        summarize_paths,
    )

    app = Dash(__name__, title="AI Auto Lab")
    app.layout = html.Div(
        style={
            "fontFamily": "Arial, sans-serif",
            "margin": "24px",
            "maxWidth": "1400px",
        },
        children=[
            html.H1("AI Auto Lab — Research UI"),
            html.Div(
                "Research/simulation only. No live orders. No broker connection. No financial advice.",
                style={
                    "padding": "12px",
                    "border": "1px solid #999",
                    "borderRadius": "8px",
                    "marginBottom": "16px",
                    "fontWeight": "bold",
                },
            ),
            html.Div(
                style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr", "gap": "12px"},
                children=[
                    html.Div([
                        html.Label("Symbols"),
                        dcc.Input(id="al-symbols", value="AMD,NVDA,MSFT,AAPL,TSLA", style={"width": "100%"}),
                    ]),
                    html.Div([
                        html.Label("Sizing mode"),
                        dcc.Dropdown(
                            id="al-sizing-mode",
                            options=[
                                {"label": "Percent cash exposure", "value": "percent_cash_exposure"},
                                {"label": "Fixed quantity", "value": "fixed_quantity"},
                                {"label": "Max affordable shares", "value": "max_affordable_shares"},
                            ],
                            value="percent_cash_exposure",
                            clearable=False,
                        ),
                    ]),
                    html.Div([
                        html.Label("Cash exposure %"),
                        dcc.Input(id="al-cash-exposure", type="number", value=95, min=1, max=100, step=1, style={"width": "100%"}),
                    ]),
                    html.Div([
                        html.Label("Universe start"),
                        dcc.Input(id="al-universe-start", value="2020-01-01", style={"width": "100%"}),
                    ]),
                    html.Div([
                        html.Label("Universe end"),
                        dcc.Input(id="al-universe-end", value="2025-12-31", style={"width": "100%"}),
                    ]),
                    html.Div([
                        html.Label("Max runs per symbol"),
                        dcc.Input(id="al-max-runs", type="number", value=20, min=1, max=200, step=1, style={"width": "100%"}),
                    ]),
                    html.Div([
                        html.Label("Train start"),
                        dcc.Input(id="al-train-start", value="2020-01-01", style={"width": "100%"}),
                    ]),
                    html.Div([
                        html.Label("Train end"),
                        dcc.Input(id="al-train-end", value="2023-12-31", style={"width": "100%"}),
                    ]),
                    html.Div([
                        html.Label("Test start"),
                        dcc.Input(id="al-test-start", value="2024-01-01", style={"width": "100%"}),
                    ]),
                    html.Div([
                        html.Label("Test end"),
                        dcc.Input(id="al-test-end", value="2025-12-31", style={"width": "100%"}),
                    ]),
                    html.Div([
                        html.Label("Top N per symbol for walk-forward"),
                        dcc.Input(id="al-top-n", type="number", value=3, min=1, max=20, step=1, style={"width": "100%"}),
                    ]),
                    html.Div([
                        html.Label("Max mutations per parent"),
                        dcc.Input(id="al-max-muts", type="number", value=4, min=1, max=50, step=1, style={"width": "100%"}),
                    ]),
                ],
            ),
            html.Div(
                style={"marginTop": "16px", "display": "flex", "gap": "12px", "flexWrap": "wrap"},
                children=[
                    html.Button("Run Universe Auto Lab", id="al-run-universe", n_clicks=0),
                    html.Button("Run Walk-Forward Validation", id="al-run-walk-forward", n_clicks=0),
                    html.Button("Refresh Latest Reports", id="al-refresh", n_clicks=0),
                ],
            ),
            html.H2("Command Output"),
            dcc.Textarea(
                id="al-command-output",
                value="Ready. Click a run button or refresh reports.",
                style={"width": "100%", "height": "260px", "fontFamily": "Consolas, monospace"},
            ),
            html.H2("Latest Report Paths"),
            html.Pre(id="al-report-paths", style={"whiteSpace": "pre-wrap", "padding": "12px", "border": "1px solid #ddd"}),
            html.Div(
                style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "18px"},
                children=[
                    html.Div([
                        html.H2("Latest Universe Report"),
                        dcc.Markdown(
                            id="al-universe-report",
                            children="No report loaded yet.",
                            style={"maxHeight": "700px", "overflowY": "auto", "border": "1px solid #ddd", "padding": "12px"},
                        ),
                    ]),
                    html.Div([
                        html.H2("Latest Walk-Forward Report"),
                        dcc.Markdown(
                            id="al-walk-forward-report",
                            children="No report loaded yet.",
                            style={"maxHeight": "700px", "overflowY": "auto", "border": "1px solid #ddd", "padding": "12px"},
                        ),
                    ]),
                ],
            ),
        ],
    )

    @app.callback(
        Output("al-command-output", "value"),
        Output("al-universe-report", "children"),
        Output("al-walk-forward-report", "children"),
        Output("al-report-paths", "children"),
        Input("al-run-universe", "n_clicks"),
        Input("al-run-walk-forward", "n_clicks"),
        Input("al-refresh", "n_clicks"),
        State("al-symbols", "value"),
        State("al-sizing-mode", "value"),
        State("al-cash-exposure", "value"),
        State("al-universe-start", "value"),
        State("al-universe-end", "value"),
        State("al-max-runs", "value"),
        State("al-train-start", "value"),
        State("al-train-end", "value"),
        State("al-test-start", "value"),
        State("al-test-end", "value"),
        State("al-top-n", "value"),
        State("al-max-muts", "value"),
        prevent_initial_call=False,
    )
    def run_or_refresh(
        run_universe_clicks,
        run_walk_forward_clicks,
        refresh_clicks,
        symbols,
        sizing_mode,
        cash_exposure,
        universe_start,
        universe_end,
        max_runs,
        train_start,
        train_end,
        test_start,
        test_end,
        top_n,
        max_muts,
    ):
        from dash import callback_context

        triggered = callback_context.triggered[0]["prop_id"].split(".")[0] if callback_context.triggered else "initial"
        command_output = "Reports refreshed."

        safe_symbols = _safe_symbols(symbols)
        if not safe_symbols:
            safe_symbols = "AMD,NVDA,MSFT,AAPL,TSLA"

        if triggered == "al-run-universe":
            cmd = [
                PYTHON_EXE,
                str(PACKAGE_DIR / "universe_runner.py"),
                "--symbols", safe_symbols,
                "--start", str(universe_start or "2020-01-01"),
                "--end", str(universe_end or ""),
                "--yfinance-first",
                "--sizing-mode", str(sizing_mode or "percent_cash_exposure"),
                "--cash-exposure-pct", str(cash_exposure or 95),
                "--max-total-runs-per-symbol", str(max_runs or 20),
                "--max-mutations-per-parent", str(max_muts or 4),
                "--continue-on-error",
            ]
            command_output = _run_command(cmd, cwd=LIVE_ROOT.parent)

        elif triggered == "al-run-walk-forward":
            cmd = [
                PYTHON_EXE,
                str(PACKAGE_DIR / "walk_forward_runner.py"),
                "--symbols", safe_symbols,
                "--train-start", str(train_start or "2020-01-01"),
                "--train-end", str(train_end or "2023-12-31"),
                "--test-start", str(test_start or "2024-01-01"),
                "--test-end", str(test_end or "2025-12-31"),
                "--yfinance-first",
                "--sizing-mode", str(sizing_mode or "percent_cash_exposure"),
                "--cash-exposure-pct", str(cash_exposure or 95),
                "--top-n-per-symbol", str(top_n or 3),
                "--max-total-runs-per-symbol", str(max_runs or 20),
                "--max-mutations-per-parent", str(max_muts or 4),
                "--continue-on-error",
            ]
            command_output = _run_command(cmd, cwd=LIVE_ROOT.parent)

        universe = load_latest_universe_report(LIVE_ROOT)
        walk_forward = load_latest_walk_forward_report(LIVE_ROOT)

        paths = [
            "UNIVERSE",
            summarize_paths(universe.get("paths", {})),
            "",
            "WALK_FORWARD",
            summarize_paths(walk_forward.get("paths", {})),
        ]

        return command_output, universe.get("report_md", ""), walk_forward.get("report_md", ""), "\n".join(paths)

    return app


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch local AI Auto Lab research UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8077)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    app = create_app()
    print("AI Auto Lab UI launcher starting.")
    print("Research/simulation only. No broker calls. No live orders.")
    print(f"Open: http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
