from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


LIVE_ROOT = Path(__file__).resolve().parents[1]
if str(LIVE_ROOT) not in sys.path:
    sys.path.insert(0, str(LIVE_ROOT))


try:
    from services.config.env_loader import load_env_file
except Exception:
    load_env_file = None


if load_env_file is not None:
    try:
        load_env_file()
    except Exception:
        pass


from services.research.fred_connector import (  # noqa: E402
    build_fred_research_brief,
    curated_fred_candidates,
    format_fred_brief_markdown,
    get_fred_api_key,
    search_fred_series,
    summarize_fred_series,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the Newsroom FRED connector.")
    parser.add_argument("--query", default="inflation rate", help="Research query to route to FRED.")
    parser.add_argument("--series", default="", help="Specific FRED series ID to fetch.")
    parser.add_argument("--limit", type=int, default=4, help="Maximum curated series to include.")
    parser.add_argument("--observation-limit", type=int, default=24, help="Observation count per series.")
    parser.add_argument("--search", action="store_true", help="Use FRED API series/search for the query.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown/text.")
    args = parser.parse_args()

    api_key = get_fred_api_key()

    if args.series:
        summary = summarize_fred_series(
            args.series,
            api_key=api_key or None,
            observation_limit=args.observation_limit,
        )
        payload = {
            "api_configured": bool(api_key),
            "summary": summary.__dict__,
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"FRED API configured: {bool(api_key)}")
            if summary.error:
                print(f"ERROR: {summary.error}")
            print(f"{summary.series_id} — {summary.title}")
            print(f"Latest: {summary.latest_value} on {summary.latest_date}")
            print(f"Previous: {summary.previous_value} on {summary.previous_date}")
            print(f"Change: {summary.change}")
            print(f"Source: {summary.source_url}")
        return 0

    if args.search:
        if not api_key:
            print("FRED_API_KEY is not configured. Add it to Live/.env before using --search.")
            return 2
        results = search_fred_series(args.query, api_key=api_key, limit=max(1, args.limit))
        if args.json:
            print(json.dumps(results, indent=2, sort_keys=True))
        else:
            print(f"Top FRED API search results for: {args.query}")
            for item in results:
                print(f"- {item.get('id')} — {item.get('title')} ({item.get('frequency')}, {item.get('units')})")
        return 0

    brief = build_fred_research_brief(
        args.query,
        api_key=api_key or None,
        max_series=max(1, args.limit),
        observation_limit=args.observation_limit,
    )

    if args.json:
        print(json.dumps(brief, indent=2, sort_keys=True))
    else:
        if not api_key:
            print("FRED_API_KEY is not configured; showing curated official links only.")
            print("")
            for candidate in curated_fred_candidates(args.query, limit=max(1, args.limit)):
                print(f"- {candidate.series_id} — {candidate.title}")
                print(f"  Reason: {candidate.reason}")
                print(f"  Link: {candidate.source_url}")
        else:
            print(format_fred_brief_markdown(brief))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
