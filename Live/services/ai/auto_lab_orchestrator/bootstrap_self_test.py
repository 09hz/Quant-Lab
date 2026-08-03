from __future__ import annotations

from pathlib import Path
import argparse
import subprocess
import sys
import pandas as pd


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

    parser = argparse.ArgumentParser(description="Test Auto Lab historical-bar bootstrapping.")
    parser.add_argument("--data-only", action="store_true", help="Run coverage, quality, and provider checks only.")
    args = parser.parse_args()

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
    assert boot.coverage_ok is True, "Expected unrestricted local coverage to pass"
    assert boot.data_quality_ok is True, "Expected deterministic sample quality to pass"
    assert boot.data_hash, "Expected content hash provenance"

    covered = bootstrap_bars_csv(
        live_root=live_root,
        symbol=symbol,
        start=boot.first_date,
        end=boot.last_date,
        timeframe="1d",
        prefer_local=True,
        allow_yfinance=False,
    )
    assert covered.coverage_ok is True, "Expected requested local range to be covered"

    try:
        bootstrap_bars_csv(
            live_root=live_root,
            symbol=symbol,
            start=boot.first_date,
            end="2099-12-31",
            timeframe="1d",
            prefer_local=True,
            allow_yfinance=False,
        )
        raise AssertionError("Expected incomplete local-only coverage to fail")
    except ValueError as exc:
        assert "coverage" in str(exc).lower()

    class FakeProvider:
        name = "phase2_fake"

        def get_history(self, symbol, timeframe="1d", start=None, end=None):
            dates = pd.date_range("2024-01-01", periods=10, freq="D")
            return pd.DataFrame(
                {
                    "time": dates,
                    "open": [100.0 + index for index in range(10)],
                    "high": [102.0 + index for index in range(10)],
                    "low": [99.0 + index for index in range(10)],
                    "close": [101.0 + index for index in range(10)],
                    "volume": [1000 + index for index in range(10)],
                }
            )

    provider_fixture_path = output_csv_path(live_root, symbol="PHASE2TEST", timeframe="1d")
    if provider_fixture_path.exists():
        provider_fixture_path.unlink()

    provider_boot = bootstrap_bars_csv(
        live_root=live_root,
        symbol="PHASE2TEST",
        start="2024-01-01",
        end="2024-01-10",
        timeframe="1d",
        prefer_local=True,
        allow_yfinance=False,
        provider=FakeProvider(),
    )
    assert provider_boot.source == "provider:phase2_fake"
    assert provider_boot.coverage_ok is True
    assert provider_boot.data_quality_ok is True

    if args.data_only:
        print("AI Auto Lab bootstrap data-contract self-test: PASS")
        print(f"CSV path: {boot.csv_path}")
        print(f"Rows: {boot.row_count}")
        print(f"Hash: {boot.data_hash}")
        return 0

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
