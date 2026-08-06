from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import re

from services.ai.auto_lab_orchestrator.models import local_now_iso, utc_now_iso


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str) and not value.strip():
            return default
        return float(value)
    except Exception:
        return default


def _safe_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _candidate_id(item: dict) -> str:
    return str(item.get("candidate_id") or "")


def _scorecard_id(item: dict) -> str:
    return str(item.get("candidate_id") or "")


def _parent_id(candidate: dict) -> str:
    params = _safe_dict(candidate.get("parameters"))
    if params.get("parent_id"):
        return str(params.get("parent_id"))
    source = str(candidate.get("source") or "")
    if source.startswith("mutation_of:"):
        return source[len("mutation_of:") :]
    return ""


def _result_key(result: dict) -> tuple[str, str]:
    return (str(result.get("candidate_id") or ""), str(result.get("symbol") or ""))


def _first_number_after_indicator(script: str, indicator: str) -> int | None:
    pattern = re.compile(rf"(?:ta\.)?{re.escape(indicator)}\(\s*close\s*,\s*(\d+)\s*\)", re.IGNORECASE)
    match = pattern.search(script or "")
    return int(match.group(1)) if match else None


def _ma_numbers(script: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    pattern = re.compile(r"\b(?:ta\.)?(ema|sma)\(\s*close\s*,\s*(\d+)\s*\)", re.IGNORECASE)
    for match in pattern.finditer(script or ""):
        out.append((match.group(1).lower(), int(match.group(2))))
    return out


def _thresholds(script: str) -> dict[str, int]:
    out: dict[str, int] = {}
    buy_match = re.search(r"(?:buy\s+when|buy\s*=).*?<\s*(\d+)", script or "", flags=re.IGNORECASE | re.DOTALL)
    sell_match = re.search(r"(?:sell\s+when|sell\s*=).*?>\s*(\d+)", script or "", flags=re.IGNORECASE | re.DOTALL)
    if buy_match:
        out["buy_threshold"] = int(buy_match.group(1))
    if sell_match:
        out["sell_threshold"] = int(sell_match.group(1))
    return out


def infer_mutation(parent_script: str, final_script: str, candidate_id: str = "") -> dict[str, Any]:
    parent_script = parent_script or ""
    final_script = final_script or ""

    parent_rsi = _first_number_after_indicator(parent_script, "rsi")
    final_rsi = _first_number_after_indicator(final_script, "rsi")
    if parent_rsi is not None and final_rsi is not None and parent_rsi != final_rsi:
        return {
            "type": "rsi_length",
            "from": parent_rsi,
            "to": final_rsi,
            "summary": f"RSI length {parent_rsi} → {final_rsi}",
        }

    parent_ma = _ma_numbers(parent_script)
    final_ma = _ma_numbers(final_script)
    for idx, ((p_fn, p_val), (f_fn, f_val)) in enumerate(zip(parent_ma, final_ma)):
        if p_fn == f_fn and p_val != f_val:
            label = "fast" if idx == 0 else ("slow" if idx == 1 else f"ma_{idx + 1}")
            return {
                "type": f"{label}_{p_fn}_window",
                "from": p_val,
                "to": f_val,
                "summary": f"{label} {p_fn.upper()} window {p_val} → {f_val}",
            }

    parent_thr = _thresholds(parent_script)
    final_thr = _thresholds(final_script)
    for key in ("buy_threshold", "sell_threshold"):
        if key in parent_thr and key in final_thr and parent_thr[key] != final_thr[key]:
            return {
                "type": key,
                "from": parent_thr[key],
                "to": final_thr[key],
                "summary": f"{key.replace('_', ' ')} {parent_thr[key]} → {final_thr[key]}",
            }

    # Fallback from candidate id.
    match = re.search(r"([a-zA-Z0-9_]+)_to_(\d+)", candidate_id)
    if match:
        return {
            "type": "candidate_id_inferred",
            "from": "",
            "to": match.group(2),
            "summary": f"Inferred mutation from candidate id: {match.group(0)}",
        }

    return {
        "type": "unknown_or_no_parameter_change",
        "from": "",
        "to": "",
        "summary": "No simple numeric parameter change detected.",
    }


def algorithm_steps(script: str, settings: dict | None = None) -> list[str]:
    settings = settings or {}
    lower = (script or "").lower()
    steps: list[str] = []

    if "rsi" in lower:
        rsi_length = _first_number_after_indicator(script, "rsi")
        if rsi_length:
            steps.append(f"Calculate RSI using a {rsi_length}-bar lookback.")
        else:
            steps.append("Calculate RSI on close prices.")

        if "crossunder" in lower:
            buy_thr = _thresholds(script).get("buy_threshold", 30)
            steps.append(f"Enter a simulated long position when RSI crosses below {buy_thr}.")
        elif "buy when" in lower and "<" in lower:
            buy_thr = _thresholds(script).get("buy_threshold", "")
            steps.append(f"Enter a simulated long position when RSI is below {buy_thr}.")
        else:
            steps.append("Use the RSI entry condition defined in the Strategy Lab script.")

        if "crossover" in lower:
            sell_thr = _thresholds(script).get("sell_threshold", 70)
            steps.append(f"Exit the simulated position when RSI crosses above {sell_thr}.")
        elif "sell when" in lower and ">" in lower:
            sell_thr = _thresholds(script).get("sell_threshold", "")
            steps.append(f"Exit the simulated position when RSI is above {sell_thr}.")
        else:
            steps.append("Use the RSI exit condition defined in the Strategy Lab script.")

    elif "crossover" in lower or "crossunder" in lower:
        ma = _ma_numbers(script)
        if len(ma) >= 2:
            steps.append(f"Calculate a fast {ma[0][0].upper()}({ma[0][1]}) and a slow {ma[1][0].upper()}({ma[1][1]}).")
        else:
            steps.append("Calculate the moving-average or crossover inputs.")
        steps.append("Enter a simulated long position when the fast signal crosses above the slow signal.")
        steps.append("Exit the simulated position when the fast signal crosses below the slow signal.")

    else:
        steps.append("Run the Strategy Lab script on each historical bar.")
        steps.append("Use the script's buy condition to enter simulated long positions.")
        steps.append("Use the script's sell condition to exit simulated positions.")

    sizing_mode = settings.get("sizing_mode") or settings.get("sizing", {}).get("sizing_mode")
    exposure = settings.get("cash_exposure_pct") or settings.get("sizing", {}).get("cash_exposure_pct")
    if sizing_mode:
        if sizing_mode == "percent_cash_exposure":
            steps.append(f"Size each simulation using approximately {exposure}% cash exposure.")
        elif sizing_mode == "max_affordable_shares":
            steps.append("Size each simulation using the maximum affordable whole shares.")
        else:
            steps.append("Size each simulation using fixed quantity.")

    steps.append("Score the result using return, drawdown, trade count, win rate, profit factor, and objective progress.")
    steps.append("Keep the result as research-only; no live orders or broker actions are created.")
    return steps


def pass_fail_notes(scorecard: dict, result: dict) -> list[str]:
    notes: list[str] = []

    if scorecard.get("engine_pass"):
        notes.append("Engine pass: StrategyEngine and BackTestEngine produced a usable simulated result.")
    else:
        notes.append("Engine fail: result had engine/data/script issues that need review.")

    if scorecard.get("research_pass"):
        notes.append("Research pass: deterministic score gates suggest this candidate is worth more research.")
    else:
        notes.append("Research fail: score gates did not support promoting this candidate.")

    if scorecard.get("objective_hit"):
        notes.append("Objective hit: simulated final equity reached the target objective.")
    else:
        notes.append("Objective not hit: simulated final equity did not reach the target objective.")

    metrics = _safe_dict(result.get("metrics"))
    if metrics:
        notes.append(
            "Key metrics: "
            f"return={metrics.get('total_return_pct', 'n/a')}%, "
            f"max_drawdown={metrics.get('max_drawdown_pct', 'n/a')}%, "
            f"trades={metrics.get('trade_count', 'n/a')}, "
            f"final_equity={metrics.get('final_equity', 'n/a')}."
        )

    for reason in _safe_list(scorecard.get("fail_reasons"))[:5]:
        notes.append(f"Fail reason: {reason}")
    for warning in _safe_list(scorecard.get("warnings"))[:5]:
        notes.append(f"Warning: {warning}")

    return notes


def next_test_idea(scorecard: dict, mutation: dict) -> str:
    if not scorecard.get("engine_pass"):
        return "Fix engine/script/data issues first, then retest the same candidate."
    if scorecard.get("objective_hit") and scorecard.get("research_pass"):
        return "Promote to walk-forward validation and stress tests before any stronger conclusion."
    if scorecard.get("research_pass"):
        return "Retest nearby parameter values and validate on an unseen out-of-sample window."
    if mutation.get("type") == "rsi_length":
        return "Try a less aggressive RSI length change or adjust RSI entry/exit thresholds."
    return "Keep as low priority or redesign the entry/exit logic."


def build_strategy_trace_packet(report_dir: Path) -> dict[str, Any]:
    mutation_path = report_dir / "mutation_results.json"
    if not mutation_path.exists():
        raise FileNotFoundError(f"Missing mutation_results.json in {report_dir}")

    payload = json.loads(mutation_path.read_text(encoding="utf-8", errors="replace"))
    run = _safe_dict(payload.get("run"))
    parents = _safe_list(payload.get("parents"))
    parent_scorecards = _safe_list(payload.get("parent_scorecards"))
    settings = _safe_dict(payload.get("settings"))

    run_candidates = _safe_list(run.get("candidates"))
    run_scorecards = _safe_list(run.get("scorecards"))
    run_results = _safe_list(run.get("results"))
    run_summary = _safe_dict(run.get("summary"))

    data_profile = _safe_dict(run_summary.get("data_profile"))
    if not data_profile:
        profile_path = report_dir / "data_profile.json"
        if profile_path.exists():
            try:
                data_profile = _safe_dict(json.loads(profile_path.read_text(encoding="utf-8", errors="replace")).get("data_profile"))
            except Exception:
                data_profile = {}

    parent_by_id = {_candidate_id(parent): parent for parent in parents}
    parent_score_by_id = {_scorecard_id(scorecard): scorecard for scorecard in parent_scorecards}
    candidate_by_id = {_candidate_id(candidate): candidate for candidate in run_candidates}
    result_by_id = {_result_key(result): result for result in run_results}

    sorted_scorecards = sorted(
        run_scorecards,
        key=lambda item: _safe_float(item.get("total_score"), 0.0),
        reverse=True,
    )

    traces: list[dict[str, Any]] = []
    for rank, scorecard in enumerate(sorted_scorecards, start=1):
        candidate_id = _scorecard_id(scorecard)
        candidate = candidate_by_id.get(candidate_id, {})
        parent_id = _parent_id(candidate)
        parent = parent_by_id.get(parent_id, {})
        parent_scorecard = parent_score_by_id.get(parent_id, {})
        result = result_by_id.get((candidate_id, str(scorecard.get("symbol") or "")), {})
        parent_script = str(parent.get("script") or "")
        final_script = str(candidate.get("script") or "")
        mutation = infer_mutation(parent_script, final_script, candidate_id=candidate_id)

        trace = {
            "rank": rank,
            "candidate_id": candidate_id,
            "symbol": str(scorecard.get("symbol") or ""),
            "parent_id": parent_id,
            "parent_name": str(parent.get("name") or parent_id),
            "candidate_name": str(candidate.get("name") or candidate_id),
            "mutation": mutation,
            "parent_code": parent_script,
            "final_code": final_script,
            "algorithm_steps": algorithm_steps(final_script, settings=settings),
            "score": {
                "total_score": scorecard.get("total_score"),
                "grade": scorecard.get("grade"),
                "engine_pass": scorecard.get("engine_pass"),
                "research_pass": scorecard.get("research_pass"),
                "objective_hit": scorecard.get("objective_hit"),
                "objective_progress_pct": scorecard.get("objective_progress_pct"),
                "component_scores": _safe_dict(scorecard.get("component_scores")),
                "delta_vs_same_data_parent": (
                    _safe_float(scorecard.get("total_score"), 0.0)
                    - _safe_float(parent_scorecard.get("total_score"), 0.0)
                    if parent_scorecard else None
                ),
                "parent_score": parent_scorecard.get("total_score") if parent_scorecard else None,
            },
            "metrics": _safe_dict(result.get("metrics")),
            "pass_fail_notes": pass_fail_notes(scorecard, result),
            "next_test_idea": next_test_idea(scorecard, mutation),
            "warnings": _safe_list(scorecard.get("warnings")),
            "fail_reasons": _safe_list(scorecard.get("fail_reasons")),
            "source": str(candidate.get("source") or ""),
        }
        traces.append(trace)

    return {
        "schema_version": "strategy_build_trace_v21_4_3",
        "generated_at": local_now_iso(),
        "generated_at_utc": utc_now_iso(),
        "run_id": str(run.get("run_id") or ""),
        "report_dir": str(report_dir),
        "settings": settings,
        "data_profile": data_profile,
        "top_candidate_id": traces[0]["candidate_id"] if traces else "",
        "trace_count": len(traces),
        "traces": traces,
        "safety": {
            "simulation_only": True,
            "broker_calls": False,
            "live_orders": False,
            "note": "This is a deterministic strategy trace, not hidden AI chain-of-thought.",
        },
    }


def _fmt_bool(value: Any) -> str:
    return "True" if bool(value) else "False"


def render_strategy_trace_markdown(packet: dict[str, Any], top_n: int = 10) -> str:
    lines: list[str] = [
        "# Strategy Build Trace",
        "",
        "This is a deterministic, auditable strategy trace. It is not hidden AI chain-of-thought.",
        "",
        "AI Auto Lab is research/simulation-only. It does not place orders, connect to brokers, or provide personalized financial advice.",
        "",
        "## Run",
        "",
        f"- run_id: `{packet.get('run_id', '')}`",
        f"- generated_at: `{packet.get('generated_at', '')}`",
        f"- trace_count: {packet.get('trace_count', 0)}",
        f"- top_candidate_id: `{packet.get('top_candidate_id', '')}`",
        "",
        "## Data profile",
        "",
    ]

    for key, value in _safe_dict(packet.get("data_profile")).items():
        lines.append(f"- {key}: {value}")

    lines += [
        "",
        "## Top strategy traces",
        "",
    ]

    for trace in _safe_list(packet.get("traces"))[:top_n]:
        score = _safe_dict(trace.get("score"))
        lines += [
            f"### Rank {trace.get('rank')} — {trace.get('candidate_id')}",
            "",
            f"- parent: `{trace.get('parent_id')}`",
            f"- mutation: {trace.get('mutation', {}).get('summary', '')}",
            f"- score: {score.get('total_score')} ({score.get('grade')})",
            f"- parent_score: {score.get('parent_score')}",
            f"- delta_vs_same_data_parent: {score.get('delta_vs_same_data_parent')}",
            f"- engine_pass: {_fmt_bool(score.get('engine_pass'))}",
            f"- research_pass: {_fmt_bool(score.get('research_pass'))}",
            f"- objective_hit: {_fmt_bool(score.get('objective_hit'))}",
            f"- objective_progress_pct: {score.get('objective_progress_pct')}",
            "",
            "#### Parent code",
            "",
            "```text",
            trace.get("parent_code") or "",
            "```",
            "",
            "#### Final tested code",
            "",
            "```text",
            trace.get("final_code") or "",
            "```",
            "",
            "#### Plain-English algorithm",
            "",
        ]
        for idx, step in enumerate(_safe_list(trace.get("algorithm_steps")), start=1):
            lines.append(f"{idx}. {step}")

        lines += [
            "",
            "#### Score breakdown",
            "",
        ]
        component_scores = _safe_dict(score.get("component_scores"))
        if component_scores:
            for key, value in component_scores.items():
                lines.append(f"- {key}: {value}")
        else:
            lines.append("- No component scores available.")

        lines += [
            "",
            "#### Metrics",
            "",
        ]
        metrics = _safe_dict(trace.get("metrics"))
        if metrics:
            for key, value in metrics.items():
                if key == "profit_factor":
                    try:
                        pf = float(value)
                    except Exception:
                        pf = 0.0
                    if pf >= 10:
                        lines.append("- profit_factor: 10.0 (score capped; no_loss_trades)")
                    else:
                        lines.append(f"- {key}: {value}")
                else:
                    lines.append(f"- {key}: {value}")
        else:
            lines.append("- No metrics available.")

        lines += [
            "",
            "#### Why it passed/failed",
            "",
        ]
        for note in _safe_list(trace.get("pass_fail_notes")):
            lines.append(f"- {note}")

        lines += [
            "",
            "#### Next test idea",
            "",
            f"- {trace.get('next_test_idea', '')}",
            "",
        ]

    lines += [
        "## Research-only limitation",
        "",
        "This trace describes simulated/hypothetical strategy tests only. It is not a guarantee of future results and is not live trading advice.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def render_top_strategy_algorithm(packet: dict[str, Any]) -> str:
    traces = _safe_list(packet.get("traces"))
    if not traces:
        return "# Top Strategy Algorithm\n\nNo traces available.\n"

    trace = traces[0]
    score = _safe_dict(trace.get("score"))
    lines = [
        "# Top Strategy Algorithm",
        "",
        "Research/simulation-only. This is a deterministic explanation of the tested strategy, not hidden AI chain-of-thought.",
        "",
        f"## Candidate: `{trace.get('candidate_id')}`",
        "",
        f"- parent: `{trace.get('parent_id')}`",
        f"- mutation: {trace.get('mutation', {}).get('summary', '')}",
        f"- score: {score.get('total_score')} ({score.get('grade')})",
        f"- objective_progress_pct: {score.get('objective_progress_pct')}",
        f"- objective_hit: {_fmt_bool(score.get('objective_hit'))}",
        "",
        "## Strategy code",
        "",
        "```text",
        trace.get("final_code") or "",
        "```",
        "",
        "## Algorithm",
        "",
    ]
    for idx, step in enumerate(_safe_list(trace.get("algorithm_steps")), start=1):
        lines.append(f"{idx}. {step}")

    lines += [
        "",
        "## Why Auto Lab kept or rejected it",
        "",
    ]
    for note in _safe_list(trace.get("pass_fail_notes")):
        lines.append(f"- {note}")

    lines += [
        "",
        "## Next test idea",
        "",
        f"- {trace.get('next_test_idea', '')}",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def write_strategy_build_trace_for_report_dir(report_dir: str | Path) -> dict[str, str]:
    report_dir = Path(report_dir)
    packet = build_strategy_trace_packet(report_dir)

    json_path = report_dir / "strategy_build_trace.json"
    md_path = report_dir / "strategy_build_trace.md"
    top_path = report_dir / "top_strategy_algorithm.md"

    json_path.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    md_path.write_text(render_strategy_trace_markdown(packet), encoding="utf-8")
    top_path.write_text(render_top_strategy_algorithm(packet), encoding="utf-8")

    return {
        "strategy_build_trace_json": str(json_path),
        "strategy_build_trace_md": str(md_path),
        "top_strategy_algorithm_md": str(top_path),
    }
