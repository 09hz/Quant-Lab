from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.research.result_hygiene import clean_newsroom_results, summarize_hygiene


SAMPLES = [
    {
        "id": "fred-cpiaucsl",
        "source": "FRED",
        "title": "CPIAUCSL: Consumer Price Index",
        "summary": "Latest value: 320.58. Prior value: 319.80. Frequency: Monthly.",
        "url": "https://fred.stlouisfed.org/series/CPIAUCSL",
        "selectable": True,
        "type": "fred_series",
    },
    {
        "id": "bea-search",
        "source": "BEA",
        "title": "BEA Search",
        "summary": "Search results for inflation rate.",
        "url": "https://www.bea.gov/search?search_api_fulltext=inflation%20rate",
        "selectable": True,
    },
    {
        "id": "fed-broken",
        "source": "Federal Reserve",
        "title": "Page not found",
        "summary": "404 page not found",
        "url": "https://www.federalreserve.gov/bad-page",
        "selectable": True,
        "http_status": 404,
    },
    {
        "id": "fiscal-dataset",
        "source": "FiscalData",
        "title": "Debt to the Penny",
        "summary": "Direct Treasury dataset page.",
        "url": "https://fiscaldata.treasury.gov/datasets/debt-to-the-penny/debt-to-the-penny",
        "selectable": True,
    },
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Newsroom result hygiene classification.")
    parser.add_argument("--json", action="store_true", help="Print full cleaned JSON.")
    args = parser.parse_args()

    cleaned = clean_newsroom_results(SAMPLES)
    print(f"Hygiene summary: {summarize_hygiene(cleaned)}")
    print()

    if args.json:
        print(json.dumps(cleaned, indent=2))
        return 0

    for item in cleaned:
        print(f"- {item.get('source')} | {item.get('title')}")
        print(f"  visible={item.get('visible', True)} selectable={item.get('selectable')} hygiene={item.get('hygiene_status')}")
        print(f"  reason={item.get('hygiene_reason', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
