from __future__ import annotations

from pathlib import Path
import ast
import inspect
import sys


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _collect_ids(component):
    found = set()
    stack = [component]
    while stack:
        item = stack.pop()
        if item is None:
            continue
        if isinstance(item, (list, tuple)):
            stack.extend(item)
            continue
        item_id = getattr(item, "id", None)
        if item_id:
            found.add(str(item_id))
        children = getattr(item, "children", None)
        if isinstance(children, (list, tuple)):
            stack.extend(children)
        elif children is not None:
            stack.append(children)
    return found


def main() -> int:
    repo_root = _repo_root()
    live_root = repo_root / "Live"
    files = [
        live_root / "ui" / "data_library_ui.py",
        live_root / "services" / "data_catalog" / "data_library_queries.py",
        live_root / "services" / "data_catalog" / "data_library_callbacks.py",
        live_root / "services" / "data_catalog" / "scanner.py",
        live_root / "services" / "data_catalog" / "storage.py",
        live_root / "app.py",
    ]

    for path in files:
        if not path.exists():
            print(f"Missing required file: {path}")
            return 2
        ast.parse(path.read_text(encoding="utf-8", errors="replace"))

    app_text = (live_root / "app.py").read_text(encoding="utf-8", errors="replace")
    if "v23.4 Data Library UI Integration" not in app_text:
        print("app.py missing v23.4 Data Library integration marker.")
        return 3

    if str(live_root) not in sys.path:
        sys.path.insert(0, str(live_root))

    from ui.data_library_ui import build_data_library_layout
    from services.data_catalog.data_library_queries import (
        get_artifact_preview,
        query_artifacts,
        refresh_or_scan_catalog,
    )

    layout = build_data_library_layout()
    ids = _collect_ids(layout)
    expected = {
        "data-library-root",
        "data-library-refresh-btn",
        "data-library-scan-btn",
        "data-library-artifact-type-filter",
        "data-library-extension-filter",
        "data-library-search-input",
        "data-library-artifact-select",
        "data-library-preview",
    }
    missing = expected.difference(ids)
    if missing:
        print(f"Data Library layout missing IDs: {sorted(missing)}")
        return 4

    result = refresh_or_scan_catalog(live_root=live_root, do_scan=False, limit=25)
    if "counts" not in result or "artifacts" not in result:
        print(f"Bad refresh result: {result}")
        return 5

    artifacts = result.get("artifacts", [])
    if not artifacts:
        result = refresh_or_scan_catalog(live_root=live_root, do_scan=True, limit=25)
        artifacts = result.get("artifacts", [])

    if not artifacts:
        print("Catalog has no artifacts after refresh/scan.")
        return 6

    preview = get_artifact_preview(live_root=live_root, artifact_id=artifacts[0]["artifact_id"])
    if not isinstance(preview, str) or len(preview) < 20:
        print("Artifact preview failed.")
        return 7

    print("v23.4 Data Library UI self-test: PASS")
    print(f"artifact_count_visible: {len(artifacts)}")
    print(f"catalog_counts: {result.get('counts')}")
    print(f"first_artifact: {artifacts[0].get('file_name')}")
    print("No files were moved or deleted.")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
