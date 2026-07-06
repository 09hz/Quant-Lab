from __future__ import annotations

import argparse
import json
from pathlib import Path

from .planner import build_backtest_requests, build_hypotheses_from_fred_manifest
from .runner_stub import run_backtest_request
from .reporter import write_report_bundle
from .sim_guard import assert_no_broker_modules_loaded, assert_safe_output_path, assert_simulation_only, safety_banner


def main() -> int:
    parser = argparse.ArgumentParser(description="Research autolab planning/backtest smoke test.")
    parser.add_argument("--series-ids", default="", help="Comma-separated FRED series IDs.")
    parser.add_argument("--symbols", default="SPY,QQQ,XLK,SMH,XLI,IWM", help="Comma-separated symbols to test.")
    parser.add_argument("--out", type=Path, default=None, help="Optional JSON output path.")
    parser.add_argument("--bars-dir", type=Path, default=None, help="Optional folder containing SYMBOL.csv OHLCV files.")
    parser.add_argument("--run-csv-backtests", action="store_true", help="Run deterministic CSV backtests instead of stub results.")
    parser.add_argument("--macro-dir", type=Path, default=None, help="Optional folder containing FRED SERIES_ID.csv files.")
    parser.add_argument("--require-macro-filters", action="store_true", help="Require hypothesis-specific FRED filters for entries.")
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument("--quantity", type=int, default=1)
    args = parser.parse_args()

    assert_simulation_only()
    assert_safe_output_path(args.out)
    assert_no_broker_modules_loaded()
    print(safety_banner())


    series_ids = [s.strip().upper() for s in args.series_ids.split(",") if s.strip()]
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    hypotheses = build_hypotheses_from_fred_manifest(
        question="auto research smoke test",
        series_ids=series_ids,
        evidence_items=[],
        symbols=symbols,
    )
    requests = build_backtest_requests(hypotheses)

    if args.run_csv_backtests:
        if args.bars_dir is None:
            raise SystemExit("--bars-dir is required with --run-csv-backtests")
        from .csv_runner import run_backtest_request_from_csv

        results = [
            run_backtest_request_from_csv(
                req,
                bars_dir=args.bars_dir,
                initial_cash=args.initial_cash,
                quantity=args.quantity,
                macro_dir=args.macro_dir,
                require_macro_filters=args.require_macro_filters,
            )
            for req in requests
        ]
    else:
        results = [run_backtest_request(req) for req in requests]

    ranked = sorted(
        results,
        key=lambda r: (
            float(r.metrics.get("total_return_pct", r.metrics.get("cagr", 0.0)) or 0.0),
            -abs(float(r.metrics.get("max_drawdown_pct", 0.0) or 0.0)),
        ),
        reverse=True,
    )

    payload = {
        "hypotheses": [h.__dict__ for h in hypotheses],
        "request_count": len(requests),
        "macro_filters_required": bool(args.require_macro_filters),
        "top_results": [
            {
                "request": r.request.__dict__,
                "metrics": r.metrics,
                "notes": r.notes,
                "passed_safety_checks": r.passed_safety_checks,
            }
            for r in ranked[:10]
        ],
        "results": [
            {
                "request": r.request.__dict__,
                "metrics": r.metrics,
                "notes": r.notes,
                "passed_safety_checks": r.passed_safety_checks,
            }
            for r in results
        ],
    }

    text = json.dumps(payload, indent=2, default=str)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
