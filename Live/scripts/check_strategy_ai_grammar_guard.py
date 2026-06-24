from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.ai.strategy_grammar_guard import (  # noqa: E402
    augment_strategy_ai_prompt,
    build_strategy_grammar_reference,
    format_grammar_issues,
    validate_strategy_lab_script,
)


BAD_SAMPLE = """
fast = ta.ema(close, 9)
slow = ta.ema(close, 21)
atr = ta.atr(close, 14)
atrSma = ta.sma(atr, 14)
volOk = atr > 0.1 and atr > atrSma * 0.8
longSetup = close > slow and r >= 40 and r <= 65 and volOk
sell when shortSetup
buy when exitShort
""".strip()


GOOD_SAMPLE = """
fast = ta.ema(close, 9)
slow = ta.ema(close, 21)
trend = ta.ema(close, 50)
r = ta.rsi(close, 14)
atr = ta.atr(close, 14)
atrSma = ta.sma(atr, 14)

bullCross = ta.crossover(fast, slow)
bearCross = ta.crossunder(fast, slow)

inSession = session("0930-1600")
aboveTrend = close > trend
belowTrend = close < trend

rsiLowOk = r > 40
rsiHighOk = r < 65
volAbsOk = atr > 0.1
volTrendOk = atr > atrSma

longSetup = inSession and bullCross and aboveTrend and rsiLowOk and rsiHighOk and volAbsOk and volTrendOk
exitSetup = bearCross or belowTrend

plot fast
plot slow
plot trend

buy when longSetup
sell when exitSetup
""".strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Strategy AI grammar guard.")
    parser.add_argument("--sample-output", default=None, help="Strategy script text to validate.")
    parser.add_argument("--file", default=None, help="Path to a strategy script/text file to validate.")
    parser.add_argument("--show-reference", action="store_true", help="Print the injected grammar reference.")
    parser.add_argument("--good", action="store_true", help="Validate a known-good sample.")
    args = parser.parse_args()

    if args.show_reference:
        print(build_strategy_grammar_reference())
        return 0

    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    elif args.sample_output is not None:
        text = args.sample_output.replace("`n", "\n")
    elif args.good:
        text = GOOD_SAMPLE
    else:
        text = BAD_SAMPLE

    issues = validate_strategy_lab_script(text)
    print(format_grammar_issues(issues))
    print()
    print("Augmented prompt preview:")
    print(augment_strategy_ai_prompt("Improve this strategy. Return script only."))
    return 0 if not issues else 2


if __name__ == "__main__":
    raise SystemExit(main())
