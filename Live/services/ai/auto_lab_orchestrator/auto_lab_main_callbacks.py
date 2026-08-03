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


def _normalize_holdout_pct(value) -> int:
    try:
        normalized = int(float(value))
    except (TypeError, ValueError, OverflowError):
        normalized = 20
    return max(5, min(50, normalized))


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


def register_auto_lab_main_callbacks(app, paper_trading_service=None):
    from dash import Input, Output, State, callback_context, html, no_update
    from dash.exceptions import PreventUpdate

    from services.ai.auto_lab_orchestrator.capital_controls import (
        append_supported_capital_flags,
        money,
        normalize_capital,
    )
    from services.ai.auto_lab_orchestrator.script_viewer import (
        build_script_packet,
        summarize_script_paths,
        write_latest_manifest,
    )
    from services.ai.auto_lab_orchestrator.ui_report_loader import (
        load_latest_paper_review_queue,
        load_latest_universe_report,
        load_latest_walk_forward_report,
        summarize_paths,
    )
    from services.ai.auto_lab_orchestrator.walk_forward_reporter import (
        build_paper_review_overlay,
    )

    live_root = _live_root()
    package_dir = _package_dir()
    python_exe = sys.executable

    @app.callback(
        Output("main-autolab-capital-summary", "children"),
        Input("main-autolab-initial-cash", "value"),
        Input("main-autolab-target-cash", "value"),
        Input("main-autolab-cash-exposure", "value"),
        Input("main-autolab-sizing-mode", "value"),
        prevent_initial_call=False,
    )
    def update_capital_summary(initial_cash, target_cash, cash_exposure, sizing_mode):
        capital = normalize_capital(
            initial_cash=initial_cash,
            target_cash=target_cash,
            cash_exposure_pct=cash_exposure,
            sizing_mode=sizing_mode,
        )
        return [
            html.H4("Simulated capital assumptions"),
            html.Ul(
                [
                    html.Li(f"Starting cash: {money(capital.initial_cash)}"),
                    html.Li(f"Target cash: {money(capital.target_cash)}"),
                    html.Li(f"Target return needed: {capital.target_return_pct:.2f}%"),
                    html.Li(f"Cash exposure: {capital.cash_exposure_pct:.2f}%"),
                    html.Li(f"Sizing mode: {capital.sizing_mode}"),
                ]
            ),
            html.Strong("Research/simulation only. These are not real account balances."),
        ]

    @app.callback(
        Output("main-autolab-paper-review-candidate", "options"),
        Output("main-autolab-paper-review-candidate", "value"),
        Output("main-autolab-paper-review-preview", "children"),
        Input("main-autolab-walk-forward-report", "children"),
        Input("main-autolab-refresh", "n_clicks"),
        State("main-autolab-paper-review-candidate", "value"),
        prevent_initial_call=False,
    )
    def refresh_paper_review_candidates(_walk_report, _refresh_clicks, selected_review_id):
        queue = load_latest_paper_review_queue(live_root)
        candidates = list(queue.get("candidates") or [])
        options = [
            {
                "label": (
                    f"{candidate.get('symbol', '?')} | {candidate.get('candidate_id', 'candidate')} "
                    f"| Test 2 {float(candidate.get('test_score') or 0):.2f} "
                    f"| Test 4 {float(candidate.get('holdout_score') or 0):.2f}"
                ),
                "value": candidate.get("review_id"),
            }
            for candidate in candidates
            if candidate.get("review_id")
        ]
        valid_ids = {option["value"] for option in options}
        selected = selected_review_id if selected_review_id in valid_ids else (options[0]["value"] if options else None)
        candidate = next(
            (item for item in candidates if item.get("review_id") == selected),
            None,
        )
        if candidate is None:
            return options, None, "No promoted candidate is available for paper review."

        reasons = candidate.get("promotion_reasons") or []
        reason_text = "; ".join(str(reason) for reason in reasons) or "All promotion gates passed."
        preview = "\n".join(
            [
                f"Symbol: {candidate.get('symbol', '')}",
                f"Candidate: {candidate.get('candidate_id', '')}",
                f"Test 2 score: {float(candidate.get('test_score') or 0):.2f}",
                f"Test 3: {candidate.get('rolling_status', 'unknown')}",
                f"Test 4 score: {float(candidate.get('holdout_score') or 0):.2f}",
                f"Promotion evidence: {reason_text}",
                "Execution: manual paper orders only",
            ]
        )
        return options, selected, preview

    @app.callback(
        Output("main-autolab-paper-review-store", "data"),
        Output("main-autolab-paper-review-status", "children"),
        Output("watch-symbol-dropdown", "value"),
        Input("main-autolab-review-activate", "n_clicks"),
        Input("main-autolab-review-deactivate", "n_clicks"),
        State("main-autolab-paper-review-candidate", "value"),
        State("main-autolab-review-max-position", "value"),
        State("main-autolab-review-max-daily-loss", "value"),
        State("main-autolab-review-max-drawdown", "value"),
        State("main-autolab-review-max-orders", "value"),
        prevent_initial_call=True,
    )
    def control_paper_review(
        _activate_clicks,
        _deactivate_clicks,
        selected_review_id,
        max_position_pct,
        max_daily_loss_pct,
        max_drawdown_pct,
        max_orders_per_day,
    ):
        triggered = callback_context.triggered[0]["prop_id"].split(".")[0] if callback_context.triggered else ""
        if paper_trading_service is None:
            return no_update, "Paper trading service is unavailable; no review was activated.", no_update

        if triggered == "main-autolab-review-deactivate":
            status = paper_trading_service.deactivate_review()
            return status, "Paper review and its Auto Lab chart overlay were deactivated.", no_update

        if triggered != "main-autolab-review-activate":
            raise PreventUpdate
        if not selected_review_id:
            return no_update, "Select a promoted candidate before activating paper review.", no_update

        queue = load_latest_paper_review_queue(live_root)
        candidate = next(
            (
                item
                for item in queue.get("candidates", [])
                if item.get("review_id") == selected_review_id
            ),
            None,
        )
        if candidate is None:
            return no_update, "The selected promoted candidate is no longer in the latest review queue.", no_update

        try:
            overlay = build_paper_review_overlay(candidate)
            status = paper_trading_service.activate_review(
                candidate,
                risk_policy={
                    "max_position_pct": max_position_pct,
                    "max_daily_loss_pct": max_daily_loss_pct,
                    "max_drawdown_pct": max_drawdown_pct,
                    "max_orders_per_day": max_orders_per_day,
                    "allow_short": False,
                },
            )
        except Exception as exc:
            return no_update, f"Paper review activation failed: {exc}", no_update

        policy = status.get("risk_policy", {})
        return (
            {**status, "overlay": overlay},
            (
                f"Active manual review: {status.get('symbol')} / {status.get('candidate_id')} | "
                f"position {policy.get('max_position_pct', 0):g}% | "
                f"daily loss {policy.get('max_daily_loss_pct', 0):g}% | "
                f"drawdown {policy.get('max_drawdown_pct', 0):g}% | "
                f"orders/day {policy.get('max_orders_per_day', 0)}. "
                "The visual strategy overlay is loaded in Watch. No order was submitted."
            ),
            status.get("symbol"),
        )

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
        State("main-autolab-holdout-pct", "value"),
        State("main-autolab-rolling-windows", "value"),
        State("main-autolab-rolling-commission", "value"),
        State("main-autolab-rolling-slippage", "value"),
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
        holdout_pct,
        rolling_windows,
        rolling_commission,
        rolling_slippage,
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
        holdout_pct = _normalize_holdout_pct(holdout_pct)
        rolling_windows = max(1, min(12, int(rolling_windows or 3)))
        rolling_commission = max(0.0, float(rolling_commission or 0.0))
        rolling_slippage = max(0.0, float(rolling_slippage or 0.0))

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
                "--sizing-mode",
                str(capital.sizing_mode),
                "--cash-exposure-pct",
                str(capital.cash_exposure_pct),
                "--top-n-per-symbol",
                str(top_n),
                "--holdout-pct",
                str(holdout_pct),
                "--rolling-windows",
                str(rolling_windows),
                "--rolling-commission-per-order",
                str(rolling_commission),
                "--rolling-slippage-bps",
                str(rolling_slippage),
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
                    "holdout_pct": holdout_pct,
                    "rolling_windows": rolling_windows,
                    "rolling_commission_per_order": rolling_commission,
                    "rolling_slippage_bps": rolling_slippage,
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
