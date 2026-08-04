from __future__ import annotations

from pathlib import Path
import argparse
from datetime import datetime
import json
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

    parser = argparse.ArgumentParser()
    parser.add_argument("--contract-only", action="store_true")
    args = parser.parse_args()

    import pandas as pd
    from services.ai.auto_lab_orchestrator.walk_forward_runner import (
        best_holdout_symbol_fields,
        build_argument_parser,
        build_rolling_windows,
        classify_holdout_regime,
        reserve_final_holdout,
        run_final_holdout_test,
        select_diverse_scorecards,
        summarize_rolling_results,
        validate_walk_forward_dates,
    )
    from services.ai.auto_lab_orchestrator.models import NormalizedBacktestResult, StrategyCandidate, StrategyScorecard

    sample_bars = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=90, freq="D"),
            "open": range(90),
            "high": range(1, 91),
            "low": range(90),
            "close": range(1, 91),
            "volume": [1000] * 90,
        }
    )
    diversity_candidates = {
        "ema_a": StrategyCandidate("ema_a", "EMA A", "crossover"),
        "ema_clone": StrategyCandidate("ema_clone", "EMA Clone", "crossover"),
        "rsi_a": StrategyCandidate("rsi_a", "RSI A", "rsi_mean_reversion"),
    }
    diversity_scores = [
        StrategyScorecard("ema_a", "AMD", 90.0, "A", engine_pass=True, research_pass=True),
        StrategyScorecard("ema_clone", "AMD", 89.0, "A", engine_pass=True, research_pass=True),
        StrategyScorecard("rsi_a", "AMD", 80.0, "B", engine_pass=True, research_pass=True),
    ]
    diversity_results = [
        NormalizedBacktestResult("ema_a", "AMD", "ok", "contract", raw_summary={"strategy_result": {"signals": [{"index": 1, "side": "BUY"}]}}),
        NormalizedBacktestResult("ema_clone", "AMD", "ok", "contract", raw_summary={"strategy_result": {"signals": [{"index": 1, "side": "BUY"}]}}),
        NormalizedBacktestResult("rsi_a", "AMD", "ok", "contract", raw_summary={"strategy_result": {"signals": [{"index": 4, "side": "BUY"}]}}),
    ]
    diverse = select_diverse_scorecards(
        scorecards=diversity_scores,
        candidates_by_id=diversity_candidates,
        results=diversity_results,
        limit=3,
    )
    assert [scorecard.candidate_id for scorecard in diverse] == ["ema_a", "rsi_a"]
    valid_dates = validate_walk_forward_dates(
        train_start="2020-01-01",
        train_end="2023-12-31",
        test_start="2024-01-01",
        test_end="2025-12-31",
    )
    assert valid_dates["train_end"] < valid_dates["test_start"]
    try:
        validate_walk_forward_dates(
            train_start="2017-01-01",
            train_end="2023-12-31",
            test_start="2017-01-01",
            test_end="2025-12-31",
        )
        raise AssertionError("Overlapping train/test windows must be rejected")
    except ValueError as exc:
        assert "overlap" in str(exc).lower()
    windows = build_rolling_windows(sample_bars, window_count=3, min_bars=20)
    assert len(windows) == 3
    assert [window["row_count"] for window in windows] == [30, 30, 30]
    assert windows[0]["end"] < windows[1]["start"] < windows[2]["start"]

    robust = summarize_rolling_results(
        [
            {"engine_pass": True, "research_pass": True, "score": 72, "max_drawdown_pct": 8},
            {"engine_pass": True, "research_pass": True, "score": 70, "max_drawdown_pct": 9},
            {"engine_pass": True, "research_pass": False, "score": 60, "max_drawdown_pct": 12},
        ],
        max_drawdown_pct=30,
    )
    assert robust["rolling_status"] == "robust"
    assert round(robust["rolling_pass_rate_pct"], 2) == 66.67

    failed = summarize_rolling_results(
        [{"engine_pass": False, "research_pass": False, "score": 0, "max_drawdown_pct": 0}],
        max_drawdown_pct=30,
    )
    assert failed["rolling_status"] == "failed"

    holdout_split = reserve_final_holdout(sample_bars, holdout_pct=20, min_holdout_bars=20)
    assert holdout_split["holdout_available"] is True
    assert len(holdout_split["validation_bars"]) == 70
    assert len(holdout_split["holdout_bars"]) == 20
    assert holdout_split["holdout_rows"] == 20
    assert holdout_split["validation_end"] < holdout_split["holdout_start"]

    minimum_split = reserve_final_holdout(sample_bars, holdout_pct=5, min_holdout_bars=20)
    assert len(minimum_split["validation_bars"]) == 70
    assert minimum_split["holdout_rows"] == 20

    unavailable_split = reserve_final_holdout(sample_bars.iloc[:20], holdout_pct=20, min_holdout_bars=20)
    assert unavailable_split["holdout_available"] is False
    assert len(unavailable_split["validation_bars"]) == 20
    assert len(unavailable_split["holdout_bars"]) == 0

    low_vol_uptrend = sample_bars.iloc[:30].copy()
    low_vol_uptrend["close"] = [100.0 + (index * 0.5) for index in range(30)]
    assert classify_holdout_regime(low_vol_uptrend) == "uptrend_low_volatility"

    high_vol_sideways = sample_bars.iloc[:6].copy()
    high_vol_sideways["close"] = [100.0, 110.0, 90.0, 110.0, 90.0, 100.0]
    assert classify_holdout_regime(high_vol_sideways) == "sideways_high_volatility"

    class FakeHoldoutAdapter:
        def __init__(self):
            self.calls = []

        def run_candidate(self, candidate, bars, goal, symbol):
            self.calls.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "rows": len(bars),
                    "commission": goal.commission_per_order,
                    "slippage_bps": goal.slippage_bps,
                }
            )
            return NormalizedBacktestResult(
                candidate_id=candidate.candidate_id,
                symbol=symbol,
                status="ok",
                engine="contract",
                metrics={
                    "total_return_pct": 8.0,
                    "final_equity": 10800.0,
                    "max_drawdown_pct": 4.0,
                    "trade_count": 3,
                    "win_rate_pct": 66.67,
                    "profit_factor": 1.5,
                    "fees": 4.0,
                    "slippage": 2.0,
                },
            )

    fake_adapter = FakeHoldoutAdapter()
    candidate = StrategyCandidate(
        candidate_id="fixed_candidate",
        name="Fixed Candidate",
        family="contract",
    )
    holdout_result = run_final_holdout_test(
        adapter=fake_adapter,
        candidate=candidate,
        symbol="AMD",
        holdout_bars=holdout_split["holdout_bars"],
        holdout_available=holdout_split["holdout_available"],
        timeframe="1d",
        initial_cash=10000.0,
        target_equity=10800.0,
        max_drawdown_pct=30.0,
        commission_per_order=1.25,
        slippage_bps=6.0,
    )
    assert len(fake_adapter.calls) == 1
    assert fake_adapter.calls[0] == {
        "candidate_id": "fixed_candidate",
        "rows": 20,
        "commission": 1.25,
        "slippage_bps": 6.0,
    }
    assert holdout_result["holdout_available"] is True
    assert holdout_result["holdout_rows"] == 20
    assert holdout_result["holdout_score"] > 0
    assert holdout_result["holdout_engine_pass"] is True
    assert holdout_result["holdout_objective_hit"] is True
    assert holdout_result["holdout_fees"] == 4.0
    assert holdout_result["holdout_slippage"] == 2.0
    assert holdout_result["holdout_regime"] == "uptrend_low_volatility"
    assert holdout_result["holdout_errors"] == []
    assert holdout_result["holdout_warnings"] == []

    class ErrorHoldoutAdapter:
        def run_candidate(self, candidate, bars, goal, symbol):
            return NormalizedBacktestResult(
                candidate_id=candidate.candidate_id,
                symbol=symbol,
                status="error",
                engine="contract",
                errors=["Strategy parser rejected the candidate."],
                warnings=["Diagnostic warning."],
            )

    error_holdout = run_final_holdout_test(
        adapter=ErrorHoldoutAdapter(),
        candidate=candidate,
        symbol="AMD",
        holdout_bars=holdout_split["holdout_bars"],
        holdout_available=True,
        timeframe="1d",
        initial_cash=10000.0,
        target_equity=10800.0,
        max_drawdown_pct=30.0,
        commission_per_order=1.25,
        slippage_bps=6.0,
    )
    assert error_holdout["holdout_engine_pass"] is False
    assert error_holdout["holdout_errors"] == ["Strategy parser rejected the candidate."]
    assert error_holdout["holdout_warnings"] == ["Diagnostic warning."]

    unavailable_result = run_final_holdout_test(
        adapter=fake_adapter,
        candidate=candidate,
        symbol="AMD",
        holdout_bars=unavailable_split["holdout_bars"],
        holdout_available=False,
        timeframe="1d",
        initial_cash=10000.0,
        target_equity=10800.0,
        max_drawdown_pct=30.0,
        commission_per_order=1.25,
        slippage_bps=6.0,
    )
    assert len(fake_adapter.calls) == 1
    assert unavailable_result["holdout_available"] is False
    assert unavailable_result["holdout_regime"] == "unavailable"

    best_holdout = best_holdout_symbol_fields(holdout_result)
    assert best_holdout["best_holdout_available"] is True
    assert best_holdout["best_holdout_score"] == holdout_result["holdout_score"]
    assert best_holdout["best_holdout_regime"] == "uptrend_low_volatility"
    empty_best_holdout = best_holdout_symbol_fields({})
    assert empty_best_holdout["best_holdout_available"] is False
    assert empty_best_holdout["best_holdout_rows"] == 0

    cli_defaults = build_argument_parser().parse_args([])
    assert cli_defaults.holdout_pct == 20.0
    assert cli_defaults.holdout_min_bars == 20
    assert cli_defaults.workers == 2
    assert cli_defaults.no_cache is False
    cli_override = build_argument_parser().parse_args(
        ["--holdout-pct", "25", "--holdout-min-bars", "30", "--workers", "1", "--no-cache"]
    )
    assert cli_override.holdout_pct == 25.0
    assert cli_override.holdout_min_bars == 30
    assert cli_override.workers == 1
    assert cli_override.no_cache is True

    from services.ai.auto_lab_orchestrator.walk_forward_reporter import (
        build_paper_review_overlay,
        build_paper_review_queue,
        build_walk_forward_payload,
        decide_promotion,
        render_top_walk_forward_strategy_algorithm,
    )

    promotable = {
        "symbol": "AMD",
        "candidate_id": "promotion_contract",
        "script": "\n".join(
            [
                "fast = ema(close, 9)",
                "slow = ema(close, 21)",
                "plot fast",
                "plot slow",
                "buy when crossover(fast, slow)",
                "sell when crossunder(fast, slow)",
            ]
        ),
        "test_engine_pass": True,
        "test_research_pass": True,
        "rolling_status": "robust",
        "rolling_pass_rate_pct": 100.0,
        "holdout_available": True,
        "holdout_engine_pass": True,
        "holdout_research_pass": True,
        "holdout_max_drawdown_pct": 8.0,
    }
    decision, _reasons = decide_promotion(promotable, {"max_drawdown_pct": 30.0})
    assert decision == "promote"

    missing_test_engine = dict(promotable)
    missing_test_engine.pop("test_engine_pass")
    decision, reasons = decide_promotion(missing_test_engine, {"max_drawdown_pct": 30.0})
    assert decision == "review"
    assert any("Test 2 engine" in reason for reason in reasons)

    failed_holdout = dict(promotable, holdout_research_pass=False)
    decision, _reasons = decide_promotion(failed_holdout, {"max_drawdown_pct": 30.0})
    assert decision == "reject"

    source_results = [{"symbol": "AMD", "validated_candidates": [promotable]}]
    promotion_payload = build_walk_forward_payload(
        walk_forward_run_id="promotion_contract",
        symbols=["AMD"],
        settings={"max_drawdown_pct": 30.0},
        symbol_results=source_results,
    )
    assert "promotion_decision" not in source_results[0]["validated_candidates"][0]
    assert promotion_payload["ranked_validated_candidates"][0]["promotion_decision"] == "promote"

    queue_payload = build_paper_review_queue(promotion_payload)
    assert queue_payload["schema_version"] == "paper_review_queue_v24_0"
    assert queue_payload["auto_execute"] is False
    assert queue_payload["candidate_count"] == 1
    review_candidate = queue_payload["candidates"][0]
    assert review_candidate["candidate_id"] == "promotion_contract"
    assert review_candidate["review_status"] == "pending_user_approval"
    assert review_candidate["auto_execute"] is False
    assert review_candidate["risk_policy"] == {
        "max_position_pct": 20.0,
        "max_daily_loss_pct": 2.0,
        "max_drawdown_pct": 10.0,
        "max_orders_per_day": 10,
        "allow_short": False,
    }
    overlay = build_paper_review_overlay(review_candidate)
    assert overlay["source"] == "auto_lab_paper_review"
    assert overlay["symbol"] == "AMD"
    assert overlay["candidate_id"] == "promotion_contract"
    assert overlay["script"] == promotable["script"]
    assert overlay["enabled"] is True
    assert overlay["visual_only"] is True
    assert overlay["auto_execute"] is False

    for invalid_overlay_candidate in (
        {**review_candidate, "promotion_decision": "review"},
        {**review_candidate, "script": ""},
    ):
        try:
            build_paper_review_overlay(invalid_overlay_candidate)
            raise AssertionError("Invalid candidates must not create review overlays")
        except ValueError:
            pass

    from services.strategy_overlay_service import StrategyOverlayService

    overlay_service = StrategyOverlayService()
    manual_store = {
        "script": "r = rsi(close, 14)",
        "enabled": True,
        "nonce": 4,
        "source": "strategy_lab_manual",
    }
    synced_overlay = overlay_service.sync_review_store(
        {"review_status": "active_paper_review", "overlay": overlay},
        manual_store,
    )
    assert synced_overlay["source"] == "auto_lab_paper_review"
    assert synced_overlay["nonce"] == 5
    assert overlay_service.script_for_symbol(synced_overlay, "AMD") == promotable["script"]
    assert overlay_service.script_for_symbol(synced_overlay, "NVDA") == ""

    cleared_overlay = overlay_service.sync_review_store(
        {"review_status": "inactive"},
        synced_overlay,
    )
    assert cleared_overlay == {
        "script": "",
        "enabled": False,
        "nonce": 6,
        "source": "auto_lab_paper_review",
    }
    assert overlay_service.sync_review_store({"review_status": "inactive"}, manual_store) is None
    assert overlay_service.script_for_symbol(manual_store, "NVDA") == manual_store["script"]

    from services.ai.auto_lab_orchestrator.sample_data import make_sample_bars_dataframe

    overlay_bars = make_sample_bars_dataframe(symbol="AMD", days=180).rename(columns={"date": "time"})
    overlay_snapshot = overlay_service.get_or_run(
        script=overlay_service.script_for_symbol(synced_overlay, "AMD"),
        bars=overlay_bars,
        symbol="AMD",
        timeframe="1d",
        source_label="replay",
    )
    assert overlay_snapshot is not None
    assert overlay_snapshot.errors == []
    assert {"fast", "slow"}.issubset(overlay_snapshot.result.lines)
    assert {"fast", "slow"}.issubset(set(overlay_snapshot.result.plots))

    import plotly.graph_objects as go
    from renderers.strategy_overlay_renderer import StrategyOverlayRenderer

    overlay_figure = StrategyOverlayRenderer().add_to_figure(
        fig=go.Figure(),
        engine=overlay_service.engine,
        chart_bars=overlay_bars,
        strategy_result=overlay_snapshot.result,
        is_replay_playing=False,
        context="PHASE5_SELF_TEST",
    )
    trace_names = {str(trace.name) for trace in overlay_figure.data}
    assert {"fast", "slow"}.issubset(trace_names)

    rejected_payload = build_walk_forward_payload(
        walk_forward_run_id="rejected_contract",
        symbols=["AMD"],
        settings={"max_drawdown_pct": 30.0},
        symbol_results=[{"symbol": "AMD", "validated_candidates": [failed_holdout]}],
    )
    assert build_paper_review_queue(rejected_payload)["candidate_count"] == 0

    from core.PaperBroker import PaperBroker
    from core.RiskGuard import TradeIntent
    from services.paper_trading_service import PaperTradingService

    paper_service = PaperTradingService(broker=PaperBroker(starting_cash=10000.0))
    orders_before_activation = len(paper_service.broker.orders)
    try:
        paper_service.activate_review({**review_candidate, "promotion_decision": "review"})
        raise AssertionError("Non-promoted candidates must not activate paper review")
    except ValueError:
        pass

    active_review = paper_service.activate_review(
        review_candidate,
        risk_policy={
            "max_position_pct": 20,
            "max_daily_loss_pct": 2,
            "max_drawdown_pct": 10,
            "max_orders_per_day": 10,
            "allow_short": False,
        },
    )
    assert active_review["review_status"] == "active_paper_review"
    assert active_review["candidate_id"] == "promotion_contract"
    assert active_review["auto_execute"] is False
    assert len(paper_service.broker.orders) == orders_before_activation

    decision, order = paper_service.market_buy("NVDA", 1, 100)
    assert decision.approved is False and order is None
    assert "review symbol" in decision.message.lower()

    automatic_intent = TradeIntent(
        symbol="AMD",
        side="BUY",
        quantity=1,
        source="strategy:auto_lab",
    )
    decision, order = paper_service.submit_intent(automatic_intent, last_price=100)
    assert decision.approved is False and order is None
    assert "manual orders" in decision.message.lower()

    decision, order = paper_service.market_buy("AMD", 21, 100)
    assert decision.approved is False and order is None
    assert "position" in decision.message.lower()

    decision, order = paper_service.market_buy("AMD", 10, 100)
    assert decision.approved is True and order is not None
    decision, order = paper_service.market_sell("AMD", 10, 50)
    assert decision.approved is True and order is not None
    decision, order = paper_service.market_buy("AMD", 1, 50)
    assert decision.approved is False and order is None
    assert "daily loss" in decision.message.lower()

    order_limited = PaperTradingService(broker=PaperBroker(starting_cash=10000.0))
    order_limited.activate_review(
        review_candidate,
        risk_policy={
            "max_position_pct": 20,
            "max_daily_loss_pct": 100,
            "max_drawdown_pct": 100,
            "max_orders_per_day": 1,
            "allow_short": False,
        },
    )
    assert order_limited.market_buy("AMD", 1, 100)[0].approved is True
    assert order_limited.market_sell("AMD", 1, 100)[0].approved is True
    decision, order = order_limited.market_buy("AMD", 1, 100)
    assert decision.approved is False and order is None
    assert "order limit" in decision.message.lower()

    inactive = order_limited.deactivate_review()
    assert inactive["review_status"] == "inactive"
    assert order_limited.market_buy("NVDA", 1, 100)[0].approved is True

    preexisting_position = PaperTradingService(broker=PaperBroker(starting_cash=10000.0))
    assert preexisting_position.market_buy("NVDA", 1, 100)[0].approved is True
    preexisting_position.activate_review(review_candidate)
    assert preexisting_position.market_sell("NVDA", 1, 100)[0].approved is True
    decision, order = preexisting_position.market_buy("NVDA", 1, 100)
    assert decision.approved is False and order is None
    assert "review symbol" in decision.message.lower()

    large_broker = PaperBroker(starting_cash=100000.0)
    large_broker.submit_order(
        TradeIntent(symbol="NVDA", side="BUY", quantity=300, source="manual"),
        last_price=100,
    )
    large_exit = PaperTradingService(broker=large_broker)
    large_exit.activate_review(review_candidate)
    decision, order = large_exit.market_sell("NVDA", 300, 100)
    assert decision.approved is True and order is not None
    assert large_exit.broker.get_position_quantity("NVDA") == 0

    replay_time = datetime(2024, 7, 17, 10, 0)
    replay_review = PaperTradingService(broker=PaperBroker(starting_cash=10000.0))
    replay_review.activate_review(review_candidate, timestamp=replay_time)
    assert replay_review.submit_intent(
        TradeIntent(symbol="AMD", side="BUY", quantity=10, source="manual:replay"),
        last_price=100,
        timestamp=replay_time,
    )[0].approved is True
    assert replay_review.submit_intent(
        TradeIntent(symbol="AMD", side="SELL", quantity=10, source="manual:replay"),
        last_price=50,
        timestamp=replay_time,
    )[0].approved is True
    assert replay_review.review_status({"AMD": 50})["daily_loss_pct"] >= 5.0
    decision, order = replay_review.submit_intent(
        TradeIntent(symbol="AMD", side="BUY", quantity=1, source="manual:replay"),
        last_price=50,
        timestamp=replay_time,
    )
    assert decision.approved is False and order is None
    assert "daily loss" in decision.message.lower()

    report = render_top_walk_forward_strategy_algorithm(
        {
            "ranked_validated_candidates": [
                {
                    "symbol": "AMD",
                    "candidate_id": "contract_candidate",
                    "rolling_status": "partial",
                    "rolling_pass_rate_pct": 33.33,
                    "rolling_worst_score": 42,
                    "rolling_worst_drawdown_pct": 18,
                    "rolling_commission_per_order": 1,
                    "rolling_slippage_bps": 5,
                }
            ]
        }
    )
    assert "Test 3 survived some rolling stress windows" in report
    assert "run rolling walk-forward windows" not in report

    if args.contract_only:
        print("AI Auto Lab rolling and final-holdout contract self-test: PASS")
        return 0

    from services.ai.auto_lab_orchestrator.data_adapters import write_sample_csv
    from services.ai.auto_lab_orchestrator.bars_bootstrapper import output_csv_path

    for symbol in ["AMD", "NVDA"]:
        write_sample_csv(output_csv_path(live_root, symbol=symbol, timeframe="1d"), symbol=symbol, days=260)

    runner = live_root / "services" / "ai" / "auto_lab_orchestrator" / "walk_forward_runner.py"
    result = subprocess.run(
        [
            sys.executable,
            str(runner),
            "--symbols",
            "AMD,NVDA",
            "--train-start",
            "2024-01-01",
            "--train-end",
            "2024-05-31",
            "--test-start",
            "2024-06-01",
            "--test-end",
            "2024-09-17",
            "--local-only",
            "--top-n-per-symbol",
            "2",
            "--max-total-runs-per-symbol",
            "6",
            "--max-mutations-per-parent",
            "2",
            "--continue-on-error",
            "--no-cache",
            "--holdout-pct",
            "20",
            "--holdout-min-bars",
            "20",
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

    runs_dir = live_root / "data" / "auto_lab_walk_forward_runs"
    latest = sorted([p for p in runs_dir.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)[0]
    required = [
        "walk_forward_universe_results.json",
        "walk_forward_universe_report.md",
        "walk_forward_symbol_leaderboard.md",
        "overfit_warning_report.md",
        "top_walk_forward_strategy_algorithm.md",
        "paper_review_queue.json",
        "paper_review_queue.md",
    ]
    for name in required:
        path = latest / name
        assert path.exists(), f"Missing {path}"

    payload = json.loads((latest / "walk_forward_universe_results.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "walk_forward_universe_v23_0"
    assert payload["settings"]["validation_mode"] == "train_unseen_test_then_rolling_stress_then_final_holdout"
    assert payload["settings"]["rolling_windows"] == 3
    assert payload["settings"]["holdout_pct"] == 20.0
    assert payload["settings"]["holdout_min_bars"] == 20

    print("AI Auto Lab walk-forward self-test: PASS")
    print(f"latest_walk_forward_run_dir: {latest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
