from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd


class BarStore:
    """
    Disk-backed OHLCV cache.

    This survives app restarts because data is written to parquet files.
    ReplayService should ask this class for cached bars before going to IB.
    """

    def __init__(self, root_dir: str | Path = "cache/replay"):
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _safe_timeframe(self, timeframe: str) -> str:
        return (timeframe or "1 min").replace(" ", "_").replace("/", "_")

    def _safe_date(self, replay_date: Optional[str]) -> str:
        return replay_date or "latest"

    def path_for(self, symbol: str, timeframe: str, replay_date: Optional[str]) -> Path:
        symbol = symbol.upper().strip()
        timeframe = self._safe_timeframe(timeframe)
        replay_date = self._safe_date(replay_date)

        return self.root_dir / symbol / timeframe / f"{replay_date}.parquet"

    def exists(self, symbol: str, timeframe: str, replay_date: Optional[str]) -> bool:
        return self.path_for(symbol, timeframe, replay_date).exists()

    def read(self, symbol: str, timeframe: str, replay_date: Optional[str]) -> Optional[pd.DataFrame]:
        path = self.path_for(symbol, timeframe, replay_date)

        if not path.exists():
            return None

        try:
            df = pd.read_parquet(path)
            if df is None or df.empty:
                return None
            return df
        except Exception as exc:
            print(f"[BAR STORE READ ERROR] {path}: {exc}", flush=True)
            return None

    def write(self, symbol: str, timeframe: str, replay_date: Optional[str], df: pd.DataFrame) -> None:
        if df is None or df.empty:
            return

        path = self.path_for(symbol, timeframe, replay_date)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(path, index=False)
            print(f"[BAR STORE WRITE] {path}", flush=True)
        except Exception as exc:
            print(f"[BAR STORE WRITE ERROR] {path}: {exc}", flush=True)

    def delete(self, symbol: str, timeframe: Optional[str] = None, replay_date: Optional[str] = None) -> None:
        symbol = symbol.upper().strip()

        if timeframe and replay_date:
            path = self.path_for(symbol, timeframe, replay_date)
            if path.exists():
                path.unlink()
            return

        symbol_dir = self.root_dir / symbol
        if not symbol_dir.exists():
            return

        for path in symbol_dir.rglob("*.parquet"):
            try:
                path.unlink()
            except OSError:
                pass

    def clear_all(self) -> None:
        if not self.root_dir.exists():
            return

        for path in self.root_dir.rglob("*.parquet"):
            try:
                path.unlink()
            except OSError:
                pass