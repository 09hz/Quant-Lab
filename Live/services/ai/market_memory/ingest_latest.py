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
    parser = argparse.ArgumentParser(description="Ingest latest local Newsroom/Auto Lab artifacts into persistent market memory.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--seed-sample", action="store_true")
    parser.add_argument("--print-json", action="store_true")
    args = parser.parse_args()

    repo_root = find_repo_root(args.repo_root or Path.cwd())
    live_root = repo_root / "Live"

    if str(live_root) not in sys.path:
        sys.path.insert(0, str(live_root))

    from services.ai.market_memory.ingest import ingest_latest_artifacts
    from services.ai.market_memory.reports import write_memory_reports

    result = ingest_latest_artifacts(
        live_root=live_root,
        limit=args.limit,
        seed_sample=args.seed_sample,
    )
    reports = write_memory_reports(live_root)
    result["reports"] = reports

    print("Market memory latest-artifact ingest complete.")
    print(f"- repo_root: {repo_root}")
    print(f"- observed_count: {result.get('observed_count')}")
    print(f"- ingested_count: {result.get('ingested_count')}")
    print(f"- counts: {result.get('counts')}")
    print(f"- market_report_path: {reports.get('market_report_path')}")
    print(f"- relationship_report_path: {reports.get('relationship_report_path')}")
    print(f"- entity_report_path: {reports.get('entity_report_path')}")
    print(f"- db_path: {reports.get('db_path')}")
    print()
    print("Research/simulation only. No broker calls or trade execution were made.")

    if args.print_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
