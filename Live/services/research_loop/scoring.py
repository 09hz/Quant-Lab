from __future__ import annotations

from hashlib import sha256
from statistics import mean
from typing import Any

from .models import CandidateEvaluation, ResearchLoopConfig, StrategyCandidate, SymbolBacktestResult


FAMILY_BIAS = {
    "momentum_breakout": 0.16,
    "trend_pullback": 0.12,
    "volatility_compression": 0.10,
    "relative_strength_rotation": 0.08,
    "mean_reversion_guarded": -0.02,
}


def _stable_unit(*parts: Any) -> float:
    text = "|".join(str(part) for part in parts)
    value = int(sha256(text.encode("utf-8")).hexdigest()[:12], 16)
    return (value % 1_000_000) / 1_000_000.0


def _bounded(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _avg(values: list[float], default: float = 0.0) -> float:
    return mean(values) if values else default


def evaluate_symbol_proxy(config: ResearchLoopConfig, candidate: StrategyCandidate, symbol: str) -> SymbolBacktestResult:
    u1 = _stable_unit(config.seed, config.theme, candidate.candidate_id, symbol, "return")
    u2 = _stable_unit(config.seed, config.theme, candidate.candidate_id, symbol, "risk")
    u3 = _stable_unit(config.seed, config.theme, candidate.candidate_id, symbol, "trades")
    u4 = _stable_unit(config.seed, config.theme, candidate.candidate_id, symbol, "win")

    family_bias = FAMILY_BIAS.get(candidate.strategy_family, 0.0)
    theme_bias = 0.05 if any(token in config.theme.lower() for token in ["ai", "semiconductor", "infrastructure", "chip"]) else 0.0

    total_return = round(-0.08 + (u1 * 0.34) + family_bias + theme_bias, 4)
    sharpe = round(-0.45 + (u1 * 2.05) + (family_bias * 2.2) + theme_bias, 4)
    max_drawdown = round(-1.0 * (0.025 + (u2 * 0.28)), 4)
    win_rate = round(_bounded(0.34 + (u4 * 0.34) + (family_bias / 3.0), 0.20, 0.82), 4)
    trade_count = int(3 + (u3 * 55))
    profit_factor = round(_bounded(0.65 + (u1 * 1.65) + family_bias, 0.2, 4.0), 4)

    warnings: list[str] = []
    data_quality = "PASS"
    if trade_count < config.min_trades:
        warnings.append("too_few_trades")
    if max_drawdown < config.max_drawdown_limit:
        warnings.append("drawdown_limit_breach")
    if sharpe < config.min_sharpe:
        warnings.append("low_sharpe")
    if not symbol or not symbol.isalpha():
        warnings.append("symbol_hygiene_warning")
        data_quality = "WARN"

    return SymbolBacktestResult(
        symbol=symbol,
        total_return=total_return,
        sharpe=sharpe,
        max_drawdown=max_drawdown,
        win_rate=win_rate,
        trade_count=trade_count,
        profit_factor=profit_factor,
        data_quality=data_quality,
        warnings=warnings,
    )


def score_candidate(config: ResearchLoopConfig, candidate: StrategyCandidate) -> CandidateEvaluation:
    symbols = candidate.symbols or config.normalized_symbols()
    symbol_results = [evaluate_symbol_proxy(config, candidate, symbol) for symbol in symbols]

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

    stability_seed = _stable_unit(config.seed, candidate.candidate_id, "stability")
    stability_score = round(_bounded(0.40 + stability_seed * 0.50 + max(0.0, avg_sharpe) * 0.05, 0.0, 1.0), 4)
    walk_forward_sharpe = round(avg_sharpe * (0.65 + stability_score * 0.35), 4)
    walk_forward_pass_rate = round(_bounded(universe_pass_rate * (0.70 + stability_score * 0.30), 0.0, 1.0), 4)

    warnings: list[str] = []
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
    data_quality = 1.0 if not warnings else 0.72
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
    }
    walk_forward_metrics = {
        "window_count": 3,
        "avg_sharpe": walk_forward_sharpe,
        "pass_rate": walk_forward_pass_rate,
        "stability_score": stability_score,
    }
    universe_metrics = {
        "symbols_tested": len(symbol_results),
        "pass_symbols": pass_symbols,
        "pass_rate": universe_pass_rate,
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
