
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from services.research.official_source_resolvers import resolve_official_sources, write_candidates_csv


def _split_csv(value: str | None) -> list[str]:
    return [x.strip().upper() for x in str(value or "").replace("\n", ",").split(",") if x.strip()]


def find_live_root(start: Path) -> Path:
    start = start.resolve()
    for candidate in [start, *start.parents]:
        if (candidate / "Live" / "services").is_dir():
            return candidate / "Live"
        if (candidate / "services").is_dir() and (candidate / "ui").is_dir():
            return candidate
    raise SystemExit("Could not locate Live root.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate official non-search Newsroom source candidates.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--query", default="GDP CPI unemployment yields FOMC industrial production")
    parser.add_argument("--symbols", default="AAPL,MSFT,NVDA,AMD")
    parser.add_argument("--out", default="data/autolab_report/newsroom_official_source_candidates.csv")
    args = parser.parse_args()

    live_root = find_live_root(args.repo_root or Path.cwd())
    candidates = resolve_official_sources(args.query, symbols=_split_csv(args.symbols), bea_api_key=os.getenv("BEA_API_KEY", "YOUR_BEA_API_KEY"))

    out = Path(args.out)
    if not out.is_absolute():
        out = live_root / out

    write_candidates_csv(out, candidates)

    print(f"Wrote {len(candidates)} official source candidate(s): {out}")
    for row in candidates[:20]:
        print(json.dumps(row.as_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
