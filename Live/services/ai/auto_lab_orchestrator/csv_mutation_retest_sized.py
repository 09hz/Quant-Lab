from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys


def _bootstrap_import_path() -> Path:
    here = Path(__file__).resolve()
    live_root = here.parents[3]
    repo_root = here.parents[4]
    for path in (str(live_root), str(repo_root)):
        if path not in sys.path:
            sys.path.insert(0, path)
    return live_root


def _candidate_from_dict(data: dict):
    from services.ai.auto_lab_orchestrator.models import StrategyCandidate

    return StrategyCandidate(
        candidate_id=str(data.get("candidate_id") or ""),
        name=str(data.get("name") or data.get("candidate_id") or "candidate"),
        family=str(data.get("family") or "unknown"),
        script=str(data.get("script") or ""),
        parameters=dict(data.get("parameters") or {}),
        symbols=list(data.get("symbols") or []),
        tags=list(data.get("tags") or []),
        source=str(data.get("source") or ""),
        notes=str(data.get("notes") or ""),
    )


def _scorecard_from_dict(data: dict):
    from services.ai.auto_lab_orchestrator.models import StrategyScorecard

    return StrategyScorecard(
        candidate_id=str(data.get("candidate_id") or ""),
        symbol=str(data.get("symbol") or ""),
        total_score=float(data.get("total_score") or 0.0),
        grade=str(data.get("grade") or "F"),
        passed=bool(data.get("passed") or data.get("research_pass") or False),
        engine_pass=bool(data.get("engine_pass") or False),
        research_pass=bool(data.get("research_pass") or False),
        objective_hit=bool(data.get("objective_hit") or False),
        objective_progress_pct=float(data.get("objective_progress_pct") or 0.0),
        component_scores=dict(data.get("component_scores") or {}),
        fail_reasons=list(data.get("fail_reasons") or []),
        warnings=list(data.get("warnings") or []),
        interpretation=str(data.get("interpretation") or ""),
        retest_recommendation=str(data.get("retest_recommendation") or ""),
    )


def _is_parent_payload(payload: dict) -> bool:
    summary = payload.get("summary") or {}
    adapter = str(summary.get("adapter") or "")
    if "core_strategy_backtest_adapter" not in adapter:
        return False
    scorecards = payload.get("scorecards") or []
    return any(bool(sc.get("engine_pass")) and bool(sc.get("research_pass")) for sc in scorecards if isinstance(sc, dict))


def _is_mutation_payload(payload: dict) -> bool:
    goal = str(((payload.get("goal") or {}).get("question")) or "").lower()
    artifacts = payload.get("artifacts") or {}
    return "mutation" in goal or "mutation_report_md" in artifacts or "mutation_results_json" in artifacts


