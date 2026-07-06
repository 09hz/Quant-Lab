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
    from services.ai.auto_lab_orchestrator.sizing import SizingConfig, compute_simulation_quantity

    qty = compute_simulation_quantity(
        initial_cash=12000,
        reference_price=100,
        candidate_parameters={"quantity": 10},
        config=SizingConfig(sizing_mode="percent_cash_exposure", cash_exposure_pct=95),
    )
    assert qty == 114, f"Expected 114 simulated shares, got {qty}"

    symbol = "AMD"
    csv_path = output_csv_path(live_root, symbol=symbol, timeframe="1d")
    write_sample_csv(csv_path, symbol=symbol, days=260)

    runner = live_root / "services" / "ai" / "auto_lab_orchestrator" / "csv_mutation_retest_sized.py"
    result = subprocess.run(
        [
            sys.executable,
            str(runner),
            "--symbol",
            symbol,
            "--csv-path",
            str(csv_path),
            "--start",
            "2024-01-01",
            "--run-id",
            "__force_csv_baseline__",
            "--sizing-mode",
            "percent_cash_exposure",
            "--cash-exposure-pct",
            "95",
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

    print("AI Auto Lab sizing self-test: PASS")
    print(f"CSV path: {csv_path}")
    print(f"Example computed quantity at $100 reference: {qty}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
