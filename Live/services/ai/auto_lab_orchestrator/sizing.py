from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
import copy
import math


@dataclass
class SizingConfig:
    sizing_mode: str = "percent_cash_exposure"
    cash_exposure_pct: float = 95.0
    fixed_quantity: int = 10
    min_quantity: int = 1
    max_quantity: int = 1_000_000
    simulation_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str) and not value.strip():
            return default
        out = float(value)
        if math.isnan(out) or math.isinf(out):
            return default
        return out
    except Exception:
        return default


def first_close_price(bars: Any) -> float:
    """
    Get first usable close from pandas DataFrame or list-of-dicts.
    """
    if bars is None:
        return 0.0

    # pandas DataFrame
    if hasattr(bars, "columns") and "close" in getattr(bars, "columns", []):
        try:
            series = bars["close"].dropna()
            if len(series) > 0:
                return _safe_float(series.iloc[0], 0.0)
        except Exception:
            pass

    # list/tuple of rows
    try:
        for row in bars:
            if isinstance(row, dict):
                close = _safe_float(row.get("close"), 0.0)
            else:
                close = _safe_float(getattr(row, "close", 0.0), 0.0)
            if close > 0:
                return close
    except Exception:
        pass

    return 0.0


def compute_simulation_quantity(
    *,
    initial_cash: float,
    reference_price: float,
    candidate_parameters: dict[str, Any] | None = None,
    config: SizingConfig | None = None,
) -> int:
    """
    Compute a simulated quantity. This is for backtest research only.
    It is not live position sizing or trading advice.
    """
    config = config or SizingConfig()
    params = dict(candidate_parameters or {})
    price = max(_safe_float(reference_price, 0.0), 0.0)
    cash = max(_safe_float(initial_cash, 0.0), 0.0)

    mode = (config.sizing_mode or "percent_cash_exposure").strip().lower()
    if mode == "fixed_quantity":
        qty = int(_safe_float(params.get("quantity", config.fixed_quantity), config.fixed_quantity))
    elif mode == "max_affordable_shares":
        qty = int(cash // price) if price > 0 else config.fixed_quantity
    elif mode == "percent_cash_exposure":
        exposure_cash = cash * max(0.0, min(_safe_float(config.cash_exposure_pct, 95.0), 100.0)) / 100.0
        qty = int(exposure_cash // price) if price > 0 else config.fixed_quantity
    else:
        raise ValueError(f"Unknown sizing_mode={config.sizing_mode!r}")

    qty = max(int(config.min_quantity), qty)
    qty = min(int(config.max_quantity), qty)
    return int(qty)


def apply_simulation_sizing_to_candidate(
    candidate: Any,
    *,
    initial_cash: float,
    reference_price: float,
    config: SizingConfig,
) -> Any:
    """
    Return a deep-copied candidate with parameters['quantity'] adjusted for simulation.
    """
    cloned = copy.deepcopy(candidate)
    params = dict(getattr(cloned, "parameters", {}) or {})
    original_quantity = params.get("quantity")
    computed = compute_simulation_quantity(
        initial_cash=initial_cash,
        reference_price=reference_price,
        candidate_parameters=params,
        config=config,
    )
    params["quantity"] = computed
    params["sizing_mode"] = config.sizing_mode
    params["cash_exposure_pct"] = config.cash_exposure_pct
    params["reference_price_for_sizing"] = reference_price
    params["original_quantity_before_sizing"] = original_quantity
    params["simulation_only_sizing"] = True
    cloned.parameters = params
    return cloned


def apply_simulation_sizing(
    candidates: list[Any],
    *,
    bars: Any,
    initial_cash: float,
    config: SizingConfig,
) -> tuple[list[Any], dict[str, Any]]:
    reference_price = first_close_price(bars)
    sized = [
        apply_simulation_sizing_to_candidate(
            candidate,
            initial_cash=initial_cash,
            reference_price=reference_price,
            config=config,
        )
        for candidate in candidates
    ]
    return sized, {
        "sizing_mode": config.sizing_mode,
        "cash_exposure_pct": config.cash_exposure_pct,
        "fixed_quantity": config.fixed_quantity,
        "reference_price": reference_price,
        "example_quantity": (
            dict(getattr(sized[0], "parameters", {}) or {}).get("quantity")
            if sized else None
        ),
        "simulation_only": True,
    }
