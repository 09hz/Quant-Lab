from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Iterable

from .source_quality import PREFERRED_SOURCE_HINTS, grade_url


URL_RE = re.compile(r"https?://[^\s'\"<>),]+")


def _candidate_files(root: Path) -> Iterable[Path]:
    folders = [
        root / "services" / "research",
        root / "services" / "ai",
        root / "ui",
        root / "config",
    ]
    suffixes = {".py", ".json", ".yaml", ".yml", ".md", ".txt", ".csv"}
    for folder in folders:
        if not folder.exists():
            continue
        for path in folder.rglob("*"):
            if path.is_file() and path.suffix.lower() in suffixes:
                yield path


def extract_urls(root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for path in _candidate_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for match in URL_RE.finditer(text):
            url = match.group(0).rstrip("].,;")
            key = (str(path), url)
            if key in seen:
                continue
            seen.add(key)

            line_no = text.count("\n", 0, match.start()) + 1
            quality = grade_url(url)
            row = {
                "file": str(path.relative_to(root)),
                "line": str(line_no),
            }
            row.update({k: str(v) for k, v in quality.as_dict().items()})
            rows.append(row)

    rows.sort(key=lambda r: (int(r["score"]), r["file"], int(r["line"])))
    return rows


def write_audit(root: Path, rows: list[dict[str, str]]) -> tuple[Path, Path]:
    csv_path = root / "newsroom_source_quality_audit.csv"
    md_path = root / "newsroom_source_quality_audit.md"

    fieldnames = ["file", "line", "url", "score", "grade", "flags", "recommendation"]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    bad = [r for r in rows if int(r["score"]) < 70]
    lines: list[str] = []
    lines.append("# Newsroom Source Quality Audit")
    lines.append("")
    lines.append(f"Total URLs found: **{len(rows)}**")
    lines.append(f"Weak/bad URLs below score 70: **{len(bad)}**")
    lines.append("")
    lines.append("## Why this matters")
    lines.append("")
    lines.append("Landing pages and search result URLs are weak evidence. They make the AI summarize generic pages instead of specific filings, releases, tables, series, PDFs, CSVs, or articles.")
    lines.append("")
    lines.append("## Weakest URLs")
    lines.append("")
    lines.append("| Score | Grade | File | Line | Flags | URL |")
    lines.append("|---:|---|---|---:|---|---|")
    for row in bad[:50]:
        lines.append(
            f"| {row['score']} | {row['grade']} | `{row['file']}` | {row['line']} | {row['flags']} | {row['url']} |"
        )

    lines.append("")
    lines.append("## Preferred source guidance")
    lines.append("")
    for name, hints in PREFERRED_SOURCE_HINTS.items():
        lines.append(f"### {name}")
        for hint in hints:
            lines.append(f"- {hint}")
        lines.append("")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return csv_path, md_path


def find_live_root(start: Path) -> Path:
    start = start.resolve()
    for candidate in [start, *start.parents]:
        if (candidate / "Live" / "services").is_dir():
            return candidate / "Live"
        if (candidate / "services").is_dir() and (candidate / "ui").is_dir():
            return candidate
    raise SystemExit("Could not locate Live root.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Newsroom URLs for landing/search pages and weak evidence links.")
    parser.add_argument("--repo-root", type=Path, default=None)
    args = parser.parse_args()

    root = find_live_root(args.repo_root or Path.cwd())
    rows = extract_urls(root)
    csv_path, md_path = write_audit(root, rows)

    print("Newsroom source audit complete.")
    print(f"URLs found: {len(rows)}")
    print(f"Weak/bad URLs: {sum(1 for r in rows if int(r['score']) < 70)}")
    print(f"- {csv_path}")
    print(f"- {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
