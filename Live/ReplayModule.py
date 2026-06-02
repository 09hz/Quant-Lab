from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


@dataclass
class ReplayEngine:
    bars: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(
        columns=["time", "open", "high", "low", "close", "volume"]
    ))
    current_index: int = 1
    playing: bool = False
    speed: float = 1.0
    progress: float = 0.0

    def reset(self) -> None:
        self.bars = pd.DataFrame(
            columns=["time", "open", "high", "low", "close", "volume"]
        )
        self.current_index = 1
        self.playing = False
        self.speed = 1.0
        self.progress = 0.0

    def load_from_csv(self, path: str) -> None:
        df = pd.read_csv(path)
        self.load_from_df(df)

    def load_from_df(self, df: pd.DataFrame) -> None:
        if df is None or df.empty:
            raise ValueError("Replay data is empty.")

        out = df.copy()

        if "time" not in out.columns:
            if "date" in out.columns:
                out = out.rename(columns={"date": "time"})
            elif "Date" in out.columns:
                out = out.rename(columns={"Date": "time"})
            elif "datetime" in out.columns:
                out = out.rename(columns={"datetime": "time"})
            elif "Datetime" in out.columns:
                out = out.rename(columns={"Datetime": "time"})

        required = ["time", "open", "high", "low", "close", "volume"]
        missing = [c for c in required if c not in out.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        out = out[required].copy()
        out["time"] = pd.to_datetime(out["time"], errors="coerce")
        out = out.dropna(subset=["time"]).sort_values("time").drop_duplicates(subset="time")

        out["open"] = pd.to_numeric(out["open"], errors="coerce")
        out["high"] = pd.to_numeric(out["high"], errors="coerce")
        out["low"] = pd.to_numeric(out["low"], errors="coerce")
        out["close"] = pd.to_numeric(out["close"], errors="coerce")
        out["volume"] = pd.to_numeric(out["volume"], errors="coerce").fillna(0)

        out = out.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)

        if out.empty:
            raise ValueError("Replay data became empty after cleaning.")

        self.bars = out
        self.current_index = max(1, min(100, len(out)))
        self.playing = False
        self.progress = 0.0

    def play(self) -> None:
        self.playing = True

    def pause(self) -> None:
        self.playing = False

    def rewind(self, steps: int = 1) -> None:
        self.current_index = max(1, self.current_index - max(1, steps))

    def forward(self, steps: int = 1) -> None:
        self.current_index = min(len(self.bars), self.current_index + max(1, steps))

    def set_index(self, index: int) -> None:
        if self.bars.empty:
            return
        self.current_index = max(1, min(int(index), len(self.bars)))

    def set_speed(self, speed: float) -> None:
        self.speed = max(0.25, float(speed))

    def tick(self) -> None:
        if not self.playing or self.bars.empty:
            return

        self.progress += self.speed
        step = int(self.progress)

        if step < 1:
            return

        self.progress -= step
        self.current_index = min(len(self.bars), self.current_index + step)

        if self.current_index >= len(self.bars):
            self.playing = False

    def visible_bars(self) -> pd.DataFrame:
        if self.bars.empty:
            return self.bars.copy()
        return self.bars.iloc[:self.current_index].copy()

    def current_bar(self) -> Optional[pd.Series]:
        visible = self.visible_bars()
        if visible.empty:
            return None
        return visible.iloc[-1]

    def info(self) -> dict:
        return {
            "playing": self.playing,
            "speed": self.speed,
            "current_index": self.current_index,
            "max_index": len(self.bars),
        }