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
    from services.ai.auto_lab_orchestrator.bars_bootstrapper import bootstrap_bars_csv, output_csv_path

    symbol = "AMD"
    local_path = output_csv_path(live_root, symbol=symbol, timeframe="1d")
    write_sample_csv(local_path, symbol=symbol, days=260)

    boot = bootstrap_bars_csv(
        live_root=live_root,
        symbol=symbol,
        start="",
        end="",
        timeframe="1d",
        prefer_local=True,
        allow_yfinance=False,
    )
    assert Path(boot.csv_path).exists(), "Expected bootstrapped CSV to exist"
    assert boot.row_count > 100, "Expected bootstrapped CSV rows"

    runner = live_root / "services" / "ai" / "auto_lab_orchestrator" / "bootstrap_bars_and_run.py"
    result = subprocess.run(
        [
            sys.executable,
            str(runner),
            "--symbol",
            symbol,
            "--start",
            "2024-01-01",
            "--local-only",
            "--max-total-runs",
            "8",
            "--max-mutations-per-parent",
            "2",
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

    print("AI Auto Lab bootstrap self-test: PASS")
    print(f"CSV path: {boot.csv_path}")
    print(f"Rows: {boot.row_count}")
    print(f"Source: {boot.source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
