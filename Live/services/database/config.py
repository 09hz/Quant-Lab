from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DatabaseConfig:
    backend: str = "sqlite"
    sqlite_path: str | None = None
    database_url: str | None = None
    host: str = "localhost"
    port: int = 5432
    database: str = "algotrader"
    user: str = "algotrader_app"
    password: str | None = None
    schema: str = "algotrader"

    @property
    def is_sqlite(self) -> bool:
        return self.backend.lower() == "sqlite"

    @property
    def is_postgres(self) -> bool:
        return self.backend.lower() in {"postgres", "postgresql"}


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except Exception:
        return default


def _repo_root_path(repo_root: str | Path | None) -> Path | None:
    if repo_root is None:
        return None
    return Path(repo_root).resolve()


def load_database_config(repo_root: str | Path | None = None, backend: str | None = None) -> DatabaseConfig:
    selected = (backend or os.environ.get("ALGOTRADER_DB_BACKEND") or "sqlite").strip().lower()
    if selected == "postgresql":
        selected = "postgres"

    root = _repo_root_path(repo_root)
    sqlite_path = os.environ.get("ALGOTRADER_SQLITE_DB_PATH")
    if not sqlite_path and root is not None:
        sqlite_path = str(root / "Live" / "data" / "catalog" / "data_catalog.sqlite")

    return DatabaseConfig(
        backend=selected,
        sqlite_path=sqlite_path,
        database_url=os.environ.get("ALGOTRADER_DATABASE_URL") or None,
        host=os.environ.get("ALGOTRADER_DB_HOST") or "localhost",
        port=_int_env("ALGOTRADER_DB_PORT", 5432),
        database=os.environ.get("ALGOTRADER_DB_NAME") or "algotrader",
        user=os.environ.get("ALGOTRADER_DB_USER") or "algotrader_app",
        password=os.environ.get("ALGOTRADER_DB_PASSWORD") or None,
        schema=os.environ.get("ALGOTRADER_DB_SCHEMA") or "algotrader",
    )


def masked_database_config(config: DatabaseConfig) -> dict[str, Any]:
    return {
        "backend": config.backend,
        "sqlite_path": config.sqlite_path if config.is_sqlite else None,
        "database_url_set": bool(config.database_url),
        "host": config.host if config.is_postgres else None,
        "port": config.port if config.is_postgres else None,
        "database": config.database if config.is_postgres else None,
        "user": config.user if config.is_postgres else None,
        "schema": config.schema if config.is_postgres else None,
        "password_set": bool(config.password) if config.is_postgres else None,
    }

# --- v24.1.1 database config compatibility helper ---
def describe_database_config(config):
    """Return a safe, non-secret dictionary describing a database config.

    This intentionally does not return the database password.
    """
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
# --- end v24.1.1 database config compatibility helper ---
