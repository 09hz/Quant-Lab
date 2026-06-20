from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import pandas as pd

from services.market_data.base import MarketDataProvider


class IBKRMarketDataProvider(MarketDataProvider):
    """
    Thin adapter around the existing RealTimeIB class.

    This keeps IBKR behavior centralized while allowing ReplayService and
    BarViewService to depend on MarketDataProvider instead of RealTimeIB.
    """

    name = "ibkr"

    def __init__(self, rt):
        self.rt = rt

    def sanitize_symbol(self, symbol: str) -> str:
        return self.rt._sanitize_symbol(symbol)

    def request_symbol(self, symbol: str) -> None:
        self.rt.request_symbol(self.sanitize_symbol(symbol))

    def get_company_name(self, symbol: str) -> str:
        return self.rt.get_company_name(self.sanitize_symbol(symbol))

    def get_symbol_options(self) -> list[dict]:
        return self.rt.get_symbol_options()

    def get_snapshot(self, symbol: str, timeframe: str = "1 min"):
        return self.rt.get_snapshot(self.sanitize_symbol(symbol), timeframe)

    def get_history(
        self,
        symbol: str,
        timeframe: str = "1 min",
        start: Optional[date | datetime | str] = None,
        end: Optional[date | datetime | str] = None,
    ) -> pd.DataFrame:
        symbol = self.sanitize_symbol(symbol)

        if start is not None and end is not None:
            return self.rt.load_history_range(symbol, timeframe, start, end)

        return self.rt.load_history(symbol, timeframe)
