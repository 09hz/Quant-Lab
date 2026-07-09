from __future__ import annotations

from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from statistics import mean
from typing import Any, Callable
import inspect
import os
import traceback

from .models import CandidateEvaluation, ResearchLoopConfig, StrategyCandidate, SymbolBacktestResult


DANGEROUS_NAME_TOKENS = {
    "live", "order", "broker", "execute", "trade", "place", "submit", "send", "ib", "alpaca"
}

BACKTEST_NAME_TOKENS = {
    "backtest", "back_test", "simulate", "simulation", "run", "evaluate"
}


@dataclass
class EngineCallAttempt:
    name: str
    status: str
    message: str


def _avg(values: list[float], default: float = 0.0) -> float:
    return mean(values) if values else default


def _bounded(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(float(value))
    except Exception:
        return default


def _flatten_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, val in value.items():
            out[str(key)] = val
            if isinstance(val, dict):
                for sub_key, sub_val in _flatten_dict(val).items():
                    out[f"{key}.{sub_key}"] = sub_val
                    out.setdefault(str(sub_key), sub_val)
        return out

    if hasattr(value, "to_dict"):
        try:
            return _flatten_dict(value.to_dict())
        except Exception:
            pass

    if hasattr(value, "__dict__"):
        try:
            return _flatten_dict(vars(value))
        except Exception:
            pass

    return {}


def _first_metric(data: dict[str, Any], names: list[str], default: Any = None) -> Any:
    lower = {str(k).lower(): v for k, v in data.items()}
    for name in names:
        if name in data:
            return data[name]
        if name.lower() in lower:
            return lower[name.lower()]
    return default


def _looks_dangerous_name(name: str) -> bool:
    lower = str(name or "").lower()
    return any(token in lower for token in DANGEROUS_NAME_TOKENS)


def _looks_like_backtest_name(name: str) -> bool:
    lower = str(name or "").lower()
    return any(token in lower for token in BACKTEST_NAME_TOKENS)


def _repo_backtest_engine_path(repo_root: str | Path) -> Path:
    repo = Path(repo_root).resolve()
    return repo / "Live" / "core" / "BackTestEngine.py"


def _load_backtest_engine_module(repo_root: str | Path):
    """Load the actual project BackTestEngine.

    Prefer normal project import so BackTestEngine.py can resolve its own
    project imports. Fall back to file loading only if needed.
    """
    import importlib
    import sys

    repo = Path(repo_root).resolve()
    live_root = repo / "Live"
    path = _repo_backtest_engine_path(repo)

    if not path.exists():
        return None, f"BackTestEngine.py not found at {path}"

    added_paths: list[str] = []
    for candidate in [str(live_root), str(repo)]:
        if candidate not in sys.path:
            sys.path.insert(0, candidate)
            added_paths.append(candidate)

    try:
        try:
            module = importlib.import_module("core.BackTestEngine")
            return module, "loaded core.BackTestEngine through project import"
        except Exception as import_exc:
            import_error_message = f"{type(import_exc).__name__}: {import_exc}"

        spec = spec_from_file_location(f"algotrader_safe_backtest_engine_{abs(hash(str(path)))}", str(path))
        if spec is None or spec.loader is None:
            return None, f"Could not load import spec for {path}; project import failed: {import_error_message}"

        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, f"loaded from file; project import failed first: {import_error_message}"

    except Exception as exc:
        return None, f"BackTestEngine import failed: {type(exc).__name__}: {exc}"

def _build_safe_kwargs(fn: Callable[..., Any], *, config: ResearchLoopConfig, candidate: StrategyCandidate, symbol: str) -> tuple[dict[str, Any] | None, str]:
    try:
        sig = inspect.signature(fn)
    except Exception as exc:
        return None, f"signature unavailable: {type(exc).__name__}: {exc}"

    kwargs: dict[str, Any] = {}

    for name, param in sig.parameters.items():
        lower = name.lower()
        if lower in {"self", "cls"}:
            continue
        if param.kind in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}:
            continue

        value_known = True
        if lower in {"symbol", "ticker", "asset"}:
            value = symbol
        elif lower in {"symbols", "tickers", "assets"}:
            value = [symbol]
        elif lower in {"strategy_name", "strategy", "strategy_id", "name"}:
            value = candidate.strategy_name
        elif lower in {"candidate", "strategy_candidate"}:
            value = candidate.to_dict()
        elif lower in {"parameters", "params", "strategy_params"}:
            value = candidate.parameters
        elif lower in {"timeframe", "interval", "bar_size", "bar"}:
            value = config.timeframe
        elif lower in {"repo_root", "root", "project_root"}:
            value = config.repo_root
        elif lower in {"simulation_only", "research_only", "backtest_only"}:
            value = True
        elif lower in {"live", "live_trading", "place_orders", "submit_orders", "send_orders"}:
            value = False
        elif lower in {"start_date", "end_date", "data", "prices", "price_data"} and param.default is not inspect._empty:
            continue
        elif param.default is not inspect._empty:
            continue
        else:
            value_known = False
            value = None

        if not value_known:
            return None, f"required parameter not supported: {name}"
        kwargs[name] = value

    return kwargs, "ok"


