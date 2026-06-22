from __future__ import annotations

import argparse
import sys
from pathlib import Path


LIVE_ROOT = Path(__file__).resolve().parents[1]
if str(LIVE_ROOT) not in sys.path:
    sys.path.insert(0, str(LIVE_ROOT))


from services.ai.strategy_context import (  # noqa: E402
    build_ai_prompt_with_context,
    build_strategy_context,
    write_context_exports,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a demo Strategy Context export for JSON/Markdown/AI wiring tests."
    )
    parser.add_argument("--symbol", default="MSFT")
    parser.add_argument("--timeframe", default="1 min")
    parser.add_argument("--start", default="2026-06-15")
    parser.add_argument("--end", default="2026-06-18")
    parser.add_argument("--output-dir", default="strategy_context_exports")
    parser.add_argument("--stem", default="")
    parser.add_argument(
        "--question",
        default="Explain what looks risky or incomplete in this example strategy context.",
    )
    args = parser.parse_args()

    stem = args.stem or f"{args.symbol}_{args.timeframe.replace(' ', '_')}_strategy_context"

    context = build_strategy_context(
        symbol=args.symbol,
        timeframe=args.timeframe,
        start=args.start,
        end=args.end,
        strategy_name="Demo moving average crossover",
        strategy_text=(
            "# Demo only\n"
            "fast = ta.sma(close, 9)\n"
            "slow = ta.sma(close, 21)\n"
            "buy = crossover(fast, slow)\n"
            "sell = crossunder(fast, slow)\n"
        ),
        initial_cash=100000,
        quantity=10,
        commission=0,
        slippage=0,
        backtest_summary={
            "total_pnl": 0,
            "trade_count": 0,
            "win_rate": None,
            "max_drawdown": None,
            "status": "demo_only",
        },
        validation_messages=["Demo export; no live backtest result attached."],
        user_question=args.question,
        selected_template="strategy_review",
        metadata={
            "created_by": "check_strategy_context_export.py",
            "safe_for_ai": True,
        },
    )

    paths = write_context_exports(
        context,
        output_dir=args.output_dir,
        stem=stem,
    )

    print("Strategy Context Export Check")
    print(f"JSON:     {paths['json'].resolve()}")
    print(f"Markdown: {paths['markdown'].resolve()}")
    print()
    print(context.preview())
    print()
    print("AI prompt preview:")
    print(build_ai_prompt_with_context(context=context, user_question=args.question)[:1200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
