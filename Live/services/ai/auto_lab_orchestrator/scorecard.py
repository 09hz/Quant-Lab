from __future__ import annotations

from .models import ExperimentGoal, NormalizedBacktestResult, StrategyScorecard


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def _grade(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 75:
        return "B"
    if score >= 65:
        return "C"
    if score >= 50:
        return "D"
    return "F"


def _objective_progress_pct(return_pct: float, target_return_pct: float) -> float:
    if target_return_pct <= 0:
        return 100.0 if return_pct > 0 else 0.0
    return round(_clamp((return_pct / target_return_pct) * 100.0, 0.0, 100.0), 4)


def _recommendation(
    *,
    engine_pass: bool,
    research_pass: bool,
    objective_hit: bool,
    return_pct: float,
    max_dd: float,
    trades: int,
    goal: ExperimentGoal,
) -> str:
    if not engine_pass:
        return "Fix engine/script/data errors before retesting."
    if objective_hit and research_pass:
        return "Promote to walk-forward validation and stress testing; still simulation-only."
    if research_pass and not objective_hit:
        if max_dd <= goal.max_drawdown_pct * 0.5:
            return "Mutate for higher return while preserving low drawdown; test larger trend/position/risk variants in simulation."
        return "Mutate cautiously; improve return without increasing drawdown."
    if trades < goal.min_trades:
        return "Retest with broader date range or less restrictive entry rules; too few trades for confidence."
    if max_dd > goal.max_drawdown_pct:
        return "Reduce risk, tighten exits, or lower exposure; drawdown gate failed."
    if return_pct < 0:
        return "Reject or materially redesign; negative simulated return."
    return "Keep as low-priority candidate; needs stronger out-of-sample evidence."


def score_strategy_result(result: NormalizedBacktestResult, goal: ExperimentGoal) -> StrategyScorecard:
    """
    Deterministic scorecard.

    v21.1 separates:
    - engine_pass: did the test run?
    - research_pass: worth further research under deterministic gates?
    - objective_hit: did it reach target equity/return?
    """
    fail_reasons: list[str] = []
    warnings: list[str] = []

    engine_pass = result.ok
    if not engine_pass:
        return StrategyScorecard(
            candidate_id=result.candidate_id,
            symbol=result.symbol,
            total_score=0.0,
            grade="F",
            passed=False,
            engine_pass=False,
            research_pass=False,
            objective_hit=False,
            objective_progress_pct=0.0,
            component_scores={},
            fail_reasons=result.errors or ["Backtest did not complete."],
            warnings=result.warnings,
            interpretation="Engine failed or produced unusable result.",
            retest_recommendation="Fix engine/script/data errors before retesting.",
        )

    return_pct = result.metric("total_return_pct", "return_pct", default=0.0)
    max_dd = abs(result.metric("max_drawdown_pct", "drawdown_pct", default=0.0))
    win_rate = result.metric("win_rate_pct", "win_rate", default=0.0)
    trades = int(result.metric("trade_count", "num_trades", default=len(result.trades)))
    profit_factor = result.metric("profit_factor", default=0.0)
    final_equity = result.metric("final_equity", "ending_equity", "final_cash", default=0.0)
    eligible_buys = int(result.metric("eligible_buy_signal_count", default=0.0))
    fill_rate_pct = result.metric("fill_rate_pct", default=100.0)

    target_return_pct = goal.target_return_pct()
    objective_hit = bool(goal.target_equity > 0 and final_equity >= goal.target_equity)
    objective_progress = _objective_progress_pct(return_pct, target_return_pct)

    if target_return_pct > 0:
        return_score = _clamp((return_pct / target_return_pct) * 25.0, 0, 25)
    else:
        return_score = _clamp(return_pct / 4.0, 0, 25)

    if max_dd <= 0:
        drawdown_score = 20.0
    else:
        drawdown_score = _clamp(20.0 * (1.0 - (max_dd / max(goal.max_drawdown_pct, 1.0))), 0, 20)

    risk_adjusted = 0.0
    if max_dd > 0:
        risk_adjusted = return_pct / max_dd
    elif return_pct > 0:
        risk_adjusted = return_pct
    risk_adjusted_score = _clamp(risk_adjusted * 6.0, 0, 15)

    trade_count_score = _clamp((trades / max(goal.min_trades, 1)) * 10.0, 0, 10)
    win_rate_score = _clamp(win_rate / 100.0 * 10.0, 0, 10)
    profit_factor_score = _clamp((profit_factor - 1.0) * 8.0, 0, 10) if profit_factor > 0 else 0.0

    # v21.1 still has no true walk-forward/stress layer. Keep honest placeholder.
    robustness_score = 5.0 if trades >= goal.min_trades else 0.0
    simplicity_score = 5.0

    component_scores = {
        "return_score": round(return_score, 2),
        "drawdown_score": round(drawdown_score, 2),
        "risk_adjusted_score": round(risk_adjusted_score, 2),
        "trade_count_score": round(trade_count_score, 2),
        "win_rate_score": round(win_rate_score, 2),
        "profit_factor_score": round(profit_factor_score, 2),
        "robustness_placeholder_score": round(robustness_score, 2),
        "simplicity_score": round(simplicity_score, 2),
    }
    total = round(sum(component_scores.values()), 2)

    if max_dd > goal.max_drawdown_pct:
        fail_reasons.append(
            f"Max drawdown {max_dd:.2f}% exceeds allowed {goal.max_drawdown_pct:.2f}%."
        )
    if trades < goal.min_trades:
        fail_reasons.append(f"Only {trades} trades; minimum required is {goal.min_trades}.")
    if final_equity <= 0:
        fail_reasons.append("Final equity was not positive.")
    if return_pct < 0:
        fail_reasons.append("Negative simulated return.")
    if eligible_buys > 0 and fill_rate_pct < 80.0:
        fail_reasons.append(
            f"Only {fill_rate_pct:.2f}% of eligible BUY signals were filled; minimum required is 80.00%."
        )

    if target_return_pct and not objective_hit:
        warnings.append(
            f"Target objective not hit. Final equity {final_equity:.2f} vs target {goal.target_equity:.2f}; "
            f"objective progress {objective_progress:.2f}%."
        )
    if target_return_pct and return_pct < target_return_pct:
        warnings.append(
            f"Simulated return {return_pct:.2f}% vs target {target_return_pct:.2f}%."
        )

    warnings.extend(result.warnings)

    research_pass = bool(total >= 65.0 and not fail_reasons)
    passed = research_pass  # v21.0 compatibility only; do not treat as objective hit.

    retest_recommendation = _recommendation(
        engine_pass=engine_pass,
        research_pass=research_pass,
        objective_hit=objective_hit,
        return_pct=return_pct,
        max_dd=max_dd,
        trades=trades,
        goal=goal,
    )

    interpretation = (
        f"Score {total:.2f}/100. "
        f"Engine pass={engine_pass}; research pass={research_pass}; objective hit={objective_hit}. "
        f"Return {return_pct:.2f}%, objective progress {objective_progress:.2f}%, "
        f"max drawdown {max_dd:.2f}%, trades {trades}, win rate {win_rate:.2f}%."
    )

    return StrategyScorecard(
        candidate_id=result.candidate_id,
        symbol=result.symbol,
        total_score=total,
        grade=_grade(total),
        passed=passed,
        engine_pass=engine_pass,
        research_pass=research_pass,
        objective_hit=objective_hit,
        objective_progress_pct=objective_progress,
        component_scores=component_scores,
        fail_reasons=fail_reasons,
        warnings=warnings,
        interpretation=interpretation,
        retest_recommendation=retest_recommendation,
    )
