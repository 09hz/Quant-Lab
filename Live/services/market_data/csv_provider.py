from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from services.market_data.base import (
    MarketDataProvider,
    MarketDataSnapshot,
    normalize_ohlcv,
    normalize_symbol,
)


class CSVMarketDataProvider(MarketDataProvider):
    """
    Local zero-cost market data provider for development, replay, demos, and tests.

    Supported file patterns under root_dir:
        root_dir / SYMBOL / TIMEFRAME / YYYY-MM-DD.parquet
        root_dir / SYMBOL / TIMEFRAME / YYYY-MM-DD.csv
        root_dir / SYMBOL / TIMEFRAME / latest.parquet
        root_dir / SYMBOL / TIMEFRAME / latest.csv
        root_dir / SYMBOL / YYYY-MM-DD.parquet
        root_dir / SYMBOL / YYYY-MM-DD.csv
        root_dir / SYMBOL.parquet
        root_dir / SYMBOL.csv
    """

    name = "csv"

    def __init__(
        self,
        root_dir: str | Path = "cache/replay",
        symbol_options: list[dict[str, object]] | None = None,
        company_names: dict[str, str] | None = None,
    ):
        self.root_dir = Path(root_dir)
        self.symbol_options = symbol_options or []
        self.company_names = company_names or {}

    def sanitize_symbol(self, symbol: str) -> str:
        return normalize_symbol(symbol)

    def _safe_timeframe(self, timeframe: str) -> str:
        return str(timeframe or "1 min").replace(" ", "_").replace("/", "_")

    def _date_key_from_start(self, start) -> str:
        if start is None:
            return "latest"

        ts = pd.to_datetime(start, errors="coerce")
        if pd.isna(ts):
            return str(start)

        return ts.date().isoformat()

    def _candidate_paths(
        self,
        symbol: str,
        timeframe: str,
        start: Optional[date | datetime | str],
    ) -> list[Path]:
        symbol = self.sanitize_symbol(symbol)
        tf = self._safe_timeframe(timeframe)
        date_key = self._date_key_from_start(start)

        return [
            self.root_dir / symbol / tf / f"{date_key}.parquet",
            self.root_dir / symbol / tf / f"{date_key}.csv",
            self.root_dir / symbol / f"{date_key}.parquet",
            self.root_dir / symbol / f"{date_key}.csv",
            self.root_dir / f"{symbol}.parquet",
            self.root_dir / f"{symbol}.csv",
        ]

    def _read_file(self, path: Path) -> pd.DataFrame:
        if path.suffix.lower() == ".parquet":
            return pd.read_parquet(path)
        if path.suffix.lower() == ".csv":
            return pd.read_csv(path)
        raise ValueError(f"Unsupported local data file type: {path}")

    def get_history(
        self,
        symbol: str,
        timeframe: str = "1 min",
        start: Optional[date | datetime | str] = None,
        end: Optional[date | datetime | str] = None,
    ) -> pd.DataFrame:
        symbol = self.sanitize_symbol(symbol)
        errors: list[str] = []

        for path in self._candidate_paths(symbol, timeframe, start):
            if not path.exists():
                continue

            try:
                df = normalize_ohlcv(self._read_file(path))
                if df.empty:
                    continue

                if start is not None or end is not None:
                    times = pd.to_datetime(df["time"], errors="coerce", format="mixed")

                    if start is not None:
                        start_ts = pd.to_datetime(start, errors="coerce")
                        if pd.notna(start_ts):
                            df = df[times >= start_ts].copy()

                    if end is not None:
                        end_ts = pd.to_datetime(end, errors="coerce")
                        if pd.notna(end_ts):
                            times = pd.to_datetime(df["time"], errors="coerce", format="mixed")
                            df = df[times <= end_ts].copy()

                    df = df.reset_index(drop=True)

                return normalize_ohlcv(df)

            except Exception as exc:
                errors.append(f"{path}: {exc}")

        searched = ", ".join(str(p) for p in self._candidate_paths(symbol, timeframe, start))
        detail = f" Errors: {' | '.join(errors)}" if errors else ""
        raise FileNotFoundError(
            f"No local OHLCV data found for {symbol} {timeframe}. "
            f"Searched: {searched}.{detail}"
        )

    def get_snapshot(self, symbol: str, timeframe: str = "1 min") -> MarketDataSnapshot:
        symbol = self.sanitize_symbol(symbol)

        try:
            bars = self.get_history(symbol, timeframe)
        except Exception:
            bars = pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

        last = None
        updated_at = None

        if not bars.empty:
            last = float(bars.iloc[-1]["close"])
            updated_at = pd.to_datetime(bars.iloc[-1]["time"], errors="coerce")
            if pd.isna(updated_at):
                updated_at = None

        return MarketDataSnapshot(
            symbol=symbol,
            timeframe=timeframe,
            bars=bars,
            last=last,
            updated_at=updated_at,
            provider=self.name,
        )

    def get_symbol_options(self) -> list[dict[str, object]]:
        if self.symbol_options:
            return self.symbol_options

        if not self.root_dir.exists():
            return []

        symbols = set()

        for path in self.root_dir.iterdir():
            if path.is_dir():
                symbols.add(path.name.upper())
            elif path.suffix.lower() in {".csv", ".parquet"}:
                symbols.add(path.stem.upper())

        return [
            {
                "label": self.get_company_name(symbol),
                "value": symbol,
                "search": f"{symbol} {self.get_company_name(symbol)}",
            }
            for symbol in sorted(symbols)
        ]

    def get_company_name(self, symbol: str) -> str:
        symbol = self.sanitize_symbol(symbol)
        name = self.company_names.get(symbol)
        return f"{symbol} - {name}" if name else symbol
