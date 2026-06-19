from __future__ import annotations

import hashlib
from dataclasses import dataclass

import pandas as pd

from core.StrategyEngine import StrategyEngine, StrategyScriptResult


@dataclass
class StrategyOverlaySnapshot:
    key: str
    result: StrategyScriptResult
    errors: list[str]


class StrategyOverlayService:
    """
    Caches strategy results so replay ticks do not repeatedly parse scripts,
    calculate indicators, build signals, and merge background ranges.
    """

    def __init__(self):
        self.engine = StrategyEngine()
        self._key: str | None = None
        self._snapshot: StrategyOverlaySnapshot | None = None

    def clear(self) -> None:
        self._key = None
        self._snapshot = None

    def make_key(
        self,
        script: str,
        bars: pd.DataFrame,
        symbol: str,
        timeframe: str,
        source_label: str = "",
    ) -> str | None:
        if bars is None or bars.empty:
            return None

        script_hash = hashlib.sha256(
            str(script or "").encode("utf-8")
        ).hexdigest()

        last_time = ""
        first_time = ""

        if "time" in bars.columns:
            times = pd.to_datetime(bars["time"], errors="coerce")
            if not times.empty:
                first_time = str(times.min())
                last_time = str(times.max())

        raw = "|".join(
            [
                str(symbol or "").upper().strip(),
                str(timeframe or ""),
                str(source_label or ""),
                str(len(bars)),
                first_time,
                last_time,
                script_hash,
            ]
        )

        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get_or_run(
        self,
        script: str,
        bars: pd.DataFrame,
        symbol: str,
        timeframe: str,
        source_label: str = "",
    ) -> StrategyOverlaySnapshot | None:
        if not str(script or "").strip():
            return None

        key = self.make_key(
            script=script,
            bars=bars,
            symbol=symbol,
            timeframe=timeframe,
            source_label=source_label,
        )

        if key is None:
            return None

        if self._snapshot is not None and self._key == key:
            return self._snapshot

        result = self.engine.run(script, bars)
        snapshot = StrategyOverlaySnapshot(
            key=key,
            result=result,
            errors=list(result.errors or []),
        )

        self._key = key
        self._snapshot = snapshot

        print(
            f"[STRATEGY CACHE REFRESH] {symbol} {timeframe} "
            f"bars={len(bars):,} signals={len(result.signals or [])} "
            f"errors={len(result.errors or [])}",
            flush=True,
        )

        return snapshot