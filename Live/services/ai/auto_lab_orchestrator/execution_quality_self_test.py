from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
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

    from services.ai.auto_lab_orchestrator.execution_quality import normalize_run_execution_quality, write_execution_quality_report
    from services.ai.auto_lab_orchestrator.models import ExperimentGoal

    insufficient_cash_error = (
        "Insufficient cash for BUY at index 176: cost $20,402.36, cash $20,000.00"
    )

    run = SimpleNamespace(
        goal=ExperimentGoal(
            symbols=["AMD"],
            starting_cash=12000.0,
            target_equity=18000.0,
            max_drawdown_pct=30.0,
            min_trades=3,
        ),
        summary={},
        results=[
            SimpleNamespace(
                candidate_id="example_rsi_mean_reversion_rsi_14_to_9",
                symbol="AMD",
                status="error",
                engine="core_strategy_backtest_adapter",
                metrics={
                    "initial_cash": 12000.0,
                    "final_equity": 20000.0,
                    "total_return_pct": 66.6667,
                    "max_drawdown_pct": 35.0,
                    "trade_count": 10,
                    "win_rate_pct": 100.0,
                    "profit_factor": 10.0,
                },
                trades=[],
                equity_curve=[],
                errors=[insufficient_cash_error],
                warnings=[],
                raw_summary={},
            )
        ],
        scorecards=[
            SimpleNamespace(
                candidate_id="example_rsi_mean_reversion_rsi_14_to_9",
                symbol="AMD",
                total_score=0.0,
                grade="F",
                passed=False,
                engine_pass=False,
                research_pass=False,
                objective_hit=False,
                objective_progress_pct=0.0,
                component_scores={},
                fail_reasons=[insufficient_cash_error],
                warnings=[],
                retest_recommendation="Fix engine/script/data errors before retesting.",
            )
        ],
    )

    summary = normalize_run_execution_quality(run, context="self_test")
    assert summary["normalized_count"] == 1, "Expected one normalized candidate"
    sc = run.scorecards[0]
    assert sc.engine_pass is True, "Expected engine_pass True after normalization"
    assert sc.research_pass is False, "Drawdown gate must remain authoritative"
    assert sc.passed is False, "Compatibility pass flag must follow research_pass"
    assert sc.objective_hit is True, "Configured target_equity must determine objective success"
    assert any("drawdown" in reason.lower() for reason in sc.fail_reasons), "Expected drawdown failure to be preserved"
    assert any("insufficient" in warning.lower() for warning in sc.warnings), "Expected insufficient cash warning"
    assert run.results[0].status == "ok", "Recovered result status should match engine_pass"
    assert run.results[0].errors == [], "Recovered insufficient-cash errors should move to warnings"
    assert run.summary["passed_count"] == 0, "Run summary pass count must follow corrected scorecards"
    assert run.summary["best_candidate_id"] == sc.candidate_id, "Run summary best candidate must be refreshed"
    assert run.summary["best_score"] == sc.total_score, "Run summary best score must be refreshed"

    out_dir = live_root / "data" / "auto_lab_runs" / "_execution_quality_self_test"
    artifacts = write_execution_quality_report(run, out_dir, summary)
    for path in artifacts.values():
        assert Path(path).exists(), f"Missing artifact: {path}"

    print("AI Auto Lab execution quality self-test: PASS")
    print(f"normalized_count: {summary['normalized_count']}")
    print(f"recovered_score: {sc.total_score}")
    for key, value in artifacts.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
