from __future__ import annotations

from pathlib import Path
import argparse
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

    parser = argparse.ArgumentParser(description="Smoke-test existing StrategyEngine + BackTestEngine through Auto Lab adapter.")
    parser.add_argument("--symbol", default="AMD")
    parser.add_argument("--days", type=int, default=220)
    parser.add_argument("--max-examples", type=int, default=8)
    parser.add_argument("--execution-only", action="store_true", help="Run only deterministic execution-model checks.")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero if no core engine candidate passes.")
    args = parser.parse_args()

    from services.ai.auto_lab_orchestrator.models import ExperimentGoal
    from services.ai.auto_lab_orchestrator.orchestrator import AutoLabOrchestrator
    from services.ai.auto_lab_orchestrator.sample_data import make_sample_bars_dataframe
    from services.ai.auto_lab_orchestrator.seed_library import discover_strategy_seed_candidates
    from services.ai.auto_lab_orchestrator.adapters import CoreStrategyBacktestAdapter, normalize_core_backtest_result
    from core.BackTestEngine import BackTestEngine
    from core.StrategyEngine import StrategyEngine
    from services.ai.strategy_grammar_guard import validate_strategy_lab_script
    from types import SimpleNamespace
    import pandas as pd

    execution_bars = pd.DataFrame(
        {
            "time": pd.date_range("2026-01-01", periods=4, freq="D"),
            "open": [100.0, 120.0, 130.0, 150.0],
            "high": [112.0, 127.0, 142.0, 152.0],
            "low": [98.0, 118.0, 128.0, 148.0],
            "close": [110.0, 125.0, 140.0, 150.0],
        }
    )
    execution_signals = [
        SimpleNamespace(index=0, time=execution_bars.iloc[0]["time"], side="BUY", price=110.0, rule="entry"),
        SimpleNamespace(index=2, time=execution_bars.iloc[2]["time"], side="SELL", price=140.0, rule="exit"),
        SimpleNamespace(index=3, time=execution_bars.iloc[3]["time"], side="BUY", price=150.0, rule="final_bar_entry"),
    ]
    execution_result = BackTestEngine().run(
        bars=execution_bars,
        signals=execution_signals,
        initial_cash=1000.0,
        quantity=1,
        execution_mode="next_open",
        commission_per_order=1.0,
        slippage_bps=100.0,
    )
    assert execution_result.execution_mode == "next_open"
    assert execution_result.trade_count == 1
    assert round(execution_result.trades[0].entry_price, 4) == 121.2
    assert round(execution_result.trades[0].exit_price, 4) == 148.5
    assert round(execution_result.trades[0].pnl, 4) == 25.3
    assert round(execution_result.final_equity, 4) == 1025.3
    assert round(execution_result.total_commission, 4) == 2.0
    assert round(execution_result.total_slippage, 4) == 2.7
    assert execution_result.unfilled_signal_count == 1
    normalized_execution = normalize_core_backtest_result(
        execution_result,
        candidate_id="execution_self_test",
        symbol="TEST",
        engine="core_strategy_backtest_adapter",
    )
    assert normalized_execution.metrics["execution_mode"] == "next_open"
    assert normalized_execution.metrics["fees"] == 2.0
    assert round(normalized_execution.metrics["slippage"], 4) == 2.7

    legacy_result = BackTestEngine().run(
        bars=execution_bars,
        signals=execution_signals,
        initial_cash=1000.0,
        quantity=1,
        execution_mode="same_close",
    )
    assert legacy_result.execution_mode == "same_close"
    assert round(legacy_result.trades[0].entry_price, 4) == 110.0
    assert round(legacy_result.trades[0].exit_price, 4) == 140.0
    assert round(legacy_result.final_equity, 4) == 1030.0

    execution_goal = ExperimentGoal()
    assert execution_goal.execution_mode == "next_open"
    assert execution_goal.commission_per_order == 0.0
    assert execution_goal.slippage_bps == 1.0

    order_bars = pd.DataFrame(
        {
            "time": pd.date_range("2026-02-01", periods=6, freq="D"),
            "open": [99.0, 101.0, 102.0, 98.0, 101.0, 97.0],
            "high": [100.0, 103.0, 104.0, 100.0, 103.0, 99.0],
            "low": [97.0, 99.0, 100.0, 96.0, 99.0, 95.0],
            "close": [99.0, 101.0, 102.0, 98.0, 101.0, 97.0],
            "volume": [1000, 1100, 1200, 1300, 1400, 1500],
        }
    )
    entry_close_script = "\n".join(
        [
            "longSignal = close > 100",
            "exitSignal = close < 100",
            "entry Long long when longSignal",
            "close Long when exitSignal",
        ]
    )
    legacy_order_script = "\n".join(
        [
            "longSignal = close > 100",
            "exitSignal = close < 100",
            "buy when longSignal",
            "sell when exitSignal",
        ]
    )
    strategy_engine = StrategyEngine()
    named_orders = strategy_engine.run(entry_close_script, order_bars)
    legacy_orders = strategy_engine.run(legacy_order_script, order_bars)
    assert named_orders.errors == []
    assert legacy_orders.errors == []
    assert [signal.side for signal in named_orders.signals] == ["BUY", "SELL", "BUY", "SELL"]
    assert [
        (intent.action, intent.position_id, intent.direction, intent.side, intent.index)
        for intent in named_orders.order_intents
    ] == [
        (intent.action, intent.position_id, intent.direction, intent.side, intent.index)
        for intent in legacy_orders.order_intents
    ]
    all_order_intents = named_orders.order_intents + legacy_orders.order_intents
    assert all(intent.auto_execute is False for intent in all_order_intents)
    assert all(intent.order_type == "MARKET" for intent in all_order_intents)
    assert all(intent.source == "strategy_engine" for intent in all_order_intents)

    filtered_orders = strategy_engine.filter_result_to_bars(
        named_orders,
        order_bars,
        order_bars.iloc[:4].reset_index(drop=True),
    )
    assert [intent.index for intent in filtered_orders.order_intents] == [1, 3]

    named_backtest = BackTestEngine().run(
        bars=order_bars,
        signals=named_orders.signals,
        initial_cash=1000.0,
        quantity=1,
        execution_mode="same_close",
    )
    assert named_backtest.trade_count == 2

    short_order_result = strategy_engine.run(
        "entry Short short when close > 100",
        order_bars,
    )
    assert any("long" in error.lower() for error in short_order_result.errors)

    assert validate_strategy_lab_script(entry_close_script) == []
    assert any(
        issue.code == "unsupported-strategy-entry"
        for issue in validate_strategy_lab_script("entry Short short when close > 100")
    )
    assert any(
        issue.code == "unsupported-pine-order"
        for issue in validate_strategy_lab_script('strategy.entry("Long", strategy.long)')
    )
    assert any(
        issue.code == "unsupported-strategy-close"
        for issue in validate_strategy_lab_script("close Long")
    )

    if args.execution_only:
        print("BackTestEngine execution model self-test: PASS")
        return 0

    symbol = args.symbol.upper().strip() or "AMD"
    bars = make_sample_bars_dataframe(symbol=symbol, days=args.days)

    candidates = discover_strategy_seed_candidates(
        live_root=live_root,
        symbol=symbol,
        max_examples=args.max_examples,
        include_built_ins=True,
    )

    goal = ExperimentGoal(
        question=(
            "Core smoke test v21.2: run cleaned strategy seeds through the existing "
            "StrategyEngine and BackTestEngine on synthetic bars."
        ),
        symbols=[symbol],
        timeframe="1d",
        starting_cash=12000.0,
        target_equity=24000.0,
        max_drawdown_pct=30.0,
        min_trades=1,
        max_runs=len(candidates),
        simulation_only=True,
        notes="Synthetic bars; real core engine path; no broker/live trading.",
    )

    orchestrator = AutoLabOrchestrator(adapter=CoreStrategyBacktestAdapter(), live_root=live_root)
    run = orchestrator.run_experiment(goal=goal, candidates=candidates, bars_by_symbol={symbol: bars})

    engine_pass_count = sum(1 for sc in run.scorecards if sc.engine_pass)
    research_pass_count = sum(1 for sc in run.scorecards if sc.research_pass)
    objective_hit_count = sum(1 for sc in run.scorecards if sc.objective_hit)

    print("AI Auto Lab Core Engine smoke test complete.")
    print(f"Run ID: {run.run_id}")
    print(f"Candidates attempted: {len(candidates)}")
    print(f"engine_pass_count: {engine_pass_count}")
    print(f"research_pass_count: {research_pass_count}")
    print(f"objective_hit_count: {objective_hit_count}")
    print(f"Report: {run.artifacts.get('report_md', '')}")

    if candidates:
        print("Candidates:")
        for candidate in candidates[:20]:
            print(f"- {candidate.candidate_id} source={candidate.source}")

    if run.scorecards:
        print("Top scorecards:")
        for sc in sorted(run.scorecards, key=lambda item: item.total_score, reverse=True)[:8]:
            print(
                f"- {sc.candidate_id}: score={sc.total_score:.2f} "
                f"engine_pass={sc.engine_pass} research_pass={sc.research_pass} "
                f"objective_hit={sc.objective_hit} progress={sc.objective_progress_pct:.2f}%"
            )
            if sc.fail_reasons:
                print(f"  fail: {' | '.join(sc.fail_reasons[:3])}")
            if sc.warnings:
                print(f"  warn: {' | '.join(sc.warnings[:3])}")

    if args.strict and engine_pass_count <= 0:
        print("STRICT CORE SMOKE FAILED: no candidates produced usable core-engine results.")
        return 2

    if engine_pass_count <= 0:
        print("CORE SMOKE DIAGNOSTIC: no candidates passed engine. This is non-blocking unless --strict is used.")
        print("Next likely fix: adapt built-in seeds to the current Strategy Lab grammar.")
    else:
        print("CORE SMOKE PASS: at least one candidate produced a usable core-engine result.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
