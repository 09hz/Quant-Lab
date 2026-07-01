from __future__ import annotations

from .models import BacktestRequest, BacktestResult
from .safety import validate_backtest_request


def run_backtest_request(request: BacktestRequest) -> BacktestResult:
    errors = validate_backtest_request(request)
    if errors:
        return BacktestResult(request=request, metrics={}, notes=errors, passed_safety_checks=False)

    return BacktestResult(
        request=request,
        metrics={"cagr": 0.0, "sharpe": 0.0, "max_drawdown": 0.0, "trade_count": 0.0},
        notes=["Runner stub only. Connect to BackTestEngine before using results."],
        passed_safety_checks=True,
    )
