from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


TRUE_VALUES = {"1", "true", "yes", "y", "on"}
FALSE_VALUES = {"0", "false", "no", "n", "off"}


@dataclass(frozen=True)
class LiveTradingDayStatus:
    enabled: bool
    allowed: bool
    today: str
    weekday: str
    reason: str
    timezone: str
    manual_override: bool = False


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    lowered = value.strip().lower()
    if lowered in TRUE_VALUES:
        return True
    if lowered in FALSE_VALUES:
        return False
    return default


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    current = date(year, month, 1)
    while current.weekday() != weekday:
        current += timedelta(days=1)
    return current + timedelta(days=7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        current = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        current = date(year, month + 1, 1) - timedelta(days=1)
    while current.weekday() != weekday:
        current -= timedelta(days=1)
    return current


def _observed_fixed_holiday(year: int, month: int, day: int) -> date:
    actual = date(year, month, day)
    if actual.weekday() == 5:
        return actual - timedelta(days=1)
    if actual.weekday() == 6:
        return actual + timedelta(days=1)
    return actual


def _easter_sunday(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def approximate_us_equity_holidays(year: int) -> set[date]:
    return {
        _observed_fixed_holiday(year, 1, 1),
        _nth_weekday(year, 1, 0, 3),
        _nth_weekday(year, 2, 0, 3),
        _easter_sunday(year) - timedelta(days=2),
        _last_weekday(year, 5, 0),
        _observed_fixed_holiday(year, 6, 19),
        _observed_fixed_holiday(year, 7, 4),
        _nth_weekday(year, 9, 0, 1),
        _nth_weekday(year, 11, 3, 4),
        _observed_fixed_holiday(year, 12, 25),
    }


def is_open_live_trading_day(check_date: date | None = None) -> tuple[bool, str]:
    timezone = os.getenv("WATCH_MARKET_TIMEZONE", "America/New_York")
    day = check_date or datetime.now(ZoneInfo(timezone)).date()

    if day.weekday() >= 5:
        return False, f"{day.isoformat()} is a weekend."

    if day in approximate_us_equity_holidays(day.year):
        return False, f"{day.isoformat()} is an approximate U.S. equity market holiday."

    return True, f"{day.isoformat()} is treated as an open live trading day."


def get_watch_live_trading_day_status(check_date: date | None = None) -> LiveTradingDayStatus:
    timezone = os.getenv("WATCH_MARKET_TIMEZONE", "America/New_York")
    enabled = _env_bool("WATCH_LIVE_GUARD_ENABLED", True)
    manual_override = _env_bool("WATCH_LIVE_MANUAL_OVERRIDE", False)

    today = check_date or datetime.now(ZoneInfo(timezone)).date()

    if not enabled:
        return LiveTradingDayStatus(
            enabled=False,
            allowed=True,
            today=today.isoformat(),
            weekday=today.strftime("%A"),
            reason="Watch live guard disabled by WATCH_LIVE_GUARD_ENABLED=false.",
            timezone=timezone,
            manual_override=False,
        )

    if manual_override:
        return LiveTradingDayStatus(
            enabled=True,
            allowed=True,
            today=today.isoformat(),
            weekday=today.strftime("%A"),
            reason="Manual live override enabled by WATCH_LIVE_MANUAL_OVERRIDE=true.",
            timezone=timezone,
            manual_override=True,
        )

    allowed, reason = is_open_live_trading_day(today)
    return LiveTradingDayStatus(
        enabled=True,
        allowed=allowed,
        today=today.isoformat(),
        weekday=today.strftime("%A"),
        reason=reason,
        timezone=timezone,
        manual_override=False,
    )
