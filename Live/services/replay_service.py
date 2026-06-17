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
        print(
            f"[REPLAY SOURCE] requesting symbol={symbol}, "
            f"timeframe={timeframe}, date={replay_date}",
            flush=True,
        )

        if replay_date:
            start_dt = datetime.fromisoformat(replay_date)

            today = datetime.now().date()
            if start_dt.date() > today:
                raise ValueError("Replay date cannot be in the future.")

            end_dt = start_dt + timedelta(days=1)

            print(
                f"[REPLAY SOURCE] loading range {start_dt} -> {end_dt}",
                flush=True,
            )

            df = self.rt.load_history_range(
                symbol,
                timeframe,
                start_dt,
                end_dt,
            )

            print(
                f"[RT HISTORY RANGE RESULT] {symbol} {timeframe} "
                f"{start_dt} -> {end_dt} rows={0 if df is None else len(df)}",
                flush=True,
            )

            if df is not None:
                print(
                    f"[RT HISTORY RANGE COLUMNS] {list(df.columns)}",
                    flush=True,
                )

            return df

        # If the live app already has bars for this symbol, use them.
        try:
            snap = self.rt.get_snapshot(symbol, timeframe)

            if snap.bars is not None and not snap.bars.empty:
                print(
                    f"[REPLAY SOURCE] using live snapshot bars "
                    f"{symbol} {timeframe} rows={len(snap.bars)}",
                    flush=True,
                )
                return snap.bars.copy()

        except Exception as snap_exc:
            print(f"[REPLAY SOURCE] live snapshot unavailable: {snap_exc}", flush=True)

        df = self.rt.load_history(symbol, timeframe)

        print(
            f"[RT HISTORY RESULT] {symbol} {timeframe} rows={0 if df is None else len(df)}",
            flush=True,
        )

        if df is not None:
            print(
                f"[RT HISTORY COLUMNS] {list(df.columns)}",
                flush=True,
            )

        return df

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
        try:
            print(
                f"[REPLAY SOURCE RESULT] symbol={symbol} timeframe={timeframe} "
                f"date={replay_date} rows={0 if hist is None else len(hist)} "
                f"columns={[] if hist is None else list(hist.columns)}",
                flush=True,
            )

            if hist is not None and not hist.empty and "time" in hist.columns:
                print(
                    f"[REPLAY SOURCE RESULT] first={hist['time'].iloc[0]} "
                    f"last={hist['time'].iloc[-1]}",
                    flush=True,
                )
        except Exception as debug_exc:
            print(f"[REPLAY SOURCE DEBUG ERROR] {debug_exc}", flush=True)



        if hist is None:
            hist = pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

        self.memory_cache[key] = hist.copy()

        if not hist.empty:
            self.bar_store.write(symbol, timeframe, replay_date, hist)

        return hist.copy()

    def load_date_range(
            self,
            symbol: str,
            start_date,
            end_date,
            timeframe: str = "1 min",
            speed: Optional[float] = 1,
            force_refresh: bool = False,
    ) -> pd.DataFrame:
        """
        Load and stitch multiple weekday replay sessions into one active replay dataset.

        Important:
            * Weekends are skipped.
            * Raw replay data is always loaded as 1-minute bars.
            * The Watch Interval dropdown should resample the chart display only.
            * The stitched DataFrame is installed into ReplayEngine, so visible_bars(),
              current_bar(), info(), the replay slider, paper trading, and backtests all
              read from the same multi-day dataset.
        """

        symbol = self.rt._sanitize_symbol(symbol)

        start = pd.to_datetime(start_date, errors="coerce")
        end = pd.to_datetime(end_date, errors="coerce")

        if pd.isna(start) or pd.isna(end):
            raise ValueError("Invalid replay date range.")

        if end < start:
            start, end = end, start

        today = datetime.now().date()
        if start.date() > today or end.date() > today:
            raise ValueError("Replay date range cannot include future dates.")

        days: list[str] = []
        current = start.normalize()

        while current <= end.normalize():
            if int(current.weekday()) < 5:
                days.append(current.date().isoformat())
            current = current + pd.Timedelta(days=1)

        if not days:
            raise ValueError("No weekday trading days found in selected range.")

        # The replay engine uses 1-minute source bars. Display intervals are handled
        # later by callbacks._resample_watch_bars(...).
        load_timeframe = "1 min"
        chunks: list[pd.DataFrame] = []

        for day in days:
            try:
                hist = self.get_history(
                    symbol=symbol,
                    timeframe=load_timeframe,
                    replay_date=day,
                    force_refresh=force_refresh,
                )
            except Exception as exc:
                print(f"[REPLAY RANGE] {symbol} {day}: load failed: {exc}", flush=True)
                continue

            if hist is None or hist.empty:
                print(f"[REPLAY RANGE] {symbol} {day}: no bars returned.", flush=True)
                continue

            day_bars = hist.copy()

            if "time" in day_bars.columns:
                day_bars["time"] = pd.to_datetime(
                    day_bars["time"],
                    errors="coerce",
                    format="mixed",
                )
                day_bars = day_bars.dropna(subset=["time"]).copy()

            required = {"time", "open", "high", "low", "close", "volume"}
            if not required.issubset(set(day_bars.columns)):
                print(
                    f"[REPLAY RANGE] {symbol} {day}: missing columns "
                    f"{sorted(required - set(day_bars.columns))}.",
                    flush=True,
                )
                continue

            if day_bars.empty:
                print(f"[REPLAY RANGE] {symbol} {day}: empty after cleaning.", flush=True)
                continue

            print(
                f"[REPLAY RANGE] {symbol} {day}: collected {len(day_bars):,} bars.",
                flush=True,
            )
            chunks.append(day_bars[["time", "open", "high", "low", "close", "volume"]].copy())

        if not chunks:
            raise ValueError("No replay bars found for selected date range.")

        stitched = pd.concat(chunks, ignore_index=True)

        stitched["time"] = pd.to_datetime(
            stitched["time"],
            errors="coerce",
            format="mixed",
        )
        stitched = stitched.dropna(subset=["time"]).copy()

        for col in ["open", "high", "low", "close"]:
            stitched[col] = pd.to_numeric(stitched[col], errors="coerce")

        stitched["volume"] = pd.to_numeric(
            stitched["volume"],
            errors="coerce",
        ).fillna(0)

        stitched = (
            stitched
            .dropna(subset=["open", "high", "low", "close"])
            .sort_values("time")
            .drop_duplicates(subset="time")
            .reset_index(drop=True)
        )

        if stitched.empty:
            raise ValueError("Replay date range became empty after cleaning.")

        self.current_symbol = symbol
        self.current_timeframe = load_timeframe
        self.current_replay_date = start.date().isoformat()
        self.current_replay_end_date = end.date().isoformat()

        self.engine.reset()
        self.engine.load_from_df(stitched)

        if speed is not None:
            self.engine.set_speed(speed)

        print(
            f"[REPLAY RANGE] installed stitched dataset: "
            f"{symbol} {start.date().isoformat()} -> {end.date().isoformat()} "
            f"{len(stitched):,} bars.",
            flush=True,
        )

        return stitched

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


    def all_bars(self) -> pd.DataFrame:
        """
        Return the full loaded replay dataset.
        """
        return self.engine.all_bars()

    def full_bars(self) -> pd.DataFrame:
        return self.all_bars()

    def loaded_bars(self) -> pd.DataFrame:
        return self.all_bars()

    def visible_bars(self) -> pd.DataFrame:
        return self.engine.visible_bars()

    def all_bars(self) -> pd.DataFrame:
        """
        Return the full loaded replay dataset.

        This is what backtests should use.
        It includes the full stitched date range when a replay range is loaded.
        """
        if self.engine is None or self.engine.bars is None:
            return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

        return self.engine.bars.copy()

    def full_bars(self) -> pd.DataFrame:
        """
        Alias for all_bars().
        """
        return self.all_bars()

    def loaded_bars(self) -> pd.DataFrame:
        """
        Alias for all_bars().
        """
        return self.all_bars()

    def current_bar(self):
        return self.engine.current_bar()

    def info(self) -> dict:
        return self.engine.info()

    def reset(self) -> None:
        self.engine.reset()
