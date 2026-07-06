from __future__ import annotations

from pathlib import Path
import argparse
import subprocess
import sys


def _bootstrap_import_path() -> Path:
    here = Path(__file__).resolve()
    live_root = here.parents[3]
    repo_root = here.parents[4]
    for path in (str(live_root), str(repo_root)):
        if path not in sys.path:
            sys.path.insert(0, path)
    return live_root


def main() -> int:
    live_root = _bootstrap_import_path()

    parser = argparse.ArgumentParser(description="Bootstrap bars CSV then run Auto Lab sized CSV mutation/retest.")
    parser.add_argument("--symbol", default="AMD")
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="")
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument("--local-only", action="store_true", help="Disable yfinance fallback.")
    parser.add_argument("--yfinance-first", action="store_true", help="Try yfinance before local cache.")
    parser.add_argument("--allow-chained-mutations", action="store_true")
    parser.add_argument("--max-parent-strategies", type=int, default=999)
    parser.add_argument("--max-mutations-per-parent", type=int, default=4)
    parser.add_argument("--max-total-runs", type=int, default=20)
    parser.add_argument("--mutate-quantity", action="store_true")
    parser.add_argument("--sizing-mode", default="percent_cash_exposure", choices=["fixed_quantity", "max_affordable_shares", "percent_cash_exposure"])
    parser.add_argument("--cash-exposure-pct", type=float, default=95.0)
    parser.add_argument("--fixed-quantity", type=int, default=10)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    from services.ai.auto_lab_orchestrator.bars_bootstrapper import bootstrap_bars_csv
    from services.ai.auto_lab_orchestrator.generation_control import find_latest_parent_run_id

    symbol = args.symbol.upper().strip() or "AMD"
    try:
        result = bootstrap_bars_csv(
            live_root=live_root,
            symbol=symbol,
            start=args.start,
            end=args.end,
            timeframe=args.timeframe,
            prefer_local=not args.yfinance_first,
            allow_yfinance=not args.local_only,
        )
    except Exception as exc:
        print("BAR BOOTSTRAP FAILED")
        print(f"{exc.__class__.__name__}: {exc}")
        print()
        print("Options:")
        print("1. Install yfinance in your venv: python -m pip install yfinance")
        print(r"2. Or place a CSV at: Live\data\market_bars\<SYMBOL>_1d.csv")
        print("3. Or run with --local-only after adding local data.")
        return 2 if args.strict else 0

    print("BAR BOOTSTRAP COMPLETE")
    print(f"symbol: {result.symbol}")
    print(f"source: {result.source}")
    print(f"csv_path: {result.csv_path}")
    print(f"rows: {result.row_count}")
    print(f"first_date: {result.first_date}")
    print(f"last_date: {result.last_date}")
    if result.warnings:
        for warning in result.warnings:
            print(f"warning: {warning}")

    parent_run_id = ""
    if not args.allow_chained_mutations:
        parent_run_id, _parent_run_dir, _payload = find_latest_parent_run_id(
            live_root,
            allow_chained_mutations=False,
        )
        if parent_run_id:
            print(f"Using latest gen0/original-seed parent run: {parent_run_id}")
        else:
            print("No gen0/original parent run found; csv sized runner will discover seed candidates.")
            parent_run_id = "__force_csv_baseline__"
    else:
        print("Chained mutations enabled; latest eligible mutation run may be used as parent.")

    runner = live_root / "services" / "ai" / "auto_lab_orchestrator" / "csv_mutation_retest_sized.py"
    cmd = [
        sys.executable,
        str(runner),
        "--symbol",
        symbol,
        "--csv-path",
        result.csv_path,
        "--start",
        args.start,
        "--max-parent-strategies",
        str(args.max_parent_strategies),
        "--max-mutations-per-parent",
        str(args.max_mutations_per_parent),
        "--max-total-runs",
        str(args.max_total_runs),
        "--sizing-mode",
        args.sizing_mode,
        "--cash-exposure-pct",
        str(args.cash_exposure_pct),
        "--fixed-quantity",
        str(args.fixed_quantity),
    ]
    if args.end:
        cmd.extend(["--end", args.end])
    if parent_run_id and not args.allow_chained_mutations:
        cmd.extend(["--run-id", parent_run_id])
    if args.allow_chained_mutations:
        cmd.append("--allow-chained-mutations")
    if args.mutate_quantity:
        cmd.append("--mutate-quantity")
    if args.strict:
        cmd.append("--strict")

    print()
    print("RUNNING SIZED CSV MUTATION RETEST")
    print(" ".join(f'"{part}"' if " " in part else part for part in cmd))

    child = subprocess.run(cmd, cwd=str(live_root.parent), text=True)
    return child.returncode


if __name__ == "__main__":
    raise SystemExit(main())
