from __future__ import annotations

from typing import Any

import pandas as pd


_ALLOWED_RANGE_KEYS = {"1D", "1W", "1M", "3M", "1Y", "5Y", "MAX"}

_TIMEFRAME_DEFAULT_RANGE = {
    "1 min": "1D",
    "5 min": "1W",
    "5 mins": "1W",
    "15 min": "1M",
    "15 mins": "1M",
    "30 min": "3M",
    "30 mins": "3M",
    "1 hour": "1D",
    "1 day": "MAX",
}


def _normalize_timeframe(value: Any) -> str:
    text = str(value or "1 min").strip().lower()
    text = " ".join(text.replace("_", " ").split())

    aliases = {
        "1m": "1 min",
        "1 min": "1 min",
        "1 minute": "1 min",
        "5m": "5 min",
        "5 min": "5 min",
        "5 mins": "5 min",
        "5 minutes": "5 min",
        "15m": "15 min",
        "15 min": "15 min",
        "15 mins": "15 min",
        "15 minutes": "15 min",
        "30m": "30 min",
        "30 min": "30 min",
        "30 mins": "30 min",
        "30 minutes": "30 min",
        "1h": "1 hour",
        "1 hr": "1 hour",
        "1 hour": "1 hour",
        "60 min": "1 hour",
        "1d": "1 day",
        "1 day": "1 day",
        "day": "1 day",
        "daily": "1 day",
    }

    return aliases.get(text, text or "1 min")


def _safe_range_key(value: Any, default: str = "1D") -> str:
    text = str(value or default).upper().strip()
    if text in _ALLOWED_RANGE_KEYS:
        return text
    return default


def _clean_bars_for_time_bounds(chart_bars: Any) -> pd.DataFrame:
    if chart_bars is None:
        return pd.DataFrame(columns=["time"])

    try:
        if getattr(chart_bars, "empty", True):
            return pd.DataFrame(columns=["time"])

        df = chart_bars.copy()
        if "time" not in df.columns:
            return pd.DataFrame(columns=["time"])

        df["time"] = pd.to_datetime(df["time"], errors="coerce")
        df = df.dropna(subset=["time"])
        return df
    except Exception:
        return pd.DataFrame(columns=["time"])


def _manual_x_range_overlaps_bars(state: dict[str, Any], chart_bars: Any) -> bool:
    x_range = state.get("x_range")
    if not x_range or not isinstance(x_range, (list, tuple)) or len(x_range) < 2:
        return False

    df = _clean_bars_for_time_bounds(chart_bars)
    if df.empty:
        return True

    try:
        x0 = pd.to_datetime(x_range[0], errors="coerce")
        x1 = pd.to_datetime(x_range[1], errors="coerce")
    except Exception:
        return False

    if pd.isna(x0) or pd.isna(x1):
        return False

    if x1 < x0:
        x0, x1 = x1, x0

    min_time = df["time"].min()
    max_time = df["time"].max()

    if pd.isna(min_time) or pd.isna(max_time):
        return True

    return not (x1 < min_time or x0 > max_time)


def _default_state_for_timeframe(display_timeframe: Any) -> dict[str, Any]:
    timeframe = _normalize_timeframe(display_timeframe)
    range_key = _TIMEFRAME_DEFAULT_RANGE.get(timeframe, "1D")
    return {
        "mode": "live",
        "range_key": range_key,
        "x_range": None,
        "y_range": None,
        "display_timeframe": timeframe,
    }


def normalize_watch_chart_state_for_render(
    chart_state: dict[str, Any] | None = None,
    chart_bars: Any = None,
    display_timeframe: Any = "1 min",
    **_: Any,
) -> dict[str, Any]:
    """
    Normalize Watch chart state before applying the viewport.

    Goals:
    - Do not carry stale 1-minute manual zoom into 1-hour or 1-day replay.
    - Open 1-hour replay on the latest session / 1D style window.
    - Open 1-day replay on the full loaded daily range so candles are visible.
    - Preserve a valid manual zoom only when it overlaps the current loaded bars.
    """

    if isinstance(chart_bars, str) and display_timeframe in (None, "1 min"):
        display_timeframe = chart_bars
        chart_bars = None

    timeframe = _normalize_timeframe(display_timeframe)
    default_state = _default_state_for_timeframe(timeframe)

    state = dict(chart_state or {})
    if not state:
        return default_state

    mode = str(state.get("mode") or "live").lower().strip()
    default_range = _TIMEFRAME_DEFAULT_RANGE.get(timeframe, "1D")
    range_key = _safe_range_key(state.get("range_key"), default_range)

    if mode == "manual":
        if _manual_x_range_overlaps_bars(state, chart_bars):
            state["range_key"] = range_key
            state["display_timeframe"] = timeframe
            return state
        return default_state

    if timeframe == "1 day":
        state["mode"] = "live"
        state["range_key"] = "MAX"
        state["x_range"] = None
        state["y_range"] = None
        state["display_timeframe"] = timeframe
        return state

    if timeframe == "1 hour":
        state["mode"] = "live"
        state["range_key"] = "1D"
        state["x_range"] = None
        state["y_range"] = None
        state["display_timeframe"] = timeframe
        return state

    state["range_key"] = range_key
    state["display_timeframe"] = timeframe
    state.setdefault("x_range", None)
    state.setdefault("y_range", None)
    return state
