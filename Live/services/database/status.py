from __future__ import annotations

import argparse
from pathlib import Path

from .backend import connect_database
from .config import load_database_config, masked_database_config
from .migrations import migrate_database


def _repo_root(start: Path) -> Path:
    start = start.resolve()
    for candidate in [start, *start.parents]:
        if (candidate / "Live" / "app.py").exists():
            return candidate
    return start


def _count(db, table: str) -> str:
    cur = db.cursor()
    try:
        cur.execute(f"SELECT COUNT(*) AS n FROM {table}")
        row = cur.fetchone()
        if isinstance(row, dict):
            return str(row.get("n", 0))
        return str(row[0])
    except Exception as exc:
        return f"unavailable ({type(exc).__name__}: {exc})"
    finally:
        cur.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Check AlgoTrader database backend status.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--backend", choices=["sqlite", "postgres"], default=None)
    parser.add_argument("--migrate", action="store_true")
    args = parser.parse_args()

    repo = _repo_root(args.repo_root)
    config = load_database_config(repo_root=repo, backend=args.backend)
    print("AlgoTrader database config:")
    for key, value in masked_database_config(config).items():
        print(f"- {key}: {value}")

    with connect_database(config) as db:
        if args.migrate:
            migrate_database(db)
            print("migration: PASS")
        for table in ["db_ingestion_runs", "db_ingested_artifacts", "db_json_payloads", "db_csv_datasets", "db_csv_rows"]:
            print(f"{table}: {_count(db, table)}")

    print("database status: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
