from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd


LIVE_ROOT = Path(__file__).resolve().parents[1]
if str(LIVE_ROOT) not in sys.path:
    sys.path.insert(0, str(LIVE_ROOT))

from services.watch_chart_state import normalize_watch_chart_state_for_render


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Watch chart state return contract.")
    parser.add_argument("--timeframe", default="1 day")
    args = parser.parse_args()

    tf = args.timeframe

    if str(tf).lower().strip() in {"1 day", "1d", "day", "daily"}:
        bars = pd.DataFrame(
            {
                "time": pd.date_range("2026-06-01", periods=15, freq="D"),
                "open": [100.0] * 15,
                "high": [101.0] * 15,
                "low": [99.0] * 15,
                "close": [100.5] * 15,
                "volume": [1000] * 15,
            }
        )
    else:
        bars = pd.DataFrame(
            {
                "time": pd.date_range("2026-06-22 09:30:00", periods=7, freq="h"),
                "open": [100.0] * 7,
                "high": [101.0] * 7,
                "low": [99.0] * 7,
                "close": [100.5] * 7,
                "volume": [1000] * 7,
            }
        )

    stale_state = {
        "mode": "manual",
        "range_key": "1D",
        "x_range": ["2026-06-22 09:30:00", "2026-06-22 10:00:00"],
        "y_range": None,
    }

    result = normalize_watch_chart_state_for_render(
        stale_state,
        bars,
        display_timeframe=tf,
        price_source="replay",
        trigger_id="replay-render-trigger",
    )

    if not isinstance(result, tuple) or len(result) != 2:
        raise SystemExit(f"BAD: expected 2-tuple, got {type(result).__name__}: {result!r}")

    normalized, default_range = result

    print(f"timeframe={tf}")
    print(f"default_range={default_range}")
    print(f"normalized={normalized}")

    if str(tf).lower().strip() in {"1 day", "1d", "day", "daily"}:
        if default_range != "MAX" or normalized.get("range_key") != "MAX":
            raise SystemExit("BAD: daily replay should normalize to MAX")

    if str(tf).lower().strip() in {"1 hour", "1h", "hour"}:
        if default_range != "1D" or normalized.get("range_key") != "1D":
            raise SystemExit("BAD: one-hour replay should normalize to 1D")

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
