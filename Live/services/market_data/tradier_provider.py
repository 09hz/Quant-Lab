from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from services.market_data.base import (
    MarketDataProvider,
    MarketDataSnapshot,
    normalize_ohlcv,
)


class TradierMarketDataProvider(MarketDataProvider):
    """
    Market-data-only Tradier provider.

    This provider is intentionally limited to market data. It does not place
    orders, read balances, or manage brokerage positions.

    Environment variables normally used by provider_factory.py:
        TRADIER_ACCESS_TOKEN
        TRADIER_ENV=sandbox or production
        TRADIER_TIMEOUT_SECONDS=30
    """

    name = "tradier"

    INTRADAY_INTERVALS = {
        "1 min": "1min",
        "1m": "1min",
        "1min": "1min",
        "5 mins": "5min",
        "5 min": "5min",
        "5m": "5min",
        "5min": "5min",
        "15 mins": "15min",
        "15 min": "15min",
        "15m": "15min",
        "15min": "15min",
    }

    DAILY_INTERVALS = {
        "1 day": "daily",
        "1d": "daily",
        "daily": "daily",
        "day": "daily",
    }

    def __init__(
        self,
        access_token: str = "",
        environment: str = "sandbox",
        timeout: float = 30,
    ) -> None:
        self.access_token = str(access_token or "").strip()
        self.environment = str(environment or "sandbox").strip().lower()
        self.timeout = float(timeout or 30)

        if self.environment in {"prod", "production", "live"}:
            self.base_url = "https://api.tradier.com/v1"
            self.environment = "production"
        else:
            self.base_url = "https://sandbox.tradier.com/v1"
            self.environment = "sandbox"

    def sanitize_symbol(self, symbol: str) -> str:
        symbol = str(symbol or "").upper().strip()
        if not symbol:
            raise ValueError("Symbol is required.")
        return symbol

    def get_company_name(self, symbol: str) -> str:
        return self.sanitize_symbol(symbol)

    def get_symbol_options(self) -> list[dict[str, Any]]:
        # Tradier does not provide your local NASDAQ dropdown list.
        # Keep this empty so the app can continue using its local symbol files.
        return []

    def get_history(
        self,
        symbol: str,
        timeframe: str = "1 min",
        start: Optional[date | datetime | str] = None,
        end: Optional[date | datetime | str] = None,
    ) -> pd.DataFrame:
        symbol = self.sanitize_symbol(symbol)
        timeframe_key = str(timeframe or "1 min").strip().lower()

        if timeframe_key in self.DAILY_INTERVALS:
            return self._get_daily_history(
                symbol=symbol,
                start=start,
                end=end,
                interval=self.DAILY_INTERVALS[timeframe_key],
            )

        interval = self.INTRADAY_INTERVALS.get(timeframe_key)
        if interval is None:
            raise ValueError(
                f"Unsupported Tradier timeframe: {timeframe}. "
                "Supported intraday intervals: 1 min, 5 mins, 15 mins. "
                "Supported daily interval: 1 day."
            )

        return self._get_timesales_history(
            symbol=symbol,
            start=start,
            end=end,
            interval=interval,
        )

    def get_snapshot(
        self,
        symbol: str,
        timeframe: str = "1 min",
    ) -> MarketDataSnapshot:
        symbol = self.sanitize_symbol(symbol)

        quote_payload = self._request_json(
            "/markets/quotes",
            {
                "symbols": symbol,
                "greeks": "false",
            },
        )

        quote = self._extract_quote(quote_payload)

        last = self._first_number(
            quote,
            ["last", "close", "bid", "ask"],
        )
        bid = self._optional_float(quote.get("bid"))
        ask = self._optional_float(quote.get("ask"))

        bars = pd.DataFrame()
        try:
            bars = self.get_history(symbol=symbol, timeframe=timeframe)
        except Exception:
            bars = pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

        if last is None and bars is not None and not bars.empty:
            last = float(bars.iloc[-1]["close"])

        return MarketDataSnapshot(
            symbol=symbol,
            timeframe=timeframe,
            bars=normalize_ohlcv(bars) if bars is not None and not bars.empty else bars,
            bid=bid,
            ask=ask,
            last=last,
            last_size=self._optional_float(quote.get("last_volume")) or 0.0,
            updated_at=datetime.now(),
            provider=self.name,
            metadata={
                "environment": self.environment,
                "raw_quote": quote,
            },
        )

    def _get_timesales_history(
        self,
        *,
        symbol: str,
        start: Optional[date | datetime | str],
        end: Optional[date | datetime | str],
        interval: str,
    ) -> pd.DataFrame:
        start_text, end_text = self._intraday_window(start, end)

        payload = self._request_json(
            "/markets/timesales",
            {
                "symbol": symbol,
                "interval": interval,
                "start": start_text,
                "end": end_text,
                "session_filter": "all",
            },
        )

        rows = self._extract_timesales_rows(payload)
        df = pd.DataFrame(rows)

        if df.empty:
            return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

        rename_map = {
            "time": "time",
            "timestamp": "time",
            "date": "time",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
        }

        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
        return normalize_ohlcv(df)

    def _get_daily_history(
        self,
        *,
        symbol: str,
        start: Optional[date | datetime | str],
        end: Optional[date | datetime | str],
        interval: str,
    ) -> pd.DataFrame:
        start_date, end_date = self._date_window(start, end)

        payload = self._request_json(
            "/markets/history",
            {
                "symbol": symbol,
                "interval": interval,
                "start": start_date,
                "end": end_date,
            },
        )

        rows = self._extract_history_rows(payload)
        df = pd.DataFrame(rows)

        if df.empty:
            return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

        if "date" in df.columns and "time" not in df.columns:
            df = df.rename(columns={"date": "time"})

        return normalize_ohlcv(df)

    def _request_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.access_token:
            raise RuntimeError(
                "Missing TRADIER_ACCESS_TOKEN. Set it in your environment or .env "
                "before using MARKET_DATA_PROVIDER=tradier."
            )

        clean_params = {
            key: value
            for key, value in params.items()
            if value is not None and str(value) != ""
        }

        url = f"{self.base_url}{path}?{urlencode(clean_params)}"

        request = Request(
            url,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/json",
            },
            method="GET",
        )

        with urlopen(request, timeout=self.timeout) as response:
            raw = response.read().decode("utf-8")

        if not raw:
            return {}

        return json.loads(raw)

    def _intraday_window(
        self,
        start: Optional[date | datetime | str],
        end: Optional[date | datetime | str],
    ) -> tuple[str, str]:
        if start is None:
            start_ts = pd.Timestamp.now().normalize()
        else:
            start_ts = pd.to_datetime(start, errors="coerce")

        if pd.isna(start_ts):
            raise ValueError(f"Invalid Tradier start value: {start}")

        if end is None:
            end_ts = start_ts + pd.Timedelta(days=1)
        else:
            end_ts = pd.to_datetime(end, errors="coerce")

        if pd.isna(end_ts):
            raise ValueError(f"Invalid Tradier end value: {end}")

        if end_ts <= start_ts:
            end_ts = start_ts + pd.Timedelta(days=1)

        return (
            start_ts.strftime("%Y-%m-%d %H:%M"),
            end_ts.strftime("%Y-%m-%d %H:%M"),
        )

    def _date_window(
        self,
        start: Optional[date | datetime | str],
        end: Optional[date | datetime | str],
    ) -> tuple[str, str]:
        if start is None:
            start_ts = pd.Timestamp.now().normalize() - pd.Timedelta(days=30)
        else:
            start_ts = pd.to_datetime(start, errors="coerce")

        if pd.isna(start_ts):
            raise ValueError(f"Invalid Tradier start value: {start}")

        if end is None:
            end_ts = pd.Timestamp.now().normalize()
        else:
            end_ts = pd.to_datetime(end, errors="coerce")

        if pd.isna(end_ts):
            raise ValueError(f"Invalid Tradier end value: {end}")

        return (
            start_ts.strftime("%Y-%m-%d"),
            end_ts.strftime("%Y-%m-%d"),
        )

    def _extract_timesales_rows(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        series = payload.get("series") if isinstance(payload, dict) else None

        if not isinstance(series, dict):
            return []

        data = series.get("data")

        if data is None:
            return []

        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]

        if isinstance(data, dict):
            return [data]

        return []

    def _extract_history_rows(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        history = payload.get("history") if isinstance(payload, dict) else None

        if not isinstance(history, dict):
            return []

        day = history.get("day")

        if day is None:
            return []

        if isinstance(day, list):
            return [row for row in day if isinstance(row, dict)]

        if isinstance(day, dict):
            return [day]

        return []

    def _extract_quote(self, payload: dict[str, Any]) -> dict[str, Any]:
        quotes = payload.get("quotes") if isinstance(payload, dict) else None

        if not isinstance(quotes, dict):
            return {}

        quote = quotes.get("quote")

        if isinstance(quote, list):
            return quote[0] if quote and isinstance(quote[0], dict) else {}

        if isinstance(quote, dict):
            return quote

        return {}

    def _optional_float(self, value: Any) -> Optional[float]:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except Exception:
            return None

    def _first_number(
        self,
        data: dict[str, Any],
        keys: list[str],
    ) -> Optional[float]:
        for key in keys:
            value = self._optional_float(data.get(key))
            if value is not None:
                return value
        return None
