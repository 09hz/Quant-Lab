from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .models import ExperimentRun
from .safety import safety_banner


def _local_timestamp(value: str) -> str:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone().isoformat()
    except (TypeError, ValueError):
        return str(value)


def build_markdown_report(run: ExperimentRun) -> str:
    sorted_scorecards = sorted(run.scorecards, key=lambda sc: sc.total_score, reverse=True)

    lines: list[str] = [
        "# AI Auto Lab Experiment Report",
        "",
        safety_banner(),
        "",
        "## Run",
        "",
        f"- run_id: `{run.run_id}`",
        f"- created_at: `{_local_timestamp(run.created_at)}`",
        f"- created_at_utc: `{run.created_at}`",
        f"- question: {run.goal.question}",
        f"- symbols: {', '.join(run.goal.symbols)}",
        f"- timeframe: {run.goal.timeframe}",
        f"- starting_cash: {run.goal.starting_cash}",
        f"- target_equity: {run.goal.target_equity}",
        f"- target_return_pct: {run.goal.target_return_pct():.4f}",
        f"- max_drawdown_pct: {run.goal.max_drawdown_pct}",
        "",
        "## Summary",
        "",
    ]

    for key, value in run.summary.items():
        lines.append(f"- {key}: {value}")
    lines.append("")

    lines += [
        "## Status labels",
        "",
        "- engine_pass: the engine produced a usable simulated result.",
        "- research_pass: deterministic score/drawdown/trade-count gates suggest the candidate is worth more research.",
        "- objective_hit: the candidate reached the target equity/return objective.",
        "- objective_progress_pct: percent of target return achieved.",
        "",
        "## Ranked Strategy Scorecards",
        "",
        "| Rank | Candidate | Symbol | Score | Grade | Engine | Research | Objective | Progress | Retest recommendation |",
        "|---:|---|---|---:|---|---|---|---|---:|---|",
    ]

    for rank, scorecard in enumerate(sorted_scorecards, start=1):
        lines.append(
            f"| {rank} | {scorecard.candidate_id} | {scorecard.symbol} | "
            f"{scorecard.total_score:.2f} | {scorecard.grade} | "
            f"{scorecard.engine_pass} | {scorecard.research_pass} | {scorecard.objective_hit} | "
            f"{scorecard.objective_progress_pct:.2f}% | {scorecard.retest_recommendation} |"
        )

    lines += ["", "## Detailed Results", ""]

    result_by_key = {(r.candidate_id, r.symbol): r for r in run.results}
    for scorecard in sorted_scorecards:
        result = result_by_key.get((scorecard.candidate_id, scorecard.symbol))
        lines.append(f"### {scorecard.candidate_id} — {scorecard.symbol}")
        lines.append("")
        lines.append(scorecard.interpretation)
        lines.append("")
        lines.append(f"- engine_pass: {scorecard.engine_pass}")
        lines.append(f"- research_pass: {scorecard.research_pass}")
        lines.append(f"- objective_hit: {scorecard.objective_hit}")
        lines.append(f"- objective_progress_pct: {scorecard.objective_progress_pct:.2f}")
        lines.append(f"- retest_recommendation: {scorecard.retest_recommendation}")
        lines.append("")
        lines.append("Component scores:")
        for key, value in scorecard.component_scores.items():
            lines.append(f"- {key}: {value}")
        if scorecard.fail_reasons:
            lines.append("")
            lines.append("Fail reasons:")
            for reason in scorecard.fail_reasons:
                lines.append(f"- {reason}")
        if scorecard.warnings:
            lines.append("")
            lines.append("Warnings:")
            for warning in scorecard.warnings:
                lines.append(f"- {warning}")
        if result:
            lines.append("")
            lines.append(f"Engine: {result.engine}")
            lines.append("Metrics:")
            for key, value in result.metrics.items():
                if key == "profit_factor":
                    try:
                        pf_value = float(value)
                    except Exception:
                        pf_value = 0.0
                    if pf_value >= 10.0:
                        lines.append("- profit_factor: 10.0 (score capped; no_loss_trades)")
                    else:
                        lines.append(f"- {key}: {value}")
                else:
                    lines.append(f"- {key}: {value}")
            if result.errors:
                lines.append("")
                lines.append("Engine/result errors:")
                for error in result.errors:
                    lines.append(f"- {error}")
        lines.append("")

    lines += [
        "## Research-only limitation",
        "",
        "This report is based on simulated/hypothetical testing only. "
        "It is not a guarantee of future results and is not live trading advice.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def write_run_bundle(run: ExperimentRun, output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_json = output_dir / "experiment_run.json"
    results_json = output_dir / "results.json"
    scorecards_json = output_dir / "scorecards.json"
    report_md = output_dir / "report.md"

    artifacts = {
        "run_json": str(run_json),
        "results_json": str(results_json),
        "scorecards_json": str(scorecards_json),
        "report_md": str(report_md),
    }
    run.artifacts = artifacts

    run_json.write_text(json.dumps(run.to_dict(), indent=2), encoding="utf-8")
    results_json.write_text(json.dumps([r.to_dict() for r in run.results], indent=2), encoding="utf-8")
    scorecards_json.write_text(json.dumps([s.to_dict() for s in run.scorecards], indent=2), encoding="utf-8")
    report_md.write_text(build_markdown_report(run), encoding="utf-8")

    return artifacts
