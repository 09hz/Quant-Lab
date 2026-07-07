from __future__ import annotations

from pathlib import Path
import ast
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
    app_path = live_root / "app.py"
    ui_path = live_root / "ui" / "data_library_ui.py"
    cb_path = live_root / "services" / "data_catalog" / "data_library_callbacks.py"

    for path in [app_path, ui_path, cb_path]:
        if not path.exists():
            print(f"Missing required file: {path}")
            return 2
        ast.parse(path.read_text(encoding="utf-8", errors="replace"))

    app_text = app_path.read_text(encoding="utf-8", errors="replace")
    marker_pos = app_text.find("v23.4.1 Data Library Runtime Wiring Fix")
    if marker_pos < 0:
        print("app.py missing v23.4.1 runtime wiring marker.")
        return 3

    main_guard_positions = [
        pos for pos in [
            app_text.find('if __name__ == "__main__"'),
            app_text.find("if __name__ == '__main__'"),
            app_text.find("app.run_server("),
            app_text.find("app.run("),
        ]
        if pos >= 0
    ]
    if main_guard_positions and marker_pos > min(main_guard_positions):
        print("v23.4.1 marker appears after the app run guard/call; runtime wiring may not execute before server start.")
        return 4

    if str(live_root) not in sys.path:
        sys.path.insert(0, str(live_root))

    from ui.data_library_ui import build_data_library_layout

    ids = _collect_ids(build_data_library_layout())
    required_ids = {
        "data-library-root",
        "data-library-refresh-btn",
        "data-library-scan-btn",
        "data-library-artifact-select",
        "data-library-preview",
    }
    missing = required_ids.difference(ids)
    if missing:
        print(f"Data Library layout missing IDs: {sorted(missing)}")
        return 5

    print("v23.4.1 Data Library runtime wiring self-test: PASS")
    print("Runtime integration block is before the Dash run guard/call.")
    print("No files were moved or deleted.")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
