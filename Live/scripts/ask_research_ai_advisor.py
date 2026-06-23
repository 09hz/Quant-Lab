from __future__ import annotations

import argparse
from pathlib import Path
import sys

LIVE_ROOT = Path(__file__).resolve().parents[1]
if str(LIVE_ROOT) not in sys.path:
    sys.path.insert(0, str(LIVE_ROOT))

try:
    from services.config.env_loader import load_app_env
    load_app_env(override=True, verbose=False)
except Exception:
    pass

from services.ai.research_aware_advisor import ResearchAwareAdvisor
from services.research.source_registry import build_default_source_registry
from services.research.research_context import ResearchContextBuilder


def main() -> int:
    parser = argparse.ArgumentParser(description="Ask the advisory AI with optional trusted research context.")
    parser.add_argument("--prompt", default="Explain what the research-aware advisor does safely.")
    parser.add_argument("--strategy-context-file", default="")
    parser.add_argument("--no-research", action="store_true")
    parser.add_argument("--include-news", action="store_true")
    parser.add_argument("--per-feed", type=int, default=2)
    parser.add_argument("--max-output-tokens", type=int, default=600)
    parser.add_argument("--export-context", action="store_true")
    parser.add_argument("--print-sources", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Build/preview context without calling the LLM.")
    args = parser.parse_args()

    if args.print_sources:
        print(build_default_source_registry().to_markdown())
        return 0

    strategy_text = ""
    if args.strategy_context_file:
        strategy_text = Path(args.strategy_context_file).read_text(encoding="utf-8")

    builder = ResearchContextBuilder()
    pack = builder.build(
        user_prompt=args.prompt,
        strategy_context=strategy_text,
        include_research=not args.no_research,
        include_news=args.include_news,
        per_feed=args.per_feed,
    )

    print("Research-aware AI Advisor")
    print(f"Research context: {'ON' if not args.no_research else 'OFF'}")
    print(f"News context: {'ON' if args.include_news else 'OFF'}")
    print(f"Strategy context chars: {len(strategy_text)}")
    print("")

    if args.export_context or args.dry_run:
        paths = pack.write_exports()
        print("[OK] Context exports_service:")
        for kind, path in paths.items():
            print(f"  {kind}: {path}")

    if args.dry_run:
        print("")
        print(pack.to_markdown()[:4000])
        return 0

    advisor = ResearchAwareAdvisor()
    result = advisor.ask(
        prompt=args.prompt,
        strategy_context=strategy_text,
        include_research=not args.no_research,
        include_news=args.include_news,
        per_feed=args.per_feed,
        max_output_tokens=args.max_output_tokens,
        export_context=args.export_context,
    )

    print(f"Context preview: {result.context_preview}")
    print("")
    if result.ok:
        print(result.response_text)
        return 0

    print("[BLOCKED/ERROR]", result.error)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