def _parse_backtest_result(value: Any, *, symbol: str) -> tuple[SymbolBacktestResult | None, str]:
    data = _flatten_dict(value)
    if not data:
        return None, f"result for {symbol} was not dict-like"

    total_return = _first_metric(
        data,
        ["total_return", "return", "returns", "strategy_return", "cumulative_return", "totalReturn", "pnl_pct", "profit_pct"],
    )
    sharpe = _first_metric(data, ["sharpe", "sharpe_ratio", "sharpeRatio"])
    max_drawdown = _first_metric(data, ["max_drawdown", "maxDrawdown", "drawdown", "max_dd"])
    win_rate = _first_metric(data, ["win_rate", "winRate", "percent_profitable", "accuracy"])
    trade_count = _first_metric(data, ["trade_count", "trades", "num_trades", "n_trades", "total_trades"])
    profit_factor = _first_metric(data, ["profit_factor", "profitFactor"], 1.0)

    # Require at least the core performance metrics to avoid inventing a "real" result.
    if total_return is None and sharpe is None and max_drawdown is None:
        return None, f"result for {symbol} did not contain recognizable return/sharpe/drawdown metrics"

    warnings: list[str] = ["source:real_backtest_engine_adapter"]

    if total_return is None:
        total_return = 0.0
        warnings.append("missing_total_return_defaulted")
    if sharpe is None:
        sharpe = 0.0
        warnings.append("missing_sharpe_defaulted")
    if max_drawdown is None:
        max_drawdown = -0.99
        warnings.append("missing_drawdown_defaulted")
    if win_rate is None:
        win_rate = 0.0
        warnings.append("missing_win_rate_defaulted")
    if trade_count is None:
        trade_count = 0
        warnings.append("missing_trade_count_defaulted")

    return SymbolBacktestResult(
        symbol=symbol,
        total_return=round(_safe_float(total_return), 6),
        sharpe=round(_safe_float(sharpe), 6),
        max_drawdown=round(_safe_float(max_drawdown), 6),
        win_rate=round(_safe_float(win_rate), 6),
        trade_count=_safe_int(trade_count),
        profit_factor=round(_safe_float(profit_factor, 1.0), 6),
        data_quality="PASS",
        warnings=warnings,
    ), "parsed"


def _candidate_functions_from_module(module: Any) -> list[tuple[str, Callable[..., Any]]]:
    out: list[tuple[str, Callable[..., Any]]] = []

    for name, obj in vars(module).items():
        if name.startswith("_"):
            continue
        if _looks_dangerous_name(name) or not _looks_like_backtest_name(name):
            continue
        if inspect.isfunction(obj):
            out.append((f"module.{name}", obj))

    for class_name, cls in vars(module).items():
        if class_name.startswith("_") or _looks_dangerous_name(class_name):
            continue
        if not inspect.isclass(cls):
            continue
        if "back" not in class_name.lower() and "test" not in class_name.lower() and "engine" not in class_name.lower():
            continue

        instance = None
        init_messages: list[str] = []
        for args, kwargs in [
            ((), {}),
            ((), {"repo_root": None}),
        ]:
            try:
                instance = cls(*args, **kwargs)
                break
            except Exception as exc:
                init_messages.append(f"{class_name} init skipped: {type(exc).__name__}: {exc}")
                instance = None

        if instance is None:
            continue

        for method_name in dir(instance):
            if method_name.startswith("_"):
                continue
            if _looks_dangerous_name(method_name) or not _looks_like_backtest_name(method_name):
                continue
            try:
                method = getattr(instance, method_name)
            except Exception:
                continue
            if callable(method):
                out.append((f"{class_name}.{method_name}", method))

    return out


