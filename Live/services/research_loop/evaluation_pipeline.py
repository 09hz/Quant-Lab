from __future__ import annotations

from .backtest_engine_adapter import SafeBackTestEngineAdapter
from .models import CandidateEvaluation, ResearchLoopConfig, StrategyCandidate, SymbolBacktestResult
from .scoring import score_candidate


def _make_real_required_failure(config: ResearchLoopConfig, candidate: StrategyCandidate, message: str) -> CandidateEvaluation:
    symbols = candidate.symbols or config.normalized_symbols()
    symbol_results = [
        SymbolBacktestResult(
            symbol=symbol,
            total_return=0.0,
            sharpe=0.0,
            max_drawdown=-0.99,
            win_rate=0.0,
            trade_count=0,
            profit_factor=0.0,
            data_quality="WARN",
            warnings=["real_backtest_required_but_unavailable"],
        )
        for symbol in symbols
    ]
    return CandidateEvaluation(
        candidate=candidate,
        symbol_results=symbol_results,
        aggregate_metrics={
            "avg_total_return": 0.0,
            "avg_sharpe": 0.0,
            "worst_drawdown": -0.99,
            "avg_win_rate": 0.0,
            "avg_profit_factor": 0.0,
            "total_trades": 0,
            "evaluation_source": "real_required_failed",
        },
        walk_forward_metrics={
            "window_count": 0,
            "avg_sharpe": 0.0,
            "pass_rate": 0.0,
            "stability_score": 0.0,
            "evaluation_source": "not_run",
        },
        universe_metrics={
            "symbols_tested": len(symbol_results),
            "pass_symbols": [],
            "pass_rate": 0.0,
            "evaluation_source": "not_run",
        },
        score=0.0,
        status="REJECT",
        rejection_reasons=["real_backtest_engine_unavailable"],
        warnings=[message],
    )


def evaluate_candidate_for_loop(config: ResearchLoopConfig, candidate: StrategyCandidate) -> CandidateEvaluation:
    mode = str(getattr(config, "evaluation_mode", "hybrid_safe") or "hybrid_safe").strip().lower()

    if mode in {"proxy", "proxy_only", "simulation_proxy"}:
        evaluation = score_candidate(config, candidate)
        evaluation.aggregate_metrics["evaluation_source"] = "proxy"
        evaluation.walk_forward_metrics["evaluation_source"] = "proxy"
        evaluation.universe_metrics["evaluation_source"] = "proxy"
        evaluation.warnings.append("evaluation_source:proxy")
        return evaluation

    if mode in {"hybrid", "hybrid_safe", "real", "real_first", "real_required"}:
        adapter = SafeBackTestEngineAdapter(getattr(config, "repo_root", None) or ".")
        real_evaluation, attempts = adapter.evaluate_candidate(config, candidate)
        if real_evaluation is not None:
            return real_evaluation

        attempt_summary = "; ".join(f"{a.name}:{a.status}:{a.message}" for a in attempts[-5:]) or "no attempts"
        if mode == "real_required":
            return _make_real_required_failure(config, candidate, f"real_backtest_engine_unavailable: {attempt_summary}")

        fallback = score_candidate(config, candidate)
        fallback.aggregate_metrics["evaluation_source"] = "proxy_fallback_after_real_adapter"
        fallback.aggregate_metrics["real_adapter_attempts"] = [attempt.__dict__ for attempt in attempts][-8:]
        fallback.walk_forward_metrics["evaluation_source"] = "proxy_fallback"
        fallback.universe_metrics["evaluation_source"] = "proxy_fallback"
        fallback.warnings.append("evaluation_source:proxy_fallback_after_real_adapter")
        fallback.warnings.append(f"real_adapter_unavailable:{attempt_summary}")
        return fallback

    fallback = score_candidate(config, candidate)
    fallback.aggregate_metrics["evaluation_source"] = f"proxy_unknown_mode_{mode}"
    fallback.warnings.append(f"unknown_evaluation_mode:{mode}")
    return fallback
