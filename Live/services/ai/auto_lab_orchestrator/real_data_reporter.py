from __future__ import annotations

from pathlib import Path
import json

from .models import ExperimentRun
from .safety import safety_banner


def build_real_data_report(run: ExperimentRun, data_profile: dict, settings: dict) -> str:
    sorted_scorecards = sorted(run.scorecards, key=lambda sc: sc.total_score, reverse=True)

    lines: list[str] = [
        "# AI Auto Lab Real Data CSV Report",
        "",
        safety_banner(),
        "",
        "## Data profile",
        "",
    ]

    for key, value in data_profile.items():
        lines.append(f"- {key}: {value}")

    lines += [
        "",
        "## Run settings",
        "",
    ]
    for key, value in settings.items():
        lines.append(f"- {key}: {value}")

    lines += [
        "",
        "## Summary",
        "",
        f"- run_id: `{run.run_id}`",
        f"- adapter: {run.summary.get('adapter')}",
        f"- data_mode: {run.summary.get('data_mode')}",
        f"- candidate_count: {run.summary.get('candidate_count')}",
        f"- result_count: {run.summary.get('result_count')}",
        f"- research_pass_count: {sum(1 for sc in run.scorecards if sc.research_pass)}",
        f"- objective_hit_count: {sum(1 for sc in run.scorecards if sc.objective_hit)}",
        "",
        "## Ranked CSV mutation results",
        "",
        "| Rank | Candidate | Score | Grade | Research | Objective | Progress | Return/Progress note |",
        "|---:|---|---:|---|---|---|---:|---|",
    ]

    result_by_key = {(r.candidate_id, r.symbol): r for r in run.results}
    for rank, sc in enumerate(sorted_scorecards, start=1):
        result = result_by_key.get((sc.candidate_id, sc.symbol))
        ret = result.metrics.get("total_return_pct") if result else ""
        lines.append(
            f"| {rank} | {sc.candidate_id} | {sc.total_score:.2f} | {sc.grade} | "
            f"{sc.research_pass} | {sc.objective_hit} | {sc.objective_progress_pct:.2f}% | "
            f"return_pct={ret} |"
        )

    lines += [
        "",
        "## Top candidate details",
        "",
    ]

    candidate_map = {c.candidate_id: c for c in run.candidates}
    for sc in sorted_scorecards[:10]:
        candidate = candidate_map.get(sc.candidate_id)
        result = result_by_key.get((sc.candidate_id, sc.symbol))
        lines.append(f"### {sc.candidate_id}")
        lines.append("")
        lines.append(f"- score: {sc.total_score:.2f}")
        lines.append(f"- research_pass: {sc.research_pass}")
        lines.append(f"- objective_hit: {sc.objective_hit}")
        lines.append(f"- objective_progress_pct: {sc.objective_progress_pct:.2f}")
        lines.append(f"- recommendation: {sc.retest_recommendation}")
        if candidate:
            lines.append(f"- source: {candidate.source}")
            lines.append("")
            lines.append("Script:")
            lines.append("```text")
            lines.append(candidate.script or "")
            lines.append("```")
        if result:
            lines.append("")
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
        if sc.warnings:
            lines.append("")
            lines.append("Warnings:")
            for warning in sc.warnings[:5]:
                lines.append(f"- {warning}")
        if sc.fail_reasons:
            lines.append("")
            lines.append("Fail reasons:")
            for reason in sc.fail_reasons:
                lines.append(f"- {reason}")
        lines.append("")

    lines += [
        "## Research-only limitation",
        "",
        "This report uses CSV historical bars and simulated strategy tests only. "
        "It is not a guarantee of future results and is not live trading advice.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def write_real_data_report(run: ExperimentRun, data_profile: dict, settings: dict) -> dict[str, str]:
    report_dir = Path(run.artifacts.get("report_md", "")).parent
    report_path = report_dir / "real_data_report.md"
    profile_path = report_dir / "data_profile.json"

    report_path.write_text(build_real_data_report(run, data_profile, settings), encoding="utf-8")
    profile_path.write_text(json.dumps({"data_profile": data_profile, "settings": settings}, indent=2), encoding="utf-8")

    run.artifacts["real_data_report_md"] = str(report_path)
    run.artifacts["data_profile_json"] = str(profile_path)

    return {
        "real_data_report_md": str(report_path),
        "data_profile_json": str(profile_path),
    }
