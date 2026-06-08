from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd


class ReplayService:
    def __init__(self, rt, engine):
        self.rt = rt
        self.engine = engine
        self.cache: dict[tuple[str, str, str], pd.DataFrame] = {}

    def _make_cache_key(self, symbol: str, timeframe: str, replay_date: Optional[str]) -> tuple[str, str, str]:
        return (symbol, timeframe, replay_date or "latest")

    def clear_cache(self) -> None:
        self.cache.clear()

    def clear_symbol_cache(self, symbol: str) -> None:
        symbol = self.rt._sanitize_symbol(symbol)
        keys_to_remove = [k for k in self.cache if k[0] == symbol]
        for k in keys_to_remove:
            del self.cache[k]

    def load_replay(self, symbol: str, timeframe: str = "1 min", replay_date: Optional[str] = None, speed: Optional[float] = None):
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
            return f"No replay history returned for {symbol}", {
                "playing": False,
                "speed": speed or 1.0,
                "current_index": 1,
                "max_index": 0,
            }

        self.engine.reset()
        self.engine.load_from_df(hist)

        if speed is not None:
            self.engine.set_speed(speed)

        return f"Replay loaded for {symbol} ({timeframe}, {len(hist)} bars)", self.engine.info()

    def play(self):
        self.engine.play()

    def pause(self):
        self.engine.pause()

    def rewind(self, steps: int = 1):
        self.engine.rewind(steps)

    def forward(self, steps: int = 1):
        self.engine.forward(steps)

    def set_index(self, index: int):
        self.engine.set_index(index)

    def set_speed(self, speed: float):
        self.engine.set_speed(speed)

    def tick(self):
        self.engine.tick()

    def visible_bars(self):
        return self.engine.visible_bars()

    def info(self):
        return self.engine.info()

    def reset(self):
        self.engine.reset()