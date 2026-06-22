from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

LIVE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = LIVE_ROOT.parent
if str(LIVE_ROOT) not in sys.path:
    sys.path.insert(0, str(LIVE_ROOT))

from services.market_data.base import normalize_ohlcv
from services.market_data.ibkr_provider import IBKRMarketDataProvider


def import_realtime_ib() -> Any:
    for module_name in ["core.RealTime", "core.realtime", "RealTime"]:
        try:
            module = __import__(module_name, fromlist=["RealTimeIB"])
            return getattr(module, "RealTimeIB")
        except Exception:
            continue
    raise ImportError("Could not import RealTimeIB from core.RealTime/core.realtime/RealTime.")


def safe_timeframe(value: str) -> str:
    return value.lower().replace(" ", "_").replace("/", "_").replace("\\", "_").replace(":", "")


def resolve_output(args: argparse.Namespace) -> Path:
    if args.output:
        path = Path(args.output)
        return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()

    root = Path(args.root or os.getenv("CSV_MARKET_DATA_ROOT", "cache/replay"))
    if not root.is_absolute():
        root = REPO_ROOT / root

    tf = safe_timeframe(args.timeframe)
    name = f"{args.symbol.upper()}_{tf}_{args.start[:10]}_to_{args.end[:10]}.csv"
    return (root / args.symbol.upper() / tf / name).resolve()


def build_rt(args: argparse.Namespace) -> Any:
    RealTimeIB = import_realtime_ib()
    try:
        return RealTimeIB()
    except TypeError:
        return RealTimeIB(host=args.host, port=args.port, client_id=args.client_id)


def maybe_start(rt: Any, args: argparse.Namespace) -> None:
    start = getattr(rt, "start", None)
    if not callable(start):
        print("[WARN] RealTimeIB has no start() method.")
        return

    for call in (
        lambda: start(),
        lambda: start(host=args.host, port=args.port, client_id=args.client_id),
        lambda: start(client_id=args.client_id),
    ):
        try:
            call()
            print("[INFO] RealTimeIB start attempted.")
            return
        except TypeError:
            continue
        except Exception as exc:
            print(f"[WARN] RealTimeIB start attempt failed: {exc}")
            return


def main() -> int:
    parser = argparse.ArgumentParser(description="Export IBKR historical bars to local CSV.")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", default="1 min")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output", default=None)
    parser.add_argument("--root", default=None)
    parser.add_argument("--host", default=os.getenv("IBKR_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("IBKR_PORT", "7497")))
    parser.add_argument("--client-id", type=int, default=int(os.getenv("IBKR_CLIENT_ID", "21")))
    parser.add_argument("--no-start", action="store_true")
    args = parser.parse_args()

    args.symbol = args.symbol.upper().strip()
    print("IBKR Historical CSV Export")
    print(f"Symbol: {args.symbol}")
    print(f"Timeframe: {args.timeframe}")
    print(f"Range: {args.start} -> {args.end}")

    rt = build_rt(args)
    if not args.no_start:
        maybe_start(rt, args)

    provider = IBKRMarketDataProvider(rt)
    df = provider.get_history(args.symbol, args.timeframe, args.start, args.end)

    if df is None or df.empty:
        print("[ERROR] No rows returned.")
        return 2

    df = normalize_ohlcv(df)
    out = resolve_output(args)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)

    print(f"[OK] Exported {len(df)} rows.")
    print(f"[OK] Wrote: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