def build_evaluation_from_symbol_results(
    *,
    config: ResearchLoopConfig,
    candidate: StrategyCandidate,
    symbol_results: list[SymbolBacktestResult],
    evaluation_source: str,
    attempts: list[EngineCallAttempt] | None = None,
) -> CandidateEvaluation:
    returns = [item.total_return for item in symbol_results]
    sharpes = [item.sharpe for item in symbol_results]
    drawdowns = [item.max_drawdown for item in symbol_results]
    trades = [float(item.trade_count) for item in symbol_results]
    win_rates = [item.win_rate for item in symbol_results]
    profit_factors = [item.profit_factor for item in symbol_results]

    avg_return = round(_avg(returns), 4)
    avg_sharpe = round(_avg(sharpes), 4)
    worst_drawdown = round(min(drawdowns) if drawdowns else 0.0, 4)
    total_trades = int(sum(trades))
    avg_win_rate = round(_avg(win_rates), 4)
    avg_profit_factor = round(_avg(profit_factors), 4)

    pass_symbols = [
        item.symbol for item in symbol_results
        if item.trade_count >= config.min_trades
        and item.max_drawdown >= config.max_drawdown_limit
        and item.sharpe >= config.min_sharpe
        and item.total_return > 0
    ]
    universe_pass_rate = round(len(pass_symbols) / max(1, len(symbol_results)), 4)

    walk_forward_sharpe = round(avg_sharpe * 0.82, 4)
    walk_forward_pass_rate = round(_bounded(universe_pass_rate * 0.86, 0.0, 1.0), 4)
    stability_score = round(_bounded(0.45 + max(0.0, avg_sharpe) * 0.12 + universe_pass_rate * 0.28, 0.0, 1.0), 4)

    warnings: list[str] = [f"evaluation_source:{evaluation_source}"]
    for item in symbol_results:
        warnings.extend([f"{item.symbol}:{warning}" for warning in item.warnings])

    rejection_reasons: list[str] = []
    if total_trades < config.min_trades:
        rejection_reasons.append("aggregate_too_few_trades")
    if worst_drawdown < config.max_drawdown_limit:
        rejection_reasons.append("aggregate_drawdown_limit_breach")
    if avg_sharpe < config.min_sharpe:
        rejection_reasons.append("aggregate_low_sharpe")
    if avg_return <= 0:
        rejection_reasons.append("aggregate_non_positive_return")
    if universe_pass_rate < 0.34:
        rejection_reasons.append("weak_universe_robustness")
    if walk_forward_sharpe < config.min_sharpe * 0.75:
        rejection_reasons.append("weak_walk_forward_proxy")

    backtest_quality = _bounded((avg_sharpe + 0.5) / 2.5, 0.0, 1.0) * 0.45 + _bounded((avg_return + 0.05) / 0.35, 0.0, 1.0) * 0.35 + _bounded(total_trades / max(1.0, config.min_trades * len(symbol_results) * 2.0), 0.0, 1.0) * 0.20
    walk_quality = _bounded((walk_forward_sharpe + 0.3) / 2.0, 0.0, 1.0) * 0.60 + walk_forward_pass_rate * 0.40
    universe_quality = universe_pass_rate
    risk_quality = _bounded((worst_drawdown - (-0.45)) / (0.0 - (-0.45)), 0.0, 1.0)
    data_quality = 0.94 if evaluation_source == "real_backtest_engine_adapter" else 0.72
    theme_confidence = 0.86 if any(token in config.theme.lower() for token in ["ai", "semiconductor", "infrastructure", "chip"]) else 0.65

    score = round(100.0 * (
        backtest_quality * 0.25
        + walk_quality * 0.25
        + universe_quality * 0.20
        + risk_quality * 0.15
        + data_quality * 0.10
        + theme_confidence * 0.05
    ), 2)

    status = "PASS" if not rejection_reasons else "REJECT"

    aggregate_metrics = {
        "avg_total_return": avg_return,
        "avg_sharpe": avg_sharpe,
        "worst_drawdown": worst_drawdown,
        "avg_win_rate": avg_win_rate,
        "avg_profit_factor": avg_profit_factor,
        "total_trades": total_trades,
        "evaluation_source": evaluation_source,
        "engine_attempts": [attempt.__dict__ for attempt in attempts or []][-8:],
    }
    walk_forward_metrics = {
        "window_count": 3,
        "avg_sharpe": walk_forward_sharpe,
        "pass_rate": walk_forward_pass_rate,
        "stability_score": stability_score,
        "evaluation_source": "proxy_walk_forward_from_backtest_metrics",
    }
    universe_metrics = {
        "symbols_tested": len(symbol_results),
        "pass_symbols": pass_symbols,
        "pass_rate": universe_pass_rate,
        "evaluation_source": evaluation_source,
    }

    return CandidateEvaluation(
        candidate=candidate,
        symbol_results=symbol_results,
        aggregate_metrics=aggregate_metrics,
        walk_forward_metrics=walk_forward_metrics,
        universe_metrics=universe_metrics,
        score=score,
        status=status,
        rejection_reasons=rejection_reasons,
        warnings=warnings,
    )


