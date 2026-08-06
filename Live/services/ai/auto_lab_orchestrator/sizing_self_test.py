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

    import pandas as pd
    from core.BackTestEngine import BackTestEngine
    from core.StrategyEngine import StrategySignal

    rising_bars = pd.DataFrame(
        {
            "time": pd.date_range("2024-01-01", periods=5, freq="D"),
            "open": [100.0, 200.0, 400.0, 500.0, 600.0],
            "high": [101.0, 201.0, 401.0, 501.0, 601.0],
            "low": [99.0, 199.0, 399.0, 499.0, 599.0],
            "close": [100.0, 200.0, 400.0, 500.0, 600.0],
            "volume": [1000] * 5,
        }
    )
    signals = [
        StrategySignal(index=0, time=rising_bars.iloc[0]["time"], side="BUY", price=100.0, rule="buy-1"),
        StrategySignal(index=1, time=rising_bars.iloc[1]["time"], side="SELL", price=200.0, rule="sell-1"),
        StrategySignal(index=2, time=rising_bars.iloc[2]["time"], side="BUY", price=400.0, rule="buy-2"),
        StrategySignal(index=3, time=rising_bars.iloc[3]["time"], side="SELL", price=500.0, rule="sell-2"),
    ]
    dynamic_result = BackTestEngine().run(
        bars=rising_bars,
        signals=signals,
        initial_cash=1000.0,
        quantity=99,
        sizing_mode="percent_cash_exposure",
        cash_exposure_pct=50.0,
        execution_mode="next_open",
        commission_per_order=1.0,
        slippage_bps=0.0,
    )
    assert dynamic_result.errors == []
    assert [trade.quantity for trade in dynamic_result.trades] == [2, 1]
    assert dynamic_result.unfilled_signal_count == 0
    assert dynamic_result.eligible_buy_signal_count == 2
    assert dynamic_result.filled_buy_signal_count == 2
    assert dynamic_result.fill_rate_pct == 100.0

    from services.ai.auto_lab_orchestrator.adapters import normalize_core_backtest_result
    from services.ai.auto_lab_orchestrator.models import ExperimentGoal
    from services.ai.auto_lab_orchestrator.scorecard import score_strategy_result

    rejected_result = BackTestEngine().run(
        bars=rising_bars,
        signals=signals,
        initial_cash=1000.0,
        quantity=99,
        sizing_mode="fixed_quantity",
        execution_mode="next_open",
    )
    normalized_rejected = normalize_core_backtest_result(
        rejected_result,
        candidate_id="unaffordable-fixed-size",
        symbol="TEST",
        engine="core",
    )
    rejected_score = score_strategy_result(
        normalized_rejected,
        ExperimentGoal(starting_cash=1000.0, target_equity=1000.0, min_trades=0),
    )
    assert rejected_result.fill_rate_pct == 0.0
    assert any("eligible BUY signals were filled" in reason for reason in rejected_score.fail_reasons)

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
