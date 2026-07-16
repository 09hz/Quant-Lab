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

    from services.ai.auto_lab_orchestrator.data_adapters import write_sample_csv, load_csv_bars

    symbol = "AMD"
    csv_path = live_root / "data" / "auto_lab_runs" / "_csv_self_test_input" / f"{symbol}.csv"
    write_sample_csv(csv_path, symbol=symbol, days=260)

    bars, profile = load_csv_bars(csv_path=csv_path, symbol=symbol, start="", end="")
    assert profile.row_count > 100, "Expected more than 100 sample CSV rows"
    assert profile.data_mode == "csv_historical_bars", "Expected CSV data mode"

    runner = live_root / "services" / "ai" / "auto_lab_orchestrator" / "csv_mutation_retest.py"
    result = subprocess.run(
        [
            sys.executable,
            str(runner),
            "--symbol",
            symbol,
            "--csv-path",
            str(csv_path),
            "--max-total-runs",
            "12",
            "--max-mutations-per-parent",
            "3",
            "--strict",
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

    print("AI Auto Lab CSV data self-test: PASS")
    print(f"CSV path: {csv_path}")
    print(f"Rows: {profile.row_count}")
    print(f"First date: {profile.first_date}")
    print(f"Last date: {profile.last_date}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
