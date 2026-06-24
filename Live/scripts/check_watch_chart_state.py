from __future__ import annotations

from pathlib import Path
import sys

LIVE_ROOT = Path(__file__).resolve().parents[1]
if str(LIVE_ROOT) not in sys.path:
    sys.path.insert(0, str(LIVE_ROOT))

import argparse

import pandas as pd

from services.watch_chart_state import normalize_watch_chart_state_for_render


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Watch chart state normalization.")
    parser.add_argument("--timeframe", default="1 hour")
    args = parser.parse_args()

    bars = pd.DataFrame(
        {
            "time": pd.date_range("2025-01-01 09:30:00", periods=20, freq="h"),
            "open": [100.0] * 20,
            "high": [101.0] * 20,
            "low": [99.0] * 20,
            "close": [100.5] * 20,
            "volume": [1000] * 20,
        }
    )

    stale_state = {
        "mode": "manual",
        "range_key": "1D",
        "x_range": ["2024-01-01", "2024-01-02"],
        "y_range": None,
    }

    normalized, default_range = normalize_watch_chart_state_for_render(
        stale_state,
        bars,
        display_timeframe=args.timeframe,
        price_source="replay",
        trigger_id="watch-load-request",
    )

    print(f"timeframe={args.timeframe}")
    print(f"default_range={default_range}")
    print(f"normalized={normalized}")

    if args.timeframe in {"1 hour", "1 day"} and normalized.get("range_key") == "1D":
        raise SystemExit("Expected higher-timeframe default range, got 1D")

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
