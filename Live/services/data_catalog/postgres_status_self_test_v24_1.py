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
        elif children is not None and not isinstance(children, str):
            stack.append(children)
    return found


def main() -> int:
    repo = _repo_root()
    live = repo / "Live"
    required = [
        live / "services" / "data_catalog" / "postgres_status_service.py",
        live / "services" / "data_catalog" / "postgres_status_ui.py",
        live / "services" / "data_catalog" / "postgres_status_callbacks.py",
        live / "ui" / "data_library_ui.py",
        live / "services" / "data_catalog" / "data_library_callbacks.py",
        repo / "scripts" / "setup_postgres.ps1",
        repo / "scripts" / "set_postgres_env.ps1",
        repo / "scripts" / "check_postgres.ps1",
        repo / ".env.example",
        repo / "docs" / "postgresql_setup.md",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        print("Missing files:")
        for path in missing:
            print(f"- {path}")
        return 2

    for path in required:
        if path.suffix == ".py":
            ast.parse(path.read_text(encoding="utf-8", errors="replace"))

    if str(live) not in sys.path:
        sys.path.insert(0, str(live))

    from ui.data_library_ui import build_data_library_layout
    from services.data_catalog.postgres_status_service import get_postgres_status

    ids = _collect_ids(build_data_library_layout())
    expected = {
        "data-library-postgres-status-panel",
        "data-library-pg-check-btn",
        "data-library-pg-ingest-btn",
        "data-library-pg-status-output",
        "data-library-pg-table-counts",
        "data-library-pg-last-run",
        "data-library-pg-skipped-summary",
    }
    missing_ids = expected.difference(ids)
    if missing_ids:
        print(f"Missing UI IDs: {sorted(missing_ids)}")
        return 3

    status = get_postgres_status(repo_root=repo, migrate=False)
    assert status.backend == "postgres"

    gitignore = (repo / ".gitignore").read_text(encoding="utf-8", errors="replace") if (repo / ".gitignore").exists() else ""
    for token in [".env.local", ".env.*.local", "!.env.example"]:
        if token not in gitignore:
            print(f".gitignore missing token: {token}")
            return 4

    print("v24.1 PostgreSQL setup + Data Library status panel self-test: PASS")
    print("UI panel IDs: PASS")
    print("Callback modules: PASS")
    print("Setup scripts: PASS")
    print("Env example/gitignore protection: PASS")
    print("No files were moved or deleted.")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
