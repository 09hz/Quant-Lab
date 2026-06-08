from __future__ import annotations

import asyncio
import csv
import queue
import random
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd
from ib_async import IB, Stock, Ticker, util

from utils.chart_utils import apply_tick_to_bars, normalize_history_df, resample_bars


TIMEFRAME_MAP: Dict[str, Tuple[str, str]] = {
    "1 min": ("1 min", "1 D"),
    "5 mins": ("5 mins", "2 D"),
    "15 mins": ("15 mins", "5 D"),
    "1 hour": ("1 hour", "30 D"),
    "1 day": ("1 day", "1 Y"),
}


@dataclass
class SymbolState:
    symbol: str
    timeframe: str
    bars: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(
        columns=["time", "open", "high", "low", "close", "volume"]
    ))
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    last_size: float = 0.0
    updated_at: Optional[datetime] = None
    tick_count: int = 0


class RealTimeIB:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 4001,
        client_id: Optional[int] = None,
    ):
        self.host = host
        self.port = port
        self.client_id = client_id if client_id is not None else random.randint(1000, 999999)

        self.ib = IB()

        self._contracts: Dict[str, Stock] = {}
        self._tickers: Dict[str, Ticker] = {}
        self._states: Dict[Tuple[str, str], SymbolState] = {}

        self._lock = threading.RLock()
        self._runner_thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._startup_error: Optional[str] = None

        self._requests: queue.Queue[tuple[Any, ...]] = queue.Queue()

        project_root = Path(__file__).resolve().parent.parent
        data_dir = project_root / "data"

        self.nasdaq_file = data_dir / "nasdaq_tickers_simple.txt"
        self.nasdaq_symbols = self._load_nasdaq_symbols(self.nasdaq_file)

        self.company_file = data_dir / "nasdaq_symbol_names_filled.csv"
        self.company_names = self._load_company_names(self.company_file)

    def _load_nasdaq_symbols(self, file_path: Path) -> set[str]:
        if not file_path.exists():
            print(f"[WARN] NASDAQ file not found: {file_path}", flush=True)
            return set()

        with open(file_path, "r", encoding="utf-8") as f:
            return {line.strip().upper() for line in f if line.strip()}

    def _load_company_names(self, file_path: Path) -> dict[str, str]:
        if not file_path.exists():
            print(f"[WARN] Company file not found: {file_path}", flush=True)
            return {}

        company_map: dict[str, str] = {}
        with open(file_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                symbol = (row.get("symbol") or "").strip().upper()
                name = (row.get("name") or "").strip()
                if symbol:
                    company_map[symbol] = name

        return company_map

    def is_valid_nasdaq_symbol(self, symbol: str) -> bool:
        symbol = self._sanitize_symbol(symbol)
        return symbol in self.nasdaq_symbols

    def get_company_name(self, symbol: str) -> str:
        symbol = self._sanitize_symbol(symbol)
        return self.company_names.get(symbol) or symbol

    def get_symbol_options(self) -> list[dict[str, object]]:
        options: list[dict[str, object]] = []

        for symbol in sorted(self.nasdaq_symbols):
            company = self.company_names.get(symbol, "")
            label_text = f"{symbol} - {company}" if company else symbol
            search_text = f"{symbol} {company}".strip()

            options.append(
                {
                    "label": label_text,
                    "value": symbol,
                    "search": search_text,
                }
            )

        return options

    def connect(self) -> None:
        if not self.ib.isConnected():
            self.ib.connect(self.host, self.port, clientId=self.client_id, timeout=30)

    def disconnect(self) -> None:
        if self.ib.isConnected():
            self.ib.disconnect()

    def start(self, symbol: str, timeframe: str) -> None:
        if self._runner_thread and self._runner_thread.is_alive():
            return

        symbol = self._sanitize_symbol(symbol)

        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                self.connect()
                self.ensure_symbol_ready(symbol, timeframe)
                self._ready.set()

                while True:
                    self._process_requests()
                    self.ib.sleep(0.25)

            except Exception as exc:
                self._startup_error = str(exc)
                self._ready.set()
                print(f"[IB LOOP ERROR] {exc}", flush=True)

        self._runner_thread = threading.Thread(target=_run, daemon=True)
        self._runner_thread.start()
        self._ready.wait(timeout=15)

        if self._startup_error:
            raise RuntimeError(self._startup_error)

    def request_symbol(self, symbol: str) -> None:
        symbol = self._sanitize_symbol(symbol)
        self._requests.put(("symbol", symbol))

    def _process_requests(self) -> None:
        while not self._requests.empty():
            req = self._requests.get()

            try:
                kind = req[0]

                if kind == "symbol":
                    symbol = str(req[1])
                    self.ensure_symbol_ready(symbol, "1 min")

            except Exception as exc:
                print(f"[REQUEST ERROR] {req}: {exc}", flush=True)

    def get_contract(self, symbol: str) -> Stock:
        symbol = self._sanitize_symbol(symbol)

        if not self.is_valid_nasdaq_symbol(symbol):
            raise ValueError(f"{symbol} is not in NASDAQ symbol list")

        with self._lock:
            if symbol in self._contracts:
                return self._contracts[symbol]

        contract = Stock(symbol, "SMART", "USD", primaryExchange="NASDAQ")
        self.ib.qualifyContracts(contract)

        with self._lock:
            self._contracts[symbol] = contract

        return contract

    def load_history(self, symbol: str, timeframe: str) -> pd.DataFrame:
        symbol = self._sanitize_symbol(symbol)

        if timeframe not in TIMEFRAME_MAP:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        contract = self.get_contract(symbol)
        bar_size, duration = TIMEFRAME_MAP[timeframe]

        bars = self.ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow="TRADES",
            useRTH=True,
            formatDate=1,
        )

        df = util.df(bars)
        df = normalize_history_df(df)

        with self._lock:
            key = (symbol, timeframe)
            state = self._states.get(key, SymbolState(symbol=symbol, timeframe=timeframe))
            state.bars = df
            state.updated_at = datetime.now()
            if not df.empty:
                state.last = float(df.iloc[-1]["close"])
            self._states[key] = state

        return df

    def load_history_at(self, symbol: str, timeframe: str, end_dt: datetime) -> pd.DataFrame:
        symbol = self._sanitize_symbol(symbol)

        if timeframe not in TIMEFRAME_MAP:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        contract = self.get_contract(symbol)
        bar_size, duration = TIMEFRAME_MAP[timeframe]

        bars = self.ib.reqHistoricalData(
            contract,
            endDateTime=end_dt.strftime("%Y%m%d %H:%M:%S"),
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow="TRADES",
            useRTH=True,
            formatDate=1,
        )

        df = util.df(bars)
        return normalize_history_df(df)

    def load_history_range(
        self,
        symbol: str,
        timeframe: str,
        start_dt: datetime,
        end_dt: datetime,
    ) -> pd.DataFrame:
        if start_dt >= end_dt:
            raise ValueError("start_dt must be before end_dt")

        pieces: list[pd.DataFrame] = []
        cursor = end_dt

        step_map = {
            "1 min": timedelta(days=1),
            "5 mins": timedelta(days=2),
            "15 mins": timedelta(days=5),
            "1 hour": timedelta(days=30),
            "1 day": timedelta(days=365),
        }

        if timeframe not in step_map:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        while cursor > start_dt:
            chunk = self.load_history_at(symbol, timeframe, cursor)

            if chunk is None or chunk.empty:
                break

            pieces.append(chunk)

            oldest = pd.to_datetime(chunk["time"].min()).to_pydatetime()
            if oldest <= start_dt:
                break

            cursor = oldest - timedelta(seconds=1)
            self.ib.sleep(0.25)

        if not pieces:
            return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

        out = pd.concat(pieces, ignore_index=True)
        out = out.drop_duplicates(subset="time").sort_values("time").reset_index(drop=True)
        out = out[(out["time"] >= start_dt) & (out["time"] <= end_dt)].reset_index(drop=True)
        return out

    def subscribe_live(self, symbol: str, timeframe: str = "1 min") -> None:
        symbol = self._sanitize_symbol(symbol)
        contract = self.get_contract(symbol)

        with self._lock:
            key = (symbol, "1 min")
            has_state = key in self._states and not self._states[key].bars.empty
            if symbol in self._tickers:
                return

        if not has_state:
            self.load_history(symbol, "1 min")

        ticker = self.ib.reqMktData(contract, "", False, False)
        ticker.updateEvent += self._make_tick_handler(symbol, "1 min")

        with self._lock:
            self._tickers[symbol] = ticker

    def _make_tick_handler(self, symbol: str, timeframe: str):
        def on_tick(ticker: Ticker, *args):
            price_raw = ticker.last if ticker.last is not None else ticker.marketPrice()

            if price_raw is None or pd.isna(price_raw):
                return

            price = float(price_raw)
            size = float(ticker.lastSize or 0)

            with self._lock:
                key = (symbol, timeframe)
                state = self._states.get(key)
                if state is None:
                    return

                state.bid = float(ticker.bid) if ticker.bid is not None else state.bid
                state.ask = float(ticker.ask) if ticker.ask is not None else state.ask
                state.last = price
                state.last_size = size
                state.updated_at = datetime.now()
                state.tick_count += 1
                state.bars = apply_tick_to_bars(
                    state.bars,
                    price=price,
                    size=size,
                    tick_time=datetime.now(),
                )
                self._states[key] = state

        return on_tick

    def get_snapshot(self, symbol: str, timeframe: str) -> SymbolState:
        symbol = self._sanitize_symbol(symbol)
        key = (symbol, "1 min")

        with self._lock:
            state = self._states.get(key)

        if state is None:
            raise ValueError(f"No loaded state for {symbol} 1 min")

        bars = state.bars.copy()
        if timeframe != "1 min":
            bars = resample_bars(bars, timeframe)

        return SymbolState(
            symbol=state.symbol,
            timeframe=timeframe,
            bars=bars,
            bid=state.bid,
            ask=state.ask,
            last=state.last,
            last_size=state.last_size,
            updated_at=state.updated_at,
            tick_count=state.tick_count,
        )

    def ensure_symbol_ready(self, symbol: str, timeframe: str) -> None:
        self.load_history(symbol, "1 min")
        self.subscribe_live(symbol, "1 min")

    @staticmethod
    def _sanitize_symbol(symbol: str) -> str:
        cleaned = "".join(
            ch for ch in symbol.upper().strip()
            if ch.isalnum() or ch in {".", "-"}
        )
        if not cleaned:
            raise ValueError("Invalid symbol.")
        return cleaned
