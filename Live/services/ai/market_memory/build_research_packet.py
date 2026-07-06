from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def find_repo_root(start: Path) -> Path:
    start = start.resolve()
    for candidate in [start, *start.parents]:
        if (candidate / "Live" / "app.py").exists() and (candidate / "Live" / "services").is_dir():
            return candidate
        if (candidate / "app.py").exists() and candidate.name.lower() == "live":
            return candidate.parent
    raise SystemExit("Could not locate repo root containing Live/app.py")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an Auto Lab research packet from persistent market memory.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--theme", default="")
    parser.add_argument("--max-symbols", type=int, default=12)
    parser.add_argument("--print-json", action="store_true")
    args = parser.parse_args()

    repo_root = find_repo_root(args.repo_root or Path.cwd())
    live_root = repo_root / "Live"

    if str(live_root) not in sys.path:
        sys.path.insert(0, str(live_root))

    from services.ai.market_memory.research_packet import build_research_packet, write_research_packet

    paths = write_research_packet(live_root, theme=args.theme, max_symbols=args.max_symbols)
    packet = build_research_packet(live_root, theme=args.theme, max_symbols=args.max_symbols)

    print("Market memory research packet complete.")
    print(f"- repo_root: {repo_root}")
    print(f"- requested_theme: {args.theme or 'none'}")
    print(f"- suggested_symbols: {paths.get('suggested_symbols')}")
    print(f"- preferred_strategy_families: {paths.get('preferred_strategy_families')}")
    print(f"- markdown_path: {paths.get('markdown_path')}")
    print(f"- json_path: {paths.get('json_path')}")
    print()
    print("Research/simulation only. No broker calls or trade execution were made.")

    if args.print_json:
        print(json.dumps(packet, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
