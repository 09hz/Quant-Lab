from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

LIVE = Path(__file__).resolve().parents[1]
if str(LIVE) not in sys.path:
    sys.path.insert(0, str(LIVE))

from services.ai.current_strategy_context import (  # noqa: E402
    build_strategy_runtime_context,
    should_auto_run_backtest_for_ai,
)


def main() -> int:
    bars = pd.DataFrame(
        [
            {"time": "2026-06-15 09:30", "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 1000},
            {"time": "2026-06-15 09:31", "open": 100.5, "high": 102, "low": 100, "close": 101.5, "volume": 1400},
            {"time": "2026-06-15 09:32", "open": 101.5, "high": 103, "low": 101, "close": 102.0, "volume": 1600},
        ]
    )

    context = build_strategy_runtime_context(
        strategy_text="buy = ta.crossover(close, ta.sma(close, 20))\nsell = ta.crossunder(close, ta.sma(close, 20))",
        symbol="MSFT",
        timeframe="1 min",
        start="2026-06-15",
        end="2026-06-18",
        initial_cash=100000,
        quantity=10,
        bars=bars,
        backtest_summary={
            "total_pnl": 123.45,
            "trades": 5,
            "win_rate": 60.0,
            "max_drawdown": -42.10,
        },
        backtest_has_run=True,
        backtest_status="completed",
        user_question="Explain this strategy result.",
        metadata={"source": "demo"},
    )

    print("Strategy Runtime Context Check")
    print(f"Symbol: {context.symbol}")
    print(f"Timeframe: {context.timeframe}")
    print(f"Bars summarized: {context.bars.rows}")
    print(f"Backtest available: {context.backtest.available}")
    print(f"Strategy chars: {context.strategy_chars}")
    print("")
    print("Auto-run decision examples:")
    print("  already ran:", should_auto_run_backtest_for_ai(has_backtest_run=True, user_requested_ai=True, allow_auto_run=True))
    print("  allowed:", should_auto_run_backtest_for_ai(has_backtest_run=False, user_requested_ai=True, allow_auto_run=True))
    print("  blocked:", should_auto_run_backtest_for_ai(has_backtest_run=False, user_requested_ai=True, allow_auto_run=False))
    print("")
    print("AI context preview:")
    print(context.to_ai_context(max_strategy_chars=500)[:1800])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
