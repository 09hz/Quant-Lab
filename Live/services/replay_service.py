from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from core.RealTime import RealTimeIB
from core.ReplayModule import ReplayEngine
from services.bar_store import BarStore


class ReplayService:
    """
    Replay data coordinator.

    Fast path:
        memory cache -> disk cache -> already-loaded live bars -> IB historical request

    The replay engine itself only plays already-loaded bars. It should never
    request IB data during playback.
    """

    def __init__(
        self,
        rt: RealTimeIB,
        engine: ReplayEngine,
        bar_store: Optional[BarStore] = None,
    ):
        self.rt = rt
        self.engine = engine
        self.bar_store = bar_store or BarStore()
        self.memory_cache: dict[tuple[str, str, str], pd.DataFrame] = {}

        self.current_symbol: Optional[str] = None
        self.current_timeframe: str = "1 min"
        self.current_replay_date: Optional[str] = None

    def _make_cache_key(
        self,
        symbol: str,
        timeframe: str,
        replay_date: Optional[str],
    ) -> tuple[str, str, str]:
        symbol = self.rt._sanitize_symbol(symbol)
        timeframe = timeframe or "1 min"
        date_key = replay_date or "latest"
        return symbol, timeframe, date_key

    def clear_memory_cache(self) -> None:
        self.memory_cache.clear()

    def clear_disk_cache(self) -> None:
        self.bar_store.clear_all()

    def clear_cache(self) -> None:
        self.clear_memory_cache()

    def clear_symbol_cache(self, symbol: str) -> None:
        symbol = self.rt._sanitize_symbol(symbol)

        for key in [key for key in self.memory_cache if key[0] == symbol]:
            del self.memory_cache[key]

        self.bar_store.delete(symbol)

    def _load_from_rt_or_ib(
        self,
        symbol: str,
        timeframe: str,
        replay_date: Optional[str],
    ) -> pd.DataFrame:
        if replay_date:
            start_dt = datetime.fromisoformat(replay_date)
            end_dt = start_dt + timedelta(days=1)
            return self.rt.load_history_range(symbol, timeframe, start_dt, end_dt)

        # If the live app already has bars for this symbol, use them.
        # This avoids a duplicate IB historical request for "latest" replay.
        try:
            snap = self.rt.get_snapshot(symbol, timeframe)
            if snap.bars is not None and not snap.bars.empty:
                return snap.bars.copy()
        except Exception:
            pass

        return self.rt.load_history(symbol, timeframe)

    def get_history(
        self,
        symbol: str,
        timeframe: str = "1 min",
        replay_date: Optional[str] = None,
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        symbol = self.rt._sanitize_symbol(symbol)
        timeframe = timeframe or "1 min"
        key = self._make_cache_key(symbol, timeframe, replay_date)

        if not force_refresh:
            cached = self.memory_cache.get(key)
            if cached is not None and not cached.empty:
                print(f"[REPLAY CACHE] memory hit {key}", flush=True)
                return cached.copy()

            disk_df = self.bar_store.read(symbol, timeframe, replay_date)
            if disk_df is not None and not disk_df.empty:
                print(f"[REPLAY CACHE] disk hit {key}", flush=True)
                self.memory_cache[key] = disk_df.copy()
                return disk_df.copy()

        print(f"[REPLAY CACHE] IB/live load {key}", flush=True)

        hist = self._load_from_rt_or_ib(
            symbol=symbol,
            timeframe=timeframe,
            replay_date=replay_date,
        )

        if hist is None:
            hist = pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

        self.memory_cache[key] = hist.copy()

        if not hist.empty:
            self.bar_store.write(symbol, timeframe, replay_date, hist)

        return hist.copy()

    def load_replay(
        self,
        symbol: str,
        timeframe: str = "1 min",
        replay_date: Optional[str] = None,
        speed: Optional[float] = None,
        force_refresh: bool = False,
        force_reload: Optional[bool] = None,
    ) -> tuple[str, dict]:
        # force_reload is kept for backwards compatibility with older callbacks.
        if force_reload is not None:
            force_refresh = force_reload

        symbol = self.rt._sanitize_symbol(symbol)
        timeframe = timeframe or "1 min"

        hist = self.get_history(
            symbol=symbol,
            timeframe=timeframe,
            replay_date=replay_date,
            force_refresh=force_refresh,
        )

        self.current_symbol = symbol
        self.current_timeframe = timeframe
        self.current_replay_date = replay_date

        if hist is None or hist.empty:
            self.engine.reset()
            if speed is not None:
                self.engine.set_speed(speed)

            return f"No replay history returned for {symbol}", {
                "playing": False,
                "speed": self.engine.speed,
                "current_index": 1,
                "max_index": 0,
            }

        self.engine.reset()
        self.engine.load_from_df(hist)

        if speed is not None:
            self.engine.set_speed(speed)

        date_label = replay_date or "latest"
        return (
            f"Replay loaded for {symbol} ({timeframe}, {date_label}, {len(hist)} bars)",
            self.engine.info(),
        )

    def play(self) -> None:
        self.engine.play()

    def pause(self) -> None:
        self.engine.pause()

    def rewind(self, steps: int = 1) -> None:
        self.engine.rewind(steps)

    def forward(self, steps: int = 1) -> None:
        self.engine.forward(steps)

    def set_index(self, index: int) -> None:
        self.engine.set_index(index)

    def set_speed(self, speed: float) -> None:
        self.engine.set_speed(speed)

    def tick(self) -> None:
        self.engine.tick()

    def visible_bars(self) -> pd.DataFrame:
        return self.engine.visible_bars()

    def current_bar(self):
        return self.engine.current_bar()

    def info(self) -> dict:
        return self.engine.info()

    def reset(self) -> None:
        self.engine.reset()
