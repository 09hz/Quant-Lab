from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

import pandas as pd


OHLCV_COLUMNS = ["time", "open", "high", "low", "close", "volume"]


def _to_tz_naive_timestamp(value) -> pd.Timestamp:
    ts = pd.Timestamp(value)

    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)

    return ts


def normalize_ohlcv(df: pd.DataFrame | None) -> pd.DataFrame:
    """
    Normalize provider-specific bar data into the app's standard OHLCV schema.

    Required output columns:
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
    out["time"] = out["time"].apply(
        lambda value: _to_tz_naive_timestamp(value) if pd.notna(value) else pd.NaT
    )

    for col in ["open", "high", "low", "close"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    out["volume"] = pd.to_numeric(out["volume"], errors="coerce").fillna(0)

    out = out.dropna(subset=["time", "open", "high", "low", "close"])
    out = out.drop_duplicates(subset="time")
    out = out.sort_values("time").reset_index(drop=True)

    return out[OHLCV_COLUMNS].copy()


@dataclass
class MarketDataSnapshot:
    """
    Normalized latest-market-data snapshot.

    Providers can return this shape even when their native API payloads differ.
    """

    symbol: str = ""
    timeframe: str = "1 min"
    bars: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=OHLCV_COLUMNS)
    )
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    last_size: float = 0.0
    updated_at: Optional[datetime] = None
    provider: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return self.bars is None or self.bars.empty


class MarketDataProvider(ABC):
    """
    Base interface for all market data providers.

    Implementations:
        - IBKRMarketDataProvider
        - CSVMarketDataProvider
        - future TradierMarketDataProvider
        - future AlpacaMarketDataProvider
    """

    name: str = "base"

    @abstractmethod
    def sanitize_symbol(self, symbol: str) -> str:
        """Return a normalized provider-safe symbol."""

    @abstractmethod
    def get_history(
        self,
        symbol: str,
        timeframe: str = "1 min",
        start: Optional[date | datetime | str] = None,
        end: Optional[date | datetime | str] = None,
    ) -> pd.DataFrame:
        """Return normalized OHLCV bars."""

    def get_snapshot(
        self,
        symbol: str,
        timeframe: str = "1 min",
    ) -> MarketDataSnapshot:
        """
        Return a latest snapshot.

        Providers without live data may return a snapshot built from history.
        """
        symbol = self.sanitize_symbol(symbol)
        bars = self.get_history(symbol=symbol, timeframe=timeframe)

        last = None
        updated_at = None

        if bars is not None and not bars.empty:
            last = float(bars.iloc[-1]["close"])
            updated_at = pd.to_datetime(
                bars.iloc[-1]["time"],
                errors="coerce",
                format="mixed",
            )
            if pd.isna(updated_at):
                updated_at = datetime.now()
            else:
                updated_at = updated_at.to_pydatetime()

        return MarketDataSnapshot(
            symbol=symbol,
            timeframe=timeframe,
            bars=normalize_ohlcv(bars),
            last=last,
            updated_at=updated_at,
            provider=self.name,
        )

    def request_symbol(self, symbol: str) -> None:
        """
        Optional live-subscription hook.

        IBKR uses this. CSV/local providers can safely no-op.
        """
        return None

    def get_company_name(self, symbol: str) -> str:
        return self.sanitize_symbol(symbol)

    def get_symbol_options(self) -> list[dict[str, Any]]:
        return []
