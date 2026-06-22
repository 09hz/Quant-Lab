from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd

LIVE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = LIVE_ROOT.parent
if str(LIVE_ROOT) not in sys.path:
    sys.path.insert(0, str(LIVE_ROOT))

try:
    from services.market_data.base import normalize_ohlcv
except Exception as exc:
    normalize_ohlcv = None
    NORMALIZE_IMPORT_ERROR = exc
else:
    NORMALIZE_IMPORT_ERROR = None

SUPPORTED_SUFFIXES = {".csv", ".parquet", ".pq", ".feather"}


def resolve_root(value: str | None) -> Path:
    root_text = value or os.getenv("CSV_MARKET_DATA_ROOT", "cache/replay")
    root = Path(root_text)
    if not root.is_absolute():
        root = REPO_ROOT / root
    return root.resolve()


def load_file(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    if suffix == ".feather":
        return pd.read_feather(path)
    raise ValueError(f"Unsupported file type: {suffix}")


def guess_timeframe(path: Path) -> str:
    text = str(path).lower()
    if any(x in text for x in ["1min", "1_min", "1m", "1-min"]):
        return "1 min"
    if any(x in text for x in ["5min", "5_min", "5m", "5-min"]):
        return "5 mins"
    if any(x in text for x in ["15min", "15_min", "15m", "15-min"]):
        return "15 mins"
    if any(x in text for x in ["daily", "1day", "1_day", "1d"]):
        return "1 day"
    return ""


def inspect_one(path: Path, root: Path, validate: bool) -> dict:
    result = {
        "path": str(path.relative_to(root)),
        "size_bytes": path.stat().st_size,
        "timeframe_guess": guess_timeframe(path),
        "status": "unchecked",
        "rows": None,
        "columns": [],
        "first_time": None,
        "last_time": None,
        "message": "",
    }

    try:
        df = load_file(path)
        result["rows"] = int(len(df))
        result["columns"] = [str(c) for c in df.columns]

        if validate:
            if normalize_ohlcv is None:
                result["status"] = "warning"
                result["message"] = f"normalize_ohlcv import failed: {NORMALIZE_IMPORT_ERROR}"
                return result

            df = normalize_ohlcv(df)
            result["rows"] = int(len(df))
            result["columns"] = [str(c) for c in df.columns]
            if not df.empty:
                result["first_time"] = str(df.iloc[0]["time"])
                result["last_time"] = str(df.iloc[-1]["time"])

        result["status"] = "ok"
        result["message"] = "Loaded successfully."
        return result

    except Exception as exc:
        result["status"] = "failed"
        result["message"] = str(exc)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect local market-data cache files.")
    parser.add_argument("--root", default=None, help="Defaults to CSV_MARKET_DATA_ROOT or cache/replay.")
    parser.add_argument("--symbol", default=None, help="Optional symbol filter, such as MSFT.")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-validate", action="store_true")
    args = parser.parse_args()

    root = resolve_root(args.root)
    files = []
    if root.exists():
        files = sorted(
            p for p in root.rglob("*")
            if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
        )

    if args.symbol:
        needle = args.symbol.upper()
        files = [p for p in files if needle in str(p).upper()]

    reports = [inspect_one(p, root, validate=not args.no_validate) for p in files]

    if args.json:
        print(json.dumps({"root": str(root), "files_found": len(reports), "reports": reports}, indent=2))
    else:
        print("Market Data Cache Inspection")
        print(f"Root: {root}")
        print(f"Files found: {len(reports)}")
        print()

        if not reports:
            print("No .csv/.parquet/.pq/.feather files found.")
            return 0

        for report in reports[: max(1, args.limit)]:
            print(f"- {report['path']}")
            print(f"  status: {report['status']}")
            print(f"  size_bytes: {report['size_bytes']}")
            print(f"  rows: {report['rows']}")
            if report["timeframe_guess"]:
                print(f"  timeframe_guess: {report['timeframe_guess']}")
            if report["first_time"] or report["last_time"]:
                print(f"  time_range: {report['first_time']} -> {report['last_time']}")
            if report["columns"]:
                print(f"  columns: {', '.join(report['columns'])}")
            print(f"  message: {report['message']}")
            print()

        if len(reports) > args.limit:
            print(f"Showing first {args.limit} files.")

    return 1 if any(r["status"] == "failed" for r in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
