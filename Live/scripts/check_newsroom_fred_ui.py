from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_env() -> None:
    try:
        from services.config.env_loader import load_project_env
        load_project_env()
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Newsroom FRED UI adapter output.")
    parser.add_argument("--query", default="inflation rate", help="Research query to test.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of readable text.")
    args = parser.parse_args()

    _load_env()

    from services.research.fred_newsroom_adapter import build_fred_newsroom_items

    items = build_fred_newsroom_items(args.query)

    if args.json:
        print(json.dumps(items, indent=2))
        return 0

    print(f"Query: {args.query}")
    print(f"Items: {len(items)}")
    print("")
    for item in items:
        print(f"- {item.get('source')} | {item.get('kind')} | {item.get('confidence')}")
        print(f"  {item.get('title')}")
        print(f"  {item.get('summary')}")
        print(f"  {item.get('url')}")
        print("")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
