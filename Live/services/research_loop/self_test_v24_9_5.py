from __future__ import annotations

from pathlib import Path
import py_compile
import tempfile


FAKE_BACKTEST_ENGINE = """
def run(bars, symbol, strategy_name, parameters, timeframe="1d", simulation_only=True):
    assert simulation_only is True
    count = len(bars) if hasattr(bars, "__len__") else 0
    return {
        "symbol": symbol,
        "total_return": 0.10 + (count / 10000.0),
        "sharpe": 1.10,
        "max_drawdown": -0.12,
        "win_rate": 0.57,
        "trade_count": max(10, count // 5),
        "profit_factor": 1.45,
    }
"""


def main() -> int:
    from services.research_loop.models import ResearchLoopConfig
    from services.research_loop.strategy_candidate_generator import generate_strategy_candidates
    from services.research_loop.backtest_engine_adapter import SafeBackTestEngineAdapter
    from services.research_loop.bars_adapter import build_engine_bars

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        repo = Path(tmp) / "AlgoTrader"
        live = repo / "Live"
        core = live / "core"
        data_dir = live / "data" / "catalog"
        core.mkdir(parents=True, exist_ok=True)
        data_dir.mkdir(parents=True, exist_ok=True)
        (live / "app.py").write_text("# temp app\n", encoding="utf-8")
        (core / "BackTestEngine.py").write_text(FAKE_BACKTEST_ENGINE, encoding="utf-8")
        (data_dir / "AMD_1d_bars.csv").write_text(
            "date,open,high,low,close,volume,symbol\n"
            "2024-01-01,100,102,99,101,1000000,AMD\n"
            "2024-01-02,101,103,100,102,1100000,AMD\n"
            "2024-01-03,102,104,101,103,1200000,AMD\n",
            encoding="utf-8",
        )

        bars = build_engine_bars(repo_root=repo, symbol="AMD", timeframe="1d")
        assert bars.row_count >= 3, bars.to_dict()
        assert bars.engine_input is not None, bars.to_dict()

        config = ResearchLoopConfig(
            theme="AI infrastructure semiconductors",
            symbols=["AMD"],
            max_candidates=1,
            max_loops=1,
            min_trades=10,
            max_drawdown_limit=-0.20,
            min_sharpe=0.25,
            backend="sqlite",
            repo_root=str(repo),
            evaluation_mode="hybrid_safe",
        )

        candidate = generate_strategy_candidates(config)[0]
        adapter = SafeBackTestEngineAdapter(repo)
        evaluation, attempts = adapter.evaluate_candidate(config, candidate)

        assert attempts, "Expected adapter attempts."
        assert evaluation is not None, "Expected evaluation from fake engine."
        assert evaluation.aggregate_metrics.get("evaluation_source") == "real_backtest_engine_adapter", evaluation.aggregate_metrics
        assert evaluation.symbol_results, "Expected symbol results."
        assert evaluation.symbol_results[0].trade_count > 0, evaluation.symbol_results[0].to_dict()

    print("v24.9.5 BackTestEngine Bars Adapter self-test: PASS")
    print("Bars adapter file discovery/loading: PASS")
    print("Synthetic fallback or file load path: PASS")
    print("Fake real BackTestEngine with bars signature: PASS")
    print("Real adapter evaluation source: PASS")
    print("No credentials were written.")
    print("No files were moved or deleted.")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
