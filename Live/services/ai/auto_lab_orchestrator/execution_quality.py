from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any
from datetime import datetime, timezone
import json
import math


INSUFFICIENT_CASH_TOKEN = "insufficient cash"


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


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(_safe_float(value, default))
    except Exception:
        return default


def _as_dict(value: Any) -> dict[str, Any]:
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
            out = value.to_dict()
            if isinstance(out, dict):
                return out
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        return dict(getattr(value, "__dict__", {}) or {})
    return {}


def _get_attr(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _set_attr(obj: Any, key: str, value: Any) -> None:
    if isinstance(obj, dict):
        obj[key] = value
    else:
        try:
            setattr(obj, key, value)
        except Exception:
            pass


def _list_attr(obj: Any, key: str) -> list[Any]:
    value = _get_attr(obj, key, [])
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return list(value) if isinstance(value, tuple) else [value]


def _is_insufficient_cash_reason(reason: Any) -> bool:
    text = str(reason or "").lower()
    return INSUFFICIENT_CASH_TOKEN in text and "buy" in text


def usable_metrics(metrics: dict[str, Any]) -> bool:
    if not metrics:
        return False
    final_equity = _safe_float(metrics.get("final_equity"), 0.0)
    initial_cash = _safe_float(metrics.get("initial_cash"), 0.0)
    trade_count = _safe_int(metrics.get("trade_count"), 0)
    has_return = "total_return_pct" in metrics or "total_pnl" in metrics
    return final_equity > 0 and initial_cash > 0 and has_return and trade_count >= 0


def grade_from_score(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 75:
        return "B"
    if score >= 65:
        return "C"
    if score >= 50:
        return "D"
    return "F"


def recommendation_from_score(engine_pass: bool, research_pass: bool, objective_hit: bool, score: float, metrics: dict[str, Any]) -> str:
    if not engine_pass:
        return "Fix engine/script/data errors before retesting."
    if objective_hit and research_pass:
        return "Promote to walk-forward validation and stress testing before stronger conclusions."
    if research_pass:
        return "Retest nearby parameter values and validate on an unseen out-of-sample window."
    if score >= 50:
        return "Keep as low-priority candidate; needs stronger out-of-sample evidence."
    return "Reject or materially redesign; weak simulated result under current score gates."


def recovered_score_from_metrics(metrics: dict[str, Any]) -> tuple[float, dict[str, float]]:
    initial_cash = _safe_float(metrics.get("initial_cash"), 0.0)
    final_equity = _safe_float(metrics.get("final_equity"), 0.0)
    total_return_pct = _safe_float(metrics.get("total_return_pct"), 0.0)
    if total_return_pct == 0.0 and initial_cash > 0 and final_equity > 0:
        total_return_pct = ((final_equity / initial_cash) - 1.0) * 100.0

    max_drawdown_pct = abs(_safe_float(metrics.get("max_drawdown_pct"), 0.0))
    trade_count = _safe_int(metrics.get("trade_count"), 0)
    win_rate_pct = max(0.0, min(_safe_float(metrics.get("win_rate_pct"), 0.0), 100.0))
    profit_factor = max(0.0, _safe_float(metrics.get("profit_factor"), 0.0))

    objective_progress_pct = max(0.0, min(total_return_pct, 100.0))

    engine_score = 20.0
    return_score = max(0.0, min(total_return_pct / 100.0, 1.0)) * 20.0
    drawdown_score = max(0.0, min(1.0 - (max_drawdown_pct / 30.0), 1.0)) * 20.0
    trade_score = max(0.0, min(trade_count / 5.0, 1.0)) * 10.0
    win_score = (win_rate_pct / 100.0) * 10.0
    profit_factor_score = max(0.0, min(profit_factor / 3.0, 1.0)) * 10.0
    objective_score = (objective_progress_pct / 100.0) * 20.0

    components = {
        "engine_score": round(engine_score, 4),
        "return_score": round(return_score, 4),
        "drawdown_score": round(drawdown_score, 4),
        "trade_count_score": round(trade_score, 4),
        "win_rate_score": round(win_score, 4),
        "profit_factor_score": round(profit_factor_score, 4),
        "objective_progress_score": round(objective_score, 4),
    }
    total = sum(components.values())
    return round(total, 4), components


def _scorecard_by_key(scorecards: list[Any]) -> dict[tuple[str, str], Any]:
    out = {}
    for sc in scorecards:
        out[(str(_get_attr(sc, "candidate_id", "")), str(_get_attr(sc, "symbol", "")))] = sc
    return out


def normalize_run_execution_quality(run: Any, context: str = "") -> dict[str, Any]:
    """
    Convert skipped BUY insufficient-cash conditions into execution warnings
    when the result has usable metrics.

    This does not hide the issue. It moves it from hard engine failure to warnings
    and recomputes a deterministic metric-based score.
    """
    results = _list_attr(run, "results")
    scorecards = _list_attr(run, "scorecards")
    score_by_key = _scorecard_by_key(scorecards)

    normalized: list[dict[str, Any]] = []
    untouched = 0

    for result in results:
        candidate_id = str(_get_attr(result, "candidate_id", ""))
        symbol = str(_get_attr(result, "symbol", ""))
        metrics = _as_dict(_get_attr(result, "metrics", {}))
        scorecard = score_by_key.get((candidate_id, symbol))
        if scorecard is None:
            untouched += 1
            continue

        fail_reasons = [str(x) for x in _list_attr(scorecard, "fail_reasons")]
        insufficient_cash_reasons = [r for r in fail_reasons if _is_insufficient_cash_reason(r)]
        other_fail_reasons = [r for r in fail_reasons if not _is_insufficient_cash_reason(r)]

        if not insufficient_cash_reasons or other_fail_reasons or not usable_metrics(metrics):
            untouched += 1
            continue

        old_score = _safe_float(_get_attr(scorecard, "total_score", 0.0), 0.0)
        old_engine_pass = bool(_get_attr(scorecard, "engine_pass", False))
        recovered_score, components = recovered_score_from_metrics(metrics)

        initial_cash = _safe_float(metrics.get("initial_cash"), 0.0)
        final_equity = _safe_float(metrics.get("final_equity"), 0.0)
        objective_hit = initial_cash > 0 and final_equity >= initial_cash * 2.0
        objective_progress_pct = max(0.0, min(_safe_float(metrics.get("total_return_pct"), 0.0), 100.0))
        research_pass = recovered_score >= 65.0

        warnings = [str(x) for x in _list_attr(scorecard, "warnings")]
        warnings.append(
            "Execution warning: one or more simulated BUY signals were skipped because available simulated cash was insufficient."
        )
        for reason in insufficient_cash_reasons[:10]:
            warnings.append(f"Skipped signal warning: {reason}")

        _set_attr(scorecard, "engine_pass", True)
        _set_attr(scorecard, "passed", bool(research_pass))
        _set_attr(scorecard, "research_pass", bool(research_pass))
        _set_attr(scorecard, "objective_hit", bool(objective_hit))
        _set_attr(scorecard, "objective_progress_pct", round(objective_progress_pct, 4))
        _set_attr(scorecard, "total_score", recovered_score)
        _set_attr(scorecard, "grade", grade_from_score(recovered_score))
        _set_attr(scorecard, "component_scores", components)
        _set_attr(scorecard, "fail_reasons", [])
        _set_attr(scorecard, "warnings", warnings)
        _set_attr(
            scorecard,
            "retest_recommendation",
            recommendation_from_score(True, bool(research_pass), bool(objective_hit), recovered_score, metrics),
        )

        normalized.append(
            {
                "candidate_id": candidate_id,
                "symbol": symbol,
                "old_engine_pass": old_engine_pass,
                "new_engine_pass": True,
                "old_score": old_score,
                "new_score": recovered_score,
                "new_grade": grade_from_score(recovered_score),
                "new_research_pass": bool(research_pass),
                "insufficient_cash_warning_count": len(insufficient_cash_reasons),
                "metrics": metrics,
                "reasons_moved_to_warnings": insufficient_cash_reasons,
            }
        )

    try:
        summary = dict(_get_attr(run, "summary", {}) or {})
        summary["execution_quality_normalized_count"] = len(normalized)
        summary["engine_pass_count"] = sum(1 for sc in scorecards if bool(_get_attr(sc, "engine_pass", False)))
        summary["research_pass_count"] = sum(1 for sc in scorecards if bool(_get_attr(sc, "research_pass", False)))
        summary["objective_hit_count"] = sum(1 for sc in scorecards if bool(_get_attr(sc, "objective_hit", False)))
        _set_attr(run, "summary", summary)
    except Exception:
        pass

    return {
        "schema_version": "execution_quality_v21_4_4",
        "context": context,
        "normalized_count": len(normalized),
        "untouched_count": untouched,
        "normalized": normalized,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rule": "Insufficient-cash BUY skips become warnings only when usable metrics exist and no other hard fail reasons are present.",
    }


def build_execution_quality_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Execution Quality Normalization Report",
        "",
        "AI Auto Lab is research/simulation-only. This report does not place orders or connect to brokers.",
        "",
        f"- generated_at: `{summary.get('generated_at', '')}`",
        f"- context: {summary.get('context', '')}",
        f"- normalized_count: {summary.get('normalized_count', 0)}",
        f"- untouched_count: {summary.get('untouched_count', 0)}",
        "",
        "## Rule",
        "",
        str(summary.get("rule", "")),
        "",
        "## Normalized candidates",
        "",
    ]

    normalized = summary.get("normalized") or []
    if not normalized:
        lines.append("No candidates required insufficient-cash warning normalization.")
    else:
        lines += [
            "| Candidate | Old score | New score | Grade | Research | Warnings moved |",
            "|---|---:|---:|---|---|---:|",
        ]
        for item in normalized:
            lines.append(
                f"| {item.get('candidate_id')} | {item.get('old_score')} | {item.get('new_score')} | "
                f"{item.get('new_grade')} | {item.get('new_research_pass')} | "
                f"{item.get('insufficient_cash_warning_count')} |"
            )

        lines += ["", "## Details", ""]
        for item in normalized:
            lines += [
                f"### {item.get('candidate_id')}",
                "",
                f"- symbol: {item.get('symbol')}",
                f"- old_engine_pass: {item.get('old_engine_pass')}",
                f"- new_engine_pass: {item.get('new_engine_pass')}",
                f"- old_score: {item.get('old_score')}",
                f"- new_score: {item.get('new_score')}",
                f"- new_grade: {item.get('new_grade')}",
                f"- new_research_pass: {item.get('new_research_pass')}",
                "",
                "Warnings moved from fail_reasons:",
                "",
            ]
            for reason in item.get("reasons_moved_to_warnings", [])[:20]:
                lines.append(f"- {reason}")
            lines.append("")

    lines += [
        "## Safety",
        "",
        "This normalization changes reporting semantics for simulated skipped signals only. It does not create orders, broker actions, live sizing, or financial advice.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def write_execution_quality_report(run: Any, report_dir: str | Path, normalization_summary: dict[str, Any]) -> dict[str, str]:
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    if "mutation" in normalization_summary or "baseline" in normalization_summary:
        render_summary = normalization_summary.get("mutation") or normalization_summary.get("baseline") or {}
        payload = normalization_summary
    else:
        render_summary = normalization_summary
        payload = {"mutation": normalization_summary}

    json_path = report_dir / "execution_quality.json"
    md_path = report_dir / "execution_quality_report.md"

    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(build_execution_quality_report(render_summary), encoding="utf-8")

    return {
        "execution_quality_json": str(json_path),
        "execution_quality_report_md": str(md_path),
    }
