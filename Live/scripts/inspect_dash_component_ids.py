from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path


ID_PATTERNS = [
    re.compile(r"\bid\s*=\s*['\"]([^'\"]+)['\"]"),
    re.compile(r"['\"]id['\"]\s*:\s*['\"]([^'\"]+)['\"]"),
    re.compile(r"\bdcc\.[A-Za-z0-9_]+\([^)]*?id\s*=\s*['\"]([^'\"]+)['\"]", re.DOTALL),
    re.compile(r"\bhtml\.[A-Za-z0-9_]+\([^)]*?id\s*=\s*['\"]([^'\"]+)['\"]", re.DOTALL),
]


def iter_python_files(root: Path):
    for path in sorted(root.rglob("*.py")):
        parts = set(path.parts)
        if "__pycache__" in parts:
            continue
        if ".venv" in parts or "venv" in parts:
            continue
        yield path


def extract_ids(text: str) -> list[str]:
    found: list[str] = []
    for pattern in ID_PATTERNS:
        found.extend(pattern.findall(text))
    return sorted(set(found))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Statically inspect Dash component ids without importing the app."
    )
    parser.add_argument("--root", default="Live", help="Root folder to scan. Default: Live")
    parser.add_argument("--filter", default="", help="Case-insensitive substring filter for ids or file paths.")
    parser.add_argument("--summary-only", action="store_true", help="Only print grouped counts.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    needle = args.filter.lower().strip()

    by_file: dict[Path, list[str]] = {}
    reverse: dict[str, list[Path]] = defaultdict(list)

    for path in iter_python_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        ids = extract_ids(text)
        if needle:
            ids = [
                component_id
                for component_id in ids
                if needle in component_id.lower() or needle in str(path).lower()
            ]

        if not ids:
            continue

        by_file[path] = ids
        for component_id in ids:
            reverse[component_id].append(path)

    print("Dash Component ID Inspection")
    print(f"Root: {root}")
    print(f"Files with ids: {len(by_file)}")
    print(f"Unique ids: {len(reverse)}")
    if needle:
        print(f"Filter: {needle}")

    duplicates = {component_id: paths for component_id, paths in reverse.items() if len(paths) > 1}
    print(f"Duplicate ids across files: {len(duplicates)}")

    if args.summary_only:
        print()
        print("Top files by id count:")
        for path, ids in sorted(by_file.items(), key=lambda item: len(item[1]), reverse=True)[:20]:
            print(f"  {len(ids):>4}  {path.relative_to(root)}")
        return 0

    print()
    for path, ids in sorted(by_file.items(), key=lambda item: str(item[0])):
        rel = path.relative_to(root)
        print(f"[{rel}]")
        for component_id in ids:
            marker = "* " if component_id in duplicates else "  "
            print(f"{marker}{component_id}")
        print()

    if duplicates:
        print("Duplicate IDs:")
        for component_id, paths in sorted(duplicates.items()):
            print(f"  {component_id}")
            for path in paths:
                print(f"    - {path.relative_to(root)}")
        print()
        print("Note: some duplicate detections can be false positives from static scanning.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
