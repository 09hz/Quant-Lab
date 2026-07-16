from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Any

from .config import DatabaseConfig


@dataclass
class DatabaseConnection:
    conn: Any
    backend: str
    schema: str = "algotrader"

    def cursor(self):
        return self.conn.cursor()

    def commit(self) -> None:
        self.conn.commit()

    def rollback(self) -> None:
        try:
            self.conn.rollback()
        except Exception:
            pass

    def close(self) -> None:
        self.conn.close()

    def placeholder(self) -> str:
        return "%s" if self.backend == "postgres" else "?"

    def __enter__(self) -> "DatabaseConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()


def _safe_schema_name(raw: str | None) -> str:
    schema = "".join(ch for ch in (raw or "algotrader") if ch.isalnum() or ch == "_")
    return schema or "algotrader"


def connect_database(config: DatabaseConfig) -> DatabaseConnection:
    if config.is_sqlite:
        if not config.sqlite_path:
            raise ValueError("SQLite backend requires sqlite_path. Pass repo_root or set ALGOTRADER_SQLITE_DB_PATH.")
        path = Path(config.sqlite_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return DatabaseConnection(conn=conn, backend="sqlite", schema=config.schema)

    if config.is_postgres:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except Exception as exc:
            raise RuntimeError(
                'PostgreSQL backend requires psycopg. Run: python -m pip install "psycopg[binary]"'
            ) from exc

        if config.database_url:
            conn = psycopg.connect(config.database_url, row_factory=dict_row)
        else:
            if not config.password:
                raise ValueError("Missing ALGOTRADER_DB_PASSWORD in this PowerShell session.")
            conn = psycopg.connect(
                host=config.host,
                port=config.port,
                dbname=config.database,
                user=config.user,
                password=config.password,
                row_factory=dict_row,
            )

        schema = _safe_schema_name(config.schema)
        with conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
            cur.execute(f"SET search_path TO {schema}, public")
        conn.commit()
        return DatabaseConnection(conn=conn, backend="postgres", schema=schema)

    raise ValueError(f"Unsupported database backend: {config.backend}")
