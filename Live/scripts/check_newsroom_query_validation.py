from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

LIVE_ROOT = Path(__file__).resolve().parents[1]
if str(LIVE_ROOT) not in sys.path:
    sys.path.insert(0, str(LIVE_ROOT))

from services.research.query_planner import plan_query
from services.research.search_links import build_source_search_links
from services.research.result_validator import validate_research_url

def main() -> int:
    parser = argparse.ArgumentParser(description="Check Newsroom query planning/search link validation.")
    parser.add_argument("--query", default="inflation rate", help="Research prompt/query.")
    parser.add_argument("--sources", default="fred,bls,bea,federal_reserve,sec_edgar,google_news", help="Comma-separated source ids.")
    parser.add_argument("--validate", action="store_true", help="Perform live HTTP validation.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args()

    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    planned = plan_query(args.query, selected_sources=sources)
    links = build_source_search_links(args.query, sources)
    rows = []
    for link in links:
        validation = validate_research_url(link.url, fetch=args.validate)
        rows.append({
            "title": link.title,
            "source": link.source,
            "type": link.result_type,
            "confidence": link.confidence,
            "validation_status": validation.status,
            "validation_message": validation.message,
            "url": link.url,
            "summary": link.summary,
        })

    if args.json:
        print(json.dumps({"query": args.query, "planned_terms": list(planned.terms), "tickers": list(planned.tickers), "source_hints": list(planned.source_hints), "results": rows}, indent=2))
        return 0

    print("Newsroom Query Validation Check")
    print(f"Query: {args.query}")
    print(f"Expanded terms: {', '.join(planned.terms)}")
    print(f"Tickers: {', '.join(planned.tickers) if planned.tickers else 'none'}")
    print(f"Sources: {', '.join(sources)}")
    print(f"Live validation: {args.validate}")
    print()
    for i, row in enumerate(rows, 1):
        print(f"{i}. {row['title']}")
        print(f"   Source: {row['source']}")
        print(f"   Type: {row['type']}")
        print(f"   Confidence: {row['confidence']}")
        print(f"   Validation: {row['validation_status']} - {row['validation_message']}")
        print(f"   URL: {row['url']}")
        print()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
