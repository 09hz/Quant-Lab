from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from core.RealTime import RealTimeIB
from core.ReplayModule import ReplayEngine


class ReplayService:
    def __init__(self, rt: RealTimeIB, engine: ReplayEngine):
        self.rt = rt
        self.engine = engine
        self.cache: dict[tuple[str, str, str], pd.DataFrame] = {}

    def _make_cache_key(
        self,
        symbol: str,
        timeframe: str,
        replay_date: Optional[str],
    ) -> tuple[str, str, str]:
        symbol = self.rt._sanitize_symbol(symbol)
        return (symbol, timeframe or "1 min", replay_date or "latest")

    def clear_cache(self) -> None:
        self.cache.clear()

    def load_replay(
        self,
        symbol: str,
        timeframe: str = "1 min",
        replay_date: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> tuple[str, dict]:
        symbol = self.rt._sanitize_symbol(symbol)
        timeframe = timeframe or "1 min"
        cache_key = self._make_cache_key(symbol, timeframe, replay_date)

        if cache_key in self.cache:
            hist = self.cache[cache_key]
        else:
            if replay_date:
                start_dt = datetime.fromisoformat(replay_date)
                end_dt = start_dt + timedelta(days=1)
                hist = self.rt.load_history_range(symbol, timeframe, start_dt, end_dt)
            else:
                hist = self.rt.load_history(symbol, timeframe)
            self.cache[cache_key] = hist

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

        return f"Replay loaded for {symbol} ({len(hist)} bars)", self.engine.info()

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