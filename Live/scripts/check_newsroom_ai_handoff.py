from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


LIVE_ROOT = Path(__file__).resolve().parents[1]
if str(LIVE_ROOT) not in sys.path:
    sys.path.insert(0, str(LIVE_ROOT))


from services.research.brief_ai_handoff import (  # noqa: E402
    brief_to_strategy_ai_context,
    default_newsroom_ai_prompt,
)


SAMPLE_BRIEF = [
    {
        "id": "fred:CPIAUCSL",
        "source": "FRED",
        "title": "Consumer Price Index for All Urban Consumers",
        "series_id": "CPIAUCSL",
        "latest_date": "2026-01-01",
        "latest_value": "315.2",
        "prior_value": "314.8",
        "change": "+0.4",
        "units": "Index 1982-1984=100",
        "frequency": "Monthly",
        "url": "https://fred.stlouisfed.org/series/CPIAUCSL",
        "summary": "Sample structured FRED inflation series result.",
        "confidence": "structured-data",
    },
    {
        "id": "fred:FEDFUNDS",
        "source": "FRED",
        "title": "Effective Federal Funds Rate",
        "series_id": "FEDFUNDS",
        "latest_date": "2026-01-01",
        "latest_value": "4.50",
        "units": "Percent",
        "frequency": "Monthly",
        "url": "https://fred.stlouisfed.org/series/FEDFUNDS",
        "summary": "Sample structured FRED interest-rate series result.",
        "confidence": "structured-data",
    },
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Newsroom-to-Strategy-AI brief handoff formatting.")
    parser.add_argument("--json", action="store_true", help="Emit JSON payload instead of markdown.")
    args = parser.parse_args()

    context = brief_to_strategy_ai_context(SAMPLE_BRIEF)
    prompt = default_newsroom_ai_prompt()

    if args.json:
        print(json.dumps({"prompt": prompt, "context": context}, indent=2))
    else:
        print("# Prompt")
        print(prompt)
        print()
        print("# Context")
        print(context)

    if "Attached Research Brief" not in context:
        raise SystemExit("Missing expected research brief heading.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
