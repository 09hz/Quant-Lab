from __future__ import annotations

import asyncio
import csv
import queue
import random
import threading
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

import pandas as pd
from ib_async import IB, Stock, Ticker, util

from utils.chart_utils import apply_tick_to_bars, normalize_history_df, resample_bars


TIMEFRAME_MAP: Dict[str, Tuple[str, str]] = {
    "1 min": ("1 min", "1 D"),
    "5 mins": ("5 mins", "2 D"),
    "15 mins": ("15 mins", "5 D"),
    "30 mins": ("30 mins", "10 D"),
    "1 hour": ("1 hour", "30 D"),
    "1 day": ("1 day", "1 Y"),
}

TIMEFRAME_ALIASES: Dict[str, str] = {
    "1m": "1 min",
    "1 min": "1 min",
    "1 mins": "1 min",
    "1 minute": "1 min",
    "5m": "5 mins",
    "5 min": "5 mins",
    "5 mins": "5 mins",
    "5 minutes": "5 mins",
    "15m": "15 mins",
    "15 min": "15 mins",
    "15 mins": "15 mins",
    "15 minutes": "15 mins",
    "30m": "30 mins",
    "30 min": "30 mins",
    "30 mins": "30 mins",
    "30 minutes": "30 mins",
    "1h": "1 hour",
    "1 hour": "1 hour",
    "1hr": "1 hour",
    "1d": "1 day",
    "1 day": "1 day",
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


@dataclass
class _IBCallRequest:
    fn: Callable[[], Any]
    done: threading.Event = field(default_factory=threading.Event)
    result: Any = None
    error: Optional[BaseException] = None


class RealTimeIB:
    """
    IBKR real-time and historical-data coordinator.

    Important threading rule:
        All IB calls are executed on the dedicated IB runner thread.

    Dash callbacks run on normal Flask/Dash worker threads. Calling ib_async/IB
    methods directly from those threads can silently hang or fail to send the
    underlying API request. Public methods in this class therefore submit work
    to the IB runner thread using _run_on_ib_thread(...).
    """

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
        self._runner_thread_id: Optional[int] = None
        self._ready = threading.Event()
        self._startup_error: Optional[str] = None
        self._stop_requested = threading.Event()

        # User-facing requests, such as changing the watched symbol.
        self._requests: queue.Queue[tuple[Any, ...]] = queue.Queue()

        # Synchronous call requests from Dash threads that must execute on the
        # IB runner thread.
        self._ib_calls: queue.Queue[_IBCallRequest] = queue.Queue()

        project_root = Path(__file__).resolve().parent.parent
        data_dir = project_root / "data"

        self.nasdaq_file = data_dir / "nasdaq_tickers_simple.txt"
        self.nasdaq_symbols = self._load_nasdaq_symbols(self.nasdaq_file)

        self.company_file = data_dir / "nasdaq_symbol_names_filled.csv"
        self.company_names = self._load_company_names(self.company_file)

    # ------------------------------------------------------------------
    # Static/reference data
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Thread/event-loop management
    # ------------------------------------------------------------------

    def connect(self) -> None:
        if not self.ib.isConnected():
            print(
                f"[IB CONNECT] host={self.host} port={self.port} client_id={self.client_id}",
                flush=True,
            )
            self.ib.connect(self.host, self.port, clientId=self.client_id, timeout=30)

    def disconnect(self) -> None:
        self._stop_requested.set()
        if self.ib.isConnected():
            self.ib.disconnect()

    def start(self, symbol: str, timeframe: str) -> None:
        """
        Start the dedicated IB runner thread.

        This method is safe to call more than once.
        """

        if self._runner_thread and self._runner_thread.is_alive():
            return

        self._ready.clear()
        self._startup_error = None
        self._stop_requested.clear()

        symbol = self._sanitize_symbol(symbol)
        timeframe = self._normalize_timeframe(timeframe)

        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._runner_thread_id = threading.get_ident()

            try:
                self.connect()
                self.ensure_symbol_ready(symbol, timeframe)
                self._ready.set()

                while not self._stop_requested.is_set():
                    self._process_ib_calls()
                    self._process_requests()
                    self.ib.sleep(0.25)

            except Exception as exc:
                self._startup_error = str(exc)
                self._ready.set()
                print(f"[IB LOOP ERROR] {exc}", flush=True)
                traceback.print_exc()

        self._runner_thread = threading.Thread(target=_run, daemon=True)
        self._runner_thread.start()
        self._ready.wait(timeout=30)

        if self._startup_error:
            raise RuntimeError(self._startup_error)

    def _is_ib_thread(self) -> bool:
        return (
            self._runner_thread_id is not None
            and threading.get_ident() == self._runner_thread_id
        )

    def _ensure_runner_started(self, symbol: str = "MSFT", timeframe: str = "1 min") -> None:
        if self._runner_thread and self._runner_thread.is_alive() and self.ib.isConnected():
            return

        self.start(symbol, timeframe)

    def _run_on_ib_thread(
        self,
        fn: Callable[[], Any],
        *,
        timeout: float = 90.0,
        start_symbol: str = "MSFT",
        start_timeframe: str = "1 min",
    ) -> Any:
        """
        Execute fn on the IB runner thread and return its result.

        Public methods that touch self.ib should go through this wrapper unless
        they are already running on the IB thread.
        """

        if self._is_ib_thread():
            return fn()

        self._ensure_runner_started(start_symbol, start_timeframe)

        call = _IBCallRequest(fn=fn)
        self._ib_calls.put(call)

        if not call.done.wait(timeout=timeout):
            raise TimeoutError(
                f"Timed out waiting for IB runner thread after {timeout:.0f} seconds."
            )

        if call.error is not None:
            raise call.error

        return call.result

    def _process_ib_calls(self) -> None:
        while not self._ib_calls.empty():
            call = self._ib_calls.get()

            try:
                call.result = call.fn()
            except BaseException as exc:
                call.error = exc
                print(f"[IB CALL ERROR] {exc}", flush=True)
                traceback.print_exc()
            finally:
                call.done.set()

    # ------------------------------------------------------------------
    # User requests
    # ------------------------------------------------------------------

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
                traceback.print_exc()

    # ------------------------------------------------------------------
    # Contracts/history
    # ------------------------------------------------------------------

    def get_contract(self, symbol: str) -> Stock:
        """
        Public contract getter.

        Returns a cached/qualified contract. If called from a Dash thread, the
        qualification work is executed on the IB runner thread.
        """

        symbol = self._sanitize_symbol(symbol)
        return self._run_on_ib_thread(
            lambda: self._get_contract_ib(symbol),
            timeout=45,
            start_symbol=symbol,
            start_timeframe="1 min",
        )

    def _get_contract_ib(self, symbol: str) -> Stock:
        symbol = self._sanitize_symbol(symbol)

        if self.nasdaq_symbols and not self.is_valid_nasdaq_symbol(symbol):
            raise ValueError(f"{symbol} is not in NASDAQ symbol list")

        with self._lock:
            if symbol in self._contracts:
                return self._contracts[symbol]

        contract = Stock(symbol, "SMART", "USD", primaryExchange="NASDAQ")

        print(f"[IB CONTRACT QUALIFY START] {symbol}", flush=True)
        qualified = self.ib.qualifyContracts(contract)

        if not qualified:
            raise ValueError(f"Could not qualify IB stock contract for {symbol}")

        contract = qualified[0]
        print(
            f"[IB CONTRACT QUALIFY DONE] {symbol} conId={getattr(contract, 'conId', None)}",
            flush=True,
        )

        with self._lock:
            self._contracts[symbol] = contract

        return contract

    def load_history(self, symbol: str, timeframe: str) -> pd.DataFrame:
        symbol = self._sanitize_symbol(symbol)
        timeframe = self._normalize_timeframe(timeframe)

        return self._run_on_ib_thread(
            lambda: self._load_history_ib(symbol, timeframe),
            timeout=90,
            start_symbol=symbol,
            start_timeframe=timeframe,
        )

    def _load_history_ib(self, symbol: str, timeframe: str) -> pd.DataFrame:
        if timeframe not in TIMEFRAME_MAP:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        contract = self._get_contract_ib(symbol)
        bar_size, duration = TIMEFRAME_MAP[timeframe]

        print(
            f"[IB HISTORY REQUEST SEND] {symbol} timeframe={timeframe} "
            f"bar_size={bar_size} duration=1 D",
            flush=True,
        )

        bars = self.ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr="1 D",
            barSizeSetting=bar_size,
            whatToShow="TRADES",
            useRTH=True,
            formatDate=1,
            keepUpToDate=False,
        )

        print(
            f"[IB HISTORY REQUEST RETURNED] {symbol} rows={0 if bars is None else len(bars)}",
            flush=True,
        )

        df = util.df(bars)
        df = normalize_history_df(df)

        with self._lock:
            key = (symbol, "1 min")
            state = self._states.get(key, SymbolState(symbol=symbol, timeframe="1 min"))
            state.bars = df
            state.updated_at = datetime.now()
            if not df.empty:
                state.last = float(df.iloc[-1]["close"])
            self._states[key] = state

        return df

    def load_history_at(self, symbol: str, timeframe: str, end_dt: datetime) -> pd.DataFrame:
        symbol = self._sanitize_symbol(symbol)
        timeframe = self._normalize_timeframe(timeframe)

        return self._run_on_ib_thread(
            lambda: self._load_history_at_ib(symbol, timeframe, end_dt),
            timeout=90,
            start_symbol=symbol,
            start_timeframe=timeframe,
        )

    def _load_history_at_ib(self, symbol: str, timeframe: str, end_dt: datetime) -> pd.DataFrame:
        if timeframe not in TIMEFRAME_MAP:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        contract = self._get_contract_ib(symbol)
        bar_size, duration = TIMEFRAME_MAP[timeframe]

        print(
            f"[IB HISTORY_AT SEND] {symbol} timeframe={timeframe} "
            f"end={end_dt} bar_size={bar_size} duration={duration}",
            flush=True,
        )

        bars = self.ib.reqHistoricalData(
            contract,
            endDateTime=end_dt.strftime("%Y%m%d %H:%M:%S"),
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow="TRADES",
            useRTH=True,
            formatDate=1,
            keepUpToDate=False,
        )

        print(
            f"[IB HISTORY_AT RETURNED] {symbol} rows={0 if bars is None else len(bars)}",
            flush=True,
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
        symbol = self._sanitize_symbol(symbol)
        timeframe = self._normalize_timeframe(timeframe)

        return self._run_on_ib_thread(
            lambda: self._load_history_range_ib(symbol, timeframe, start_dt, end_dt),
            timeout=120,
            start_symbol=symbol,
            start_timeframe=timeframe,
        )

    def _load_history_range_ib(
        self,
        symbol: str,
        timeframe: str,
        start_dt: datetime,
        end_dt: datetime,
    ) -> pd.DataFrame:
        if start_dt >= end_dt:
            raise ValueError("start_dt must be before end_dt")

        if timeframe not in TIMEFRAME_MAP:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        print(
            f"[REALTIME load_history_range ENTERED] "
            f"symbol={symbol}, timeframe={timeframe}, start={start_dt}, end={end_dt}",
            flush=True,
        )

        pieces: list[pd.DataFrame] = []
        cursor = end_dt

        step_map = {
            "1 min": timedelta(days=1),
            "5 mins": timedelta(days=2),
            "15 mins": timedelta(days=5),
            "30 mins": timedelta(days=10),
            "1 hour": timedelta(days=30),
            "1 day": timedelta(days=365),
        }

        while cursor > start_dt:
            print(f"[LHR CHUNK START] {symbol} cursor={cursor}", flush=True)

            chunk = self._load_history_at_ib(symbol, timeframe, cursor)

            if chunk is None or chunk.empty:
                print(f"[LHR CHUNK EMPTY] {symbol} cursor={cursor}", flush=True)
                break

            pieces.append(chunk)

            oldest = pd.to_datetime(chunk["time"].min(), errors="coerce")

            if pd.isna(oldest):
                print(f"[LHR CHUNK BAD TIME] {symbol} cursor={cursor}", flush=True)
                break

            oldest_dt = oldest.to_pydatetime()

            print(
                f"[LHR CHUNK DONE] {symbol} rows={len(chunk)} "
                f"oldest={oldest_dt} newest={chunk['time'].max()}",
                flush=True,
            )

            if oldest_dt <= start_dt:
                break

            cursor = oldest_dt - timedelta(seconds=1)
            self.ib.sleep(0.25)

        if not pieces:
            return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

        out = pd.concat(pieces, ignore_index=True)
        out = out.drop_duplicates(subset="time").sort_values("time").reset_index(drop=True)
        out = out[(out["time"] >= start_dt) & (out["time"] < end_dt)].reset_index(drop=True)

        print(
            f"[LHR COMPLETE] {symbol} {start_dt} -> {end_dt} rows={len(out)}",
            flush=True,
        )

        return out

    # ------------------------------------------------------------------
    # Live data
    # ------------------------------------------------------------------

    def subscribe_live(self, symbol: str, timeframe: str = "1 min") -> None:
        symbol = self._sanitize_symbol(symbol)
        timeframe = self._normalize_timeframe(timeframe)

        self._run_on_ib_thread(
            lambda: self._subscribe_live_ib(symbol, timeframe),
            timeout=90,
            start_symbol=symbol,
            start_timeframe=timeframe,
        )

    def _subscribe_live_ib(self, symbol: str, timeframe: str = "1 min") -> None:
        contract = self._get_contract_ib(symbol)

        with self._lock:
            key = (symbol, "1 min")
            has_state = key in self._states and not self._states[key].bars.empty
            if symbol in self._tickers:
                return

        if not has_state:
            self._load_history_ib(symbol, "1 min")

        print(f"[IB LIVE SUBSCRIBE] {symbol}", flush=True)

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
        timeframe = self._normalize_timeframe(timeframe)
        key = (symbol, "1 min")

        with self._lock:
            state = self._states.get(key)

            if state is None:
                raise ValueError(f"No loaded state for {symbol} 1 min")

            bars = state.bars.copy()

            if state.last is not None:
                try:
                    bars = apply_tick_to_bars(
                        bars,
                        price=float(state.last),
                        size=float(state.last_size or 0),
                        tick_time=datetime.now(),
                    )

                    state.bars = bars.copy()
                    self._states[key] = state

                except Exception as exc:
                    print(f"[SNAPSHOT BAR PATCH ERROR] {symbol}: {exc}", flush=True)

            bid = state.bid
            ask = state.ask
            last = state.last
            last_size = state.last_size
            updated_at = state.updated_at
            tick_count = state.tick_count

        if timeframe != "1 min":
            bars = resample_bars(bars, timeframe)

        return SymbolState(
            symbol=symbol,
            timeframe=timeframe,
            bars=bars,
            bid=bid,
            ask=ask,
            last=last,
            last_size=last_size,
            updated_at=updated_at,
            tick_count=tick_count,
        )

    def ensure_symbol_ready(self, symbol: str, timeframe: str) -> None:
        symbol = self._sanitize_symbol(symbol)
        timeframe = self._normalize_timeframe(timeframe)

        # This method is called on the IB runner thread during startup/request
        # processing, so call the private IB-thread methods directly.
        self._load_history_ib(symbol, "1 min")
        self._subscribe_live_ib(symbol, "1 min")

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_timeframe(timeframe: str) -> str:
        tf = str(timeframe or "1 min").lower().strip()
        tf = TIMEFRAME_ALIASES.get(tf, tf)

        if tf not in TIMEFRAME_MAP:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        return tf

    @staticmethod
    def _sanitize_symbol(symbol: str) -> str:
        cleaned = "".join(
            ch for ch in str(symbol or "").upper().strip()
            if ch.isalnum() or ch in {".", "-"}
        )
        if not cleaned:
            raise ValueError("Invalid symbol.")
        return cleaned
