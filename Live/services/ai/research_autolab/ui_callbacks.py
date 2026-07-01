from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dash import Input, Output, State, html, no_update

from services.ai.research_autolab.csv_runner import run_backtest_request_from_csv
from services.ai.research_autolab.planner import build_backtest_requests, build_hypotheses_from_fred_manifest
from services.ai.research_autolab.reporter import write_report_bundle
from services.ai.research_autolab.sim_guard import (
    assert_safe_output_path,
    assert_simulation_only,
    safety_banner,
)


def _split_csv(value: str) -> list[str]:
    return [x.strip().upper() for x in str(value or "").replace("\n", ",").split(",") if x.strip()]


def _live_root() -> Path:
    # ui_callbacks.py lives at Live/services/ai/research_autolab/ui_callbacks.py.
    # parents[3] is the Live directory.
    return Path(__file__).resolve().parents[3]


def _resolve_live_path(value: str, *, default: str) -> Path:
    text = str(value or "").strip() or default
    path = Path(text)
    if not path.is_absolute():
        path = _live_root() / path
    return path.resolve()


def _metric(row: dict[str, Any], name: str, default: float = 0.0) -> float:
    try:
        return float((row.get("metrics") or {}).get(name, default) or default)
    except Exception:
        return default


def _result_key(row: dict[str, Any]) -> tuple[str, str, int, int]:
    req = row.get("request") or {}
    params = req.get("parameters") or {}
    return (
        str(req.get("hypothesis_id") or ""),
        str(req.get("symbol") or ""),
        int(params.get("lookback") or 0),
        int(params.get("holding_days") or 0),
    )


def _serialize_result(result: Any) -> dict[str, Any]:
    return {
        "request": result.request.__dict__,
        "metrics": dict(result.metrics or {}),
        "notes": list(result.notes or []),
        "passed_safety_checks": bool(result.passed_safety_checks),
    }


def _run_suite(
    *,
    series_ids: list[str],
    symbols: list[str],
    bars_dir: Path,
    macro_dir: Path,
    require_macro_filters: bool,
) -> dict[str, Any]:
    hypotheses = build_hypotheses_from_fred_manifest(
        question="newsroom research autolab",
        series_ids=series_ids,
        evidence_items=[],
        symbols=symbols,
    )
    requests = build_backtest_requests(hypotheses)

    results = [
        _serialize_result(
            run_backtest_request_from_csv(
                req,
                bars_dir=bars_dir,
                macro_dir=macro_dir,
                require_macro_filters=require_macro_filters,
            )
        )
        for req in requests
    ]

    ranked = sorted(
        results,
        key=lambda r: (
            _metric(r, "total_return_pct"),
            -abs(_metric(r, "max_drawdown_pct")),
        ),
        reverse=True,
    )

    return {
        "hypotheses": [h.__dict__ for h in hypotheses],
        "request_count": len(requests),
        "macro_filters_required": require_macro_filters,
        "top_results": ranked[:10],
        "results": results,
    }


def _compare(baseline: dict[str, Any], macro: dict[str, Any]) -> list[dict[str, Any]]:
    base_by_key = {_result_key(row): row for row in baseline.get("results", [])}
    rows: list[dict[str, Any]] = []

    for macro_row in macro.get("results", []):
        key = _result_key(macro_row)
        base_row = base_by_key.get(key)
        if not base_row:
            continue

        base_ret = _metric(base_row, "total_return_pct")
        macro_ret = _metric(macro_row, "total_return_pct")
        base_dd = _metric(base_row, "max_drawdown_pct")
        macro_dd = _metric(macro_row, "max_drawdown_pct")
        base_trades = _metric(base_row, "trade_count")
        macro_trades = _metric(macro_row, "trade_count")

        rows.append(
            {
                "hypothesis_id": key[0],
                "symbol": key[1],
                "lookback": key[2],
                "holding_days": key[3],
                "baseline_return_pct": base_ret,
                "macro_return_pct": macro_ret,
                "return_delta": macro_ret - base_ret,
                "baseline_max_drawdown_pct": base_dd,
                "macro_max_drawdown_pct": macro_dd,
                "baseline_trades": base_trades,
                "macro_trades": macro_trades,
                "macro_improved_return": macro_ret > base_ret,
                "macro_reduced_drawdown": abs(macro_dd) < abs(base_dd),
            }
        )

    rows.sort(key=lambda r: (r["return_delta"], -abs(r["macro_max_drawdown_pct"])), reverse=True)
    return rows


