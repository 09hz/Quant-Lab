from __future__ import annotations

from pathlib import Path
import json

from .models import ResearchLoopResult


def _repo_root_from_result(result: ResearchLoopResult) -> Path:
    if result.config.repo_root:
        return Path(result.config.repo_root).resolve()
    return Path.cwd().resolve().parent if Path.cwd().name.lower() == "live" else Path.cwd().resolve()


def build_feedback_markdown(result: ResearchLoopResult) -> str:
    lines: list[str] = []
    lines.append(f"# Research Loop Feedback — {result.loop_id}")
    lines.append("")
    lines.append("Research/simulation only. No broker calls or live orders.")
    lines.append("")
    lines.append("## Role in the system")
    lines.append("")
    lines.append("Research Loop is the research manager. Auto Lab is an experiment worker. The loop decides what to test, evaluates outcomes, stores results, and writes lessons for the next iteration.")
    lines.append("")
    lines.append(f"- Theme: `{result.config.theme}`")
    lines.append(f"- Symbols: `{', '.join(result.config.normalized_symbols())}`")
    lines.append(f"- Status: `{result.status}`")
    lines.append(f"- Candidates tested: `{len(result.evaluations)}`")
    lines.append(f"- Survivors: `{len(result.survivors)}`")
    lines.append(f"- Quant persist: `{result.quant_persist_status}`")
    lines.append("")

    lines.append("## Top candidates")
    lines.append("")
    ranked = sorted(result.evaluations, key=lambda item: item.score, reverse=True)
    for item in ranked[:5]:
        c = item.candidate
        m = item.aggregate_metrics
        u = item.universe_metrics
        w = item.walk_forward_metrics
        lines.append(
            f"- **{c.strategy_name}** `{item.status}` score `{item.score}` "
            f"avg_sharpe `{m.get('avg_sharpe')}` drawdown `{m.get('worst_drawdown')}` "
            f"trades `{m.get('total_trades')}` universe_pass `{u.get('pass_rate')}` "
            f"wf_sharpe `{w.get('avg_sharpe')}`"
        )
        if item.rejection_reasons:
            lines.append(f"  - Rejection reasons: {', '.join(item.rejection_reasons)}")
        lines.append(f"  - Parameters: `{json.dumps(item.candidate.parameters, sort_keys=True)}`")
    lines.append("")

    lines.append("## Lessons for next loop")
    lines.append("")
    if result.survivors:
        for item in result.survivors[:5]:
            lines.append(
                f"- Strengthen hypothesis: `{item.candidate.strategy_family}` showed proxy robustness "
                f"with universe pass rate `{item.universe_metrics.get('pass_rate')}` and score `{item.score}`."
            )
    else:
        lines.append("- No survivors. Improve candidate diversity or relax proxy gates only if justified by real backtest results.")

    rejected = [item for item in ranked if item.status != "PASS"]
    common_reasons: dict[str, int] = {}
    for item in rejected:
        for reason in item.rejection_reasons:
            common_reasons[reason] = common_reasons.get(reason, 0) + 1
    for reason, count in sorted(common_reasons.items(), key=lambda kv: kv[1], reverse=True)[:5]:
        lines.append(f"- Avoid/rework candidates that trigger `{reason}`; seen `{count}` times this loop.")

    lines.append("")
    lines.append("## Next recommended action")
    lines.append("")
    if result.survivors:
        lines.append("- Run real BackTestEngine adapter for the top survivor candidates, then walk-forward validation.")
    else:
        lines.append("- Generate a wider candidate set or adjust theme/symbol universe, then rerun the loop.")
    lines.append("")
    lines.append("## Guardrail")
    lines.append("")
    lines.append("- Do not treat proxy scores as trade signals. Use them only to prioritize further research.")
    return "\n".join(lines).rstrip() + "\n"


def write_memory_feedback(result: ResearchLoopResult) -> str:
    repo = _repo_root_from_result(result)
    out_dir = repo / "Live" / "data" / "research_loop" / "memory_feedback"
    out_dir.mkdir(parents=True, exist_ok=True)

    md_path = out_dir / f"{result.loop_id}_feedback.md"
    json_path = out_dir / f"{result.loop_id}_feedback.json"

    md_path.write_text(build_feedback_markdown(result), encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "loop_id": result.loop_id,
                "theme": result.config.theme,
                "symbols": result.config.normalized_symbols(),
                "survivor_count": len(result.survivors),
                "quant_persist_status": result.quant_persist_status,
                "top_scores": [
                    {
                        "strategy_name": item.candidate.strategy_name,
                        "strategy_family": item.candidate.strategy_family,
                        "score": item.score,
                        "status": item.status,
                        "avg_sharpe": item.aggregate_metrics.get("avg_sharpe"),
                        "worst_drawdown": item.aggregate_metrics.get("worst_drawdown"),
                        "universe_pass_rate": item.universe_metrics.get("pass_rate"),
                        "walk_forward_sharpe": item.walk_forward_metrics.get("avg_sharpe"),
                        "rejection_reasons": item.rejection_reasons,
                    }
                    for item in sorted(result.evaluations, key=lambda ev: ev.score, reverse=True)[:10]
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return str(md_path)
