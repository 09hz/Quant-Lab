from __future__ import annotations

from pathlib import Path
import subprocess
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

    from services.ai.auto_lab_orchestrator.data_adapters import write_sample_csv
    from services.ai.auto_lab_orchestrator.bars_bootstrapper import output_csv_path
    from services.ai.auto_lab_orchestrator.universe_reporter import build_universe_payload

    aggregation = build_universe_payload(
        universe_run_id="aggregation_self_test",
        symbols=["AMD", "NVDA"],
        settings={},
        symbol_results=[
            {
                "symbol": "AMD",
                "ranked_mutations": [
                    {
                        "candidate_id": "trend_fast",
                        "strategy_family": "trend",
                        "score": 90.0,
                        "research_pass": True,
                        "objective_hit": False,
                        "objective_progress_pct": 80.0,
                    },
                    {
                        "candidate_id": "trend_slow",
                        "strategy_family": "trend",
                        "score": 70.0,
                        "research_pass": False,
                        "objective_hit": True,
                        "objective_progress_pct": 100.0,
                    },
                ],
            },
            {
                "symbol": "NVDA",
                "ranked_mutations": [
                    {
                        "candidate_id": "trend_nvda",
                        "strategy_family": "trend",
                        "score": 60.0,
                        "research_pass": False,
                        "objective_hit": False,
                        "objective_progress_pct": 50.0,
                    }
                ],
            },
        ],
    )
    robustness = aggregation["strategy_robustness"][0]
    assert robustness["symbols_tested"] == 2, "Mutations must not inflate unique symbol coverage"
    assert robustness["symbols"] == ["AMD", "NVDA"], "Robustness symbols must be unique"
    assert robustness["symbols_research_pass"] == 1, "Research pass count must be symbol-level"
    assert robustness["symbols_objective_hit"] == 1, "Objective count must be symbol-level"
    assert robustness["avg_score"] == 75.0, "Average score must use each symbol's best family result"
    assert robustness["avg_objective_progress_pct"] == 75.0, "Progress must not overweight repeated mutations"

    for symbol in ["AMD", "NVDA"]:
        write_sample_csv(output_csv_path(live_root, symbol=symbol, timeframe="1d"), symbol=symbol, days=260)

    runner = live_root / "services" / "ai" / "auto_lab_orchestrator" / "universe_runner.py"
    result = subprocess.run(
        [
            sys.executable,
            str(runner),
            "--symbols",
            "AMD,NVDA",
            "--start",
            "2024-01-01",
            "--local-only",
            "--max-total-runs-per-symbol",
            "6",
            "--max-mutations-per-parent",
            "2",
            "--continue-on-error",
            "--no-cache",
        ],
        cwd=str(live_root.parent),
        text=True,
        capture_output=True,
    )

    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip())
    if result.returncode != 0:
        return result.returncode

    runs_dir = live_root / "data" / "auto_lab_universe_runs"
    latest = sorted([p for p in runs_dir.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)[0]
    required = [
        "universe_results.json",
        "universe_report.md",
        "symbol_leaderboard.md",
        "strategy_robustness_report.md",
        "top_universe_strategy_algorithm.md",
    ]
    for name in required:
        path = latest / name
        assert path.exists(), f"Missing {path}"

    print("AI Auto Lab universe self-test: PASS")
    print(f"latest_universe_run_dir: {latest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
