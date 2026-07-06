from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
import os
from typing import Any


@dataclass(frozen=True)
class ReplayRangePolicy:
    timeframe: str
    max_calendar_days: int
    max_trading_days: int
    label: str


@dataclass(frozen=True)
class ReplayRangeDecision:
    allowed: bool
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    calendar_days: int
    trading_days: int
    max_calendar_days: int
    max_trading_days: int
    message: str
    suggestions: tuple[str, ...]
    reason: str = "ok"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["suggestions"] = list(self.suggestions)
        return payload


_POLICIES: dict[str, ReplayRangePolicy] = {
    "1 min": ReplayRangePolicy("1 min", max_calendar_days=14, max_trading_days=10, label="intraday detail"),
    "2 min": ReplayRangePolicy("2 min", max_calendar_days=21, max_trading_days=15, label="intraday detail"),
    "3 min": ReplayRangePolicy("3 min", max_calendar_days=30, max_trading_days=22, label="intraday detail"),
    "5 min": ReplayRangePolicy("5 min", max_calendar_days=90, max_trading_days=60, label="medium intraday"),
    "10 min": ReplayRangePolicy("10 min", max_calendar_days=180, max_trading_days=125, label="medium intraday"),
    "15 min": ReplayRangePolicy("15 min", max_calendar_days=370, max_trading_days=260, label="large intraday"),
    "30 min": ReplayRangePolicy("30 min", max_calendar_days=740, max_trading_days=520, label="large intraday"),
    "1 hour": ReplayRangePolicy("1 hour", max_calendar_days=3650, max_trading_days=2600, label="long horizon"),
    "4 hour": ReplayRangePolicy("4 hour", max_calendar_days=3650, max_trading_days=2600, label="long horizon"),
    "1 day": ReplayRangePolicy("1 day", max_calendar_days=7300, max_trading_days=5200, label="multi-year"),
}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def normalize_timeframe(value: Any) -> str:
    raw = str(value or "1 min").strip().lower()
    raw = raw.replace("_", " ").replace("-", " ")
    raw = " ".join(raw.split())

    aliases = {
        "1m": "1 min",
        "1 min": "1 min",
        "1 minute": "1 min",
        "2m": "2 min",
        "2 min": "2 min",
        "2 minute": "2 min",
        "3m": "3 min",
        "3 min": "3 min",
        "3 minute": "3 min",
        "5m": "5 min",
        "5 min": "5 min",
        "5 minute": "5 min",
        "10m": "10 min",
        "10 min": "10 min",
        "10 minute": "10 min",
        "15m": "15 min",
        "15 min": "15 min",
        "15 minute": "15 min",
        "30m": "30 min",
        "30 min": "30 min",
        "30 minute": "30 min",
        "60m": "1 hour",
        "1h": "1 hour",
        "1 hr": "1 hour",
        "1 hour": "1 hour",
        "4h": "4 hour",
        "4 hr": "4 hour",
        "4 hour": "4 hour",
        "1d": "1 day",
        "1 day": "1 day",
        "daily": "1 day",
        "day": "1 day",
    }
    return aliases.get(raw, raw)


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    if "T" in text:
        text = text.split("T", 1)[0]
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def estimate_trading_days(start_date: date, end_date: date) -> int:
    if end_date < start_date:
        start_date, end_date = end_date, start_date

    days = 0
    cur = start_date
    while cur <= end_date:
        if cur.weekday() < 5:
            days += 1
        cur += timedelta(days=1)
    return max(0, days)


def get_policy(timeframe: Any) -> ReplayRangePolicy:
    tf = normalize_timeframe(timeframe)
    return _POLICIES.get(tf, ReplayRangePolicy(tf, max_calendar_days=30, max_trading_days=22, label="unknown timeframe"))


def suggest_timeframes(trading_days: int) -> tuple[str, ...]:
    if trading_days <= 10:
        return ("1 min is okay for this range.",)
    if trading_days <= 60:
        return ("Use 5 min for this range, or use 1 min for a smaller window.",)
    if trading_days <= 260:
        return ("Use 15 min for this range; switch to 1 min only for selected days.",)
    if trading_days <= 520:
        return ("Use 30 min or 1 hour for this range.",)
    return ("Use 1 hour or 1 day for multi-year ranges.", "Use the batch exporter/cache builder for 1 min history.")


