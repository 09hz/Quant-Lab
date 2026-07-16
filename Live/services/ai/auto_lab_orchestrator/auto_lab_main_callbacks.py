from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import time


def _live_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _package_dir() -> Path:
    return Path(__file__).resolve().parent


def _clean_symbols(value: str | None) -> str:
    symbols = []
    for raw in (value or "").replace(";", ",").split(","):
        token = raw.strip().upper()
        if token and token.replace(".", "").replace("-", "").isalnum():
            symbols.append(token)
    return ",".join(dict.fromkeys(symbols)) or "AMD,NVDA,MSFT,AAPL,TSLA"


def _run_command(cmd: list[str], cwd: Path) -> tuple[str, int]:
    started = time.strftime("%Y-%m-%d %H:%M:%S")
    result = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)
    ended = time.strftime("%Y-%m-%d %H:%M:%S")
    output = "\n".join(
        [
            f"Started: {started}",
            f"Ended: {ended}",
            f"Return code: {result.returncode}",
            "",
            "Research/simulation only. No live orders or broker calls were made.",
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
    )
    return output, result.returncode


def register_auto_lab_main_callbacks(app):
    from dash import Input, Output, State, callback_context
    from dash.exceptions import PreventUpdate

    from services.ai.auto_lab_orchestrator.capital_controls import (
        append_supported_capital_flags,
        normalize_capital,
    )
    from services.ai.auto_lab_orchestrator.script_viewer import (
        build_script_packet,
        summarize_script_paths,
        write_latest_manifest,
    )
    from services.ai.auto_lab_orchestrator.ui_report_loader import (
        load_latest_universe_report,
        load_latest_walk_forward_report,
        summarize_paths,
    )

    live_root = _live_root()
    package_dir = _package_dir()
    python_exe = sys.executable

    @app.callback(
        Output("main-autolab-symbols", "value"),
        Output("main-autolab-discovery-report", "children"),
        Output("main-autolab-discovery-paths", "children"),
        Input("main-autolab-suggest-symbols", "n_clicks"),
        State("main-autolab-symbols", "value"),
        State("main-autolab-discovery-theme", "value"),
        State("main-autolab-discovery-max-symbols", "value"),
        prevent_initial_call=True,
    )
    def suggest_symbols(n_clicks, symbols, theme, max_symbols):
        if not n_clicks:
            raise PreventUpdate

        from services.ai.auto_lab_orchestrator.symbol_discovery import discover_symbol_universe
        from services.ai.auto_lab_orchestrator.symbol_discovery_reporter import write_symbol_discovery_reports

        packet = discover_symbol_universe(
            seed_symbols=symbols,
            theme=theme,
            max_symbols=max_symbols or 10,
        )
        paths = write_symbol_discovery_reports(live_root, packet)
        suggested_value = ",".join(packet.get("suggested_symbols", []))

        path_text = "\n".join(
            [
                f"run_dir: {paths.get('run_dir', '')}",
                f"report_path: {paths.get('report_path', '')}",
                f"json_path: {paths.get('json_path', '')}",
                f"manifest_path: {paths.get('manifest_path', '')}",
            ]
        )

        return suggested_value, paths.get("report_md", ""), path_text

    @app.callback(
        Output("main-autolab-command-output", "value"),
        Output("main-autolab-universe-report", "children"),
        Output("main-autolab-walk-forward-report", "children"),
        Output("main-autolab-report-paths", "children"),
        Output("main-autolab-universe-script", "children"),
        Output("main-autolab-walk-forward-script", "children"),
        Output("main-autolab-script-paths", "children"),
        Input("main-autolab-run-universe", "n_clicks"),
        Input("main-autolab-run-walk-forward", "n_clicks"),
        Input("main-autolab-refresh", "n_clicks"),
        State("main-autolab-symbols", "value"),
        State("main-autolab-sizing-mode", "value"),
        State("main-autolab-cash-exposure", "value"),
        State("main-autolab-initial-cash", "value"),
        State("main-autolab-target-cash", "value"),
        State("main-autolab-universe-start", "value"),
        State("main-autolab-universe-end", "value"),
        State("main-autolab-max-runs", "value"),
        State("main-autolab-max-mutations", "value"),
        State("main-autolab-train-start", "value"),
        State("main-autolab-train-end", "value"),
        State("main-autolab-test-start", "value"),
        State("main-autolab-test-end", "value"),
        State("main-autolab-top-n", "value"),
        prevent_initial_call=False,
    )
    def run_or_refresh(
        _run_universe_clicks,
        _run_walk_forward_clicks,
        _refresh_clicks,
        symbols,
        sizing_mode,
        cash_exposure,
        initial_cash,
        target_cash,
        universe_start,
        universe_end,
        max_runs,
        max_mutations,
        train_start,
        train_end,
        test_start,
        test_end,
        top_n,
    ):
        triggered = callback_context.triggered[0]["prop_id"].split(".")[0] if callback_context.triggered else "initial"
        command_output = "Reports refreshed."
        flag_warnings: list[str] = []
        manifest_paths: dict[str, str] = {}

        symbols_clean = _clean_symbols(symbols)
        capital = normalize_capital(
            initial_cash=initial_cash,
            target_cash=target_cash,
            cash_exposure_pct=cash_exposure,
            sizing_mode=sizing_mode,
        )

        max_runs = max_runs or 20
        max_mutations = max_mutations or 4
        top_n = top_n or 3

        if triggered == "main-autolab-run-universe":
            script_path = package_dir / "universe_runner.py"
            cmd = [
                python_exe,
                str(script_path),
                "--symbols",
                symbols_clean,
                "--start",
                str(universe_start or "2020-01-01"),
                "--end",
                str(universe_end or "2025-12-31"),
                "--yfinance-first",
                "--sizing-mode",
                str(capital.sizing_mode),
                "--cash-exposure-pct",
                str(capital.cash_exposure_pct),
                "--max-total-runs-per-symbol",
                str(max_runs),
                "--max-mutations-per-parent",
                str(max_mutations),
                "--continue-on-error",
            ]
            cmd, flag_warnings = append_supported_capital_flags(cmd, script_path, capital)
            command_output, _return_code = _run_command(cmd, cwd=live_root.parent)
            manifest_paths = write_latest_manifest(
                live_root,
                "universe",
                {
                    "symbols": symbols_clean,
                    "universe_start": universe_start,
                    "universe_end": universe_end,
                    "max_runs_per_symbol": max_runs,
                    "max_mutations_per_parent": max_mutations,
                },
                capital.to_dict(),
                command=cmd,
                warnings=flag_warnings,
            )

        elif triggered == "main-autolab-run-walk-forward":
            script_path = package_dir / "walk_forward_runner.py"
            cmd = [
                python_exe,
                str(script_path),
                "--symbols",
                symbols_clean,
                "--train-start",
                str(train_start or "2020-01-01"),
                "--train-end",
                str(train_end or "2023-12-31"),
                "--test-start",
                str(test_start or "2024-01-01"),
                "--test-end",
                str(test_end or "2025-12-31"),
                "--yfinance-first",
                "--sizing-mode",
                str(capital.sizing_mode),
                "--cash-exposure-pct",
                str(capital.cash_exposure_pct),
                "--top-n-per-symbol",
                str(top_n),
                "--max-total-runs-per-symbol",
                str(max_runs),
                "--max-mutations-per-parent",
                str(max_mutations),
                "--continue-on-error",
            ]
            cmd, flag_warnings = append_supported_capital_flags(cmd, script_path, capital)
            command_output, _return_code = _run_command(cmd, cwd=live_root.parent)
            manifest_paths = write_latest_manifest(
                live_root,
                "walk_forward",
                {
                    "symbols": symbols_clean,
                    "train_start": train_start,
                    "train_end": train_end,
                    "test_start": test_start,
                    "test_end": test_end,
                    "top_n_per_symbol": top_n,
                    "max_runs_per_symbol": max_runs,
                    "max_mutations_per_parent": max_mutations,
                },
                capital.to_dict(),
                command=cmd,
                warnings=flag_warnings,
            )

        universe = load_latest_universe_report(live_root)
        walk_forward = load_latest_walk_forward_report(live_root)
        scripts = build_script_packet(live_root)

        path_text = "\n".join(
            [
                "UNIVERSE",
                summarize_paths(universe.get("paths", {})),
                "",
                "WALK_FORWARD",
                summarize_paths(walk_forward.get("paths", {})),
                "",
                "UI MANIFEST",
                summarize_paths(manifest_paths),
            ]
        )

        return (
            command_output,
            universe.get("report_md", "No universe report available."),
            walk_forward.get("report_md", "No walk-forward report available."),
            path_text,
            scripts.get("universe_md", "No universe strategy script loaded."),
            scripts.get("walk_forward_md", "No walk-forward strategy script loaded."),
            summarize_script_paths(scripts.get("paths", {})),
        )

# --- v23.2.2.1 Market Memory Packet Callback Registration ---
try:
    from services.ai.auto_lab_orchestrator.market_memory_packet_callbacks import (
        register_market_memory_packet_callbacks as _v23_2_2_1_register_market_memory_packet_callbacks,
    )

    _V23_2_2_1_MEMORY_SYMBOL_INPUT_ID = "main-autolab-symbols"

    def _v23_2_2_1_wrap_callback_register(fn):
        if getattr(fn, "_v23_2_2_1_market_memory_callbacks_wrapped", False):
            return fn

        def _wrapped(app, *args, **kwargs):
            result = fn(app, *args, **kwargs)
            _v23_2_2_1_register_market_memory_packet_callbacks(
                app,
                symbol_input_id=_V23_2_2_1_MEMORY_SYMBOL_INPUT_ID,
            )
            return result

        _wrapped.__name__ = getattr(fn, "__name__", "wrapped_market_memory_callback_register")
        _wrapped.__doc__ = getattr(fn, "__doc__", None)
        _wrapped._v23_2_2_1_market_memory_callbacks_wrapped = True
        return _wrapped

    for _v23_2_2_1_name, _v23_2_2_1_obj in list(globals().items()):
        _v23_2_2_1_lower = str(_v23_2_2_1_name).lower()
        if (
            callable(_v23_2_2_1_obj)
            and "register" in _v23_2_2_1_lower
            and "callback" in _v23_2_2_1_lower
            and ("auto" in _v23_2_2_1_lower or "autolab" in _v23_2_2_1_lower or "lab" in _v23_2_2_1_lower)
            and _v23_2_2_1_name != "register_market_memory_packet_callbacks"
        ):
            globals()[_v23_2_2_1_name] = _v23_2_2_1_wrap_callback_register(_v23_2_2_1_obj)

except Exception as _v23_2_2_1_memory_callback_error:
    print(f"v23.2.2.1 Market Memory Packet Callback Registration failed: {_v23_2_2_1_memory_callback_error}")
# --- end v23.2.2.1 Market Memory Packet Callback Registration ---

# BEGIN v24.6 direct producer wiring
try:
    from services.quant_schema.producer_runtime import wire_current_module
    wire_current_module(__name__, globals())
except Exception as _v24_6_direct_wiring_exc:
    print(f"[v24.6 direct producer wiring] disabled for {__name__}: {type(_v24_6_direct_wiring_exc).__name__}: {_v24_6_direct_wiring_exc}")
# END v24.6 direct producer wiring
