from __future__ import annotations

from pathlib import Path
import argparse
import sys


def _bootstrap_import_path() -> Path:
    here = Path(__file__).resolve()
    live_root = here.parents[3]
    repo_root = here.parents[4]
    for path in (str(live_root), str(repo_root)):
        if path not in sys.path:
            sys.path.insert(0, path)
    return live_root


def main() -> int:
    live_root = _bootstrap_import_path()

    parser = argparse.ArgumentParser(description="Smoke-test existing StrategyEngine + BackTestEngine through Auto Lab adapter.")
    parser.add_argument("--symbol", default="AMD")
    parser.add_argument("--days", type=int, default=220)
    parser.add_argument("--max-examples", type=int, default=8)
    parser.add_argument("--strict", action="store_true", help="Exit nonzero if no core engine candidate passes.")
    args = parser.parse_args()

    from services.ai.auto_lab_orchestrator.models import ExperimentGoal
    from services.ai.auto_lab_orchestrator.orchestrator import AutoLabOrchestrator
    from services.ai.auto_lab_orchestrator.sample_data import make_sample_bars_dataframe
    from services.ai.auto_lab_orchestrator.seed_library import discover_strategy_seed_candidates
    from services.ai.auto_lab_orchestrator.adapters import CoreStrategyBacktestAdapter

    symbol = args.symbol.upper().strip() or "AMD"
    bars = make_sample_bars_dataframe(symbol=symbol, days=args.days)

    candidates = discover_strategy_seed_candidates(
        live_root=live_root,
        symbol=symbol,
        max_examples=args.max_examples,
        include_built_ins=True,
    )

    goal = ExperimentGoal(
        question=(
            "Core smoke test v21.2: run cleaned strategy seeds through the existing "
            "StrategyEngine and BackTestEngine on synthetic bars."
        ),
        symbols=[symbol],
        timeframe="1d",
        starting_cash=12000.0,
        target_equity=24000.0,
        max_drawdown_pct=30.0,
        min_trades=1,
        max_runs=len(candidates),
        simulation_only=True,
        notes="Synthetic bars; real core engine path; no broker/live trading.",
    )

    orchestrator = AutoLabOrchestrator(adapter=CoreStrategyBacktestAdapter(), live_root=live_root)
    run = orchestrator.run_experiment(goal=goal, candidates=candidates, bars_by_symbol={symbol: bars})

    engine_pass_count = sum(1 for sc in run.scorecards if sc.engine_pass)
    research_pass_count = sum(1 for sc in run.scorecards if sc.research_pass)
    objective_hit_count = sum(1 for sc in run.scorecards if sc.objective_hit)

    print("AI Auto Lab Core Engine smoke test complete.")
    print(f"Run ID: {run.run_id}")
    print(f"Candidates attempted: {len(candidates)}")
    print(f"engine_pass_count: {engine_pass_count}")
    print(f"research_pass_count: {research_pass_count}")
    print(f"objective_hit_count: {objective_hit_count}")
    print(f"Report: {run.artifacts.get('report_md', '')}")

    if candidates:
        print("Candidates:")
        for candidate in candidates[:20]:
            print(f"- {candidate.candidate_id} source={candidate.source}")

    if run.scorecards:
        print("Top scorecards:")
        for sc in sorted(run.scorecards, key=lambda item: item.total_score, reverse=True)[:8]:
            print(
                f"- {sc.candidate_id}: score={sc.total_score:.2f} "
                f"engine_pass={sc.engine_pass} research_pass={sc.research_pass} "
                f"objective_hit={sc.objective_hit} progress={sc.objective_progress_pct:.2f}%"
            )
            if sc.fail_reasons:
                print(f"  fail: {' | '.join(sc.fail_reasons[:3])}")
            if sc.warnings:
                print(f"  warn: {' | '.join(sc.warnings[:3])}")

    if args.strict and engine_pass_count <= 0:
        print("STRICT CORE SMOKE FAILED: no candidates produced usable core-engine results.")
        return 2

    if engine_pass_count <= 0:
        print("CORE SMOKE DIAGNOSTIC: no candidates passed engine. This is non-blocking unless --strict is used.")
        print("Next likely fix: adapt built-in seeds to the current Strategy Lab grammar.")
    else:
        print("CORE SMOKE PASS: at least one candidate produced a usable core-engine result.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
