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
        live / "services" / "data_catalog" / "postgres_setup_service.py",
        live / "services" / "data_catalog" / "postgres_status_ui.py",
        live / "services" / "data_catalog" / "postgres_status_callbacks.py",
        live / "services" / "data_catalog" / "postgres_status_self_test_v24_1_2.py",
        live / "ui" / "data_library_ui.py",
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

    from services.data_catalog.postgres_setup_service import normalize_credentials, validate_identifier
    from ui.data_library_ui import build_data_library_layout

    creds = normalize_credentials(
        host="localhost",
        port="5432",
        database="algotrader",
        schema="algotrader",
        app_user="algotrader_app",
        app_password="secret",
        admin_user="postgres",
        admin_password="admin",
    )
    assert creds.port == 5432
    assert creds.app_password == "secret"

    validate_identifier("algotrader_app", "app user")
    try:
        validate_identifier("bad-name", "app user")
        print("Expected invalid identifier to fail.")
        return 3
    except ValueError:
        pass

    ids = _collect_ids(build_data_library_layout())
    expected = {
        "data-library-postgres-status-panel",
        "data-library-pg-host",
        "data-library-pg-port",
        "data-library-pg-database",
        "data-library-pg-schema",
        "data-library-pg-app-user",
        "data-library-pg-app-password",
        "data-library-pg-admin-user",
        "data-library-pg-admin-password",
        "data-library-pg-setup-btn",
        "data-library-pg-test-typed-btn",
        "data-library-pg-check-btn",
        "data-library-pg-ingest-btn",
        "data-library-pg-setup-output",
    }
    missing_ids = expected.difference(ids)
    if missing_ids:
        print(f"Missing UI IDs: {sorted(missing_ids)}")
        return 4

    print("v24.1.2 browser PostgreSQL setup wizard self-test: PASS")
    print("Typed credential UI IDs: PASS")
    print("Setup service import: PASS")
    print("Identifier validation: PASS")
    print("No credentials were written.")
    print("No files were moved or deleted.")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
