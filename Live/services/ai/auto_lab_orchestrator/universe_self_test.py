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
