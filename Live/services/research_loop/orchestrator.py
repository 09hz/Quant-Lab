from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .memory_feedback import write_memory_feedback
from .models import ResearchLoopConfig, ResearchLoopResult, make_id, utc_now_iso
from .scoring import score_candidate
from .strategy_candidate_generator import generate_strategy_candidates


def _repo_root(start: str | Path | None = None) -> Path:
    if start:
        return Path(start).resolve()
    p = Path.cwd().resolve()
    for c in [p, *p.parents]:
        if (c / "Live" / "app.py").exists():
            return c
        if c.name.lower() == "live" and (c / "app.py").exists():
            return c.parent
    return p.parent if p.name.lower() == "live" else p


def _slug(text: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in text)
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_")[:64] or "research_loop"


def _write_reports(repo: Path, result_payload: dict[str, Any], loop_id: str, theme: str) -> dict[str, str]:
    date_part = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = repo / "Live" / "data" / "research_loop" / "reports" / date_part
    out_dir.mkdir(parents=True, exist_ok=True)

    base = f"{loop_id}_{_slug(theme)}"
    json_path = out_dir / f"{base}.json"
    md_path = out_dir / f"{base}.md"

    json_path.write_text(json.dumps(result_payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_build_report_markdown(result_payload), encoding="utf-8")

    # Best-effort registration with Artifact Writer. This should never break the loop.
    try:
        from services.artifacts.artifact_writer import register_existing_file
        try:
            register_existing_file(path=json_path, repo_root=str(repo), module="research_loop", artifact_type="loop_report")
            register_existing_file(path=md_path, repo_root=str(repo), module="research_loop", artifact_type="loop_report")
        except TypeError:
            register_existing_file(str(json_path))
            register_existing_file(str(md_path))
    except Exception:
        pass

    return {"json": str(json_path), "markdown": str(md_path)}


def _build_report_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# Research Loop Report — {payload.get('loop_id')}")
    lines.append("")
    lines.append("Research/simulation only. No broker calls or live orders.")
    lines.append("")
    config = payload.get("config", {})
    lines.append(f"- Theme: `{config.get('theme')}`")
    lines.append(f"- Symbols: `{', '.join(config.get('symbols', []))}`")
    lines.append(f"- Backend: `{config.get('backend')}`")
    lines.append(f"- Status: `{payload.get('status')}`")
    lines.append(f"- Quant persist: `{payload.get('quant_persist_status')}`")
    lines.append("")

    evaluations = payload.get("evaluations", [])
    lines.append("## Candidate rankings")
    lines.append("")
    lines.append("| Rank | Strategy | Family | Status | Score | Avg Sharpe | Drawdown | Trades | Reasons |")
    lines.append("| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- |")
    ranked = sorted(evaluations, key=lambda item: item.get("score", 0), reverse=True)
    for idx, item in enumerate(ranked, 1):
        candidate = item.get("candidate", {})
        metrics = item.get("aggregate_metrics", {})
        reasons = ", ".join(item.get("rejection_reasons", []))
        lines.append(
            f"| {idx} | {candidate.get('strategy_name')} | {candidate.get('strategy_family')} | "
            f"{item.get('status')} | {item.get('score')} | {metrics.get('avg_sharpe')} | "
            f"{metrics.get('worst_drawdown')} | {metrics.get('total_trades')} | {reasons} |"
        )
    lines.append("")
    lines.append("## Survivors")
    lines.append("")
    survivors = payload.get("survivors", [])
    if not survivors:
        lines.append("No candidates passed the current simulated research gates.")
    else:
        for item in survivors:
            candidate = item.get("candidate", {})
            lines.append(f"- {candidate.get('strategy_name')} score `{item.get('score')}`")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _db_imports():
    from services.database.config import load_database_config
    try:
        from services.database.backend import connect_database
    except Exception:
        from services.database.connections import connect_database  # type: ignore
    from services.quant_schema.migrations import migrate_quant_schema
    from services.quant_schema import repository
    return load_database_config, connect_database, migrate_quant_schema, repository


def _persist_to_quant_schema(repo: Path, result: ResearchLoopResult) -> str:
    try:
        load_database_config, connect_database, migrate_quant_schema, repository = _db_imports()
        config = load_database_config(repo_root=str(repo), backend=result.config.backend)
        artifact_id = result.report_paths.get("json", result.loop_id)

        with connect_database(config) as db:
            migrate_quant_schema(db)

            exp_id = repository.insert_experiment_run(
                db,
                experiment_id=result.loop_id,
                module="research_loop",
                experiment_name=f"Research Loop: {result.config.theme}",
                status=result.status,
                config=result.config.to_dict(),
                artifact_id=artifact_id,
                commit=False,
            )

            for evaluation in result.evaluations:
                candidate = evaluation.candidate
                primary_symbol = (candidate.symbols or result.config.normalized_symbols() or ["MULTI"])[0]
                strategy_run_id = f"strat_{candidate.candidate_id}"

                try:
                    repository.insert_strategy_run(
                        db,
                        strategy_run_id=strategy_run_id,
                        experiment_id=exp_id,
                        artifact_id=artifact_id,
                        strategy_name=candidate.strategy_name,
                        strategy_family=candidate.strategy_family,
                        symbol=primary_symbol,
                        timeframe=candidate.timeframe,
                        parameters=candidate.parameters,
                        status=evaluation.status,
                        commit=False,
                    )
                except Exception:
                    pass

                for symbol_result in evaluation.symbol_results:
                    try:
                        repository.insert_backtest_run(
                            db,
                            backtest_run_id=f"bt_{candidate.candidate_id}_{symbol_result.symbol}",
                            strategy_run_id=strategy_run_id,
                            experiment_id=exp_id,
                            artifact_id=artifact_id,
                            symbol=symbol_result.symbol,
                            strategy_name=candidate.strategy_name,
                            timeframe=candidate.timeframe,
                            sharpe=symbol_result.sharpe,
                            max_drawdown=symbol_result.max_drawdown,
                            win_rate=symbol_result.win_rate,
                            total_return=symbol_result.total_return,
                            trade_count=symbol_result.trade_count,
                            status=evaluation.status,
                            metrics={
                                "profit_factor": symbol_result.profit_factor,
                                "data_quality": symbol_result.data_quality,
                                "warnings": symbol_result.warnings,
                                "candidate_score": evaluation.score,
                                "simulation_only": True,
                            },
                            commit=False,
                        )
                    except Exception:
                        pass

                try:
                    repository.insert_walk_forward_run(
                        db,
                        walk_forward_run_id=f"wf_{candidate.candidate_id}",
                        experiment_id=exp_id,
                        artifact_id=artifact_id,
                        symbol=primary_symbol,
                        strategy_name=candidate.strategy_name,
                        timeframe=candidate.timeframe,
                        window_count=int(evaluation.walk_forward_metrics.get("window_count", 3)),
                        avg_sharpe=float(evaluation.walk_forward_metrics.get("avg_sharpe", 0.0)),
                        pass_rate=float(evaluation.walk_forward_metrics.get("pass_rate", 0.0)),
                        status=evaluation.status,
                        metrics={
                            **evaluation.walk_forward_metrics,
                            "stability_score": evaluation.walk_forward_metrics.get("stability_score"),
                            "simulation_only": True,
                        },
                        commit=False,
                    )
                except Exception:
                    pass

            try:
                ranking = [
                    {
                        "strategy_name": ev.candidate.strategy_name,
                        "strategy_family": ev.candidate.strategy_family,
                        "score": ev.score,
                        "status": ev.status,
                    }
                    for ev in sorted(result.evaluations, key=lambda item: item.score, reverse=True)
                ]
                repository.insert_universe_run(
                    db,
                    universe_run_id=f"uni_{result.loop_id}",
                    experiment_id=exp_id,
                    artifact_id=artifact_id,
                    universe_name=f"Research Loop Universe: {result.config.theme}",
                    theme=result.config.theme,
                    symbols=result.config.normalized_symbols(),
                    selected_count=len(result.survivors),
                    ranking=ranking,
                    status=result.status,
                    commit=False,
                )
            except Exception:
                pass

            for evaluation in result.evaluations:
                if evaluation.warnings or evaluation.rejection_reasons:
                    try:
                        repository.insert_data_quality_event(
                            db,
                            event_id=f"dq_{evaluation.candidate.candidate_id}",
                            artifact_id=artifact_id,
                            symbol=",".join(evaluation.candidate.symbols),
                            dataset_name="research_loop_proxy",
                            severity="warn" if evaluation.status == "PASS" else "info",
                            event_type="research_loop_filter",
                            message="; ".join((evaluation.rejection_reasons or evaluation.warnings)[:5]),
                            details={
                                "warnings": evaluation.warnings,
                                "rejection_reasons": evaluation.rejection_reasons,
                                "simulation_only": True,
                            },
                            commit=False,
                        )
                    except Exception:
                        pass

            if hasattr(db, "commit"):
                db.commit()
            elif hasattr(db, "conn"):
                db.conn.commit()

        return "PASS"
    except Exception as exc:
        return f"WARN: quant schema persist skipped: {type(exc).__name__}: {exc}"


def run_research_loop(config: ResearchLoopConfig) -> ResearchLoopResult:
    started_at = utc_now_iso()
    repo = _repo_root(config.repo_root)
    config.repo_root = str(repo)

    loop_id = make_id("research_loop")
    errors: list[str] = []

    candidates = generate_strategy_candidates(config)
    evaluations = [score_candidate(config, candidate) for candidate in candidates]
    survivors = [
        item for item in sorted(evaluations, key=lambda ev: ev.score, reverse=True)
        if item.status == "PASS"
    ]

    status = "PASS" if survivors else "WARN"

    # Create a temporary result to generate initial payload/report paths.
    temp_result = ResearchLoopResult(
        loop_id=loop_id,
        config=config,
        candidates=candidates,
        evaluations=evaluations,
        survivors=survivors,
        report_paths={},
        quant_persist_status="PENDING",
        feedback_path="",
        started_at=started_at,
        finished_at=utc_now_iso(),
        status=status,
        errors=errors,
    )

    report_paths = _write_reports(repo, temp_result.to_dict(), loop_id, config.theme)
    temp_result.report_paths = report_paths
    quant_status = _persist_to_quant_schema(repo, temp_result)
    temp_result.quant_persist_status = quant_status
    feedback_path = write_memory_feedback(temp_result)
    temp_result.feedback_path = feedback_path
    temp_result.finished_at = utc_now_iso()

    # Rewrite final report with quant/feedback paths included.
    report_paths = _write_reports(repo, temp_result.to_dict(), loop_id, config.theme)
    temp_result.report_paths = report_paths

    return temp_result


def _parse_symbols(value: str) -> list[str]:
    return [part.strip().upper() for part in str(value or "").split(",") if part.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run simulation-only strategy/backtest research loop.")
    parser.add_argument("--repo-root", type=str, default=None)
    parser.add_argument("--theme", type=str, default="AI infrastructure semiconductors")
    parser.add_argument("--symbols", type=str, default="AMD,NVDA,SMH")
    parser.add_argument("--max-candidates", type=int, default=10)
    parser.add_argument("--max-loops", type=int, default=1)
    parser.add_argument("--min-trades", type=int, default=10)
    parser.add_argument("--max-drawdown-limit", type=float, default=-0.20)
    parser.add_argument("--min-sharpe", type=float, default=0.25)
    parser.add_argument("--backend", choices=["sqlite", "postgres"], default="sqlite")
    parser.add_argument("--timeframe", type=str, default="1d")
    args = parser.parse_args()

    config = ResearchLoopConfig(
        theme=args.theme,
        symbols=_parse_symbols(args.symbols),
        max_candidates=args.max_candidates,
        max_loops=args.max_loops,
        min_trades=args.min_trades,
        max_drawdown_limit=args.max_drawdown_limit,
        min_sharpe=args.min_sharpe,
        backend=args.backend,
        timeframe=args.timeframe,
        repo_root=args.repo_root,
    )
    result = run_research_loop(config)

    summary = {
        "status": result.status,
        "loop_id": result.loop_id,
        "theme": result.config.theme,
        "symbols": result.config.normalized_symbols(),
        "candidates": len(result.candidates),
        "survivors": len(result.survivors),
        "quant_persist_status": result.quant_persist_status,
        "report_paths": result.report_paths,
        "feedback_path": result.feedback_path,
        "top_candidates": [
            {
                "strategy_name": item.candidate.strategy_name,
                "family": item.candidate.strategy_family,
                "score": item.score,
                "status": item.status,
            }
            for item in sorted(result.evaluations, key=lambda ev: ev.score, reverse=True)[:5]
        ],
        "safety": "simulation_only_no_broker_no_orders",
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if result.status in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
