from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.ai.context_packet import (
    missing_strategy_script_message,
    prepare_strategy_ai_context,
    should_warn_missing_strategy_script,
)


SAMPLE_CONTEXT = """
#Research Brief

## Selected Research Links

### 1. CPIAUCSL
- Source: FRED
- Type: fred-data
- Confidence: high
- Summary: Latest FRED value...

# Current Strategy Context

## Market Selection
- Symbol: MSFT
- Timeframe: 1 min

## Strategy Script
```
fast = ta.ema(close, 9)
slow = ta.ema(close, 21)
bullCross = ta.crossover(fast, slow)

buy when bullCross
sell when ta.crossunder(fast, slow)
```

## Current Backtest Results
Final Equity
$110,407.80
Trades
222
Win Rate
30.18%
Cumulative PnL
{"props": {"figure": {"data": ["huge chart payload"]}}}
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Strategy AI context packet preparation.")
    parser.add_argument("--file", default="", help="Optional markdown/text context file to inspect.")
    parser.add_argument("--prompt", default="Improve the current strategy. Return only script.", help="Sample user prompt.")
    parser.add_argument("--show", action="store_true", help="Print prepared context packet.")
    args = parser.parse_args()

    if args.file:
        raw = Path(args.file).read_text(encoding="utf-8")
    else:
        raw = SAMPLE_CONTEXT

    prepared, report = prepare_strategy_ai_context(raw, user_prompt=args.prompt)

    print("Strategy AI context packet check")
    print(f"Research brief: {report.has_research_brief}")
    print(f"Strategy context: {report.has_strategy_context}")
    print(f"Strategy script: {report.has_strategy_script}")
    print(f"Backtest results: {report.has_backtest_results}")
    print(f"Original chars: {report.original_chars}")
    print(f"Prepared chars: {report.prepared_chars}")
    print(f"Trimmed chart JSON: {report.trimmed_chart_json}")

    if should_warn_missing_strategy_script(args.prompt, report):
        print("WARNING:", missing_strategy_script_message())

    if args.show:
        print("\n--- Prepared Context ---")
        print(prepared)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
