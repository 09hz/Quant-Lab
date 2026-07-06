from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import (
    ExperimentGoal,
    ExperimentRun,
    StrategyCandidate,
    utc_now_iso,
)
from .scorecard import score_strategy_result
from .adapters import ToyBacktestAdapter
from .report_builder import write_run_bundle
from .safety import assert_no_live_broker_modules_loaded, assert_safe_output_path, assert_simulation_only


class AutoLabOrchestrator:
    """
    Coordinates AI Auto Lab experiments.

    The orchestrator does not decide strategy performance by itself. It delegates:
    - engine adapter runs the strategy/backtest
    - deterministic scorecard judges the result
    - report builder records the run
    """

    def __init__(self, adapter: Any | None = None, live_root: Path | None = None, output_root: Path | None = None) -> None:
        self.adapter = adapter or ToyBacktestAdapter()
        self.live_root = live_root or Path(__file__).resolve().parents[3]
        self.output_root = output_root or (self.live_root / "data" / "auto_lab_runs")

    def run_experiment(
        self,
        goal: ExperimentGoal,
        candidates: list[StrategyCandidate],
        bars_by_symbol: dict[str, Any],
        run_id: str | None = None,
    ) -> ExperimentRun:
        assert_simulation_only(goal.simulation_only)
        assert_no_live_broker_modules_loaded()

        if not candidates:
            raise ValueError("No strategy candidates supplied.")

        run_id = run_id or "autolab_" + utc_now_iso().replace(":", "").replace("+", "Z")
        run_dir = self.output_root / run_id
        assert_safe_output_path(run_dir, self.live_root)

        results = []
        scorecards = []

        for candidate in candidates:
            symbols = candidate.symbols or goal.symbols
            for symbol in symbols:
                bars = bars_by_symbol.get(symbol)
                result = self.adapter.run_candidate(candidate=candidate, bars=bars, goal=goal, symbol=symbol)
                scorecard = score_strategy_result(result, goal)
                results.append(result)
                scorecards.append(scorecard)

        best = max(scorecards, key=lambda sc: sc.total_score) if scorecards else None
        passed = [sc for sc in scorecards if sc.passed]
        summary = {
            "candidate_count": len(candidates),
            "result_count": len(results),
            "passed_count": len(passed),
            "best_candidate_id": best.candidate_id if best else "",
            "best_symbol": best.symbol if best else "",
            "best_score": best.total_score if best else 0.0,
            "adapter": getattr(self.adapter, "engine_name", self.adapter.__class__.__name__),
            "simulation_only": goal.simulation_only,
        }

        run = ExperimentRun(
            run_id=run_id,
            created_at=utc_now_iso(),
            goal=goal,
            candidates=candidates,
            results=results,
            scorecards=scorecards,
            summary=summary,
            artifacts={},
        )
        run.artifacts = write_run_bundle(run, run_dir)
        # Rewrite run bundle once so artifacts are included in experiment_run.json.
        write_run_bundle(run, run_dir)
        return run