def _build_table(rows: list[dict[str, Any]]) -> Any:
    if not rows:
        return html.Div("No matched comparison rows.", className="paper-empty")

    header = html.Tr(
        [
            html.Th("Rank"),
            html.Th("Hypothesis"),
            html.Th("Symbol"),
            html.Th("Lookback"),
            html.Th("Hold"),
            html.Th("Base Ret"),
            html.Th("Macro Ret"),
            html.Th("Delta"),
            html.Th("Base DD"),
            html.Th("Macro DD"),
            html.Th("Trades"),
        ]
    )

    body = []
    for idx, row in enumerate(rows[:15], start=1):
        body.append(
            html.Tr(
                [
                    html.Td(str(idx)),
                    html.Td(row["hypothesis_id"]),
                    html.Td(row["symbol"]),
                    html.Td(str(row["lookback"])),
                    html.Td(str(row["holding_days"])),
                    html.Td(f"{row['baseline_return_pct']:.4f}"),
                    html.Td(f"{row['macro_return_pct']:.4f}"),
                    html.Td(f"{row['return_delta']:.4f}"),
                    html.Td(f"{row['baseline_max_drawdown_pct']:.4f}"),
                    html.Td(f"{row['macro_max_drawdown_pct']:.4f}"),
                    html.Td(f"{row['baseline_trades']:.0f} -> {row['macro_trades']:.0f}"),
                ]
            )
        )

    return html.Table([html.Thead(header), html.Tbody(body)], className="research-autolab-table")


def _summary_md(rows: list[dict[str, Any]], *, baseline: dict[str, Any], macro: dict[str, Any]) -> str:
    total = len(rows)
    improved = sum(1 for r in rows if r["macro_improved_return"])
    reduced_dd = sum(1 for r in rows if r["macro_reduced_drawdown"])
    both = sum(1 for r in rows if r["macro_improved_return"] and r["macro_reduced_drawdown"])

    best = rows[0] if rows else None
    lines = [
        "## Baseline vs macro overlay",
        "",
        f"- Hypotheses: **{len(macro.get('hypotheses', []))}**",
        f"- Matched runs: **{total}**",
        f"- Macro improved return: **{improved}/{total}**",
        f"- Macro reduced drawdown: **{reduced_dd}/{total}**",
        f"- Macro improved return and reduced drawdown: **{both}/{total}**",
        "",
    ]

    if best:
        lines += [
            "### Current top return-delta candidate",
            "",
            f"- Hypothesis: **{best['hypothesis_id']}**",
            f"- Symbol: **{best['symbol']}**",
            f"- Lookback / hold: **{best['lookback']} / {best['holding_days']}**",
            f"- Baseline return: **{best['baseline_return_pct']:.4f}**",
            f"- Macro return: **{best['macro_return_pct']:.4f}**",
            f"- Return delta: **{best['return_delta']:.4f}**",
            f"- Baseline drawdown: **{best['baseline_max_drawdown_pct']:.4f}**",
            f"- Macro drawdown: **{best['macro_max_drawdown_pct']:.4f}**",
            "",
        ]

    lines += [
        "### Safety",
        "",
        "This panel is simulation-only and advisory-only. It reads local CSV/FRED files and writes research artifacts only. It does not place orders or access a broker.",
    ]

    return "\n".join(lines)


def _write_json(path: Path, payload: Any) -> None:
    assert_safe_output_path(path)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    assert_safe_output_path(path)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _artifact_links(paths: list[Path]) -> Any:
    children = [html.Span("Artifacts: ", className="research-autolab-artifact-label")]
    for idx, path in enumerate(paths):
        if idx:
            children.append(html.Span(" | "))
        children.append(html.Code(str(path.name)))
    return html.Div(children, className="research-autolab-artifact-list")


