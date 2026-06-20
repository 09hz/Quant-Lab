from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def find_live_dir() -> Path:
    current = Path(__file__).resolve()

    # Expected: Live/scripts/check_market_data_provider.py
    live_dir = current.parents[1]
    if (live_dir / "app.py").exists():
        return live_dir

    cwd = Path.cwd().resolve()
    if (cwd / "Live" / "app.py").exists():
        return cwd / "Live"

    if cwd.name.lower() == "live" and (cwd / "app.py").exists():
        return cwd

    raise RuntimeError("Could not locate Live directory.")


LIVE_DIR = find_live_dir()
REPO_ROOT = LIVE_DIR.parent

# Match how Live/app.py imports project modules.
if str(LIVE_DIR) not in sys.path:
    sys.path.insert(0, str(LIVE_DIR))


def load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return

    env_path = LIVE_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    root_env_path = REPO_ROOT / ".env"
    if root_env_path.exists():
        load_dotenv(root_env_path)


def build_provider_for_check(provider_name: str):
    """
    Build the configured provider without starting Dash.

    IBKR mode:
        Creates RealTimeIB but does not call rt.start() by default.
        This avoids opening an IBKR connection just to check imports/wrapping.

    CSV mode:
        Uses CSVMarketDataProvider directly.
    """
    provider_name = str(provider_name or os.getenv("MARKET_DATA_PROVIDER", "ibkr")).lower().strip()

    if provider_name == "ibkr":
        from core.RealTime import RealTimeIB
        from services.market_data.ibkr_provider import IBKRMarketDataProvider

        host = os.getenv("IBKR_HOST", "127.0.0.1")
        port = int(os.getenv("IBKR_PORT", "4001") or 4001)
        client_id_raw = os.getenv("IBKR_CLIENT_ID", "").strip()
        client_id = int(client_id_raw) if client_id_raw else None

        rt = RealTimeIB(host=host, port=port, client_id=client_id)
        return IBKRMarketDataProvider(rt)

    if provider_name == "csv":
        from services.market_data.csv_provider import CSVMarketDataProvider

        root_dir = os.getenv("CSV_MARKET_DATA_ROOT", "cache/replay")
        return CSVMarketDataProvider(root_dir=root_dir)

    # Fall back to provider_factory if future providers are added.
    from services.market_data.provider_factory import build_market_data_provider

    try:
        return build_market_data_provider(provider_name=provider_name)
    except TypeError:
        return build_market_data_provider()


def main() -> int:
    load_dotenv_if_available()

    parser = argparse.ArgumentParser(
        description="Check Stock Visualizer Live market data provider health."
    )
    parser.add_argument(
        "--provider",
        default=os.getenv("MARKET_DATA_PROVIDER", "ibkr"),
        help="Provider name, for example ibkr or csv.",
    )
    parser.add_argument(
        "--symbol",
        default=os.getenv("DEFAULT_SYMBOL", "MSFT"),
        help="Ticker symbol to test.",
    )
    parser.add_argument(
        "--timeframe",
        default=os.getenv("DEFAULT_TIMEFRAME", "1 min"),
        help="Timeframe to test.",
    )
    parser.add_argument(
        "--skip-history",
        action="store_true",
        help="Skip get_history() call. Useful for IBKR if Gateway/TWS is not running.",
    )
    parser.add_argument(
        "--skip-snapshot",
        action="store_true",
        help="Skip get_snapshot() call.",
    )
    parser.add_argument(
        "--require-snapshot",
        action="store_true",
        help="Treat get_snapshot() failure as fatal. Default is warning only.",
    )

    args = parser.parse_args()

    from services.market_data.provider_health import check_provider_health

    provider = build_provider_for_check(args.provider)

    result = check_provider_health(
        provider,
        symbol=args.symbol,
        timeframe=args.timeframe,
        fetch_history=not args.skip_history,
        fetch_snapshot=not args.skip_snapshot,
        require_snapshot=args.require_snapshot,
    )

    print()
    for line in result.to_lines():
        print(line)
    print()

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
