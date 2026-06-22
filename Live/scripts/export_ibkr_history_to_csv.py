from __future__ import annotations

import argparse
import os
import sys
import time
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
    return (
        str(value or "1 min")
        .lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "")
    )


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


def apply_ibkr_env(args: argparse.Namespace) -> None:
    """
    Make connection settings visible to RealTimeIB variants that read env vars.
    """
    env_values = {
        "IBKR_HOST": str(args.host),
        "IBKR_PORT": str(args.port),
        "IBKR_CLIENT_ID": str(args.client_id),
        "IB_HOST": str(args.host),
        "IB_PORT": str(args.port),
        "IB_CLIENT_ID": str(args.client_id),
    }
    for key, value in env_values.items():
        os.environ[key] = value


def build_rt(args: argparse.Namespace) -> Any:
    RealTimeIB = import_realtime_ib()

    attempts = [
        ("RealTimeIB(host=..., port=..., client_id=...)", lambda: RealTimeIB(host=args.host, port=args.port, client_id=args.client_id)),
        ("RealTimeIB(host=..., port=..., clientId=...)", lambda: RealTimeIB(host=args.host, port=args.port, clientId=args.client_id)),
        ("RealTimeIB(... positional ...)", lambda: RealTimeIB(args.host, args.port, args.client_id)),
        ("RealTimeIB()", lambda: RealTimeIB()),
    ]

    last_type_error: Exception | None = None
    for label, factory in attempts:
        try:
            rt = factory()
            print(f"[INFO] Built {label}")
            attach_connection_settings(rt, args)
            return rt
        except TypeError as exc:
            last_type_error = exc
            continue

    raise TypeError(f"Could not construct RealTimeIB. Last error: {last_type_error}")


def attach_connection_settings(rt: Any, args: argparse.Namespace) -> None:
    """
    Best-effort attribute injection for RealTimeIB variants that store connection
    settings on the instance before start().
    """
    candidates = {
        "host": args.host,
        "ib_host": args.host,
        "_host": args.host,
        "IBKR_HOST": args.host,
        "port": args.port,
        "ib_port": args.port,
        "_port": args.port,
        "IBKR_PORT": args.port,
        "client_id": args.client_id,
        "clientId": args.client_id,
        "_client_id": args.client_id,
        "IBKR_CLIENT_ID": args.client_id,
    }

    for attr, value in candidates.items():
        try:
            if hasattr(rt, attr):
                setattr(rt, attr, value)
        except Exception:
            pass


def ib_connection_state(rt: Any) -> bool | None:
    ib = getattr(rt, "ib", None) or getattr(rt, "_ib", None) or getattr(rt, "client", None)

    if ib is None:
        return None

    is_connected = getattr(ib, "isConnected", None)
    if callable(is_connected):
        try:
            return bool(is_connected())
        except Exception:
            return None

    connected = getattr(ib, "connected", None)
    if connected is not None:
        try:
            return bool(connected)
        except Exception:
            return None

    return None


def wait_for_connection(rt: Any, seconds: float) -> bool | None:
    deadline = time.time() + max(0.0, float(seconds or 0.0))
    state = ib_connection_state(rt)

    while state is not True and time.time() < deadline:
        time.sleep(0.25)
        state = ib_connection_state(rt)

    return state