def validate_interactive_replay_range(
    *,
    symbol: Any,
    timeframe: Any,
    start_date: Any,
    end_date: Any,
    load_mode: Any = "range",
) -> ReplayRangeDecision:
    symbol_text = str(symbol or "").upper().strip() or "UNKNOWN"
    tf = normalize_timeframe(timeframe)
    mode = str(load_mode or "").lower().strip()

    start = _parse_date(start_date)
    end = _parse_date(end_date) or start

    if mode != "range":
        return ReplayRangeDecision(
            allowed=True,
            symbol=symbol_text,
            timeframe=tf,
            start_date=str(start or ""),
            end_date=str(end or ""),
            calendar_days=0,
            trading_days=0,
            max_calendar_days=0,
            max_trading_days=0,
            message="Replay range guard skipped because this is not a range load.",
            suggestions=(),
            reason="not_range",
        )

    if not _env_bool("REPLAY_RANGE_GUARD_ENABLED", True):
        return ReplayRangeDecision(
            allowed=True,
            symbol=symbol_text,
            timeframe=tf,
            start_date=str(start or ""),
            end_date=str(end or ""),
            calendar_days=0,
            trading_days=0,
            max_calendar_days=0,
            max_trading_days=0,
            message="Replay range guard disabled by REPLAY_RANGE_GUARD_ENABLED=false.",
            suggestions=(),
            reason="disabled",
        )

    if _env_bool("REPLAY_RANGE_FORCE_ALLOW", False):
        return ReplayRangeDecision(
            allowed=True,
            symbol=symbol_text,
            timeframe=tf,
            start_date=str(start or ""),
            end_date=str(end or ""),
            calendar_days=0,
            trading_days=0,
            max_calendar_days=0,
            max_trading_days=0,
            message="Replay range guard bypassed by REPLAY_RANGE_FORCE_ALLOW=true.",
            suggestions=("Use this only when you expect a long blocking load.",),
            reason="forced",
        )

    if start is None or end is None:
        return ReplayRangeDecision(
            allowed=True,
            symbol=symbol_text,
            timeframe=tf,
            start_date=str(start or ""),
            end_date=str(end or ""),
            calendar_days=0,
            trading_days=0,
            max_calendar_days=0,
            max_trading_days=0,
            message="Replay range guard could not parse dates; allowing request.",
            suggestions=(),
            reason="date_parse",
        )

    if end < start:
        start, end = end, start

    calendar_days = (end - start).days + 1
    trading_days = estimate_trading_days(start, end)
    policy = get_policy(tf)
    suggestions = suggest_timeframes(trading_days)

    allowed = calendar_days <= policy.max_calendar_days and trading_days <= policy.max_trading_days
    if allowed:
        return ReplayRangeDecision(
            allowed=True,
            symbol=symbol_text,
            timeframe=tf,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            calendar_days=calendar_days,
            trading_days=trading_days,
            max_calendar_days=policy.max_calendar_days,
            max_trading_days=policy.max_trading_days,
            message=(
                f"Replay range allowed for {symbol_text}: {tf}, {trading_days} trading day(s), "
                f"{calendar_days} calendar day(s)."
            ),
            suggestions=suggestions,
            reason="ok",
        )

    message = (
        f"Replay range blocked for {symbol_text}: {tf} over {trading_days} trading day(s) "
        f"({calendar_days} calendar day(s)). Interactive limit for {tf} is "
        f"{policy.max_trading_days} trading day(s). Choose a larger timeframe or prepare/cache "
        f"the data with the batch exporter."
    )
    return ReplayRangeDecision(
        allowed=False,
        symbol=symbol_text,
        timeframe=tf,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        calendar_days=calendar_days,
        trading_days=trading_days,
        max_calendar_days=policy.max_calendar_days,
        max_trading_days=policy.max_trading_days,
        message=message,
        suggestions=suggestions,
        reason="too_large",
    )


def format_replay_range_decision(decision: ReplayRangeDecision) -> str:
    lines = [decision.message]
    for suggestion in decision.suggestions:
        lines.append(f"Suggestion: {suggestion}")
    return " ".join(lines)