def _refresh_fred_macro(series_ids: list[str], macro_dir: Path) -> tuple[int, dict[str, str]]:
    from services.ai.research_autolab.download_fred_macro import download_fred_graph_csv, write_csv

    macro_dir.mkdir(parents=True, exist_ok=True)
    failures: dict[str, str] = {}
    ok = 0

    for series_id in series_ids:
        try:
            rows = download_fred_graph_csv(series_id)
            write_csv(macro_dir / f"{series_id}.csv", rows)
            ok += 1
        except Exception as exc:
            failures[series_id] = str(exc)

    return ok, failures


def register_research_autolab_callbacks(app) -> None:
    @app.callback(
        Output("autolab-status", "children"),
        Output("autolab-artifacts", "children"),
        Output("autolab-top-table", "children"),
        Output("autolab-summary", "children"),
        Output("autolab-last-results", "data"),
        Input("autolab-refresh-macro", "n_clicks"),
        Input("autolab-run-comparison", "n_clicks"),
        Input("autolab-clear", "n_clicks"),
        State("autolab-bars-dir", "value"),
        State("autolab-macro-dir", "value"),
        State("autolab-symbols", "value"),
        State("autolab-series-ids", "value"),
        prevent_initial_call=True,
    )
    def _run_autolab(refresh_clicks, run_clicks, clear_clicks, bars_dir_value, macro_dir_value, symbols_value, series_ids_value):
        from dash import callback_context

        trigger = (callback_context.triggered or [{}])[0].get("prop_id", "")

        if trigger.startswith("autolab-clear"):
            return "Cleared.", "", "", "", None

        try:
            assert_simulation_only()

            bars_dir = _resolve_live_path(bars_dir_value, default="data/autolab_bars")
            macro_dir = _resolve_live_path(macro_dir_value, default="data/autolab_macro")
            out_dir = _live_root()
            symbols = _split_csv(symbols_value)
            series_ids = _split_csv(series_ids_value)

            if not series_ids:
                raise RuntimeError("Enter at least one FRED series ID.")

            if trigger.startswith("autolab-refresh-macro"):
                ok, failures = _refresh_fred_macro(series_ids, macro_dir)
                status = f"{safety_banner()} Refreshed {ok}/{len(series_ids)} FRED macro CSVs into {macro_dir}."
                if failures:
                    status += f" Failed: {', '.join(list(failures)[:6])}"
                return status, "", "", "", {"macro_refresh": {"ok": ok, "failures": failures}}

            if not run_clicks:
                return no_update, no_update, no_update, no_update, no_update

            if not symbols:
                raise RuntimeError("Enter at least one symbol.")
            if not bars_dir.exists():
                raise RuntimeError(f"Bars directory not found: {bars_dir}")
            if not macro_dir.exists():
                raise RuntimeError(f"Macro directory not found: {macro_dir}")

            baseline = _run_suite(
                series_ids=series_ids,
                symbols=symbols,
                bars_dir=bars_dir,
                macro_dir=macro_dir,
                require_macro_filters=False,
            )
            macro = _run_suite(
                series_ids=series_ids,
                symbols=symbols,
                bars_dir=bars_dir,
                macro_dir=macro_dir,
                require_macro_filters=True,
            )
            rows = _compare(baseline, macro)

            payload = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "safety": safety_banner(),
                "bars_dir": str(bars_dir),
                "macro_dir": str(macro_dir),
                "symbols": symbols,
                "series_ids": series_ids,
                "baseline": baseline,
                "macro": macro,
                "comparison": rows,
            }

            json_path = out_dir / "autolab_ui_overlay_comparison.json"
            csv_path = out_dir / "autolab_ui_overlay_comparison.csv"
            _write_json(json_path, payload)
            _write_csv(csv_path, rows)

            report_artifacts = write_report_bundle(payload, out_dir=out_dir)
            report_path = Path(report_artifacts["report_md"])
            journal_path = Path(report_artifacts["journal_csv"])

            status = (
                f"{safety_banner()} Compared {len(rows)} matched simulated runs. "
                f"Detailed report and strategy journal updated. "
                f"Journal rows added: {report_artifacts.get('journal_rows_added', '0')}."
            )
            return (
                status,
                _artifact_links([json_path, csv_path, report_path, journal_path]),
                _build_table(rows),
                _summary_md(rows, baseline=baseline, macro=macro),
                payload,
            )

        except Exception as exc:
            return f"Research Autolab failed safely: {exc}", "", "", "", None
