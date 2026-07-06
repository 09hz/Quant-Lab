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

    run = SimpleNamespace(
        summary={},
        results=[
            SimpleNamespace(
                candidate_id="example_rsi_mean_reversion_rsi_14_to_9",
                symbol="AMD",
                metrics={
                    "initial_cash": 12000.0,
                    "final_equity": 13171.3614,
                    "total_return_pct": 9.761344999999997,
                    "max_drawdown_pct": 8.542728708626615,
                    "trade_count": 3,
                    "win_rate_pct": 100.0,
                    "profit_factor": 10.0,
                },
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
                fail_reasons=[
                    "Insufficient cash for BUY at index 176: cost $13,402.36, cash $13,171.36",
                    "Insufficient cash for BUY at index 226: cost $13,987.49, cash $13,171.36",
                ],
                warnings=[],
                retest_recommendation="Fix engine/script/data errors before retesting.",
            )
        ],
    )

    summary = normalize_run_execution_quality(run, context="self_test")
    assert summary["normalized_count"] == 1, "Expected one normalized candidate"
    sc = run.scorecards[0]
    assert sc.engine_pass is True, "Expected engine_pass True after normalization"
    assert sc.fail_reasons == [], "Expected fail_reasons moved to warnings"
    assert sc.total_score > 0, "Expected recovered score"

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
