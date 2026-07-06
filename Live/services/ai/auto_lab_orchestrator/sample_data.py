from __future__ import annotations

from datetime import date, timedelta
import math


def make_sample_bars(symbol: str = "AMD", days: int = 180) -> list[dict]:
    """
    Deterministic synthetic OHLCV bars for self-test only.

    The data is intentionally fake. It exercises the orchestration loop without
    hitting external APIs or the user's market data store.
    """
    bars: list[dict] = []
    start = date(2024, 1, 2)
    for i in range(days):
        trend = 0.10 * i
        cycle = math.sin(i / 8.0) * 4.0
        shock = -7.0 if i in (45, 92, 137) else 0.0
        close = max(10.0, 100.0 + trend + cycle + shock)
        open_ = close * (1.0 + math.sin(i / 5.0) * 0.002)
        high = max(open_, close) * 1.012
        low = min(open_, close) * 0.988
        volume = 50_000_000 + int(math.sin(i / 9.0) * 4_000_000)
        bars.append(
            {
                "date": (start + timedelta(days=i)).isoformat(),
                "symbol": symbol,
                "open": round(open_, 4),
                "high": round(high, 4),
                "low": round(low, 4),
                "close": round(close, 4),
                "volume": volume,
            }
        )
    return bars


def make_sample_bars_dataframe(symbol: str = "AMD", days: int = 180):
    """
    Return synthetic bars as pandas DataFrame when pandas is available.

    Core StrategyEngine/BackTestEngine paths commonly expect DataFrame input.
    """
    bars = make_sample_bars(symbol=symbol, days=days)
    try:
        import pandas as pd
    except Exception:
        return bars

    df = pd.DataFrame(bars)
    if "date" in df.columns:
        try:
            df["date"] = pd.to_datetime(df["date"])
        except Exception:
            pass
    return df
