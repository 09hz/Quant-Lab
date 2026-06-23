from __future__ import annotations

import os
from typing import Any

from dash import Input, Output

try:
    from services.market_calendar.live_trading_day import get_live_trading_day_status
except Exception:
    get_live_trading_day_status = None


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


def _live_mode_enabled() -> tuple[bool, str]:
    # Return whether the Watch tab should be treated as live mode.

    if not _env_bool("WATCH_LIVE_GUARD_ENABLED", True):
        return False, "guard disabled"

    if _env_bool("WATCH_LIVE_MANUAL_OVERRIDE", False):
        return True, "manual override"

    if get_live_trading_day_status is None:
        return False, "calendar unavailable"

    try:
        status = get_live_trading_day_status()
    except TypeError:
        status = get_live_trading_day_status(None)
    except Exception as exc:
        return False, f"calendar error: {exc}"

    if isinstance(status, dict):
        is_open = bool(
            status.get("is_live_allowed")
            or status.get("live_allowed")
            or status.get("is_open")
            or status.get("is_trading_day")
        )
        reason = str(status.get("reason") or status.get("message") or "calendar status")
        return is_open, reason

    if hasattr(status, "is_live_allowed"):
        return bool(getattr(status, "is_live_allowed")), str(
            getattr(status, "reason", "calendar status")
        )
    if hasattr(status, "live_allowed"):
        return bool(getattr(status, "live_allowed")), str(
            getattr(status, "reason", "calendar status")
        )
    if hasattr(status, "is_open"):
        return bool(getattr(status, "is_open")), str(
            getattr(status, "reason", "calendar status")
        )
    if hasattr(status, "is_trading_day"):
        return bool(getattr(status, "is_trading_day")), str(
            getattr(status, "reason", "calendar status")
        )

    return bool(status), "calendar status"


def register_live_replay_guard_callbacks(app: Any) -> None:
    # Disable replay range controls while Watch is in live mode.

    @app.callback(
        Output("replay-date", "disabled"),
        Output("replay-end-date", "disabled"),
        Output("replay-load-range", "disabled"),
        Input("ui-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def _sync_replay_range_controls(_n_intervals: int | None):
        live_enabled, _reason = _live_mode_enabled()
        disabled = bool(live_enabled)
        return disabled, disabled, disabled
