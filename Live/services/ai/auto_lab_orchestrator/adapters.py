from __future__ import annotations

from dataclasses import is_dataclass, asdict
from typing import Any

from .models import ExperimentGoal, NormalizedBacktestResult, StrategyCandidate, safe_float, safe_int, to_plain_data
from .safety import assert_simulation_only, assert_no_live_broker_modules_loaded


def _row_close(row: dict[str, Any]) -> float:
    return safe_float(row.get("close"), 0.0)


def _row_date(row: dict[str, Any], idx: int) -> str:
    return str(row.get("date") or row.get("datetime") or row.get("timestamp") or idx)


def _max_drawdown_pct(equity_values: list[float]) -> float:
    if not equity_values:
        return 0.0
    peak = equity_values[0]
    max_dd = 0.0
    for value in equity_values:
        peak = max(peak, value)
        if peak:
            dd = (peak - value) / peak * 100.0
            max_dd = max(max_dd, dd)
    return round(abs(max_dd), 4)


def _moving_average(values: list[float], index: int, lookback: int) -> float:
    start = max(0, index - lookback + 1)
    window = values[start:index + 1]
    return sum(window) / max(len(window), 1)


def _highest(values: list[float], index: int, lookback: int) -> float:
    start = max(0, index - lookback)
    window = values[start:index]
    return max(window) if window else values[index]


