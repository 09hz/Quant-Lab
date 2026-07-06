from __future__ import annotations

from .models import BacktestRequest


ALLOWED_STRATEGY_FAMILIES = {
    "trend_following",
    "mean_reversion",
    "breakout",
    "macro_filter_overlay",
    "volatility_filter_overlay",
}

MAX_SYMBOLS_PER_RUN = 25
MAX_PARAMETER_GRID = 200


def validate_backtest_request(request: BacktestRequest) -> list[str]:
    errors: list[str] = []

    if not request.symbol or len(request.symbol) > 24:
        errors.append("Invalid symbol.")

    if request.strategy_family not in ALLOWED_STRATEGY_FAMILIES:
        errors.append(f"Strategy family not allowed: {request.strategy_family}")

    if request.timeframe not in {"1 day", "1 hour", "30 mins", "15 mins", "5 mins"}:
        errors.append(f"Timeframe not allowed: {request.timeframe}")

    banned_keys = {"order", "trade", "broker", "account", "quantity", "notional", "leverage", "margin"}
    bad_keys = banned_keys.intersection({str(k).lower() for k in request.parameters})
    if bad_keys:
        errors.append(f"Backtest request contains broker/order-like parameters: {sorted(bad_keys)}")

    return errors
