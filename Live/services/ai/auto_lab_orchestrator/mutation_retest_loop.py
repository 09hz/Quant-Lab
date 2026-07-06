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


def _is_core_run(payload: dict) -> bool:
    summary = payload.get("summary") or {}
    adapter = str(summary.get("adapter") or "")
    question = str(((payload.get("goal") or {}).get("question")) or "")
    return "core_strategy_backtest_adapter" in adapter or "Core smoke" in question or "core smoke" in question


def find_latest_core_run(live_root: Path, explicit_run_id: str = "") -> tuple[Path | None, dict]:
    runs_dir = live_root / "data" / "auto_lab_runs"
    if not runs_dir.exists():
        return None, {}

    candidates = []
    if explicit_run_id:
        candidates = [runs_dir / explicit_run_id]
    else:
        candidates = sorted([p for p in runs_dir.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)

    for run_dir in candidates:
        path = run_dir / "experiment_run.json"
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if _is_core_run(payload):
            return run_dir, payload
    return None, {}


def select_parent_candidates_from_run(payload: dict, symbol: str, max_parent_strategies: int = 999):
    candidates_raw = payload.get("candidates") or []
    scorecards_raw = payload.get("scorecards") or []

    candidates = [_candidate_from_dict(item) for item in candidates_raw if isinstance(item, dict)]
    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    scorecards = [_scorecard_from_dict(item) for item in scorecards_raw if isinstance(item, dict)]

    eligible_scorecards = [
        sc for sc in sorted(scorecards, key=lambda item: item.total_score, reverse=True)
        if sc.engine_pass and sc.research_pass and (not symbol or sc.symbol.upper() == symbol.upper())
    ][:max_parent_strategies]

    parents = []
    for scorecard in eligible_scorecards:
        candidate = candidate_by_id.get(scorecard.candidate_id)
        if not candidate:
            continue
        if not candidate.symbols:
            candidate.symbols = [symbol]
        parents.append(candidate)

    return parents, eligible_scorecards


def run_baseline_if_needed(live_root: Path, symbol: str, days: int, max_examples: int):
    from services.ai.auto_lab_orchestrator.models import ExperimentGoal
    from services.ai.auto_lab_orchestrator.orchestrator import AutoLabOrchestrator
    from services.ai.auto_lab_orchestrator.sample_data import make_sample_bars_dataframe
    from services.ai.auto_lab_orchestrator.seed_library import discover_strategy_seed_candidates
    from services.ai.auto_lab_orchestrator.adapters import CoreStrategyBacktestAdapter

    bars = make_sample_bars_dataframe(symbol=symbol, days=days)
    seeds = discover_strategy_seed_candidates(live_root=live_root, symbol=symbol, max_examples=max_examples, include_built_ins=True)
    goal = ExperimentGoal(
        question="Baseline run for v21.3 mutation parent discovery.",
        symbols=[symbol],
        timeframe="1d",
        starting_cash=12000.0,
        target_equity=24000.0,
        max_drawdown_pct=30.0,
        min_trades=1,
        max_runs=len(seeds),
        simulation_only=True,
        notes="Synthetic bars; baseline only.",
    )
    orchestrator = AutoLabOrchestrator(adapter=CoreStrategyBacktestAdapter(), live_root=live_root)
    return orchestrator.run_experiment(goal=goal, candidates=seeds, bars_by_symbol={symbol: bars})


def main() -> int:
    live_root = _bootstrap_import_path()

    parser = argparse.ArgumentParser(description="Run first Auto Lab mutation/retest loop.")
    parser.add_argument("--symbol", default="AMD")
    parser.add_argument("--days", type=int, default=220)
    parser.add_argument("--run-id", default="", help="Optional parent run id from Live/data/auto_lab_runs.")
    parser.add_argument("--max-parent-strategies", type=int, default=999)
    parser.add_argument("--max-mutations-per-parent", type=int, default=4)
    parser.add_argument("--max-total-runs", type=int, default=20)
    parser.add_argument("--max-examples", type=int, default=8)
    parser.add_argument("--mutate-quantity", action="store_true", help="Disabled by default in v21.3.")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    from services.ai.auto_lab_orchestrator.models import ExperimentGoal
    from services.ai.auto_lab_orchestrator.orchestrator import AutoLabOrchestrator
    from services.ai.auto_lab_orchestrator.sample_data import make_sample_bars_dataframe
    from services.ai.auto_lab_orchestrator.adapters import CoreStrategyBacktestAdapter
    from services.ai.auto_lab_orchestrator.mutator import generate_mutations_for_parents
    from services.ai.auto_lab_orchestrator.mutation_reporter import write_mutation_artifacts

    symbol = args.symbol.upper().strip() or "AMD"

    parent_run_dir, parent_payload = find_latest_core_run(live_root, explicit_run_id=args.run_id)
    if not parent_payload:
        print("No latest core run found. Running a baseline seed smoke first.")
        baseline_run = run_baseline_if_needed(live_root=live_root, symbol=symbol, days=args.days, max_examples=args.max_examples)
        parent_payload = baseline_run.to_dict()
        parent_run_dir = Path(baseline_run.artifacts.get("report_md", "")).parent

    parents, parent_scorecards = select_parent_candidates_from_run(
        parent_payload,
        symbol=symbol,
        max_parent_strategies=args.max_parent_strategies,
    )

    if not parents:
        print("No eligible parent candidates found with engine_pass=True and research_pass=True.")
        if args.strict:
            return 2
        return 0

    mutations = generate_mutations_for_parents(
        parents=parents,
        max_mutations_per_parent=args.max_mutations_per_parent,
        max_total=args.max_total_runs,
        mutate_quantity=args.mutate_quantity,
    )

    if not mutations:
        print("No mutations generated from eligible parents.")
        if args.strict:
            return 3
        return 0

    bars = make_sample_bars_dataframe(symbol=symbol, days=args.days)
    goal = ExperimentGoal(
        question=(
            "v21.3 mutation retest loop: mutate all research-pass parent strategies "
            "from the latest core-engine smoke run and retest on synthetic bars."
        ),
        symbols=[symbol],
        timeframe="1d",
        starting_cash=12000.0,
        target_equity=24000.0,
        max_drawdown_pct=30.0,
        min_trades=1,
        max_runs=len(mutations),
        simulation_only=True,
        notes="Synthetic bars; first mutation loop; quantity fixed unless explicitly enabled.",
    )

    orchestrator = AutoLabOrchestrator(adapter=CoreStrategyBacktestAdapter(), live_root=live_root)
    run = orchestrator.run_experiment(goal=goal, candidates=mutations, bars_by_symbol={symbol: bars})

    settings = {
        "parent_run_dir": str(parent_run_dir) if parent_run_dir else "",
        "symbol": symbol,
        "days": args.days,
        "max_parent_strategies": args.max_parent_strategies,
        "max_mutations_per_parent": args.max_mutations_per_parent,
        "max_total_runs": args.max_total_runs,
        "mutate_quantity": args.mutate_quantity,
        "data_mode": "synthetic_bars",
        "simulation_only": True,
    }
    mutation_artifacts = write_mutation_artifacts(
        run=run,
        parents=parents,
        parent_scorecards=parent_scorecards,
        settings=settings,
    )
    run.artifacts.update(mutation_artifacts)

    research_pass_count = sum(1 for sc in run.scorecards if sc.research_pass)
    objective_hit_count = sum(1 for sc in run.scorecards if sc.objective_hit)
    best = max(run.scorecards, key=lambda sc: sc.total_score) if run.scorecards else None

    print("AI Auto Lab mutation retest loop complete.")
    print(f"Parent run: {parent_run_dir}")
    print(f"Parents selected: {len(parents)}")
    print(f"Mutations generated: {len(mutations)}")
    print(f"Mutation results: {len(run.results)}")
    print(f"Research pass mutations: {research_pass_count}")
    print(f"Objective hit mutations: {objective_hit_count}")
    if best:
        print(
            f"Best mutation: {best.candidate_id} score={best.total_score:.2f} "
            f"research_pass={best.research_pass} objective_hit={best.objective_hit} "
            f"progress={best.objective_progress_pct:.2f}%"
        )
    print(f"Run report: {run.artifacts.get('report_md')}")
    print(f"Mutation report: {mutation_artifacts.get('mutation_report_md')}")
    print(f"Experiment memory: {mutation_artifacts.get('experiment_memory_json')}")

    if args.strict and not run.results:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
