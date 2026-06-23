from __future__ import annotations

import argparse
import sys
from pathlib import Path

LIVE_ROOT = Path(__file__).resolve().parents[1]
if str(LIVE_ROOT) not in sys.path:
    sys.path.insert(0, str(LIVE_ROOT))

from services.research.source_registry import build_default_source_registry
from services.research.news_feeds import fetch_news_feeds, news_items_markdown
from services.research.research_brief import build_research_brief


def main() -> int:
    parser = argparse.ArgumentParser(description="Check trusted research/news source registry.")
    parser.add_argument("--print-brief", action="store_true", help="Print a markdown research brief.")
    parser.add_argument("--fetch-news", action="store_true", help="Fetch RSS/Atom news from configured sources.")
    parser.add_argument("--per-feed", type=int, default=2, help="Max news items per feed.")
    args = parser.parse_args()

    sources = build_default_source_registry()
    print("Research Source Registry")
    print(f"Sources: {len(sources)}")
    print()

    for source in sources:
        feed = " feed" if source.rss_url else ""
        api = " api" if source.api_url else ""
        print(f"- {source.name} [{source.category}] ({source.reliability}){api}{feed}")

    news_items = []
    errors = []
    if args.fetch_news:
        print()
        print("Fetching news feeds...")
        news_items, errors = fetch_news_feeds(per_feed=args.per_feed)
        print(f"News items: {len(news_items)}")
        if errors:
            print(f"Feed errors: {len(errors)}")

    if args.print_brief:
        print()
        print(build_research_brief(news_items=news_items).to_markdown())

    if args.fetch_news:
        print()
        print(news_items_markdown(news_items, errors=errors))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
