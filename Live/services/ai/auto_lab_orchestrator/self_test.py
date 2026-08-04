from __future__ import annotations

from pathlib import Path
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

    from services.ai.auto_lab_orchestrator.models import ExperimentGoal
    from services.ai.auto_lab_orchestrator.orchestrator import AutoLabOrchestrator, build_run_id
    from services.ai.auto_lab_orchestrator.sample_data import make_sample_bars
    from services.ai.auto_lab_orchestrator.templates import starter_strategy_candidates
    from services.ai.auto_lab_orchestrator.adapters import ToyBacktestAdapter

    symbol = "AMD"
    goal = ExperimentGoal(
        question=(
            "Self-test: find simulation-only candidate strategies for a $12k account. "
            "Target is aggressive growth, but this is synthetic data only."
        ),
        symbols=[symbol],
        timeframe="1d",
        starting_cash=12000.0,
        target_equity=24000.0,
        max_drawdown_pct=30.0,
        min_trades=1,
        max_runs=3,
        simulation_only=True,
    )
    bars = make_sample_bars(symbol=symbol, days=180)
    candidates = starter_strategy_candidates(symbol=symbol)[:3]
    assert build_run_id() != build_run_id(), "Concurrent run IDs must be unique within the same second"

    orchestrator = AutoLabOrchestrator(adapter=ToyBacktestAdapter(), live_root=live_root)
    run = orchestrator.run_experiment(goal=goal, candidates=candidates, bars_by_symbol={symbol: bars})

    assert run.results, "Expected results"
    assert len(run.results) == len(candidates), "Expected one result per candidate"
    assert run.scorecards, "Expected scorecards"
    assert run.artifacts.get("report_md"), "Expected report artifact"
    assert Path(run.artifacts["report_md"]).exists(), "Report file does not exist"

    for sc in run.scorecards:
        assert sc.engine_pass is True, "Toy self-test should have engine_pass True"
        assert isinstance(sc.research_pass, bool), "research_pass should be bool"
        assert sc.objective_hit is False, "Toy self-test should not hit 2x target"
        assert sc.objective_progress_pct >= 0, "Expected objective progress"

    best = max(run.scorecards, key=lambda sc: sc.total_score)
    print("AI Auto Lab Orchestrator self-test: PASS")
    print(f"Run ID: {run.run_id}")
    print(f"Adapter: {run.summary.get('adapter')}")
    print(f"Candidates: {len(candidates)}")
    print(f"Results: {len(run.results)}")
    print(f"Best: {best.candidate_id} score={best.total_score:.2f} grade={best.grade}")
    print(f"Best statuses: engine_pass={best.engine_pass} research_pass={best.research_pass} objective_hit={best.objective_hit} objective_progress_pct={best.objective_progress_pct:.2f}")
    print(f"Report: {run.artifacts['report_md']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
