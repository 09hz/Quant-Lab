from __future__ import annotations

from pathlib import Path
import json

from .models import ExperimentRun, StrategyCandidate, StrategyScorecard
from .safety import safety_banner


def _candidate_by_id(candidates: list[StrategyCandidate]) -> dict[str, StrategyCandidate]:
    return {candidate.candidate_id: candidate for candidate in candidates}


def _parent_id(candidate: StrategyCandidate | None) -> str:
    if not candidate:
        return ""
    source = candidate.source or ""
    prefix = "mutation_of:"
    if source.startswith(prefix):
        return source[len(prefix):]
    return ""


def _metric_line(key: str, value) -> str:
    if key == "profit_factor":
        try:
            pf_value = float(value)
        except Exception:
            pf_value = 0.0
        if pf_value >= 10.0:
            return "- profit_factor: 10.0 (score capped; no_loss_trades)"
    return f"- {key}: {value}"


def build_mutation_report(
    run: ExperimentRun,
    parents: list[StrategyCandidate],
    parent_scorecards: list[StrategyScorecard],
    settings: dict,
) -> str:
    parent_scores = {sc.candidate_id: sc for sc in parent_scorecards}
    candidate_map = _candidate_by_id(run.candidates)
    sorted_scorecards = sorted(run.scorecards, key=lambda sc: sc.total_score, reverse=True)

    lines: list[str] = [
        "# AI Auto Lab Mutation Retest Report",
        "",
        safety_banner(),
        "",
        "## Run",
        "",
        f"- run_id: `{run.run_id}`",
        f"- created_at: `{run.created_at}`",
        f"- adapter: {run.summary.get('adapter')}",
        f"- mutation_count: {len(run.candidates)}",
        f"- result_count: {len(run.results)}",
        f"- research_pass_count: {sum(1 for sc in run.scorecards if sc.research_pass)}",
        f"- objective_hit_count: {sum(1 for sc in run.scorecards if sc.objective_hit)}",
        "",
        "## Settings",
        "",
    ]

    for key, value in settings.items():
        lines.append(f"- {key}: {value}")

    lines += [
        "",
        "## Parent strategies",
        "",
        "| Parent | Score | Research | Objective | Progress |",
        "|---|---:|---|---|---:|",
    ]
    for parent in parents:
        parent_sc = parent_scores.get(parent.candidate_id)
        if parent_sc:
            lines.append(
                f"| {parent.candidate_id} | {parent_sc.total_score:.2f} | "
                f"{parent_sc.research_pass} | {parent_sc.objective_hit} | "
                f"{parent_sc.objective_progress_pct:.2f}% |"
            )
        else:
            lines.append(f"| {parent.candidate_id} | n/a | n/a | n/a | n/a |")

    lines += [
        "",
        "## Ranked mutation results",
        "",
        "| Rank | Mutation | Parent | Score | Grade | Engine | Research | Objective | Progress | Delta vs parent | Retest recommendation |",
        "|---:|---|---|---:|---|---|---|---|---:|---:|---|",
    ]

    for rank, scorecard in enumerate(sorted_scorecards, start=1):
        candidate = candidate_map.get(scorecard.candidate_id)
        parent = _parent_id(candidate)
        parent_sc = parent_scores.get(parent)
        delta = scorecard.total_score - parent_sc.total_score if parent_sc else 0.0
        lines.append(
            f"| {rank} | {scorecard.candidate_id} | {parent or 'unknown'} | "
            f"{scorecard.total_score:.2f} | {scorecard.grade} | "
            f"{scorecard.engine_pass} | {scorecard.research_pass} | {scorecard.objective_hit} | "
            f"{scorecard.objective_progress_pct:.2f}% | {delta:+.2f} | {scorecard.retest_recommendation} |"
        )

    lines += ["", "## Top detailed mutations", ""]
    result_by_key = {(r.candidate_id, r.symbol): r for r in run.results}
    for scorecard in sorted_scorecards[:10]:
        candidate = candidate_map.get(scorecard.candidate_id)
        parent = _parent_id(candidate)
        parent_sc = parent_scores.get(parent)
        delta = scorecard.total_score - parent_sc.total_score if parent_sc else 0.0
        result = result_by_key.get((scorecard.candidate_id, scorecard.symbol))

        lines.append(f"### {scorecard.candidate_id}")
        lines.append("")
        lines.append(f"- parent: {parent or 'unknown'}")
        lines.append(f"- score: {scorecard.total_score:.2f}")
        lines.append(f"- delta_vs_parent: {delta:+.2f}")
        lines.append(f"- engine_pass: {scorecard.engine_pass}")
        lines.append(f"- research_pass: {scorecard.research_pass}")
        lines.append(f"- objective_hit: {scorecard.objective_hit}")
        lines.append(f"- objective_progress_pct: {scorecard.objective_progress_pct:.2f}")
        lines.append(f"- retest_recommendation: {scorecard.retest_recommendation}")
        if candidate:
            lines.append("")
            lines.append("Script:")
            lines.append("```text")
            lines.append(candidate.script or "")
            lines.append("```")
        if result:
            lines.append("")
            lines.append("Metrics:")
            for key, value in result.metrics.items():
                lines.append(_metric_line(key, value))
        if scorecard.fail_reasons:
            lines.append("")
            lines.append("Fail reasons:")
            for reason in scorecard.fail_reasons:
                lines.append(f"- {reason}")
        if scorecard.warnings:
            lines.append("")
            lines.append("Warnings:")
            for warning in scorecard.warnings[:5]:
                lines.append(f"- {warning}")
        lines.append("")

    lines += [
        "## Research-only limitation",
        "",
        "This mutation report is simulated/hypothetical research only. "
        "It is not a guarantee of future results and is not live trading advice.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_experiment_memory(
    run: ExperimentRun,
    parents: list[StrategyCandidate],
    parent_scorecards: list[StrategyScorecard],
    settings: dict,
) -> dict:
    sorted_scorecards = sorted(run.scorecards, key=lambda sc: sc.total_score, reverse=True)
    parent_scores = {sc.candidate_id: sc.to_dict() for sc in parent_scorecards}

    return {
        "schema_version": "auto_lab_mutation_memory_v21_3",
        "run_id": run.run_id,
        "created_at": run.created_at,
        "settings": settings,
        "goal": run.goal.to_dict(),
        "parents": [parent.to_dict() for parent in parents],
        "parent_scorecards": parent_scores,
        "summary": run.summary,
        "best_mutation": sorted_scorecards[0].to_dict() if sorted_scorecards else {},
        "top_mutations": [sc.to_dict() for sc in sorted_scorecards[:10]],
        "research_pass_mutations": [sc.to_dict() for sc in sorted_scorecards if sc.research_pass],
        "objective_hit_mutations": [sc.to_dict() for sc in sorted_scorecards if sc.objective_hit],
        "artifacts": run.artifacts,
        "safety": {
            "simulation_only": True,
            "broker_calls": False,
            "live_orders": False,
        },
    }


