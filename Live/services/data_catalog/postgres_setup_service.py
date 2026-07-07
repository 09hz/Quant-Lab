from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import os
import re


IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


@dataclass
class PostgresUiCredentials:
    host: str = "localhost"
    port: int = 5432
    database: str = "algotrader"
    schema: str = "algotrader"
    app_user: str = "algotrader_app"
    app_password: str | None = None
    admin_user: str = "postgres"
    admin_password: str | None = None


@dataclass
class PostgresSetupResult:
    ok: bool
    action: str
    messages: list[str]
    error: str | None = None


def _as_int(value: Any, default: int = 5432) -> int:
    try:
        return int(value)
    except Exception:
        return default


def normalize_credentials(
    *,
    host: Any = None,
    port: Any = None,
    database: Any = None,
    schema: Any = None,
    app_user: Any = None,
    app_password: Any = None,
    admin_user: Any = None,
    admin_password: Any = None,
) -> PostgresUiCredentials:
    return PostgresUiCredentials(
        host=str(host or "localhost").strip(),
        port=_as_int(port, 5432),
        database=str(database or "algotrader").strip(),
        schema=str(schema or "algotrader").strip(),
        app_user=str(app_user or "algotrader_app").strip(),
        app_password=str(app_password).strip() if app_password not in (None, "") else None,
        admin_user=str(admin_user or "postgres").strip(),
        admin_password=str(admin_password).strip() if admin_password not in (None, "") else None,
    )


def validate_identifier(value: str, label: str) -> None:
    if not IDENTIFIER_RE.match(value or ""):
        raise ValueError(
            f"Invalid {label}: {value!r}. Use letters, numbers, and underscores only; "
            "the first character must be a letter or underscore."
        )


def validate_setup_identifiers(creds: PostgresUiCredentials) -> None:
    validate_identifier(creds.database, "database name")
    validate_identifier(creds.schema, "schema name")
    validate_identifier(creds.app_user, "app user")
    validate_identifier(creds.admin_user, "admin user")


@contextmanager
def temporary_postgres_env(creds: PostgresUiCredentials):
    """Temporarily expose typed credentials as env vars for existing v24.0 services.

    The previous environment is restored when the callback finishes.
    """
    keys = {
        "ALGOTRADER_DB_BACKEND": "postgres",
        "ALGOTRADER_DB_HOST": creds.host,
        "ALGOTRADER_DB_PORT": str(creds.port),
        "ALGOTRADER_DB_NAME": creds.database,
        "ALGOTRADER_DB_USER": creds.app_user,
        "ALGOTRADER_DB_SCHEMA": creds.schema,
        "ALGOTRADER_DB_PASSWORD": creds.app_password or "",
    }
    old = {key: os.environ.get(key) for key in keys}
    old_url = os.environ.get("ALGOTRADER_DATABASE_URL")
    try:
        for key, value in keys.items():
            if value == "":
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        os.environ.pop("ALGOTRADER_DATABASE_URL", None)
        yield
    finally:
        for key, previous in old.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous
        if old_url is None:
            os.environ.pop("ALGOTRADER_DATABASE_URL", None)
        else:
            os.environ["ALGOTRADER_DATABASE_URL"] = old_url


def test_app_connection(creds: PostgresUiCredentials) -> PostgresSetupResult:
    if not creds.app_password:
        return PostgresSetupResult(False, "test_app_connection", [], "Missing app-user password.")

    try:
        import psycopg

        with psycopg.connect(
            host=creds.host,
            port=creds.port,
            dbname=creds.database,
            user=creds.app_user,
            password=creds.app_password,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database(), current_user, current_schema()")
                row = cur.fetchone()

        return PostgresSetupResult(
            True,
            "test_app_connection",
            [f"Connected as {row[1]} to database {row[0]} using schema {row[2]}."],
        )
    except Exception as exc:
        return PostgresSetupResult(False, "test_app_connection", [], f"{type(exc).__name__}: {exc}")


def setup_or_repair_database(creds: PostgresUiCredentials) -> PostgresSetupResult:
    """Create or repair database/user/schema using typed admin credentials.

    This is local-development convenience. It does not save passwords.
    """
    messages: list[str] = []
    if not creds.admin_password:
        return PostgresSetupResult(False, "setup_or_repair_database", messages, "Missing admin password.")
    if not creds.app_password:
        return PostgresSetupResult(False, "setup_or_repair_database", messages, "Missing app-user password.")

    try:
        validate_setup_identifiers(creds)

        import psycopg
        from psycopg import sql

        with psycopg.connect(
            host=creds.host,
            port=creds.port,
            dbname="postgres",
            user=creds.admin_user,
            password=creds.admin_password,
            autocommit=True,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (creds.database,))
                if cur.fetchone():
                    messages.append(f"Database already exists: {creds.database}")
                else:
                    cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(creds.database)))
                    messages.append(f"Created database: {creds.database}")

                cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (creds.app_user,))
                if cur.fetchone():
                    cur.execute(
                        sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
                            sql.Identifier(creds.app_user),
                            sql.Literal(creds.app_password),
                        )
                    )
                    messages.append(f"Updated app user password/login: {creds.app_user}")
                else:
                    cur.execute(
                        sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                            sql.Identifier(creds.app_user),
                            sql.Literal(creds.app_password),
                        )
                    )
                    messages.append(f"Created app user: {creds.app_user}")

        with psycopg.connect(
            host=creds.host,
            port=creds.port,
            dbname=creds.database,
            user=creds.admin_user,
            password=creds.admin_password,
            autocommit=True,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("CREATE SCHEMA IF NOT EXISTS {} AUTHORIZATION {}").format(
                        sql.Identifier(creds.schema),
                        sql.Identifier(creds.app_user),
                    )
                )
                messages.append(f"Created/verified schema: {creds.schema}")

                cur.execute(
                    sql.SQL("ALTER SCHEMA {} OWNER TO {}").format(
                        sql.Identifier(creds.schema),
                        sql.Identifier(creds.app_user),
                    )
                )
                cur.execute(
                    sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                        sql.Identifier(creds.database),
                        sql.Identifier(creds.app_user),
                    )
                )
                cur.execute(
                    sql.SQL("GRANT CREATE ON DATABASE {} TO {}").format(
                        sql.Identifier(creds.database),
                        sql.Identifier(creds.app_user),
                    )
                )
                cur.execute(
                    sql.SQL("GRANT USAGE, CREATE ON SCHEMA {} TO {}").format(
                        sql.Identifier(creds.schema),
                        sql.Identifier(creds.app_user),
                    )
                )
                cur.execute(
                    sql.SQL("ALTER ROLE {} SET search_path TO {}, public").format(
                        sql.Identifier(creds.app_user),
                        sql.Identifier(creds.schema),
                    )
                )
                messages.append("Granted database/schema permissions and search_path.")

        test = test_app_connection(creds)
        if not test.ok:
            messages.extend(test.messages)
            return PostgresSetupResult(False, "setup_or_repair_database", messages, test.error)

        messages.extend(test.messages)
        return PostgresSetupResult(True, "setup_or_repair_database", messages)

    except Exception as exc:
        return PostgresSetupResult(False, "setup_or_repair_database", messages, f"{type(exc).__name__}: {exc}")


def result_as_dict(result: PostgresSetupResult) -> dict[str, Any]:
    return asdict(result)
