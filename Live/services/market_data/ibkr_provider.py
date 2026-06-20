from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import pandas as pd

from services.market_data.base import (
    MarketDataProvider,
    MarketDataSnapshot,
    normalize_ohlcv,
)


class IBKRMarketDataProvider(MarketDataProvider):
    """
    Thin adapter around the existing RealTimeIB class.

    This keeps current IBKR behavior working while allowing replay, watch,
    FastAPI, and future providers to depend on MarketDataProvider.
    """

    name = "ibkr"

    def __init__(self, rt):
        self.rt = rt

    def sanitize_symbol(self, symbol: str) -> str:
        return self.rt._sanitize_symbol(symbol)

    def request_symbol(self, symbol: str, timeframe: str = "1 min") -> None:
        symbol = self.sanitize_symbol(symbol)
        try:
            self.rt.request_symbol(symbol)
        except TypeError:
            self.rt.request_symbol(symbol, timeframe)

    def get_history(
        self,
        symbol: str,
        timeframe: str = "1 min",
        start: Optional[date | datetime | str] = None,
        end: Optional[date | datetime | str] = None,
    ) -> pd.DataFrame:
        symbol = self.sanitize_symbol(symbol)

        if start is not None and end is not None:
            df = self.rt.load_history_range(symbol, timeframe, start, end)
        else:
            df = self.rt.load_history(symbol, timeframe)

        return normalize_ohlcv(df)

    def get_snapshot(self, symbol: str, timeframe: str = "1 min") -> MarketDataSnapshot:
        symbol = self.sanitize_symbol(symbol)
        snap = self.rt.get_snapshot(symbol, timeframe)
        bars = normalize_ohlcv(getattr(snap, "bars", None))

        return MarketDataSnapshot(
            symbol=symbol,
            timeframe=timeframe,
            bars=bars,
            bid=getattr(snap, "bid", None),
            ask=getattr(snap, "ask", None),
            last=getattr(snap, "last", None),
            last_size=float(getattr(snap, "last_size", 0.0) or 0.0),
            updated_at=getattr(snap, "updated_at", None),
            provider=self.name,
            raw=snap,
        )

    def get_symbol_options(self) -> list[dict[str, object]]:
        try:
            return list(self.rt.get_symbol_options())
        except Exception:
            return []

    def get_company_name(self, symbol: str) -> str:
        symbol = self.sanitize_symbol(symbol)
        try:
            return self.rt.get_company_name(symbol)
        except Exception:
            return symbol