def write_mutation_artifacts(
    run: ExperimentRun,
    parents: list[StrategyCandidate],
    parent_scorecards: list[StrategyScorecard],
    settings: dict,
) -> dict[str, str]:
    report_path = Path(run.artifacts.get("report_md", "")).parent / "mutation_report.md"
    memory_path = report_path.parent / "experiment_memory.json"
    mutation_results_path = report_path.parent / "mutation_results.json"

    report_text = build_mutation_report(run, parents, parent_scorecards, settings)
    memory = build_experiment_memory(run, parents, parent_scorecards, settings)

    report_path.write_text(report_text, encoding="utf-8")
    memory_path.write_text(json.dumps(memory, indent=2), encoding="utf-8")
    mutation_results_path.write_text(
        json.dumps(
            {
                "run": run.to_dict(),
                "parents": [p.to_dict() for p in parents],
                "parent_scorecards": [p.to_dict() for p in parent_scorecards],
                "settings": settings,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    run.artifacts["mutation_report_md"] = str(report_path)
    run.artifacts["experiment_memory_json"] = str(memory_path)
    run.artifacts["mutation_results_json"] = str(mutation_results_path)

    return {
        "mutation_report_md": str(report_path),
        "experiment_memory_json": str(memory_path),
        "mutation_results_json": str(mutation_results_path),
    }
