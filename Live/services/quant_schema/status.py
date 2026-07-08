from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .migrations import migrate_quant_schema, quant_table_counts


def _repo_root(start: Path) -> Path:
    start = start.resolve()
    for candidate in [start, *start.parents]:
        if (candidate / "Live" / "app.py").exists():
            return candidate
        if candidate.name.lower() == "live" and (candidate / "app.py").exists():
            return candidate.parent
    return start


def _db_imports():
    from services.database.config import load_database_config
    try:
        from services.database.backend import connect_database
    except Exception:
        from services.database.connections import connect_database  # type: ignore
    return load_database_config, connect_database


def main() -> int:
    parser = argparse.ArgumentParser(description="Check/migrate typed quant research schema.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--backend", choices=["sqlite", "postgres"], default=None)
    parser.add_argument("--migrate", action="store_true")
    args = parser.parse_args()

    repo = _repo_root(args.repo_root or Path.cwd())
    (repo / "Live" / "data" / "catalog").mkdir(parents=True, exist_ok=True)

    load_database_config, connect_database = _db_imports()
    config = load_database_config(repo_root=str(repo), backend=args.backend)

    out = {
        "repo_root": str(repo),
        "backend_requested": args.backend,
        "migrated": False,
        "counts": {},
        "status": "UNKNOWN",
    }

    try:
        with connect_database(config) as db:
            if args.migrate:
                migrate_quant_schema(db)
                out["migrated"] = True
            out["counts"] = quant_table_counts(db)
        out["status"] = "PASS"
        print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0
    except Exception as exc:
        out["status"] = "FAIL"
        out["error"] = f"{type(exc).__name__}: {exc}"
        print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
