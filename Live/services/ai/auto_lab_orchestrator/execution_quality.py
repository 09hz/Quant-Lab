from __future__ import annotations

from dataclasses import asdict, fields, is_dataclass
from pathlib import Path
from typing import Any
from datetime import datetime, timezone
import json
import math

from .models import ExperimentGoal, NormalizedBacktestResult
from .scorecard import score_strategy_result


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


def _experiment_goal(run: Any) -> ExperimentGoal | None:
    raw_goal = _get_attr(run, "goal")
    if isinstance(raw_goal, ExperimentGoal):
        return raw_goal

    goal_data = _as_dict(raw_goal)
    if not goal_data:
        return None

    allowed = {item.name for item in fields(ExperimentGoal)}
    return ExperimentGoal(**{key: value for key, value in goal_data.items() if key in allowed})


def _unique_strings(values: list[Any]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            output.append(text)
    return output


def _scorecard_by_key(scorecards: list[Any]) -> dict[tuple[str, str], Any]:
    out = {}
    for sc in scorecards:
        out[(str(_get_attr(sc, "candidate_id", "")), str(_get_attr(sc, "symbol", "")))] = sc
    return out


def normalize_run_execution_quality(run: Any, context: str = "") -> dict[str, Any]:
    """
    Convert skipped BUY insufficient-cash conditions into execution warnings
    when the result has usable metrics.

    This does not hide the issue. It moves it from hard engine failure to warnings,
    then delegates scoring back to the configured experiment policy.
    """
    results = _list_attr(run, "results")
    scorecards = _list_attr(run, "scorecards")
    score_by_key = _scorecard_by_key(scorecards)
    goal = _experiment_goal(run)

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
        result_errors = [str(x) for x in _list_attr(result, "errors")]
        insufficient_cash_reasons = _unique_strings(
            [r for r in result_errors + fail_reasons if _is_insufficient_cash_reason(r)]
        )
        other_result_errors = [r for r in result_errors if not _is_insufficient_cash_reason(r)]

        if not insufficient_cash_reasons or other_result_errors or not usable_metrics(metrics) or goal is None:
            untouched += 1
            continue

        old_score = _safe_float(_get_attr(scorecard, "total_score", 0.0), 0.0)
        old_engine_pass = bool(_get_attr(scorecard, "engine_pass", False))
        warnings = _unique_strings(
            _list_attr(result, "warnings")
            + _list_attr(scorecard, "warnings")
            + ["Execution warning: one or more simulated BUY signals were skipped because available simulated cash was insufficient."]
            + [f"Skipped signal warning: {reason}" for reason in insufficient_cash_reasons[:10]]
        )

        policy_result = NormalizedBacktestResult(
            candidate_id=candidate_id,
            symbol=symbol,
            status="ok",
            engine=str(_get_attr(result, "engine", "")),
            metrics=metrics,
            trades=_list_attr(result, "trades"),
            equity_curve=_list_attr(result, "equity_curve"),
            errors=[],
            warnings=warnings,
            raw_summary=_as_dict(_get_attr(result, "raw_summary", {})),
        )
        rescored = score_strategy_result(policy_result, goal)

        _set_attr(result, "status", "ok")
        _set_attr(result, "errors", [])
        _set_attr(result, "warnings", warnings)

        for key, value in _as_dict(rescored).items():
            _set_attr(scorecard, key, value)

        normalized.append(
            {
                "candidate_id": candidate_id,
                "symbol": symbol,
                "old_engine_pass": old_engine_pass,
                "new_engine_pass": rescored.engine_pass,
                "old_score": old_score,
                "new_score": rescored.total_score,
                "new_grade": rescored.grade,
                "new_research_pass": rescored.research_pass,
                "insufficient_cash_warning_count": len(insufficient_cash_reasons),
                "metrics": metrics,
                "reasons_moved_to_warnings": insufficient_cash_reasons,
            }
        )

    try:
        summary = dict(_get_attr(run, "summary", {}) or {})
        best_scorecard = (
            max(scorecards, key=lambda sc: _safe_float(_get_attr(sc, "total_score", 0.0)))
            if scorecards
            else None
        )
        summary["execution_quality_normalized_count"] = len(normalized)
        summary["engine_pass_count"] = sum(1 for sc in scorecards if bool(_get_attr(sc, "engine_pass", False)))
        summary["research_pass_count"] = sum(1 for sc in scorecards if bool(_get_attr(sc, "research_pass", False)))
        summary["objective_hit_count"] = sum(1 for sc in scorecards if bool(_get_attr(sc, "objective_hit", False)))
        summary["passed_count"] = summary["research_pass_count"]
        if best_scorecard is not None:
            summary["best_candidate_id"] = str(_get_attr(best_scorecard, "candidate_id", ""))
            summary["best_symbol"] = str(_get_attr(best_scorecard, "symbol", ""))
            summary["best_score"] = _safe_float(_get_attr(best_scorecard, "total_score", 0.0))
        _set_attr(run, "summary", summary)
    except Exception:
        pass

    return {
        "schema_version": "execution_quality_v21_4_5",
        "context": context,
        "normalized_count": len(normalized),
        "untouched_count": untouched,
        "normalized": normalized,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rule": "Insufficient-cash BUY skips become warnings only when usable metrics and the configured experiment goal are available; all research gates are then reapplied.",
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
