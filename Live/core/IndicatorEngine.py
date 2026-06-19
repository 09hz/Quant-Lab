from __future__ import annotations

import pandas as pd


class IndicatorEngine:
    """
    Safe indicator calculator for strategy scripts.

    This class does not execute user Python.
    It only exposes approved indicator functions.
    """

    ALLOWED_SOURCES = {"open", "high", "low", "close", "volume"}

    def _series(self, bars: pd.DataFrame, source: str) -> pd.Series:
        source = str(source or "").lower().strip()

        if source not in self.ALLOWED_SOURCES:
            raise ValueError(f"Unsupported source: {source}")

        if bars is None or bars.empty:
            raise ValueError("No bars available.")

        if source not in bars.columns:
            raise ValueError(f"Bars are missing column: {source}")

        return pd.to_numeric(bars[source], errors="coerce")

    def sma(self, bars: pd.DataFrame, source: str, length: int) -> pd.Series:
        length = int(length)
        if length <= 0:
            raise ValueError("SMA length must be greater than zero.")

        return self._series(bars, source).rolling(length).mean()

    def ema(self, bars: pd.DataFrame, source: str, length: int) -> pd.Series:
        length = int(length)
        if length <= 0:
            raise ValueError("EMA length must be greater than zero.")

        return self._series(bars, source).ewm(span=length, adjust=False).mean()

    def rsi(self, bars: pd.DataFrame, source: str = "close", length: int = 14) -> pd.Series:
        length = int(length)
        if length <= 0:
            raise ValueError("RSI length must be greater than zero.")

        src = self._series(bars, source)
        delta = src.diff()

        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.rolling(length).mean()
        avg_loss = loss.rolling(length).mean()

        rs = avg_gain / avg_loss.replace(0, pd.NA)
        return 100 - (100 / (1 + rs))

    def highest(self, bars: pd.DataFrame, source: str, length: int) -> pd.Series:
        length = int(length)
        if length <= 0:
            raise ValueError("Highest length must be greater than zero.")

        return self._series(bars, source).rolling(length).max()

    def lowest(self, bars: pd.DataFrame, source: str, length: int) -> pd.Series:
        length = int(length)
        if length <= 0:
            raise ValueError("Lowest length must be greater than zero.")

        return self._series(bars, source).rolling(length).min()