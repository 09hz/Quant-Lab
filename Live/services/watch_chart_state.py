from __future__ import annotations

from typing import Any

import pandas as pd


_TIMEFRAME_DEFAULT_RANGE = {
    "1 min": "1D",
    "5 min": "1W",
    "15 min": "1M",
    "30 min": "3M",
    "1 hour": "3M",
    "1 day": "1Y",
}


_TIMEFRAME_MIN_RANGE = {
    "1 min": {"1D", "1W", "1M", "3M", "1Y", "5Y", "MAX"},
    "5 min": {"1W", "1M", "3M", "1Y", "5Y", "MAX"},
    "15 min": {"1M", "3M", "1Y", "5Y", "MAX"},
    "30 min": {"3M", "1Y", "5Y", "MAX"},
    "1 hour": {"3M", "1Y", "5Y", "MAX"},
    "1 day": {"1Y", "5Y", "MAX"},
}


def default_range_for_timeframe(display_timeframe: str | None) -> str:
    tf = str(display_timeframe or "1 min").strip()
    return _TIMEFRAME_DEFAULT_RANGE.get(tf, "1D")


def _coerce_time(value: Any):
    try:
        return pd.to_datetime(value, errors="coerce")
    except Exception:
        return pd.NaT


def _manual_range_overlaps_bars(state: dict[str, Any], chart_bars: pd.DataFrame | None) -> bool:
    if not isinstance(state, dict):
        return False

    x_range = state.get("x_range")
    if not x_range or len(x_range) != 2:
        return True

    if chart_bars is None or chart_bars.empty or "time" not in chart_bars.columns:
        return False

    start = _coerce_time(x_range[0])
    end = _coerce_time(x_range[1])
    if pd.isna(start) or pd.isna(end):
        return False

    times = pd.to_datetime(chart_bars["time"], errors="coerce").dropna()
    if times.empty:
        return False

    bar_start = times.min()
    bar_end = times.max()
    return not (end < bar_start or start > bar_end)


def normalize_watch_chart_state_for_render(
    state: dict[str, Any] | None,
    chart_bars: pd.DataFrame | None,
    *,
    display_timeframe: str | None,
    price_source: str | None = None,
    trigger_id: str | None = None,
) -> tuple[dict[str, Any], str]:
    """
    Normalize Watch chart viewport state before rendering.

    The Watch chart's stored range defaults to 1D. That is fine for 1-minute
    replay but too narrow for 1-hour and 1-day replay ranges. It can make higher
    timeframe candles look missing after double-click/autorange or after
    switching from a 1-minute view.

    This keeps manual zoom when it still overlaps the loaded bars, but resets
    stale or too-narrow state for higher timeframe replay.
    """
    tf = str(display_timeframe or "1 min").strip()
    normalized = dict(state or {})
    default_range = default_range_for_timeframe(tf)

    if not normalized:
        return {"mode": "live", "range_key": default_range, "x_range": None, "y_range": None}, default_range

    normalized.setdefault("mode", "live")
    normalized.setdefault("range_key", default_range)

    if normalized.get("mode") == "manual" and not _manual_range_overlaps_bars(normalized, chart_bars):
        normalized = {"mode": "live", "range_key": default_range, "x_range": None, "y_range": None}
        return normalized, default_range

    if tf in {"15 min", "30 min", "1 hour", "1 day"}:
        allowed = _TIMEFRAME_MIN_RANGE.get(tf, {"1D", "1W", "1M", "3M", "1Y", "5Y", "MAX"})
        range_key = str(normalized.get("range_key") or default_range).upper()
        if range_key not in allowed:
            normalized["range_key"] = default_range
            normalized["x_range"] = None
            normalized["y_range"] = None
            normalized["mode"] = "live"

    return normalized, default_range