class SafeBackTestEngineAdapter:
    """Safe adapter for real BackTestEngine historical simulation.

    It avoids known live/broker/order names and only calls compatible functions.
    """

    def __init__(self, repo_root: str | Path):
        self.repo_root = str(Path(repo_root).resolve())
        self.attempts: list[EngineCallAttempt] = []

    def _record(self, name: str, status: str, message: str) -> None:
        self.attempts.append(EngineCallAttempt(name=name, status=status, message=message))

    def evaluate_candidate(self, config: ResearchLoopConfig, candidate: StrategyCandidate) -> tuple[CandidateEvaluation | None, list[EngineCallAttempt]]:
        old_env = {
            "ALGOTRADER_SIMULATION_ONLY": os.environ.get("ALGOTRADER_SIMULATION_ONLY"),
            "ALGOTRADER_DISABLE_BROKER": os.environ.get("ALGOTRADER_DISABLE_BROKER"),
            "ALGOTRADER_ENABLE_LIVE_TRADING": os.environ.get("ALGOTRADER_ENABLE_LIVE_TRADING"),
        }
        os.environ["ALGOTRADER_SIMULATION_ONLY"] = "1"
        os.environ["ALGOTRADER_DISABLE_BROKER"] = "1"
        os.environ["ALGOTRADER_ENABLE_LIVE_TRADING"] = "0"

        try:
            module, message = _load_backtest_engine_module(self.repo_root)
            if module is None:
                self._record("BackTestEngine", "skip", message)
                return None, self.attempts

            functions = _candidate_functions_from_module(module)
            if not functions:
                self._record("BackTestEngine", "skip", "no safe compatible backtest-like functions found")
                return None, self.attempts

            symbol_results: list[SymbolBacktestResult] = []
            symbols = candidate.symbols or config.normalized_symbols()

            for symbol in symbols:
                parsed = None
                last_message = ""
                for name, fn in functions:
                    kwargs, reason = _build_safe_kwargs(fn, config=config, candidate=candidate, symbol=symbol)
                    if kwargs is None:
                        self._record(name, "skip", reason)
                        continue
                    try:
                        raw = fn(**kwargs)
                        parsed, parse_message = _parse_backtest_result(raw, symbol=symbol)
                        if parsed is not None:
                            self._record(name, "pass", f"{symbol}: {parse_message}")
                            break
                        last_message = parse_message
                        self._record(name, "skip", f"{symbol}: {parse_message}")
                    except Exception as exc:
                        last_message = f"{type(exc).__name__}: {exc}"
                        self._record(name, "fail", f"{symbol}: {last_message}")
                        continue

                if parsed is None:
                    self._record("BackTestEngine", "fail", f"{symbol}: no callable produced parseable metrics; last={last_message}")
                    return None, self.attempts

                symbol_results.append(parsed)

            evaluation = build_evaluation_from_symbol_results(
                config=config,
                candidate=candidate,
                symbol_results=symbol_results,
                evaluation_source="real_backtest_engine_adapter",
                attempts=self.attempts,
            )
            return evaluation, self.attempts

        except Exception as exc:
            self._record("BackTestEngine", "fail", f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=6)}")
            return None, self.attempts
        finally:
            for key, value in old_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
