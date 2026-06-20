from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from types import SimpleNamespace
from typing import Optional

import pandas as pd


OHLCV_COLUMNS = ["time", "open", "high", "low", "close", "volume"]


class MarketDataProvider(ABC):
    """
    Provider interface for OHLCV history, snapshots, and symbol metadata.

    Keep this small. Broker/order-routing belongs in a separate BrokerAdapter,
    not here.
    """

    name: str

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
    def get_snapshot(self, symbol: str, timeframe: str = "1 min") -> SimpleNamespace:
        """Return a snapshot-like object with bars, last, updated_at fields."""

    @abstractmethod
    def get_symbol_options(self) -> list[dict]:
        """Return Dash dropdown symbol options."""

    def request_symbol(self, symbol: str) -> None:
        """Optional live subscription/request hook."""
        return None

    def get_company_name(self, symbol: str) -> str:
        """Optional symbol metadata hook."""
        return self.sanitize_symbol(symbol)
