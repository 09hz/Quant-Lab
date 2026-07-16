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
        live / "services" / "database" / "config.py",
        live / "services" / "data_catalog" / "postgres_status_service.py",
        live / "services" / "data_catalog" / "postgres_status_ui.py",
        live / "services" / "data_catalog" / "postgres_status_callbacks.py",
        live / "services" / "data_catalog" / "postgres_status_self_test_v24_1.py",
        live / "services" / "data_catalog" / "postgres_status_self_test_v24_1_1.py",
        live / "ui" / "data_library_ui.py",
        live / "services" / "data_catalog" / "data_library_callbacks.py",
        repo / ".env.example",
    ]

    missing = [str(path) for path in required if not path.exists()]
    if missing:
        print("Missing required files:")
        for path in missing:
            print(f"- {path}")
        return 2

    for path in required:
        if path.suffix == ".py":
            ast.parse(path.read_text(encoding="utf-8", errors="replace"))

    if str(live) not in sys.path:
        sys.path.insert(0, str(live))

    from services.database.config import load_database_config, describe_database_config
    from services.data_catalog.postgres_status_service import get_postgres_status

    config = load_database_config(repo_root=str(repo), backend="postgres")
    desc = describe_database_config(config)
    assert desc["backend"] == "postgres", desc
    assert "password_set" in desc, desc

    status = get_postgres_status(repo_root=repo, migrate=False)
    assert status.backend == "postgres", status

    from ui.data_library_ui import build_data_library_layout

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
        print(f"Missing Data Library PostgreSQL UI IDs: {sorted(missing_ids)}")
        return 3

    print("v24.1.1 database config compatibility self-test: PASS")
    print("describe_database_config: PASS")
    print("PostgreSQL status service import: PASS")
    print("Data Library PostgreSQL panel IDs: PASS")
    print("No credentials were written.")
    print("No files were moved or deleted.")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
