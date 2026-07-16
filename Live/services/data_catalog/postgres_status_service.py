from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import traceback

from services.database.config import load_database_config

try:
    from services.database.config import describe_database_config
except Exception:
    def describe_database_config(config):
        backend = str(getattr(config, "backend", "sqlite") or "sqlite").lower()
        is_postgres = backend in {"postgres", "postgresql"}
        return {
            "backend": "postgres" if is_postgres else backend,
            "sqlite_path": getattr(config, "sqlite_path", None) if not is_postgres else None,
            "database_url_set": bool(getattr(config, "database_url", None)),
            "host": getattr(config, "host", None) if is_postgres else None,
            "port": getattr(config, "port", None) if is_postgres else None,
            "database": (
                getattr(config, "database", None)
                or getattr(config, "database_name", None)
                or getattr(config, "dbname", None)
            ) if is_postgres else None,
            "user": getattr(config, "user", None) if is_postgres else None,
            "schema": getattr(config, "schema", None) if is_postgres else None,
            "password_set": bool(getattr(config, "password", None)) if is_postgres else None,
        }

try:
    from services.database.backend import connect_database
except Exception:  # pragma: no cover
    from services.database.connections import connect_database  # type: ignore

from services.database.migrations import migrate_database


COUNT_TABLES = [
    "db_ingestion_runs",
    "db_ingested_artifacts",
    "db_json_payloads",
    "db_csv_datasets",
    "db_csv_rows",
]


@dataclass
class PostgresStatus:
    configured: bool
    connected: bool
    migrated: bool
    backend: str
    host: str | None
    port: int | None
    database: str | None
    user: str | None
    schema: str | None
    password_set: bool
    database_url_set: bool
    counts: dict[str, int]
    latest_run: dict[str, Any] | None
    skipped_summary: list[dict[str, Any]]
    error: str | None = None
    traceback_tail: str | None = None


def _repo_root(start: str | Path | None = None) -> Path:
    if start is None:
        start = Path.cwd()
    start = Path(start).resolve()
    for candidate in [start, *start.parents]:
        if (candidate / "Live" / "app.py").exists():
            return candidate
        if candidate.name.lower() == "live" and (candidate / "app.py").exists():
            return candidate.parent
    return start


def _row_to_dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return {str(i): value for i, value in enumerate(row)}


def _cursor(db):
    return db.cursor() if hasattr(db, "cursor") else db.conn.cursor()


def _count_table(db, table: str) -> int:
    if table not in COUNT_TABLES:
        raise ValueError(f"Unsupported count table: {table}")
    cur = _cursor(db)
    try:
        cur.execute(f"SELECT COUNT(*) AS n FROM {table}")
        row = cur.fetchone()
        if isinstance(row, dict):
            return int(row.get("n", 0))
        return int(row[0])
    finally:
        cur.close()


def _latest_run(db) -> dict[str, Any] | None:
    cur = _cursor(db)
    try:
        cur.execute(
            """
            SELECT run_id, backend, started_at, finished_at, status,
                   artifacts_seen, json_ingested, csv_datasets_ingested,
                   csv_rows_ingested, skipped, errors
            FROM db_ingestion_runs
            ORDER BY started_at DESC
            LIMIT 1
            """
        )
        row = cur.fetchone()
        return _row_to_dict(row) if row else None
    finally:
        cur.close()


def _skipped_summary(db, limit: int = 15) -> list[dict[str, Any]]:
    cur = _cursor(db)
    try:
        try:
            cur.execute(
                """
                SELECT status, skip_reason, COUNT(*) AS count
                FROM db_ingested_artifacts
                GROUP BY status, skip_reason
                ORDER BY COUNT(*) DESC
                LIMIT %s
                """,
                (int(limit),),
            )
        except Exception:
            # SQLite compatibility for self-tests/local fallback.
            cur.execute(
                """
                SELECT status, skip_reason, COUNT(*) AS count
                FROM db_ingested_artifacts
                GROUP BY status, skip_reason
                ORDER BY COUNT(*) DESC
                LIMIT ?
                """,
                (int(limit),),
            )
        rows = cur.fetchall()
        return [_row_to_dict(row) for row in rows]
    finally:
        cur.close()


def get_postgres_status(repo_root: str | Path | None = None, migrate: bool = False) -> PostgresStatus:
    repo = _repo_root(repo_root)
    config = load_database_config(repo_root=str(repo), backend="postgres")
    desc = describe_database_config(config)

    status = PostgresStatus(
        configured=True,
        connected=False,
        migrated=False,
        backend="postgres",
        host=desc.get("host"),
        port=desc.get("port"),
        database=desc.get("database"),
        user=desc.get("user"),
        schema=desc.get("schema"),
        password_set=bool(desc.get("password_set")),
        database_url_set=bool(desc.get("database_url_set")),
        counts={},
        latest_run=None,
        skipped_summary=[],
    )

    if not status.password_set and not status.database_url_set:
        status.error = (
            "Missing PostgreSQL password. Set ALGOTRADER_DB_PASSWORD in the shell that starts Dash, "
            "or use scripts/set_postgres_env.ps1 before launching the app."
        )
        return status

    try:
        with connect_database(config) as db:
            status.connected = True
            if migrate:
                migrate_database(db)
                status.migrated = True

            for table in COUNT_TABLES:
                try:
                    status.counts[table] = _count_table(db, table)
                except Exception:
                    status.counts[table] = -1

            try:
                status.latest_run = _latest_run(db)
            except Exception as exc:
                status.latest_run = {"error": str(exc)}

            try:
                status.skipped_summary = _skipped_summary(db)
            except Exception as exc:
                status.skipped_summary = [{"error": str(exc)}]

        return status
    except Exception as exc:
        status.error = f"{type(exc).__name__}: {exc}"
        status.traceback_tail = "\n".join(traceback.format_exc().splitlines()[-8:])
        return status


def status_as_dict(status: PostgresStatus) -> dict[str, Any]:
    return asdict(status)


def env_setup_hint() -> str:
    return (
        "$env:ALGOTRADER_DB_BACKEND = \"postgres\"\\n"
        "$env:ALGOTRADER_DB_HOST = \"localhost\"\\n"
        "$env:ALGOTRADER_DB_PORT = \"5432\"\\n"
        "$env:ALGOTRADER_DB_NAME = \"algotrader\"\\n"
        "$env:ALGOTRADER_DB_USER = \"algotrader_app\"\\n"
        "$env:ALGOTRADER_DB_SCHEMA = \"algotrader\"\\n"
        "$env:ALGOTRADER_DB_PASSWORD = Read-Host \"Enter algotrader_app password\""
    )


def main() -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Check AlgoTrader PostgreSQL status.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--migrate", action="store_true")
    args = parser.parse_args()

    status = get_postgres_status(repo_root=args.repo_root, migrate=args.migrate)
    print(json.dumps(status_as_dict(status), indent=2, default=str, sort_keys=True))
    return 0 if status.connected else 1


if __name__ == "__main__":
    raise SystemExit(main())
