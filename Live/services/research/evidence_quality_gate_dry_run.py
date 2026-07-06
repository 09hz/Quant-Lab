from __future__ import annotations

import argparse
import re
from pathlib import Path

from services.research.evidence_quality_gate import decide_evidence_item


URL_RE = re.compile(r"https?://[^\s'\"<>),]+")


def find_live_root(start: Path) -> Path:
    start = start.resolve()
    for candidate in [start, *start.parents]:
        if (candidate / "Live" / "services").is_dir():
            return candidate / "Live"
        if (candidate / "services").is_dir() and (candidate / "ui").is_dir():
            return candidate
    raise SystemExit("Could not locate Live root.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run the AI evidence quality gate against URLs embedded in Newsroom code.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--min-score", type=int, default=70)
    args = parser.parse_args()

    root = find_live_root(args.repo_root or Path.cwd())
    paths = [root / "services" / "research", root / "services" / "ai", root / "ui"]

    total = 0
    blocked = 0
    for folder in paths:
        if not folder.exists():
            continue
        for path in folder.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for match in URL_RE.finditer(text):
                total += 1
                url = match.group(0).rstrip("].,;")
                item = {"url": url, "source": str(path.relative_to(root))}
                decision = decide_evidence_item(item, min_score=args.min_score)
                if not decision.keep:
                    blocked += 1
                    line = text.count("\n", 0, match.start()) + 1
                    print(f"BLOCK score={decision.score} grade={decision.grade} {path.relative_to(root)}:{line} {url}")

    print()
    print(f"Dry-run complete. URLs checked={total}; would block={blocked}; min_score={args.min_score}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
