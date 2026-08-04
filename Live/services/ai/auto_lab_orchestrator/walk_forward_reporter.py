from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import math

from services.ai.auto_lab_orchestrator.models import local_now_iso, utc_now_iso


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


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    try:
        return f"{float(value):.2f}"
    except Exception:
        return str(value)


def _rolling_rank(value: Any) -> int:
    return {"robust": 3, "partial": 2, "failed": 1, "unavailable": 0}.get(str(value or "").lower(), 0)


def _promotion_rank(value: Any) -> int:
    return {"promote": 3, "review": 2, "reject": 1}.get(str(value or "").lower(), 0)


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if not normalized:
            return None
        if normalized in {"true", "1", "yes", "pass", "passed"}:
            return True
        if normalized in {"false", "0", "no", "fail", "failed"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return None


def _has_value(value: Any) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def _optional_float(value: Any) -> float | None:
    if not _has_value(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def decide_promotion(candidate: dict[str, Any], settings: dict[str, Any] | None = None) -> tuple[str, list[str]]:
    """Return a deterministic governance decision without mutating the candidate."""
    settings = settings or {}
    reject_reasons: list[str] = []
    review_reasons: list[str] = []

    test_engine_pass = _optional_bool(candidate.get("test_engine_pass"))
    test_research_pass = _optional_bool(candidate.get("test_research_pass"))
    rolling_status = str(candidate.get("rolling_status") or "unavailable").strip().lower()
    holdout_available = _optional_bool(candidate.get("holdout_available")) is True
    max_drawdown_pct = _optional_float(settings.get("max_drawdown_pct"))
    holdout_drawdown_pct = _optional_float(candidate.get("holdout_max_drawdown_pct"))

    if test_engine_pass is False:
        reject_reasons.append("Test 2 engine execution failed.")
    elif test_engine_pass is not True:
        review_reasons.append("Test 2 engine result is missing.")
    if test_research_pass is not True:
        review_reasons.append("Test 2 research gate did not pass.")

    if rolling_status == "failed":
        reject_reasons.append("Test 3 rolling validation failed.")
    elif rolling_status != "robust":
        review_reasons.append(f"Test 3 rolling validation is not robust (status: {rolling_status}).")

    if not holdout_available:
        review_reasons.append("Test 4 holdout is unavailable.")
    else:
        holdout_engine_pass = _optional_bool(candidate.get("holdout_engine_pass"))
        holdout_research_pass = _optional_bool(candidate.get("holdout_research_pass"))
        if holdout_engine_pass is False:
            reject_reasons.append("Test 4 holdout engine execution failed.")
        elif holdout_engine_pass is not True:
            review_reasons.append("Test 4 holdout engine result is missing.")

        if holdout_research_pass is False:
            reject_reasons.append("Test 4 holdout research gate failed.")
        elif holdout_research_pass is not True:
            review_reasons.append("Test 4 holdout research result is missing.")

        if max_drawdown_pct is None:
            review_reasons.append("The configured maximum drawdown limit is missing or invalid.")
        elif holdout_drawdown_pct is None:
            review_reasons.append("Test 4 holdout drawdown is missing or invalid.")
        else:
            max_drawdown_pct = abs(max_drawdown_pct)
            holdout_drawdown_pct = abs(holdout_drawdown_pct)
            if holdout_drawdown_pct > max_drawdown_pct:
                reject_reasons.append(
                    f"Test 4 holdout drawdown {holdout_drawdown_pct:.2f}% exceeds the "
                    f"{max_drawdown_pct:.2f}% limit."
                )

    if reject_reasons:
        return "reject", reject_reasons + review_reasons

    can_promote = (
        test_engine_pass is True
        and test_research_pass is True
        and rolling_status == "robust"
        and holdout_available
        and _optional_bool(candidate.get("holdout_engine_pass")) is True
        and _optional_bool(candidate.get("holdout_research_pass")) is True
        and max_drawdown_pct is not None
        and holdout_drawdown_pct is not None
        and abs(holdout_drawdown_pct) <= abs(max_drawdown_pct)
    )
    if can_promote:
        return "promote", [
            "Test 2 research gate passed.",
            "Test 3 rolling validation is robust.",
            "Test 4 holdout engine and research gates passed.",
            "Test 4 holdout drawdown respected the configured limit.",
        ]
    return "review", review_reasons or ["Promotion evidence is incomplete and requires review."]


def _candidate_rank_key(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        _promotion_rank(item.get("promotion_decision")),
        _rolling_rank(item.get("rolling_status")),
        _safe_float(item.get("rolling_pass_rate_pct"), 0.0),
        _optional_bool(item.get("test_research_pass")) is True,
        _optional_bool(item.get("test_objective_hit")) is True,
        _safe_float(item.get("test_score"), 0.0),
        _safe_float(item.get("test_objective_progress_pct"), 0.0),
    )


def overfit_label(train_progress: float, test_progress: float, train_hit: bool, test_hit: bool) -> str:
    train_progress = _safe_float(train_progress)
    test_progress = _safe_float(test_progress)

    if train_hit and test_hit:
        return "walk_forward_pass"
    if train_progress >= 75 and test_progress < 25:
        return "high_overfit_warning"
    if train_progress >= 50 and test_progress < 25:
        return "medium_overfit_warning"
    if test_progress >= train_progress * 0.5 and test_progress > 0:
        return "partial_survival"
    return "weak_out_of_sample"


def build_walk_forward_payload(
    *,
    walk_forward_run_id: str,
    symbols: list[str],
    settings: dict[str, Any],
    symbol_results: list[dict[str, Any]],
) -> dict[str, Any]:
    annotated_symbol_results = []
    all_rows = []
    for symbol_result in symbol_results:
        symbol_copy = dict(symbol_result)
        candidate_copies = []
        for row in symbol_result.get("validated_candidates") or []:
            candidate_copy = dict(row)
            decision, reasons = decide_promotion(candidate_copy, settings)
            candidate_copy["promotion_decision"] = decision
            candidate_copy["promotion_reasons"] = reasons
            candidate_copies.append(candidate_copy)

        candidate_copies = sorted(candidate_copies, key=_candidate_rank_key, reverse=True)
        symbol_copy["validated_candidates"] = candidate_copies
        if candidate_copies:
            best = candidate_copies[0]
            symbol_copy.update(
                {
                    "best_candidate_id": best.get("candidate_id", ""),
                    "best_train_score": best.get("train_score", 0.0),
                    "best_test_score": best.get("test_score", 0.0),
                    "best_test_objective_hit": best.get("test_objective_hit", False),
                    "best_test_objective_progress_pct": best.get("test_objective_progress_pct", 0.0),
                    "best_overfit_label": best.get("overfit_label", ""),
                    "best_rolling_status": best.get("rolling_status", "unavailable"),
                    "best_rolling_pass_rate_pct": best.get("rolling_pass_rate_pct", 0.0),
                    "best_rolling_worst_score": best.get("rolling_worst_score", 0.0),
                    "best_promotion_decision": best.get("promotion_decision", "review"),
                    "best_promotion_reasons": list(best.get("promotion_reasons") or []),
                    "best_holdout_available": best.get("holdout_available", False),
                    "best_holdout_score": best.get("holdout_score", 0.0),
                    "best_holdout_engine_pass": best.get("holdout_engine_pass"),
                    "best_holdout_research_pass": best.get("holdout_research_pass"),
                    "best_holdout_objective_hit": best.get("holdout_objective_hit"),
                    "best_holdout_regime": best.get("holdout_regime", "unavailable"),
                }
            )
        else:
            symbol_copy.setdefault("best_promotion_decision", "review")
            symbol_copy.setdefault("best_promotion_reasons", ["No validated candidates are available."])

        annotated_symbol_results.append(symbol_copy)
        all_rows.extend(candidate_copies)

    ranked_validated = sorted(all_rows, key=_candidate_rank_key, reverse=True)

    ranked_symbols = sorted(
        annotated_symbol_results,
        key=lambda item: (
            _promotion_rank(item.get("best_promotion_decision")),
            _rolling_rank(item.get("best_rolling_status")),
            _safe_float(item.get("best_rolling_pass_rate_pct"), 0.0),
            _safe_float(item.get("best_test_score"), 0.0),
            _safe_float(item.get("best_test_objective_progress_pct"), 0.0),
        ),
        reverse=True,
    )

    return {
        "schema_version": "walk_forward_universe_v23_0",
        "walk_forward_run_id": walk_forward_run_id,
        "generated_at": local_now_iso(),
        "generated_at_utc": utc_now_iso(),
        "symbols": symbols,
        "settings": settings,
        "symbol_results": annotated_symbol_results,
        "ranked_symbols": ranked_symbols,
        "ranked_validated_candidates": ranked_validated,
        "safety": {
            "simulation_only": True,
            "broker_calls": False,
            "live_orders": False,
            "note": "Walk-forward runner is research/simulation-only.",
        },
    }


def _paper_review_risk_policy(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    values = dict(overrides or {})

    def bounded_float(name: str, default: float, low: float, high: float) -> float:
        value = _safe_float(values.get(name), default)
        return round(max(low, min(high, value)), 4)

    try:
        max_orders = int(float(values.get("max_orders_per_day", 10)))
    except Exception:
        max_orders = 10

    return {
        "max_position_pct": bounded_float("max_position_pct", 20.0, 1.0, 100.0),
        "max_daily_loss_pct": bounded_float("max_daily_loss_pct", 2.0, 0.1, 100.0),
        "max_drawdown_pct": bounded_float("max_drawdown_pct", 10.0, 0.1, 100.0),
        "max_orders_per_day": max(1, min(1000, max_orders)),
        "allow_short": bool(values.get("allow_short", False)),
    }


def build_paper_review_queue(
    payload: dict[str, Any],
    risk_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a manual-approval queue from candidates that cleared every promotion gate."""
    policy = _paper_review_risk_policy(risk_policy)
    run_id = str(payload.get("walk_forward_run_id") or "")
    candidates = []

    for row in payload.get("ranked_validated_candidates") or []:
        decision, reasons = _promotion_view(row, payload.get("settings") or {})
        if decision != "promote":
            continue
        candidate_id = str(row.get("candidate_id") or "").strip()
        symbol = str(row.get("symbol") or "").upper().strip()
        if not candidate_id or not symbol:
            continue
        candidates.append(
            {
                "review_id": f"{run_id}:{symbol}:{candidate_id}",
                "walk_forward_run_id": run_id,
                "candidate_id": candidate_id,
                "symbol": symbol,
                "script": str(row.get("script") or ""),
                "promotion_decision": decision,
                "promotion_reasons": reasons,
                "test_score": _safe_float(row.get("test_score"), 0.0),
                "rolling_status": str(row.get("rolling_status") or "unavailable"),
                "rolling_pass_rate_pct": _safe_float(row.get("rolling_pass_rate_pct"), 0.0),
                "holdout_score": _safe_float(row.get("holdout_score"), 0.0),
                "holdout_regime": str(row.get("holdout_regime") or "unavailable"),
                "review_status": "pending_user_approval",
                "auto_execute": False,
                "risk_policy": dict(policy),
            }
        )

    return {
        "schema_version": "paper_review_queue_v24_0",
        "walk_forward_run_id": run_id,
        "generated_at": local_now_iso(),
        "generated_at_utc": utc_now_iso(),
        "candidate_count": len(candidates),
        "auto_execute": False,
        "candidates": candidates,
        "safety": {
            "simulation_only": True,
            "manual_user_approval_required": True,
            "automatic_strategy_execution": False,
            "live_orders": False,
        },
    }


def build_paper_review_overlay(candidate: dict[str, Any]) -> dict[str, Any]:
    """Create a visual-only Strategy Overlay store packet for a promoted candidate."""
    if not isinstance(candidate, dict):
        raise ValueError("Paper review overlay requires a candidate dictionary.")
    if str(candidate.get("promotion_decision") or "").strip().lower() != "promote":
        raise ValueError("Only promoted candidates can create a paper review overlay.")

    script = str(candidate.get("script") or "").strip()
    symbol = str(candidate.get("symbol") or "").upper().strip()
    candidate_id = str(candidate.get("candidate_id") or "").strip()
    if not script or not symbol or not candidate_id:
        raise ValueError("Paper review overlay requires a script, symbol, and candidate ID.")

    return {
        "script": script,
        "enabled": True,
        "source": "auto_lab_paper_review",
        "review_id": str(candidate.get("review_id") or candidate_id),
        "candidate_id": candidate_id,
        "symbol": symbol,
        "visual_only": True,
        "auto_execute": False,
    }


def render_paper_review_queue(queue: dict[str, Any]) -> str:
    lines = [
        "# Auto Lab Paper Review Queue",
        "",
        "Simulation-only. Candidates require explicit user activation and never execute automatically.",
        "",
        f"- walk_forward_run_id: `{queue.get('walk_forward_run_id', '')}`",
        f"- candidate_count: {queue.get('candidate_count', 0)}",
        f"- auto_execute: {queue.get('auto_execute', False)}",
        "",
    ]
    candidates = queue.get("candidates") or []
    if not candidates:
        lines.append("No candidates cleared all promotion gates.")
        return "\n".join(lines).rstrip() + "\n"

    lines += [
        "| Symbol | Candidate | Status | Test 2 | Test 3 | Test 4 | Regime |",
        "|---|---|---|---:|---|---:|---|",
    ]
    for candidate in candidates:
        lines.append(
            f"| {candidate.get('symbol')} | {candidate.get('candidate_id')} | "
            f"{candidate.get('review_status')} | {_fmt(candidate.get('test_score', 0.0))} | "
            f"{candidate.get('rolling_status')} | {_fmt(candidate.get('holdout_score', 0.0))} | "
            f"{candidate.get('holdout_regime')} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def _promotion_view(row: dict[str, Any], settings: dict[str, Any]) -> tuple[str, list[str]]:
    decision = str(row.get("promotion_decision") or "").strip().lower()
    reasons = row.get("promotion_reasons")
    if decision in {"promote", "review", "reject"} and isinstance(reasons, list):
        return decision, [str(reason) for reason in reasons]
    return decide_promotion(row, settings)


def _holdout_status(row: dict[str, Any], prefix: str = "") -> str:
    field = lambda name: row.get(f"{prefix}{name}")
    if _optional_bool(field("holdout_available")) is not True:
        return "unavailable"
    engine_pass = _optional_bool(field("holdout_engine_pass"))
    research_pass = _optional_bool(field("holdout_research_pass"))
    if engine_pass is False or research_pass is False:
        return "failed"
    if engine_pass is True and research_pass is True:
        return "passed"
    return "pending"


def render_walk_forward_report(payload: dict[str, Any]) -> str:
    settings = payload.get("settings") or {}
    lines = [
        "# AI Auto Lab Walk-Forward Universe Report",
        "",
        "AI Auto Lab is research/simulation-only. It does not place orders, connect to brokers, or provide personalized financial advice.",
        "",
        "## Run",
        "",
        f"- walk_forward_run_id: `{payload.get('walk_forward_run_id')}`",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- symbols: {', '.join(payload.get('symbols') or [])}",
        "",
        "## Settings",
        "",
    ]
    for key, value in (payload.get("settings") or {}).items():
        lines.append(f"- {key}: {value}")

    lines += [
        "",
        "## Symbol walk-forward leaderboard",
        "",
        "| Rank | Symbol | Best candidate | Promotion | Test 2 score | Test 3 | Rolling pass | Test 4 | Holdout score | Regime |",
        "|---:|---|---|---|---:|---|---:|---|---:|---|",
    ]

    for rank, row in enumerate(payload.get("ranked_symbols") or [], start=1):
        decision = row.get("best_promotion_decision")
        if decision not in {"promote", "review", "reject"}:
            candidates = row.get("validated_candidates") or []
            decision = _promotion_view(candidates[0], settings)[0] if candidates else "review"
        lines.append(
            f"| {rank} | {row.get('symbol')} | {row.get('best_candidate_id', '')} | "
            f"{decision} | {_fmt(row.get('best_test_score', 0.0))} | "
            f"{row.get('best_rolling_status', 'unavailable')} | "
            f"{_fmt(row.get('best_rolling_pass_rate_pct', 0.0))}% | "
            f"{_holdout_status(row, 'best_')} | {_fmt(row.get('best_holdout_score', 0.0))} | "
            f"{row.get('best_holdout_regime', 'unavailable')} |"
        )

    lines += [
        "",
        "## Top validated candidates",
        "",
        "| Rank | Symbol | Candidate | Promotion | Test 2 research | Test 2 score | Test 3 | Test 4 | Holdout score | Regime |",
        "|---:|---|---|---|---|---:|---|---|---:|---|",
    ]

    for rank, row in enumerate((payload.get("ranked_validated_candidates") or [])[:30], start=1):
        decision, _ = _promotion_view(row, settings)
        lines.append(
            f"| {rank} | {row.get('symbol')} | {row.get('candidate_id')} | "
            f"{decision} | {row.get('test_research_pass', False)} | {_fmt(row.get('test_score', 0.0))} | "
            f"{row.get('rolling_status', 'unavailable')} | {_holdout_status(row)} | "
            f"{_fmt(row.get('holdout_score', 0.0))} | {row.get('holdout_regime', 'unavailable')} |"
        )

    lines += [
        "",
        "## Symbol details",
        "",
    ]

    for symbol_result in payload.get("ranked_symbols") or []:
        lines += [
            f"### {symbol_result.get('symbol')}",
            "",
            f"- data_source: {symbol_result.get('data_source')}",
            f"- train_rows: {symbol_result.get('train_rows')}",
            f"- test_rows: {symbol_result.get('test_rows')}",
            f"- buy_hold_train_return_pct: {_fmt(symbol_result.get('buy_hold_train_return_pct', 0.0))}%",
            f"- buy_hold_test_return_pct: {_fmt(symbol_result.get('buy_hold_test_return_pct', 0.0))}%",
            f"- train_research_pass_candidates: {symbol_result.get('train_research_pass_candidates')}",
            f"- validated_candidate_count: {len(symbol_result.get('validated_candidates') or [])}",
            "",
            "| Rank | Candidate | Promotion | Test 2 score | Test 2 return | Test 3 | Test 4 | Holdout return | Holdout drawdown | Regime |",
            "|---:|---|---|---:|---:|---|---|---:|---:|---|",
        ]
        for rank, row in enumerate(symbol_result.get("validated_candidates") or [], start=1):
            decision, reasons = _promotion_view(row, settings)
            lines.append(
                f"| {rank} | {row.get('candidate_id')} | {decision} | "
                f"{_fmt(row.get('test_score', 0.0))} | {_fmt(row.get('test_total_return_pct', 0.0))}% | "
                f"{row.get('rolling_status', 'unavailable')} | {_holdout_status(row)} | "
                f"{_fmt(row.get('holdout_total_return_pct', 0.0))}% | "
                f"{_fmt(row.get('holdout_max_drawdown_pct', 0.0))}% | "
                f"{row.get('holdout_regime', 'unavailable')} |"
            )
            lines.append(f"  - Promotion reasons: {' '.join(reasons)}")
            for window in row.get("rolling_windows") or []:
                lines.append(
                    f"  - Test 3 window {window.get('window')}: {window.get('start')} to {window.get('end')}; "
                    f"score {_fmt(window.get('score', 0.0))}, return {_fmt(window.get('total_return_pct', 0.0))}%, "
                    f"drawdown {_fmt(window.get('max_drawdown_pct', 0.0))}%, trades {window.get('trade_count', 0)}."
                )
            if _optional_bool(row.get("holdout_available")) is True:
                lines.append(
                    f"  - Test 4 holdout ({row.get('holdout_regime', 'unavailable')}): "
                    f"engine_pass {row.get('holdout_engine_pass')}, research_pass {row.get('holdout_research_pass')}, "
                    f"objective_hit {row.get('holdout_objective_hit')}, "
                    f"progress {_fmt(row.get('holdout_objective_progress_pct', 0.0))}%, "
                    f"score {_fmt(row.get('holdout_score', 0.0))}, trades {row.get('holdout_trade_count', 0)}."
                )
            else:
                lines.append("  - Test 4 holdout: unavailable; this candidate cannot be promoted.")
        lines.append("")

    lines += [
        "## Research-only limitation",
        "",
        "Training selection, an unseen Test 2 window, rolling cost-stressed Test 3 windows, and a final Test 4 holdout are stronger than a single in-sample test, but remain historical simulations. Promotion is a research governance decision, not authorization for live trading.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def render_symbol_leaderboard(payload: dict[str, Any]) -> str:
    settings = payload.get("settings") or {}
    lines = [
        "# Walk-Forward Symbol Leaderboard",
        "",
        "| Rank | Symbol | Best candidate | Promotion | Test 2 score | Test 3 | Test 4 | Holdout score | Regime |",
        "|---:|---|---|---|---:|---|---|---:|---|",
    ]
    for rank, row in enumerate(payload.get("ranked_symbols") or [], start=1):
        decision = row.get("best_promotion_decision")
        if decision not in {"promote", "review", "reject"}:
            candidates = row.get("validated_candidates") or []
            decision = _promotion_view(candidates[0], settings)[0] if candidates else "review"
        lines.append(
            f"| {rank} | {row.get('symbol')} | {row.get('best_candidate_id', '')} | "
            f"{decision} | {_fmt(row.get('best_test_score', 0.0))} | "
            f"{row.get('best_rolling_status', 'unavailable')} | "
            f"{_holdout_status(row, 'best_')} | {_fmt(row.get('best_holdout_score', 0.0))} | "
            f"{row.get('best_holdout_regime', 'unavailable')} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def render_overfit_warning_report(payload: dict[str, Any]) -> str:
    settings = payload.get("settings") or {}
    rows = payload.get("ranked_validated_candidates") or []
    rows = sorted(rows, key=lambda item: _safe_float(item.get("train_score", 0.0)) - _safe_float(item.get("test_score", 0.0)), reverse=True)

    lines = [
        "# Walk-Forward Overfit Warning Report",
        "",
        "This report flags strategies that looked strong on train data but weakened on test data.",
        "",
        "| Rank | Symbol | Candidate | Promotion | Train score | Test score | Score drop | Test progress | Test 4 | Regime | Label |",
        "|---:|---|---|---|---:|---:|---:|---:|---|---|---|",
    ]
    for rank, row in enumerate(rows[:50], start=1):
        train_score = _safe_float(row.get("train_score", 0.0))
        test_score = _safe_float(row.get("test_score", 0.0))
        decision, _ = _promotion_view(row, settings)
        lines.append(
            f"| {rank} | {row.get('symbol')} | {row.get('candidate_id')} | "
            f"{decision} | {_fmt(train_score)} | {_fmt(test_score)} | {_fmt(train_score - test_score)} | "
            f"{_fmt(row.get('test_objective_progress_pct', 0.0))}% | {_holdout_status(row)} | "
            f"{row.get('holdout_regime', 'unavailable')} | {row.get('overfit_label', '')} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def render_top_walk_forward_strategy_algorithm(payload: dict[str, Any]) -> str:
    rows = payload.get("ranked_validated_candidates") or []
    if not rows:
        return "# Top Walk-Forward Strategy Algorithm\n\nNo validated candidates available.\n"

    top = rows[0]
    decision, reasons = _promotion_view(top, payload.get("settings") or {})
    lines = [
        "# Top Walk-Forward Strategy Algorithm",
        "",
        "Research/simulation-only. This candidate ranks highest under four-stage promotion governance.",
        "",
        f"- symbol: {top.get('symbol')}",
        f"- candidate: `{top.get('candidate_id')}`",
        f"- train_score: {_fmt(top.get('train_score', 0.0))}",
        f"- test_score: {_fmt(top.get('test_score', 0.0))}",
        f"- train_objective_hit: {top.get('train_objective_hit', False)}",
        f"- test_objective_hit: {top.get('test_objective_hit', False)}",
        f"- test_objective_progress_pct: {_fmt(top.get('test_objective_progress_pct', 0.0))}%",
        f"- buy_hold_test_return_pct: {_fmt(top.get('buy_hold_test_return_pct', 0.0))}%",
        f"- overfit_label: {top.get('overfit_label', '')}",
        f"- rolling_status: {top.get('rolling_status', 'unavailable')}",
        f"- rolling_pass_rate_pct: {_fmt(top.get('rolling_pass_rate_pct', 0.0))}%",
        f"- rolling_worst_score: {_fmt(top.get('rolling_worst_score', 0.0))}",
        f"- rolling_worst_drawdown_pct: {_fmt(top.get('rolling_worst_drawdown_pct', 0.0))}%",
        f"- rolling_commission_per_order: ${_fmt(top.get('rolling_commission_per_order', 0.0))}",
        f"- rolling_slippage_bps: {_fmt(top.get('rolling_slippage_bps', 0.0))}",
        f"- holdout_available: {top.get('holdout_available', False)}",
        f"- holdout_score: {_fmt(top.get('holdout_score', 0.0))}",
        f"- holdout_engine_pass: {top.get('holdout_engine_pass')}",
        f"- holdout_research_pass: {top.get('holdout_research_pass')}",
        f"- holdout_objective_hit: {top.get('holdout_objective_hit')}",
        f"- holdout_objective_progress_pct: {_fmt(top.get('holdout_objective_progress_pct', 0.0))}%",
        f"- holdout_total_return_pct: {_fmt(top.get('holdout_total_return_pct', 0.0))}%",
        f"- holdout_max_drawdown_pct: {_fmt(top.get('holdout_max_drawdown_pct', 0.0))}%",
        f"- holdout_trade_count: {top.get('holdout_trade_count', 0)}",
        f"- holdout_regime: {top.get('holdout_regime', 'unavailable')}",
        f"- promotion_decision: {decision}",
        f"- promotion_reasons: {' '.join(reasons)}",
        "",
        "## Strategy code",
        "",
        "```text",
        top.get("script", ""),
        "```",
        "",
        "## Deterministic interpretation",
        "",
    ]

    lines.append(
        f"- Test 1 training research gate: "
        f"{'passed' if _optional_bool(top.get('train_research_pass')) is True else 'did not pass'}."
    )
    lines.append(
        f"- Test 2 unseen research gate: "
        f"{'passed' if _optional_bool(top.get('test_research_pass')) is True else 'did not pass'}; "
        f"objective {'reached' if _optional_bool(top.get('test_objective_hit')) is True else 'not reached'}."
    )

    if top.get("rolling_status") == "robust":
        lines.append("- Test 3 passed the rolling fee and slippage stress gate.")
    elif top.get("rolling_status") == "partial":
        lines.append("- Test 3 survived some rolling stress windows, but stability is not yet consistent.")
    elif top.get("rolling_status") == "failed":
        lines.append("- Test 3 failed the rolling fee/slippage stress gate; do not promote this candidate.")
    else:
        lines.append("- Test 3 was unavailable because the test period did not contain enough bars for rolling windows.")

    if _optional_bool(top.get("holdout_available")) is True:
        lines.append(
            f"- Test 4 holdout regime `{top.get('holdout_regime', 'unavailable')}`: "
            f"engine {'passed' if _optional_bool(top.get('holdout_engine_pass')) is True else 'did not pass'}, "
            f"research {'passed' if _optional_bool(top.get('holdout_research_pass')) is True else 'did not pass'}, "
            f"drawdown {_fmt(top.get('holdout_max_drawdown_pct', 0.0))}%."
        )
    else:
        lines.append("- Test 4 holdout is unavailable, so promotion is not permitted.")

    lines.append(f"- Promotion decision: {decision}. {' '.join(reasons)}")
    if decision == "promote":
        lines.append("- Next step: proceed to controlled paper-trading review with monitoring and explicit risk limits.")
    elif decision == "review":
        lines.append("- Next step: resolve the listed governance gaps and rerun the affected validation stage.")
    else:
        lines.append("- Next step: reject this candidate or redesign it before any new promotion review.")

    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_walk_forward_artifacts(payload: dict[str, Any], out_dir: str | Path) -> dict[str, str]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "walk_forward_universe_results_json": out_dir / "walk_forward_universe_results.json",
        "walk_forward_universe_report_md": out_dir / "walk_forward_universe_report.md",
        "walk_forward_symbol_leaderboard_md": out_dir / "walk_forward_symbol_leaderboard.md",
        "overfit_warning_report_md": out_dir / "overfit_warning_report.md",
        "top_walk_forward_strategy_algorithm_md": out_dir / "top_walk_forward_strategy_algorithm.md",
        "paper_review_queue_json": out_dir / "paper_review_queue.json",
        "paper_review_queue_md": out_dir / "paper_review_queue.md",
    }

    paper_review_queue = build_paper_review_queue(payload)

    paths["walk_forward_universe_results_json"].write_text(json.dumps(payload, indent=2), encoding="utf-8")
    paths["walk_forward_universe_report_md"].write_text(render_walk_forward_report(payload), encoding="utf-8")
    paths["walk_forward_symbol_leaderboard_md"].write_text(render_symbol_leaderboard(payload), encoding="utf-8")
    paths["overfit_warning_report_md"].write_text(render_overfit_warning_report(payload), encoding="utf-8")
    paths["top_walk_forward_strategy_algorithm_md"].write_text(render_top_walk_forward_strategy_algorithm(payload), encoding="utf-8")
    paths["paper_review_queue_json"].write_text(json.dumps(paper_review_queue, indent=2), encoding="utf-8")
    paths["paper_review_queue_md"].write_text(render_paper_review_queue(paper_review_queue), encoding="utf-8")

    return {key: str(value) for key, value in paths.items()}