def find_parent_run(live_root: Path, run_id: str = "", allow_chained_mutations: bool = False) -> tuple[Path | None, dict]:
    runs_dir = live_root / "data" / "auto_lab_runs"
    if not runs_dir.exists():
        return None, {}

    if run_id and run_id != "__force_csv_baseline__":
        candidates = [runs_dir / run_id]
    else:
        candidates = sorted([p for p in runs_dir.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)

    for run_dir in candidates:
        payload_path = run_dir / "experiment_run.json"
        if not payload_path.exists():
            continue
        try:
            payload = json.loads(payload_path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if not _is_parent_payload(payload):
            continue
        if not allow_chained_mutations and _is_mutation_payload(payload):
            continue
        return run_dir, payload

    return None, {}


def select_parent_candidates_from_payload(payload: dict, symbol: str, max_parent_strategies: int = 999):
    candidates_raw = payload.get("candidates") or []
    scorecards_raw = payload.get("scorecards") or []
    candidates = [_candidate_from_dict(item) for item in candidates_raw if isinstance(item, dict)]
    scorecards = [_scorecard_from_dict(item) for item in scorecards_raw if isinstance(item, dict)]
    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}

    eligible = [
        sc for sc in sorted(scorecards, key=lambda item: item.total_score, reverse=True)
        if sc.engine_pass and sc.research_pass and (not symbol or sc.symbol.upper() == symbol.upper())
    ][:max_parent_strategies]

    parents = []
    for scorecard in eligible:
        candidate = candidate_by_id.get(scorecard.candidate_id)
        if candidate:
            if not candidate.symbols:
                candidate.symbols = [symbol]
            parents.append(candidate)

    return parents, eligible


def discover_seed_parents(live_root: Path, symbol: str, max_examples: int):
    from services.ai.auto_lab_orchestrator.seed_library import discover_strategy_seed_candidates
    return discover_strategy_seed_candidates(
        live_root=live_root,
        symbol=symbol,
        max_examples=max_examples,
        include_built_ins=True,
    )


def write_same_data_baseline_artifacts(baseline_run, report_dir: Path, sizing_info: dict, data_profile: dict) -> dict[str, str]:
    report_path = report_dir / "same_data_baseline_report.md"
    json_path = report_dir / "same_data_baseline.json"

    sorted_scores = sorted(baseline_run.scorecards, key=lambda item: item.total_score, reverse=True)
    lines = [
        "# Same-Data CSV Parent Baseline",
        "",
        "Research/simulation-only. This baseline uses the same CSV bars and sizing settings as the mutation run.",
        "",
        "## Data",
        "",
    ]
    for key, value in data_profile.items():
        lines.append(f"- {key}: {value}")
    lines += ["", "## Sizing", ""]
    for key, value in sizing_info.items():
        lines.append(f"- {key}: {value}")
    lines += [
        "",
        "## Ranked same-data parent scores",
        "",
        "| Rank | Parent | Score | Grade | Engine | Research | Objective | Progress |",
        "|---:|---|---:|---|---|---|---|---:|",
    ]
    for rank, sc in enumerate(sorted_scores, start=1):
        lines.append(
            f"| {rank} | {sc.candidate_id} | {sc.total_score:.2f} | {sc.grade} | "
            f"{sc.engine_pass} | {sc.research_pass} | {sc.objective_hit} | {sc.objective_progress_pct:.2f}% |"
        )
    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    payload = {
        "baseline_run": baseline_run.to_dict(),
        "sizing_info": sizing_info,
        "data_profile": data_profile,
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {
        "same_data_baseline_report_md": str(report_path),
        "same_data_baseline_json": str(json_path),
    }


def main() -> int:
    live_root = _bootstrap_import_path()

    parser = argparse.ArgumentParser(description="Run CSV mutation/retest with same-data baseline and simulation sizing.")
    parser.add_argument("--symbol", default="AMD")
    parser.add_argument("--csv-path", default="")
    parser.add_argument("--bars-dir", default="")
    parser.add_argument("--start", default="")
    parser.add_argument("--end", default="")
    parser.add_argument("--run-id", default="", help="Optional parent run id, or __force_csv_baseline__.")
    parser.add_argument("--allow-chained-mutations", action="store_true")
    parser.add_argument("--max-parent-strategies", type=int, default=999)
    parser.add_argument("--max-mutations-per-parent", type=int, default=4)
    parser.add_argument("--max-total-runs", type=int, default=20)
    parser.add_argument("--max-examples", type=int, default=8)
    parser.add_argument("--mutate-quantity", action="store_true", help="Secondary to sizing mode.")
    parser.add_argument("--sizing-mode", default="percent_cash_exposure", choices=["fixed_quantity", "max_affordable_shares", "percent_cash_exposure"])
    parser.add_argument("--cash-exposure-pct", type=float, default=95.0)
    parser.add_argument("--fixed-quantity", type=int, default=10)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    from services.ai.auto_lab_orchestrator.models import ExperimentGoal
    from services.ai.auto_lab_orchestrator.orchestrator import AutoLabOrchestrator
    from services.ai.auto_lab_orchestrator.adapters import CoreStrategyBacktestAdapter
    from services.ai.auto_lab_orchestrator.data_adapters import load_csv_bars
    from services.ai.auto_lab_orchestrator.mutator import generate_mutations_for_parents
    from services.ai.auto_lab_orchestrator.mutation_reporter import write_mutation_artifacts
    from services.ai.auto_lab_orchestrator.real_data_reporter import write_real_data_report
    from services.ai.auto_lab_orchestrator.report_builder import write_run_bundle
    from services.ai.auto_lab_orchestrator.sizing import SizingConfig, apply_simulation_sizing
    from services.ai.auto_lab_orchestrator.execution_quality import normalize_run_execution_quality, write_execution_quality_report
    from services.ai.auto_lab_orchestrator.strategy_trace import write_strategy_build_trace_for_report_dir

    symbol = args.symbol.upper().strip() or "AMD"
    initial_cash = 12000.0

    bars, profile = load_csv_bars(
        csv_path=args.csv_path or None,
        bars_dir=args.bars_dir or None,
        symbol=symbol,
        start=args.start,
        end=args.end,
    )
    data_profile = profile.to_dict()

    parent_run_dir, parent_payload = find_parent_run(
        live_root,
        run_id=args.run_id,
        allow_chained_mutations=args.allow_chained_mutations,
    )

    if parent_payload:
        parents, _old_parent_scorecards = select_parent_candidates_from_payload(
            parent_payload,
            symbol=symbol,
            max_parent_strategies=args.max_parent_strategies,
        )
    else:
        print("No eligible parent run found; discovering seed candidates for same-data CSV baseline.")
        parents = discover_seed_parents(live_root, symbol=symbol, max_examples=args.max_examples)
        parent_run_dir = None

    if not parents:
        print("No parent candidates available.")
        return 2 if args.strict else 0

    sizing_config = SizingConfig(
        sizing_mode=args.sizing_mode,
        cash_exposure_pct=args.cash_exposure_pct,
        fixed_quantity=args.fixed_quantity,
        simulation_only=True,
    )
    sized_parents, sizing_info = apply_simulation_sizing(
        parents,
        bars=bars,
        initial_cash=initial_cash,
        config=sizing_config,
    )

    baseline_goal = ExperimentGoal(
        question="v21.4.2 same-data CSV baseline for parent strategies before mutation.",
        symbols=[symbol],
        timeframe="1d",
        starting_cash=initial_cash,
        target_equity=24000.0,
        max_drawdown_pct=30.0,
        min_trades=1,
        max_runs=len(sized_parents),
        simulation_only=True,
        notes="CSV historical bars; same-data baseline; simulation sizing only.",
    )

    orchestrator = AutoLabOrchestrator(adapter=CoreStrategyBacktestAdapter(), live_root=live_root)
    baseline_run = orchestrator.run_experiment(
        goal=baseline_goal,
        candidates=sized_parents,
        bars_by_symbol={symbol: bars},
    )
    baseline_run.summary["data_mode"] = "csv_historical_bars"
    baseline_run.summary["same_data_baseline"] = True
    baseline_run.summary["sizing"] = sizing_info
    baseline_run.summary["data_profile"] = data_profile
    baseline_quality_summary = normalize_run_execution_quality(baseline_run, context="same_data_baseline")
    write_run_bundle(baseline_run, Path(baseline_run.artifacts["report_md"]).parent)

    baseline_scorecards = list(baseline_run.scorecards)
    baseline_research_pass = {sc.candidate_id for sc in baseline_scorecards if sc.engine_pass and sc.research_pass}
    eligible_sized_parents = [candidate for candidate in sized_parents if candidate.candidate_id in baseline_research_pass]
    eligible_baseline_scorecards = [sc for sc in baseline_scorecards if sc.candidate_id in baseline_research_pass]

    if not eligible_sized_parents:
        print("Same-data baseline produced no engine_pass=True/research_pass=True parents.")
        if args.strict:
            return 3
        eligible_sized_parents = sized_parents
        eligible_baseline_scorecards = baseline_scorecards

    mutations = generate_mutations_for_parents(
        parents=eligible_sized_parents,
        max_mutations_per_parent=args.max_mutations_per_parent,
        max_total=args.max_total_runs,
        mutate_quantity=args.mutate_quantity,
    )
    if not mutations:
        print("No mutations generated from eligible parents.")
        return 4 if args.strict else 0

    sized_mutations, mutation_sizing_info = apply_simulation_sizing(
        mutations,
        bars=bars,
        initial_cash=initial_cash,
        config=sizing_config,
    )

    mutation_goal = ExperimentGoal(
        question=(
            "v21.4.2 CSV mutation retest with same-data parent baseline "
            "and simulation sizing modes."
        ),
        symbols=[symbol],
        timeframe="1d",
        starting_cash=initial_cash,
        target_equity=24000.0,
        max_drawdown_pct=30.0,
        min_trades=1,
        max_runs=len(sized_mutations),
        simulation_only=True,
        notes="CSV historical bars; mutation retest; same-data baseline; simulation sizing only.",
    )

    run = orchestrator.run_experiment(
        goal=mutation_goal,
        candidates=sized_mutations,
        bars_by_symbol={symbol: bars},
    )
    run.summary["data_mode"] = "csv_historical_bars"
    run.summary["synthetic_vs_real_data"] = "csv_historical_bars"
    run.summary["same_data_baseline"] = True
    run.summary["sizing"] = mutation_sizing_info
    run.summary["data_profile"] = data_profile
    mutation_quality_summary = normalize_run_execution_quality(run, context="mutation_run")
    write_run_bundle(run, Path(run.artifacts["report_md"]).parent)

    settings = {
        "parent_run_dir": str(parent_run_dir) if parent_run_dir else "",
        "same_data_baseline_run_id": baseline_run.run_id,
        "symbol": symbol,
        "csv_path": args.csv_path,
        "bars_dir": args.bars_dir,
        "start": args.start,
        "end": args.end,
        "max_parent_strategies": args.max_parent_strategies,
        "max_muts_per_parent": args.max_mutations_per_parent,
        "max_total_runs": args.max_total_runs,
        "mutate_quantity": args.mutate_quantity,
        "sizing_mode": args.sizing_mode,
        "cash_exposure_pct": args.cash_exposure_pct,
        "fixed_quantity": args.fixed_quantity,
        "data_mode": "csv_historical_bars",
        "same_data_delta": True,
        "simulation_only": True,
    }

    mutation_artifacts = write_mutation_artifacts(
        run=run,
        parents=eligible_sized_parents,
        parent_scorecards=eligible_baseline_scorecards,
        settings=settings,
    )
    run.artifacts.update(mutation_artifacts)

    real_data_artifacts = write_real_data_report(run=run, data_profile=data_profile, settings=settings)
    run.artifacts.update(real_data_artifacts)

    baseline_artifacts = write_same_data_baseline_artifacts(
        baseline_run=baseline_run,
        report_dir=Path(run.artifacts["report_md"]).parent,
        sizing_info=sizing_info,
        data_profile=data_profile,
    )
    run.artifacts.update(baseline_artifacts)

    trace_artifacts = write_strategy_build_trace_for_report_dir(Path(run.artifacts["report_md"]).parent)
    run.artifacts.update(trace_artifacts)

    execution_quality_artifacts = write_execution_quality_report(
        run=run,
        report_dir=Path(run.artifacts["report_md"]).parent,
        normalization_summary={
            "baseline": baseline_quality_summary,
            "mutation": mutation_quality_summary,
        },
    )
    run.artifacts.update(execution_quality_artifacts)

    # Rewrite final bundle so artifact links persist.
    write_run_bundle(run, Path(run.artifacts["report_md"]).parent)

    research_pass_count = sum(1 for sc in run.scorecards if sc.research_pass)
    objective_hit_count = sum(1 for sc in run.scorecards if sc.objective_hit)
    best = max(run.scorecards, key=lambda sc: sc.total_score) if run.scorecards else None

    print("AI Auto Lab CSV sized mutation retest complete.")
    print(f"Data rows: {data_profile.get('row_count')}")
    print(f"Data first_date: {data_profile.get('first_date')}")
    print(f"Data last_date: {data_profile.get('last_date')}")
    print(f"Parent run: {parent_run_dir}")
    print(f"Same-data baseline run: {baseline_run.run_id}")
    print(f"Parents selected: {len(parents)}")
    print(f"Same-data research-pass parents: {len(eligible_sized_parents)}")
    print(f"Mutations generated: {len(sized_mutations)}")
    print(f"Mutation results: {len(run.results)}")
    print(f"Research pass mutations: {research_pass_count}")
    print(f"Objective hit mutations: {objective_hit_count}")
    print(f"Sizing mode: {args.sizing_mode}")
    print(f"Cash exposure pct: {args.cash_exposure_pct}")
    print(f"Reference price: {mutation_sizing_info.get('reference_price')}")
    print(f"Example quantity: {mutation_sizing_info.get('example_quantity')}")
    if best:
        print(
            f"Best mutation: {best.candidate_id} score={best.total_score:.2f} "
            f"research_pass={best.research_pass} objective_hit={best.objective_hit} "
            f"progress={best.objective_progress_pct:.2f}%"
        )
    print(f"Run report: {run.artifacts.get('report_md')}")
    print(f"Mutation report: {mutation_artifacts.get('mutation_report_md')}")
    print(f"Real data report: {real_data_artifacts.get('real_data_report_md')}")
    print(f"Same-data baseline report: {baseline_artifacts.get('same_data_baseline_report_md')}")
    print(f"Strategy build trace: {trace_artifacts.get('strategy_build_trace_md')}")
    print(f"Top strategy algorithm: {trace_artifacts.get('top_strategy_algorithm_md')}")
    print(f"Execution quality report: {execution_quality_artifacts.get('execution_quality_report_md')}")
    print(f"Experiment memory: {mutation_artifacts.get('experiment_memory_json')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