def maybe_start(rt: Any, args: argparse.Namespace) -> bool | None:
    start = getattr(rt, "start", None)
    if not callable(start):
        print("[WARN] RealTimeIB has no start() method.")
        return ib_connection_state(rt)

    attempts = [
        ("start(symbol=..., timeframe=...)", lambda: start(symbol=args.symbol, timeframe=args.timeframe)),
        ("start(symbol=...)", lambda: start(symbol=args.symbol)),
        ("start(... positional symbol)", lambda: start(args.symbol)),
        ("start(host=..., port=..., client_id=..., symbol=...)", lambda: start(host=args.host, port=args.port, client_id=args.client_id, symbol=args.symbol)),
        ("start(host=..., port=..., clientId=..., symbol=...)", lambda: start(host=args.host, port=args.port, clientId=args.client_id, symbol=args.symbol)),
        ("start(port=..., client_id=..., symbol=...)", lambda: start(port=args.port, client_id=args.client_id, symbol=args.symbol)),
        ("start(port=..., clientId=..., symbol=...)", lambda: start(port=args.port, clientId=args.client_id, symbol=args.symbol)),
        ("start(client_id=..., symbol=...)", lambda: start(client_id=args.client_id, symbol=args.symbol)),
        ("start(clientId=..., symbol=...)", lambda: start(clientId=args.client_id, symbol=args.symbol)),
        ("start(host=..., port=..., client_id=...)", lambda: start(host=args.host, port=args.port, client_id=args.client_id)),
        ("start(host=..., port=..., clientId=...)", lambda: start(host=args.host, port=args.port, clientId=args.client_id)),
        ("start(port=..., client_id=...)", lambda: start(port=args.port, client_id=args.client_id)),
        ("start(port=..., clientId=...)", lambda: start(port=args.port, clientId=args.client_id)),
        ("start(client_id=...)", lambda: start(client_id=args.client_id)),
        ("start(clientId=...)", lambda: start(clientId=args.client_id)),
        ("start()", lambda: start()),
    ]

    last_type_error: Exception | None = None
    for label, call in attempts:
        try:
            call()
            print(f"[INFO] RealTimeIB {label} attempted.")
            state = wait_for_connection(rt, args.connect_wait)
            if state is True:
                print("[INFO] IBKR connection detected after RealTimeIB.start().")
            return state
        except TypeError as exc:
            last_type_error = exc
            continue
        except Exception as exc:
            print(f"[WARN] RealTimeIB {label} failed: {exc}")
            return wait_for_connection(rt, args.connect_wait)

    print(f"[WARN] Could not call RealTimeIB.start(). Last TypeError: {last_type_error}")
    return ib_connection_state(rt)


def direct_connect_fallback(rt: Any, args: argparse.Namespace) -> bool | None:
    """
    Fallback for exporter usage only.

    Some RealTimeIB.start() implementations require a symbol and handle live
    subscription startup, but the historical exporter only needs the underlying
    IB object connected. If start() did not connect, try ib.connect(...) directly.
    """
    ib = getattr(rt, "ib", None) or getattr(rt, "_ib", None)
    if ib is None:
        print("[WARN] Direct IB connect fallback skipped: no rt.ib/_ib object found.")
        return ib_connection_state(rt)

    connect = getattr(ib, "connect", None)
    if not callable(connect):
        print("[WARN] Direct IB connect fallback skipped: ib.connect is not callable.")
        return ib_connection_state(rt)

    if ib_connection_state(rt) is True:
        return True

    attempts = [
        ("ib.connect(host, port, clientId=..., timeout=...)", lambda: connect(args.host, args.port, clientId=args.client_id, timeout=args.connect_timeout)),
        ("ib.connect(host, port, client_id=..., timeout=...)", lambda: connect(args.host, args.port, client_id=args.client_id, timeout=args.connect_timeout)),
        ("ib.connect(host, port, clientId=...)", lambda: connect(args.host, args.port, clientId=args.client_id)),
        ("ib.connect(host, port, client_id=...)", lambda: connect(args.host, args.port, client_id=args.client_id)),
        ("ib.connect(host, port, clientId positional)", lambda: connect(args.host, args.port, args.client_id)),
    ]

    last_type_error: Exception | None = None
    for label, call in attempts:
        try:
            print(f"[INFO] Trying direct {label}")
            call()
            state = wait_for_connection(rt, args.connect_wait)
            if state is True:
                print("[INFO] IBKR connection detected after direct ib.connect fallback.")
            return state
        except TypeError as exc:
            last_type_error = exc
            continue
        except Exception as exc:
            print(f"[WARN] Direct {label} failed: {exc}")
            return wait_for_connection(rt, args.connect_wait)

    print(f"[WARN] Direct IB connect fallback had no compatible signature. Last TypeError: {last_type_error}")
    return ib_connection_state(rt)


