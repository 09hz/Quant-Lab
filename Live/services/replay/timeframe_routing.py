"""
Replay timeframe routing helpers.

These helpers keep Watch/Replay range loads from silently falling back to
1-minute bars when the user selected a larger timeframe such as 15 min,
30 min, or 1 hour.
"""

from __future__ import annotations


_TIMEFRAME_ALIASES = {
    "1": "1 min",
    "1m": "1 min",
    "1 min": "1 min",
    "1 minute": "1 min",
    "1min": "1 min",
    "5": "5 min",
    "5m": "5 min",
    "5 min": "5 min",
    "5 minutes": "5 min",
    "5min": "5 min",
    "15": "15 min",
    "15m": "15 min",
    "15 min": "15 min",
    "15 minutes": "15 min",
    "15min": "15 min",
    "30": "30 min",
    "30m": "30 min",
    "30 min": "30 min",
    "30 minutes": "30 min",
    "30min": "30 min",
    "60": "1 hour",
    "60m": "1 hour",
    "60 min": "1 hour",
    "1h": "1 hour",
    "1 h": "1 hour",
    "1 hour": "1 hour",
    "1 hr": "1 hour",
    "hour": "1 hour",
    "1d": "1 day",
    "1 d": "1 day",
    "1 day": "1 day",
    "daily": "1 day",
    "day": "1 day",
}


def normalize_replay_timeframe(value: object, default: str = "1 min") -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return default
    raw = raw.replace("_", " ").replace("-", " ")
    raw = " ".join(raw.split())
    return _TIMEFRAME_ALIASES.get(raw, str(value).strip() or default)


def replay_cache_key_timeframe(value: object) -> str:
    return normalize_replay_timeframe(value).replace(" ", "_")


def describe_timeframe_route(value: object) -> dict[str, str]:
    normalized = normalize_replay_timeframe(value)
    return {
        "input": str(value or ""),
        "normalized": normalized,
        "cache_key": replay_cache_key_timeframe(normalized),
    }
