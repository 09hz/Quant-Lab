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
    # A one-hour replay should open on the latest loaded session.
    "1 hour": "1D",
    # Daily replay should open on the full loaded daily range.
    "1 day": "MAX",
}


def _normalize_timeframe(value: Any) -> str:
    text = str(value or "1 min").strip().lower()
    text = " ".join(text.replace("_", " ").replace("-", " ").split())

    aliases = {
        "1m": "1 min",
        "1 min": "1 min",
        "1 minute": "1 min",
        "1 minutes": "1 min",
        "5m": "5 min",
        "5 min": "5 min",
        "5 mins": "5 min",
        "5 minute": "5 min",
        "5 minutes": "5 min",
        "15m": "15 min",
        "15 min": "15 min",
        "15 mins": "15 min",
        "15 minute": "15 min",
        "15 minutes": "15 min",
        "30m": "30 min",
        "30 min": "30 min",
        "30 mins": "30 min",
        "30 minute": "30 min",
        "30 minutes": "30 min",
        "1h": "1 hour",
        "1 hr": "1 hour",
        "1 hour": "1 hour",
        "hour": "1 hour",
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


def default_range_for_timeframe(display_timeframe: Any) -> str:
    timeframe = _normalize_timeframe(display_timeframe)
    return _TIMEFRAME_DEFAULT_RANGE.get(timeframe, "1D")


def _default_state_for_timeframe(display_timeframe: Any) -> dict[str, Any]:
    timeframe = _normalize_timeframe(display_timeframe)
    range_key = default_range_for_timeframe(timeframe)
    return {
        "mode": "live",
        "range_key": range_key,
        "x_range": None,
        "y_range": None,
        "display_timeframe": timeframe,
    }


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


def _coerce_time(value: Any):
    try:
        return pd.to_datetime(value, errors="coerce")
    except Exception:
        return pd.NaT


def _manual_x_range_overlaps_bars(state: dict[str, Any], chart_bars: Any) -> bool:
    x_range = state.get("x_range")
    if not x_range or not isinstance(x_range, (list, tuple)) or len(x_range) < 2:
        return False

    df = _clean_bars_for_time_bounds(chart_bars)
    if df.empty:
        return True

    x0 = _coerce_time(x_range[0])
    x1 = _coerce_time(x_range[1])

    if pd.isna(x0) or pd.isna(x1):
        return False

    if x1 < x0:
        x0, x1 = x1, x0

    min_time = df["time"].min()
    max_time = df["time"].max()

    if pd.isna(min_time) or pd.isna(max_time):
        return True

    return not (x1 < min_time or x0 > max_time)


def _manual_range_too_narrow_for_timeframe(state: dict[str, Any], display_timeframe: Any) -> bool:
    x_range = state.get("x_range")
    if not x_range or not isinstance(x_range, (list, tuple)) or len(x_range) < 2:
        return False

    x0 = _coerce_time(x_range[0])
    x1 = _coerce_time(x_range[1])

    if pd.isna(x0) or pd.isna(x1):
        return True

    if x1 < x0:
        x0, x1 = x1, x0

    span = x1 - x0
    timeframe = _normalize_timeframe(display_timeframe)

    if timeframe == "1 day" and span < pd.Timedelta(days=14):
        return True

    if timeframe == "1 hour" and span < pd.Timedelta(hours=4):
        return True

    return False


def normalize_watch_chart_state_for_render(
    chart_state: dict[str, Any] | None = None,
    chart_bars: Any = None,
    display_timeframe: Any = "1 min",
    *,
    price_source: str | None = None,
    trigger_id: str | None = None,
    **_: Any,
) -> tuple[dict[str, Any], str]:
    """
    Normalize Watch chart state before applying the viewport.

    Return contract:
        (normalized_state, default_range)

    callbacks.py expects exactly two values. A previous hotfix accidentally
    returned only the dict, which made Python unpack dict keys and raised:
    "too many values to unpack (expected 2)".
    """

    # Backward tolerance for accidental positional calls:
    # normalize_watch_chart_state_for_render(state, "1 day")
    if isinstance(chart_bars, str) and display_timeframe in (None, "1 min"):
        display_timeframe = chart_bars
        chart_bars = None

    timeframe = _normalize_timeframe(display_timeframe)
    default_range = default_range_for_timeframe(timeframe)
    default_state = _default_state_for_timeframe(timeframe)

    state = dict(chart_state or {})
    if not state:
        return default_state, default_range

    state["display_timeframe"] = timeframe

    mode = str(state.get("mode") or "live").lower().strip()
    range_key = _safe_range_key(state.get("range_key"), default_range)

    triggered_by_data_or_timeframe = str(trigger_id or "") in {
        "watch-timeframe-dropdown",
        "watch-load-request",
        "replay-render-trigger",
    }

    # Daily replay should never inherit an intraday/manual window on load.
    if timeframe == "1 day":
        if triggered_by_data_or_timeframe or mode == "manual":
            state = {
                "mode": "live",
                "range_key": "MAX",
                "x_range": None,
                "y_range": None,
                "display_timeframe": timeframe,
            }
            return state, default_range

        state["mode"] = "live"
        state["range_key"] = "MAX"
        state["x_range"] = None
        state["y_range"] = None
        return state, default_range

    # Hourly replay should open on the latest session-style window.
    if timeframe == "1 hour":
        if triggered_by_data_or_timeframe or mode == "manual":
            state = {
                "mode": "live",
                "range_key": "1D",
                "x_range": None,
                "y_range": None,
                "display_timeframe": timeframe,
            }
            return state, default_range

    if mode == "manual":
        if (
            not _manual_x_range_overlaps_bars(state, chart_bars)
            or _manual_range_too_narrow_for_timeframe(state, timeframe)
        ):
            return default_state, default_range

        state["mode"] = "manual"
        state["range_key"] = range_key
        state.setdefault("x_range", None)
        state.setdefault("y_range", None)
        return state, default_range

    state["mode"] = "live"
    state["range_key"] = range_key
    state.setdefault("x_range", None)
    state.setdefault("y_range", None)

    return state, default_range