class ToyBacktestAdapter:
    engine_name = "toy_simulation_adapter"

    def run_candidate(
        self,
        candidate: StrategyCandidate,
        bars: list[dict[str, Any]],
        goal: ExperimentGoal,
        symbol: str,
    ) -> NormalizedBacktestResult:
        assert_simulation_only(goal.simulation_only)
        assert_no_live_broker_modules_loaded()

        if not bars:
            return NormalizedBacktestResult(
                candidate_id=candidate.candidate_id,
                symbol=symbol,
                status="error",
                engine=self.engine_name,
                errors=["No bars supplied."],
            )

        closes = [_row_close(row) for row in bars]
        quantity = safe_int(candidate.parameters.get("quantity"), 10)
        cash = float(goal.starting_cash)
        position = 0
        entry_price = 0.0
        entry_index = -1
        trades: list[dict[str, Any]] = []
        equity_curve: list[dict[str, Any]] = []

        def buy(idx: int, reason: str) -> None:
            nonlocal cash, position, entry_price, entry_index
            price = closes[idx]
            cost = price * quantity
            if position == 0 and cash >= cost and price > 0:
                cash -= cost
                position = quantity
                entry_price = price
                entry_index = idx
                trades.append(
                    {
                        "date": _row_date(bars[idx], idx),
                        "side": "BUY",
                        "price": round(price, 4),
                        "quantity": quantity,
                        "reason": reason,
                    }
                )

        def sell(idx: int, reason: str) -> None:
            nonlocal cash, position, entry_price, entry_index
            price = closes[idx]
            if position > 0:
                pnl = (price - entry_price) * position
                cash += price * position
                trades.append(
                    {
                        "date": _row_date(bars[idx], idx),
                        "side": "SELL",
                        "price": round(price, 4),
                        "quantity": position,
                        "pnl": round(pnl, 4),
                        "hold_bars": idx - entry_index if entry_index >= 0 else 0,
                        "reason": reason,
                    }
                )
                position = 0
                entry_price = 0.0
                entry_index = -1

        family = candidate.family.lower()
        for i, row in enumerate(bars):
            price = closes[i]
            if price <= 0:
                continue

            if family == "momentum":
                lookback = max(2, safe_int(candidate.parameters.get("lookback"), 20))
                ma = _moving_average(closes, i, lookback)
                if i >= lookback and position == 0 and price > ma:
                    buy(i, f"close_above_ma_{lookback}")
                elif position > 0 and price < ma:
                    sell(i, f"close_below_ma_{lookback}")

            elif family == "mean_reversion":
                dip_pct = safe_float(candidate.parameters.get("dip_pct"), 3.0)
                profit_take_pct = safe_float(candidate.parameters.get("profit_take_pct"), 4.0)
                max_hold = max(1, safe_int(candidate.parameters.get("max_hold_bars"), 10))
                prior = closes[i - 1] if i > 0 else price
                one_day_change = ((price / prior) - 1.0) * 100.0 if prior else 0.0
                if position == 0 and one_day_change <= -abs(dip_pct):
                    buy(i, f"dip_{dip_pct:.1f}pct")
                elif position > 0:
                    gain = ((price / entry_price) - 1.0) * 100.0 if entry_price else 0.0
                    if gain >= profit_take_pct:
                        sell(i, f"profit_take_{profit_take_pct:.1f}pct")
                    elif i - entry_index >= max_hold:
                        sell(i, f"max_hold_{max_hold}")

            elif family == "breakout":
                lookback = max(2, safe_int(candidate.parameters.get("lookback"), 30))
                stop_pct = safe_float(candidate.parameters.get("stop_pct"), 6.0)
                high = _highest(closes, i, lookback)
                if i >= lookback and position == 0 and price > high:
                    buy(i, f"breakout_{lookback}")
                elif position > 0:
                    loss = ((price / entry_price) - 1.0) * 100.0 if entry_price else 0.0
                    if loss <= -abs(stop_pct):
                        sell(i, f"stop_{stop_pct:.1f}pct")
                    elif price < _moving_average(closes, i, max(2, lookback // 2)):
                        sell(i, "trend_failure")
            else:
                if i == 0 and position == 0:
                    buy(i, "default_buy_hold")

            equity = cash + position * price
            equity_curve.append(
                {
                    "date": _row_date(row, i),
                    "equity": round(equity, 4),
                    "cash": round(cash, 4),
                    "position": position,
                    "close": round(price, 4),
                }
            )

        if position > 0:
            sell(len(bars) - 1, "final_bar_exit")
            price = closes[-1]
            equity_curve.append(
                {
                    "date": _row_date(bars[-1], len(bars) - 1),
                    "equity": round(cash, 4),
                    "cash": round(cash, 4),
                    "position": 0,
                    "close": round(price, 4),
                }
            )

        sells = [trade for trade in trades if str(trade.get("side", "")).upper() == "SELL"]
        pnl_values = [safe_float(trade.get("pnl"), 0.0) for trade in sells]
        wins = [pnl for pnl in pnl_values if pnl > 0]
        losses = [pnl for pnl in pnl_values if pnl < 0]
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (10.0 if gross_profit > 0 else 0.0)
        final_equity = safe_float(equity_curve[-1].get("equity"), cash) if equity_curve else cash
        total_pnl = final_equity - goal.starting_cash
        total_return_pct = (total_pnl / goal.starting_cash * 100.0) if goal.starting_cash else 0.0
        max_dd = _max_drawdown_pct([safe_float(row.get("equity"), 0.0) for row in equity_curve])
        win_rate = (len(wins) / len(sells) * 100.0) if sells else 0.0

        metrics = {
            "initial_cash": round(goal.starting_cash, 4),
            "final_equity": round(final_equity, 4),
            "total_pnl": round(total_pnl, 4),
            "total_return_pct": round(total_return_pct, 4),
            "max_drawdown_pct": round(abs(max_dd), 4),
            "trade_count": len(sells),
            "order_count": len(trades),
            "win_rate_pct": round(win_rate, 4),
            "profit_factor": round(profit_factor, 4),
        }

        return NormalizedBacktestResult(
            candidate_id=candidate.candidate_id,
            symbol=symbol,
            status="ok",
            engine=self.engine_name,
            metrics=metrics,
            trades=trades,
            equity_curve=equity_curve,
            warnings=["Toy adapter uses synthetic self-test data; not a real market result."],
        )


class CoreStrategyBacktestAdapter:
    engine_name = "core_strategy_backtest_adapter"

    def __init__(self) -> None:
        self._strategy_cls = None
        self._backtest_cls = None

    def _load_core_classes(self) -> tuple[type, type]:
        if self._strategy_cls and self._backtest_cls:
            return self._strategy_cls, self._backtest_cls

        errors: list[str] = []
        for strategy_mod, backtest_mod in (
            ("core.StrategyEngine", "core.BackTestEngine"),
            ("Live.core.StrategyEngine", "Live.core.BackTestEngine"),
        ):
            try:
                strategy_module = __import__(strategy_mod, fromlist=["StrategyEngine"])
                backtest_module = __import__(backtest_mod, fromlist=["BackTestEngine"])
                self._strategy_cls = getattr(strategy_module, "StrategyEngine")
                self._backtest_cls = getattr(backtest_module, "BackTestEngine")
                return self._strategy_cls, self._backtest_cls
            except Exception as exc:
                errors.append(f"{strategy_mod}/{backtest_mod}: {exc}")
        raise RuntimeError("Could not import core StrategyEngine/BackTestEngine. " + " | ".join(errors))

    def run_candidate(
        self,
        candidate: StrategyCandidate,
        bars: Any,
        goal: ExperimentGoal,
        symbol: str,
    ) -> NormalizedBacktestResult:
        assert_simulation_only(goal.simulation_only)
        assert_no_live_broker_modules_loaded()

        if bars is None:
            return NormalizedBacktestResult(
                candidate_id=candidate.candidate_id,
                symbol=symbol,
                status="error",
                engine=self.engine_name,
                errors=["No bars supplied to core adapter."],
            )
        if not candidate.script:
            return NormalizedBacktestResult(
                candidate_id=candidate.candidate_id,
                symbol=symbol,
                status="error",
                engine=self.engine_name,
                errors=["Candidate script is empty."],
            )

        try:
            strategy_cls, backtest_cls = self._load_core_classes()
            strategy_engine = strategy_cls()
            backtest_engine = backtest_cls()

            strategy_result = strategy_engine.run(candidate.script, bars)
            strategy_errors = _extract_errors(strategy_result)
            signals = _extract_signals(strategy_result)

            if strategy_errors:
                return NormalizedBacktestResult(
                    candidate_id=candidate.candidate_id,
                    symbol=symbol,
                    status="error",
                    engine=self.engine_name,
                    errors=[f"StrategyEngine: {err}" for err in strategy_errors],
                    raw_summary={"strategy_result": to_plain_data(strategy_result)},
                )

            result = backtest_engine.run(
                bars=bars,
                signals=signals or [],
                initial_cash=goal.starting_cash,
                quantity=safe_int(candidate.parameters.get("quantity"), 1),
            )
            normalized = normalize_core_backtest_result(
                result=result,
                candidate_id=candidate.candidate_id,
                symbol=symbol,
                engine=self.engine_name,
            )
            normalized.raw_summary["strategy_result"] = to_plain_data(strategy_result)
            normalized.raw_summary["signal_count"] = len(signals or [])
            if not signals:
                normalized.warnings.append("StrategyEngine produced no signals.")
            return normalized
        except Exception as exc:
            return NormalizedBacktestResult(
                candidate_id=candidate.candidate_id,
                symbol=symbol,
                status="error",
                engine=self.engine_name,
                errors=[f"{exc.__class__.__name__}: {exc}"],
            )


def _object_to_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if is_dataclass(value):
        try:
            return asdict(value)
        except Exception:
            pass
    if hasattr(value, "to_dict"):
        try:
            data = value.to_dict()
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            return {k: v for k, v in vars(value).items() if not k.startswith("_")}
        except Exception:
            pass
    return {}


def _extract_errors(value: Any) -> list[str]:
    mapping = _object_to_mapping(value)
    raw = None
    for name in ("errors", "error", "messages", "validation_errors"):
        if name in mapping:
            raw = mapping.get(name)
            break
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw] if raw.strip() else []
    if isinstance(raw, (list, tuple)):
        return [str(item) for item in raw if str(item).strip()]
    return [str(raw)] if str(raw).strip() else []


def _extract_signals(strategy_result: Any) -> list[Any]:
    if strategy_result is None:
        return []
    if isinstance(strategy_result, dict):
        raw = strategy_result.get("signals") or strategy_result.get("signal_events") or []
    else:
        raw = getattr(strategy_result, "signals", None)
        if raw is None:
            raw = getattr(strategy_result, "signal_events", None)
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    try:
        return list(raw)
    except Exception:
        return []


def _pick(mapping: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in mapping:
            return mapping.get(name)
    lower = {str(k).lower(): v for k, v in mapping.items()}
    for name in names:
        if name.lower() in lower:
            return lower[name.lower()]
    return default


def _normalize_sequence(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if hasattr(value, "to_dict") and not isinstance(value, dict):
        try:
            value = value.to_dict("records")
        except Exception:
            pass
    if isinstance(value, dict):
        return [to_plain_data(value)]
    if isinstance(value, (list, tuple)):
        normalized = []
        for row in value:
            if isinstance(row, dict):
                normalized.append(to_plain_data(row))
            else:
                normalized.append(to_plain_data(row))
        return normalized
    return []


def _trade_side(trade: dict[str, Any]) -> str:
    for key in ("side", "action", "type", "signal", "direction"):
        value = trade.get(key)
        if value:
            return str(value).upper()
    return ""


def _trade_pnl(trade: dict[str, Any]) -> float | None:
    for key in ("pnl", "profit", "profit_loss", "realized_pnl", "net_pnl"):
        if key in trade:
            return safe_float(trade.get(key), 0.0)
    return None


def _derive_trade_metrics(trades: list[dict[str, Any]]) -> dict[str, float]:
    if not trades:
        return {"trade_count": 0, "win_rate_pct": 0.0, "profit_factor": 0.0}

    pnl_values = []
    closed_count = 0
    for trade in trades:
        side = _trade_side(trade)
        pnl = _trade_pnl(trade)
        if pnl is not None:
            pnl_values.append(pnl)
            closed_count += 1
        elif side in {"SELL", "EXIT", "CLOSE"}:
            closed_count += 1

    if not pnl_values:
        return {
            "trade_count": closed_count if closed_count else len(trades),
            "win_rate_pct": 0.0,
            "profit_factor": 0.0,
        }

    wins = [value for value in pnl_values if value > 0]
    losses = [value for value in pnl_values if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (10.0 if gross_profit > 0 else 0.0)
    win_rate = len(wins) / len(pnl_values) * 100.0 if pnl_values else 0.0

    return {
        "trade_count": closed_count if closed_count else len(pnl_values),
        "win_rate_pct": round(win_rate, 4),
        "profit_factor": round(profit_factor, 4),
    }


def normalize_core_backtest_result(
    result: Any,
    candidate_id: str,
    symbol: str,
    engine: str,
) -> NormalizedBacktestResult:
    mapping = _object_to_mapping(result)
    error_texts = _extract_errors(result)

    trades = _normalize_sequence(_pick(mapping, "trades", "trade_ledger", default=[]))
    equity_curve = _normalize_sequence(_pick(mapping, "equity_curve", "equity", default=[]))
    derived_trade_metrics = _derive_trade_metrics(trades)

    metrics = {
        "initial_cash": safe_float(_pick(mapping, "initial_cash", "starting_cash", default=0.0)),
        "final_equity": safe_float(_pick(mapping, "final_equity", "ending_equity", "final_cash", "cash", default=0.0)),
        "total_pnl": safe_float(_pick(mapping, "total_pnl", "pnl", "profit_loss", default=0.0)),
        "total_return_pct": safe_float(_pick(mapping, "total_return_pct", "return_pct", "total_return", default=0.0)),
        "max_drawdown_pct": abs(safe_float(_pick(mapping, "max_drawdown_pct", "drawdown_pct", "max_drawdown", default=0.0))),
        "trade_count": safe_int(_pick(mapping, "trade_count", "num_trades", default=derived_trade_metrics["trade_count"])),
        "win_rate_pct": safe_float(_pick(mapping, "win_rate_pct", "win_rate", default=derived_trade_metrics["win_rate_pct"])),
        "profit_factor": safe_float(_pick(mapping, "profit_factor", default=derived_trade_metrics["profit_factor"])),
    }

    if not metrics["profit_factor"] and derived_trade_metrics["profit_factor"]:
        metrics["profit_factor"] = derived_trade_metrics["profit_factor"]
    if not metrics["trade_count"] and derived_trade_metrics["trade_count"]:
        metrics["trade_count"] = derived_trade_metrics["trade_count"]
    if not metrics["win_rate_pct"] and derived_trade_metrics["win_rate_pct"]:
        metrics["win_rate_pct"] = derived_trade_metrics["win_rate_pct"]

    if not metrics["final_equity"] and equity_curve:
        last = equity_curve[-1]
        if isinstance(last, dict):
            metrics["final_equity"] = safe_float(
                _pick(last, "equity", "value", "portfolio_value", "cash", default=0.0)
            )

    if metrics["initial_cash"] and metrics["final_equity"] and not metrics["total_return_pct"]:
        metrics["total_return_pct"] = round(
            ((metrics["final_equity"] / metrics["initial_cash"]) - 1.0) * 100.0,
            4,
        )
    if metrics["initial_cash"] and metrics["final_equity"] and not metrics["total_pnl"]:
        metrics["total_pnl"] = round(metrics["final_equity"] - metrics["initial_cash"], 4)

    metrics["max_drawdown_pct"] = abs(metrics["max_drawdown_pct"])

    return NormalizedBacktestResult(
        candidate_id=candidate_id,
        symbol=symbol,
        status="error" if error_texts else "ok",
        engine=engine,
        metrics=metrics,
        trades=trades,
        equity_curve=equity_curve,
        errors=error_texts,
        raw_summary=to_plain_data(mapping),
    )
