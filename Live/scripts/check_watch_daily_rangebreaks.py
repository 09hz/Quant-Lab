from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


def main() -> int:
    live_root = Path(__file__).resolve().parents[1]
    if str(live_root) not in sys.path:
        sys.path.insert(0, str(live_root))

    from renderers.watch_chart_renderer import WatchChartRenderer

    bars = pd.DataFrame(
        {
            "time": pd.to_datetime(["2026-06-01", "2026-06-02", "2026-06-03"]),
            "open": [100.0, 101.0, 102.0],
            "high": [102.0, 103.0, 104.0],
            "low": [99.0, 100.0, 101.0],
            "close": [101.0, 102.0, 103.0],
            "volume": [1000, 1200, 1100],
        }
    )

    renderer = WatchChartRenderer()
    fig = renderer.base_candles(
        chart_bars=bars,
        symbol="TEST",
        display_timeframe="1 day",
        current_price=103.0,
    )

    if not fig.data:
        raise SystemExit("FAIL: no traces were rendered")

    xaxis = fig.layout.xaxis
    rangebreaks = getattr(xaxis, "rangebreaks", None)

    print(f"trace_count={len(fig.data)}")
    print(f"xaxis_type={getattr(xaxis, 'type', None)}")
    print(f"xaxis_range={getattr(xaxis, 'range', None)}")
    print(f"rangebreaks={rangebreaks}")

    if rangebreaks not in (None, (), []):
        try:
            if len(rangebreaks) != 0:
                raise SystemExit("FAIL: daily rangebreaks were not cleared")
        except TypeError:
            raise SystemExit("FAIL: daily rangebreaks were not cleared")

    print("OK: Watch daily renderer force-clears intraday rangebreaks and renders candles.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
