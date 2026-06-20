from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Any

import pandas as pd


OHLCV_COLUMNS = ["time", "open", "high", "low", "close", "volume"]


@dataclass
class MarketDataSnapshot:
    """
    Provider-neutral latest market snapshot.

    Keep this small. Provider-specific raw payloads should not leak into
    callbacks, replay, strategy, backtest, or paper trading services.
    """

    symbol: str
    timeframe: str = "1 min"
    bars: pd.DataFrame | None = None
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    last_size: float = 0.0
    updated_at: datetime | None = None
    provider: str = "unknown"
    raw: Any = None


def normalize_symbol(symbol: str) -> str:
    """Canonical app-level equity symbol cleanup."""
    return str(symbol or "").upper().strip()


def normalize_ohlcv(df: pd.DataFrame | None) -> pd.DataFrame:
    """
    Convert provider output into Stock Visualizer Live's internal OHLCV schema.

    Required columns returned:
        time, open, high, low, close, volume
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=OHLCV_COLUMNS)

    out = df.copy()

    rename_map = {}
    for src, dst in [
        ("date", "time"),
        ("Date", "time"),
        ("datetime", "time"),
        ("Datetime", "time"),
        ("timestamp", "time"),
        ("Timestamp", "time"),
        ("t", "time"),
        ("o", "open"),
        ("h", "high"),
        ("l", "low"),
        ("c", "close"),
        ("v", "volume"),
    ]:
        if src in out.columns and dst not in out.columns:
            rename_map[src] = dst

    if rename_map:
        out = out.rename(columns=rename_map)

    for col in OHLCV_COLUMNS:
        if col not in out.columns:
            if col == "volume":
                out[col] = 0
            else:
                raise ValueError(f"Missing required OHLCV column: {col}")

    out = out[OHLCV_COLUMNS].copy()
    out["time"] = pd.to_datetime(out["time"], errors="coerce", format="mixed")

    try:
        if getattr(out["time"].dt, "tz", None) is not None:
            out["time"] = out["time"].dt.tz_localize(None)
    except Exception:
        pass

    for col in ["open", "high", "low", "close"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    out["volume"] = pd.to_numeric(out["volume"], errors="coerce").fillna(0)

    out = out.dropna(subset=["time", "open", "high", "low", "close"]).copy()

    if out.empty:
        return pd.DataFrame(columns=OHLCV_COLUMNS)

    out = (
        out.sort_values("time")
        .drop_duplicates(subset=["time"])
        .reset_index(drop=True)
    )

    return out[OHLCV_COLUMNS].copy()


class MarketDataProvider(ABC):
    """
    Base interface for all market data providers.

    This interface is data-only. Do not place orders here.
    Order routing belongs in a separate BrokerAdapter layer.
    """

    name: str = "base"

    @abstractmethod
    def sanitize_symbol(self, symbol: str) -> str:
        """Return provider-safe normalized symbol."""

    @abstractmethod
    def get_history(
        self,
        symbol: str,
        timeframe: str = "1 min",
        start: Optional[date | datetime | str] = None,
        end: Optional[date | datetime | str] = None,
    ) -> pd.DataFrame:
        """Return OHLCV bars with columns: time, open, high, low, close, volume."""

    @abstractmethod
    def get_snapshot(self, symbol: str, timeframe: str = "1 min") -> MarketDataSnapshot:
        """Return latest quote/snapshot plus recent bars when available."""

    def request_symbol(self, symbol: str, timeframe: str = "1 min") -> None:
        """Optional live subscription hook. Providers without streaming can no-op."""
        return None

    def get_symbol_options(self) -> list[dict[str, object]]:
        """Return Dash dropdown options."""
        return []

    def get_company_name(self, symbol: str) -> str:
        """Return display company name if known."""
        return self.sanitize_symbol(symbol)
