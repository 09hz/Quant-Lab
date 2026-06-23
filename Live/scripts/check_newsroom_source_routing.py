from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LIVE = Path(__file__).resolve().parents[1]
if str(LIVE) not in sys.path:
    sys.path.insert(0, str(LIVE))

from services.research.source_relevance import route_sources_for_query
from services.research.search_links import build_source_search_links

def main() -> int:
    parser = argparse.ArgumentParser(description="Check Newsroom source relevance routing.")
    parser.add_argument("--query", default="inflation rate")
    parser.add_argument("--sources", default="fred,bls,bea,fed,treasury,sec,news,imf,worldbank,wef")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    routes = route_sources_for_query(args.query, sources, include_skipped=True)
    links = build_source_search_links(args.query, sources, include_skipped=True)
    payload = {
        "query": args.query,
        "routes": [route.__dict__ for route in routes],
        "links": [{"title": link.title, "source": link.source, "type": link.result_type, "confidence": link.confidence, "url": link.url, "summary": link.summary} for link in links],
    }
    if args.json:
        print(json.dumps(payload, indent=2))
        return 0
    print("Newsroom Source Routing Check")
    print(f"Query: {args.query}\n")
    print("Routes:")
    for route in routes:
        state = "include" if route.is_relevant else "skip"
        print(f"  - {route.source_name}: {route.relevance} ({state})")
        print(f"    {route.reason}")
    print("\nGenerated links:")
    for link in links:
        print(f"  - {link.source}: {link.title}")
        print(f"    type={link.result_type} confidence={link.confidence}")
        print(f"    {link.url or '[no link: skipped/not relevant]'}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
