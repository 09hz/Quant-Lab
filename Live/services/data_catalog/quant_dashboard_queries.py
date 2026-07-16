from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import os
import traceback


QUANT_TABLES = [
    "symbols",
    "experiment_runs",
    "strategy_runs",
    "backtest_runs",
    "walk_forward_runs",
    "universe_runs",
    "feature_snapshots",
    "risk_snapshots",
    "model_candidates",
    "data_quality_events",
]


@dataclass
class QuantDashboardPayload:
    status: str
    backend: str
    repo_root: str
    counts: dict[str, int]
    sections: dict[str, list[dict[str, Any]]]
    errors: list[str]
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def find_repo_root(start: str | Path | None = None) -> Path:
    p = Path(start or Path.cwd()).resolve()
    for c in [p, *p.parents]:
        if (c / "Live" / "app.py").exists():
            return c
        if c.name.lower() == "live" and (c / "app.py").exists():
            return c.parent
    return p


def _connect(repo_root: Path, backend: str):
    from services.database.config import load_database_config
    try:
        from services.database.backend import connect_database
    except Exception:
        from services.database.connections import connect_database  # type: ignore

    config = load_database_config(repo_root=str(repo_root), backend=backend)
    return connect_database(config)


def _raw_connection(db: Any) -> Any:
    for attr in ["conn", "connection", "_conn", "_connection"]:
        if hasattr(db, attr):
            return getattr(db, attr)
    return db


def _rollback(conn: Any) -> None:
    try:
        conn.rollback()
    except Exception:
        pass


def _execute(conn: Any, sql: str):
    if hasattr(conn, "execute"):
        return conn.execute(sql)
    cur = conn.cursor()
    cur.execute(sql)
    return cur


def _rows_to_dicts(cursor: Any) -> list[dict[str, Any]]:
    description = getattr(cursor, "description", None) or []
    columns = [str(item[0]) for item in description]
    raw_rows = cursor.fetchall()
    out: list[dict[str, Any]] = []

    for row in raw_rows:
        if isinstance(row, dict):
            data = dict(row)
        elif hasattr(row, "keys"):
            try:
                data = {key: row[key] for key in row.keys()}
            except Exception:
                data = dict(row)
        else:
            data = {columns[idx]: value for idx, value in enumerate(row)} if columns else {"value": row}

        clean: dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                clean[key] = value
            else:
                clean[key] = str(value)
        out.append(clean)

    return out


def _count_table(conn: Any, table: str) -> tuple[int, str | None]:
    try:
        cur = _execute(conn, f"SELECT COUNT(*) AS count FROM {table}")
        row = cur.fetchone()
        if isinstance(row, dict):
            return int(row.get("count", 0)), None
        if hasattr(row, "keys"):
            try:
                return int(row["count"]), None
            except Exception:
                pass
        return int(row[0]), None
    except Exception as exc:
        _rollback(conn)
        return 0, f"{table}: {type(exc).__name__}: {exc}"


def _select_rows(conn: Any, table: str, *, order_by: str | None = None, limit: int = 10) -> tuple[list[dict[str, Any]], str | None]:
    sql_with_order = f"SELECT * FROM {table}"
    if order_by:
        sql_with_order += f" ORDER BY {order_by}"
    sql_with_order += f" LIMIT {int(limit)}"

    try:
        cur = _execute(conn, sql_with_order)
        return _rows_to_dicts(cur), None
    except Exception as first_exc:
        _rollback(conn)
        try:
            cur = _execute(conn, f"SELECT * FROM {table} LIMIT {int(limit)}")
            return _rows_to_dicts(cur), None
        except Exception as second_exc:
            _rollback(conn)
            return [], f"{table}: {type(second_exc).__name__}: {second_exc}; ordered_query_error={type(first_exc).__name__}: {first_exc}"


def _preferred_backend(value: str | None = None) -> str:
    if value in {"sqlite", "postgres"}:
        return value
    env_backend = os.environ.get("ALGOTRADER_DB_BACKEND", "").strip().lower()
    if env_backend in {"postgres", "postgresql"}:
        return "postgres"
    return "sqlite"


def load_quant_dashboard(
    *,
    repo_root: str | Path | None = None,
    backend: str | None = None,
    limit: int = 10,
) -> QuantDashboardPayload:
    root = find_repo_root(repo_root)
    selected_backend = _preferred_backend(backend)
    limit = max(1, min(int(limit or 10), 100))

    errors: list[str] = []
    counts = {table: 0 for table in QUANT_TABLES}
    sections: dict[str, list[dict[str, Any]]] = {
        "recent_experiments": [],
        "recent_strategies": [],
        "best_backtests": [],
        "walk_forward_runs": [],
        "universe_runs": [],
        "data_quality_events": [],
    }

    try:
        with _connect(root, selected_backend) as db:
            conn = _raw_connection(db)

            for table in QUANT_TABLES:
                count, error = _count_table(conn, table)
                counts[table] = count
                if error:
                    errors.append(error)

            section_specs = {
                "recent_experiments": ("experiment_runs", "created_at DESC"),
                "recent_strategies": ("strategy_runs", "created_at DESC"),
                "best_backtests": ("backtest_runs", "COALESCE(sharpe, -999999) DESC, created_at DESC"),
                "walk_forward_runs": ("walk_forward_runs", "created_at DESC"),
                "universe_runs": ("universe_runs", "created_at DESC"),
                "data_quality_events": ("data_quality_events", "created_at DESC"),
            }

            for section, (table, order_by) in section_specs.items():
                rows, error = _select_rows(conn, table, order_by=order_by, limit=limit)
                sections[section] = rows
                if error:
                    errors.append(error)

        status = "PASS" if not errors else "WARN"
        message = "Quant dashboard loaded." if status == "PASS" else "Quant dashboard loaded with warnings. Some tables may be empty or not migrated."
        return QuantDashboardPayload(
            status=status,
            backend=selected_backend,
            repo_root=str(root),
            counts=counts,
            sections=sections,
            errors=errors[:25],
            message=message,
        )

    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
        errors.append(traceback.format_exc(limit=8))
        return QuantDashboardPayload(
            status="FAIL",
            backend=selected_backend,
            repo_root=str(root),
            counts=counts,
            sections=sections,
            errors=errors[:25],
            message="Quant dashboard could not connect. For PostgreSQL, set env vars or use the PostgreSQL setup panel first.",
        )