def print_connection_help(args: argparse.Namespace) -> None:
    print()
    print("[ERROR] IBKR is not connected.")
    print(f"        Host: {args.host}")
    print(f"        Port: {args.port}")
    print(f"        Client ID: {args.client_id}")
    print()
    print("For IB Gateway, confirm:")
    print("  1. IB Gateway is fully logged in.")
    print("  2. API socket clients are enabled.")
    print("  3. The configured socket port matches the command.")
    print("  4. The selected client ID is not already in use.")
    print("  5. Your Gateway session type matches the port you chose.")
    print()
    print("Common local ports:")
    print("  IB Gateway live:  4001")
    print("  IB Gateway paper: 4002")
    print("  TWS live:         7496")
    print("  TWS paper:        7497")
    print()
    print("Try a different client ID if the Dash app is already connected:")
    print('  python .\\Live\\scripts\\export_ibkr_history_to_csv.py --symbol MSFT --timeframe "1 min" --start 2026-06-15 --end 2026-06-18 --port 4001 --client-id 31')
    print()
    print("Or test the low-level connection:")
    print('  python -c "from ib_async import IB; ib=IB(); ib.connect(\'127.0.0.1\', 4001, clientId=91, timeout=10); print(ib.isConnected()); ib.disconnect()"')


def main() -> int:
    parser = argparse.ArgumentParser(description="Export IBKR historical bars to local CSV.")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", default="1 min")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output", default=None)
    parser.add_argument("--root", default=None)
    parser.add_argument("--host", default=os.getenv("IBKR_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("IBKR_PORT", "4001")))
    parser.add_argument("--client-id", type=int, default=int(os.getenv("IBKR_CLIENT_ID", "21")))
    parser.add_argument("--gateway-live", action="store_true", help="Shortcut: set --port 4001.")
    parser.add_argument("--gateway-paper", action="store_true", help="Shortcut: set --port 4002.")
    parser.add_argument("--tws-live", action="store_true", help="Shortcut: set --port 7496.")
    parser.add_argument("--tws-paper", action="store_true", help="Shortcut: set --port 7497.")
    parser.add_argument("--connect-wait", type=float, default=8.0)
    parser.add_argument("--connect-timeout", type=float, default=10.0)
    parser.add_argument("--no-start", action="store_true")
    parser.add_argument("--no-direct-connect-fallback", action="store_true")
    args = parser.parse_args()

    if args.gateway_live:
        args.port = 4001
    if args.gateway_paper:
        args.port = 4002
    if args.tws_live:
        args.port = 7496
    if args.tws_paper:
        args.port = 7497

    args.symbol = args.symbol.upper().strip()
    apply_ibkr_env(args)

    print("IBKR Historical CSV Export")
    print(f"Symbol: {args.symbol}")
    print(f"Timeframe: {args.timeframe}")
    print(f"Range: {args.start} -> {args.end}")
    print(f"IBKR host: {args.host}")
    print(f"IBKR port: {args.port}")
    print(f"IBKR client id: {args.client_id}")

    rt = build_rt(args)

    connected = ib_connection_state(rt)
    if not args.no_start and connected is not True:
        connected = maybe_start(rt, args)

    if (
        connected is not True
        and not args.no_direct_connect_fallback
        and not args.no_start
    ):
        connected = direct_connect_fallback(rt, args)

    connected = ib_connection_state(rt)
    if connected is False:
        print_connection_help(args)
        return 3

    if connected is None:
        print("[WARN] Could not confirm IBKR connection state from RealTimeIB internals.")
        print("       Continuing; the history request will prove whether the connection is usable.")

    provider = IBKRMarketDataProvider(rt)

    try:
        df = provider.get_history(args.symbol, args.timeframe, args.start, args.end)
    except ConnectionError:
        print_connection_help(args)
        return 3
    except Exception as exc:
        if "not connected" in str(exc).lower():
            print_connection_help(args)
            return 3
        print()
        print(f"[ERROR] IBKR export failed: {exc}")
        print("        Re-run with a small date range and confirm Gateway is connected.")
        return 4

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
