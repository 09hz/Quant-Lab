from __future__ import annotations

import csv
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import pandas as pd

from services.market_data.base import MarketDataProvider, OHLCV_COLUMNS


class CSVMarketDataProvider(MarketDataProvider):
    """
    Local CSV/parquet market-data provider.

    This lets replay/history workflows run without IBKR, Tradier, Alpaca, or
    any live broker/API connection.

    Expected cache layout follows BarStore:
        cache/replay/MSFT/1_min/2025-01-02.parquet
        cache/replay/MSFT/1_min/2025-01-02.csv
        cache/replay/MSFT/1_min/latest.parquet

    CSV files must contain:
        time, open, high, low, close, volume

    Common timestamp aliases are accepted:
        date, Date, datetime, Datetime
    """

    name = "csv"

    def __init__(self, root_dir: str | Path = "cache/replay"):
        self.root_dir = Path(root_dir)

    def sanitize_symbol(self, symbol: str) -> str:
        symbol = str(symbol or "").upper().strip()
        symbol = re.sub(r"[^A-Z0-9._-]", "", symbol)
        if not symbol:
            raise ValueError("Missing symbol.")
        return symbol

    def request_symbol(self, symbol: str) -> None:
        # Local provider has no streaming subscription.
        self.sanitize_symbol(symbol)

    def get_company_name(self, symbol: str) -> str:
        symbol = self.sanitize_symbol(symbol)
        names = self._load_company_names()
        return names.get(symbol, symbol)

    def get_symbol_options(self) -> list[dict]:
        symbols = set()

        # Prefer local project symbol file if available.
        data_symbols = self._load_symbols_from_project_data()
        symbols.update(data_symbols)

        # Also include anything found in the cache root.
        if self.root_dir.exists():
            for child in self.root_dir.iterdir():
                if child.is_dir():
                    symbols.add(child.name.upper())

        names = self._load_company_names()

        options = []
        for symbol in sorted(symbols):
            company = names.get(symbol, "")
            label = f"{symbol} - {company}" if company else symbol
            options.append(
                {
                    "label": label,
                    "value": symbol,
                    "search": f"{symbol} {company}".strip(),
                }
            )

        return options

    def get_snapshot(self, symbol: str, timeframe: str = "1 min") -> SimpleNamespace:
        bars = self.get_history(symbol=symbol, timeframe=timeframe)
        last = None
        updated_at = None

        if bars is not None and not bars.empty:
            last = float(bars.iloc[-1]["close"])
            updated_at = pd.to_datetime(bars.iloc[-1]["time"], errors="coerce")

            if pd.isna(updated_at):
                updated_at = datetime.now()
            else:
                updated_at = updated_at.to_pydatetime()

        return SimpleNamespace(
            symbol=self.sanitize_symbol(symbol),
            timeframe=timeframe,
            bars=bars,
            bid=None,
            ask=None,
            last=last,
            last_size=0.0,
            updated_at=updated_at or datetime.now(),
            tick_count=0,
        )

    def get_history(
        self,
        symbol: str,
        timeframe: str = "1 min",
        start: Optional[date | datetime | str] = None,
        end: Optional[date | datetime | str] = None,
    ) -> pd.DataFrame:
        symbol = self.sanitize_symbol(symbol)
        timeframe = timeframe or "1 min"

        frames: list[pd.DataFrame] = []

        if start is not None and end is not None:
            for day_key in self._date_keys_between(start, end):
                df = self._read_for_date(symbol, timeframe, day_key)
                if df is not None and not df.empty:
                    frames.append(df)
        elif start is not None:
            day_key = self._date_key(start)
            df = self._read_for_date(symbol, timeframe, day_key)
            if df is not None and not df.empty:
                frames.append(df)
        else:
            # Try latest first, then fall back to all cached files for the symbol/timeframe.
            df = self._read_for_date(symbol, timeframe, "latest")
            if df is not None and not df.empty:
                frames.append(df)
            else:
                frames.extend(self._read_all_for_symbol_timeframe(symbol, timeframe))

        if not frames:
            return self._empty_bars()

        out = pd.concat(frames, ignore_index=True)
        out = self._normalize_bars(out)

        if start is not None:
            start_ts = pd.to_datetime(start, errors="coerce")
            if pd.notna(start_ts):
                out = out[out["time"] >= start_ts]

        if end is not None:
            end_ts = pd.to_datetime(end, errors="coerce")
            if pd.notna(end_ts):
                out = out[out["time"] <= end_ts]

        return out.reset_index(drop=True)

    def _empty_bars(self) -> pd.DataFrame:
        return pd.DataFrame(columns=OHLCV_COLUMNS)

    def _safe_timeframe(self, timeframe: str) -> str:
        return str(timeframe or "1 min").replace(" ", "_").replace("/", "_")

    def _path_base(self, symbol: str, timeframe: str, date_key: str) -> Path:
        return self.root_dir / self.sanitize_symbol(symbol) / self._safe_timeframe(timeframe) / date_key

    def _read_for_date(self, symbol: str, timeframe: str, date_key: str) -> pd.DataFrame | None:
        base = self._path_base(symbol, timeframe, date_key)

        for path in (base.with_suffix(".parquet"), base.with_suffix(".csv")):
            if path.exists():
                return self._read_file(path)

        return None

    def _read_all_for_symbol_timeframe(self, symbol: str, timeframe: str) -> list[pd.DataFrame]:
        folder = self.root_dir / self.sanitize_symbol(symbol) / self._safe_timeframe(timeframe)

        if not folder.exists():
            return []

        frames = []
        for path in sorted([*folder.glob("*.parquet"), *folder.glob("*.csv")]):
            df = self._read_file(path)
            if df is not None and not df.empty:
                frames.append(df)

        return frames

    def _read_file(self, path: Path) -> pd.DataFrame:
        try:
            if path.suffix.lower() == ".parquet":
                df = pd.read_parquet(path)
            elif path.suffix.lower() == ".csv":
                df = pd.read_csv(path)
            else:
                return self._empty_bars()

            return self._normalize_bars(df)
        except Exception as exc:
            print(f"[CSV PROVIDER READ ERROR] {path}: {exc}", flush=True)
            return self._empty_bars()

    def _normalize_bars(self, df: pd.DataFrame | None) -> pd.DataFrame:
        if df is None or df.empty:
            return self._empty_bars()

        out = df.copy()

        rename_map = {}
        for src in ("date", "Date", "datetime", "Datetime"):
            if src in out.columns and "time" not in out.columns:
                rename_map[src] = "time"

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

        for col in ["open", "high", "low", "close"]:
            out[col] = pd.to_numeric(out[col], errors="coerce")

        out["volume"] = pd.to_numeric(out["volume"], errors="coerce").fillna(0)

        out = out.dropna(subset=["time", "open", "high", "low", "close"])
        out = out.drop_duplicates(subset=["time"]).sort_values("time").reset_index(drop=True)

        return out

    def _date_key(self, value) -> str:
        ts = pd.to_datetime(value, errors="coerce")
        if pd.isna(ts):
            raise ValueError(f"Invalid date: {value}")
        return ts.date().isoformat()

    def _date_keys_between(self, start, end) -> list[str]:
        start_ts = pd.to_datetime(start, errors="coerce")
        end_ts = pd.to_datetime(end, errors="coerce")

        if pd.isna(start_ts) or pd.isna(end_ts):
            raise ValueError("Invalid start/end date for CSV provider.")

        if end_ts < start_ts:
            start_ts, end_ts = end_ts, start_ts

        # If end is exactly next-day midnight, include dates before that end date.
        start_day = start_ts.date()
        end_day = end_ts.date()

        if (
            end_ts.time().hour == 0
            and end_ts.time().minute == 0
            and end_ts.time().second == 0
            and end_day > start_day
        ):
            end_day = end_day - timedelta(days=1)

        keys = []
        current = start_day
        while current <= end_day:
            keys.append(current.isoformat())
            current = current + timedelta(days=1)

        return keys

    def _project_root(self) -> Path:
        # csv_provider.py -> market_data -> services -> Live -> repo root
        return Path(__file__).resolve().parents[3]

    def _live_dir(self) -> Path:
        return Path(__file__).resolve().parents[2]

    def _load_symbols_from_project_data(self) -> set[str]:
        symbols: set[str] = set()

        for candidate in (
            self._live_dir() / "data" / "nasdaq_tickers_simple.txt",
            self._project_root() / "Live" / "data" / "nasdaq_tickers_simple.txt",
        ):
            if not candidate.exists():
                continue

            try:
                symbols.update(
                    line.strip().upper()
                    for line in candidate.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                )
            except Exception:
                pass

        return symbols

    def _load_company_names(self) -> dict[str, str]:
        names: dict[str, str] = {}

        for candidate in (
            self._live_dir() / "data" / "nasdaq_symbol_names_filled.csv",
            self._project_root() / "Live" / "data" / "nasdaq_symbol_names_filled.csv",
        ):
            if not candidate.exists():
                continue

            try:
                with candidate.open("r", encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        symbol = (row.get("symbol") or "").strip().upper()
                        name = (row.get("name") or "").strip()
                        if symbol and name:
                            names[symbol] = name
            except Exception:
                pass

        return names
