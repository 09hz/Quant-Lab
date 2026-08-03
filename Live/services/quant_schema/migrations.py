from __future__ import annotations

from typing import Any


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


def _backend(db: Any) -> str:
    return str(getattr(db, "backend", "sqlite")).lower()


def _is_postgres(db: Any) -> bool:
    return _backend(db) in {"postgres", "postgresql"}


def _cursor(db: Any):
    return db.cursor() if hasattr(db, "cursor") else db.conn.cursor()


def _commit(db: Any) -> None:
    if hasattr(db, "commit"):
        db.commit()
    elif hasattr(db, "conn"):
        db.conn.commit()


def _execute(db: Any, sql: str) -> None:
    cur = _cursor(db)
    try:
        cur.execute(sql)
    finally:
        cur.close()


def _types(db: Any) -> dict[str, str]:
    if _is_postgres(db):
        return {
            "json": "JSONB",
            "ts": "TIMESTAMPTZ",
            "bool": "BOOLEAN",
            "int": "BIGINT",
            "real": "DOUBLE PRECISION",
        }
    return {
        "json": "TEXT",
        "ts": "TEXT",
        "bool": "INTEGER",
        "int": "INTEGER",
        "real": "REAL",
    }


def _required_columns(db: Any) -> dict[str, dict[str, str]]:
    """Return additive column definitions for canonical Quant Schema tables."""
    t = _types(db)
    json_t = t["json"]
    ts_t = t["ts"]
    bool_t = t["bool"]
    int_t = t["int"]
    real_t = t["real"]

    return {
        "symbols": {
            "symbol": "TEXT",
            "name": "TEXT",
            "asset_type": "TEXT",
            "exchange": "TEXT",
            "currency": "TEXT",
            "sector": "TEXT",
            "industry": "TEXT",
            "active": bool_t,
            "metadata_json": json_t,
            "created_at": ts_t,
            "updated_at": ts_t,
        },
        "experiment_runs": {
            "experiment_id": "TEXT",
            "module": "TEXT",
            "experiment_name": "TEXT",
            "status": "TEXT",
            "started_at": ts_t,
            "finished_at": ts_t,
            "config_json": json_t,
            "notes": "TEXT",
            "artifact_id": "TEXT",
            "created_at": ts_t,
        },
        "strategy_runs": {
            "strategy_run_id": "TEXT",
            "experiment_id": "TEXT",
            "artifact_id": "TEXT",
            "strategy_name": "TEXT",
            "strategy_family": "TEXT",
            "symbol": "TEXT",
            "timeframe": "TEXT",
            "parameters_json": json_t,
            "signal_count": int_t,
            "status": "TEXT",
            "created_at": ts_t,
        },
        "backtest_runs": {
            "backtest_run_id": "TEXT",
            "strategy_run_id": "TEXT",
            "experiment_id": "TEXT",
            "artifact_id": "TEXT",
            "symbol": "TEXT",
            "strategy_name": "TEXT",
            "timeframe": "TEXT",
            "start_date": "TEXT",
            "end_date": "TEXT",
            "initial_capital": real_t,
            "ending_capital": real_t,
            "total_return": real_t,
            "cagr": real_t,
            "sharpe": real_t,
            "sortino": real_t,
            "max_drawdown": real_t,
            "win_rate": real_t,
            "profit_factor": real_t,
            "trade_count": int_t,
            "turnover": real_t,
            "fees": real_t,
            "slippage": real_t,
            "status": "TEXT",
            "metrics_json": json_t,
            "created_at": ts_t,
        },
        "walk_forward_runs": {
            "walk_forward_run_id": "TEXT",
            "experiment_id": "TEXT",
            "artifact_id": "TEXT",
            "symbol": "TEXT",
            "strategy_name": "TEXT",
            "timeframe": "TEXT",
            "train_start": "TEXT",
            "train_end": "TEXT",
            "test_start": "TEXT",
            "test_end": "TEXT",
            "window_count": int_t,
            "avg_sharpe": real_t,
            "median_sharpe": real_t,
            "avg_return": real_t,
            "max_drawdown": real_t,
            "pass_rate": real_t,
            "stability_score": real_t,
            "status": "TEXT",
            "metrics_json": json_t,
            "created_at": ts_t,
        },
        "universe_runs": {
            "universe_run_id": "TEXT",
            "experiment_id": "TEXT",
            "artifact_id": "TEXT",
            "universe_name": "TEXT",
            "theme": "TEXT",
            "symbol_count": int_t,
            "selected_count": int_t,
            "symbols_json": json_t,
            "ranking_json": json_t,
            "status": "TEXT",
            "created_at": ts_t,
        },
        "feature_snapshots": {
            "feature_snapshot_id": "TEXT",
            "artifact_id": "TEXT",
            "symbol": "TEXT",
            "as_of": "TEXT",
            "timeframe": "TEXT",
            "feature_set_name": "TEXT",
            "features_json": json_t,
            "source_module": "TEXT",
            "created_at": ts_t,
        },
        "risk_snapshots": {
            "risk_snapshot_id": "TEXT",
            "artifact_id": "TEXT",
            "symbol": "TEXT",
            "as_of": "TEXT",
            "portfolio_value": real_t,
            "position_value": real_t,
            "exposure": real_t,
            "volatility": real_t,
            "var_95": real_t,
            "expected_shortfall": real_t,
            "max_drawdown": real_t,
            "sizing_method": "TEXT",
            "risk_json": json_t,
            "created_at": ts_t,
        },
        "model_candidates": {
            "model_candidate_id": "TEXT",
            "experiment_id": "TEXT",
            "artifact_id": "TEXT",
            "symbol": "TEXT",
            "model_name": "TEXT",
            "model_type": "TEXT",
            "target_name": "TEXT",
            "feature_set_name": "TEXT",
            "features_json": json_t,
            "metrics_json": json_t,
            "status": "TEXT",
            "created_at": ts_t,
        },
        "data_quality_events": {
            "event_id": "TEXT",
            "artifact_id": "TEXT",
            "symbol": "TEXT",
            "dataset_name": "TEXT",
            "severity": "TEXT",
            "event_type": "TEXT",
            "message": "TEXT",
            "details_json": json_t,
            "created_at": ts_t,
        },
    }


def _column_names(db: Any, table: str) -> set[str]:
    cur = _cursor(db)
    try:
        if _is_postgres(db):
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = %s
                """,
                (table,),
            )
            rows = cur.fetchall()
            return {
                str(row.get("column_name") if isinstance(row, dict) else row[0])
                for row in rows
            }

        cur.execute(f'PRAGMA table_info("{table}")')
        rows = cur.fetchall()
        names: set[str] = set()
        for row in rows:
            if hasattr(row, "keys") and "name" in row.keys():
                names.add(str(row["name"]))
            else:
                names.add(str(row[1]))
        return names
    finally:
        cur.close()


def _upgrade_legacy_tables(db: Any) -> None:
    for table, columns in _required_columns(db).items():
        existing = _column_names(db, table)
        for column, column_type in columns.items():
            if column in existing:
                continue
            _execute(db, f'ALTER TABLE "{table}" ADD COLUMN "{column}" {column_type}')
            existing.add(column)


def _backfill_legacy_experiment_runs(db: Any) -> None:
    columns = _column_names(db, "experiment_runs")
    aliases = {
        "experiment_id": "run_id",
        "module": "run_type",
        "finished_at": "completed_at",
        "config_json": "metadata_json",
        "created_at": "started_at",
    }
    for target, source in aliases.items():
        if target in columns and source in columns:
            _execute(
                db,
                f'UPDATE "experiment_runs" SET "{target}" = "{source}" '
                f'WHERE "{target}" IS NULL AND "{source}" IS NOT NULL',
            )


def _statements(db: Any) -> list[str]:
    t = _types(db)
    json_t = t["json"]
    ts_t = t["ts"]
    bool_t = t["bool"]
    int_t = t["int"]
    real_t = t["real"]

    return [
        f"""
        CREATE TABLE IF NOT EXISTS symbols (
            symbol TEXT PRIMARY KEY,
            name TEXT,
            asset_type TEXT,
            exchange TEXT,
            currency TEXT,
            sector TEXT,
            industry TEXT,
            active {bool_t},
            metadata_json {json_t},
            created_at {ts_t},
            updated_at {ts_t}
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS experiment_runs (
            experiment_id TEXT PRIMARY KEY,
            module TEXT,
            experiment_name TEXT,
            status TEXT,
            started_at {ts_t},
            finished_at {ts_t},
            config_json {json_t},
            notes TEXT,
            artifact_id TEXT,
            created_at {ts_t}
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS strategy_runs (
            strategy_run_id TEXT PRIMARY KEY,
            experiment_id TEXT,
            artifact_id TEXT,
            strategy_name TEXT,
            strategy_family TEXT,
            symbol TEXT,
            timeframe TEXT,
            parameters_json {json_t},
            signal_count {int_t},
            status TEXT,
            created_at {ts_t}
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS backtest_runs (
            backtest_run_id TEXT PRIMARY KEY,
            strategy_run_id TEXT,
            experiment_id TEXT,
            artifact_id TEXT,
            symbol TEXT,
            strategy_name TEXT,
            timeframe TEXT,
            start_date TEXT,
            end_date TEXT,
            initial_capital {real_t},
            ending_capital {real_t},
            total_return {real_t},
            cagr {real_t},
            sharpe {real_t},
            sortino {real_t},
            max_drawdown {real_t},
            win_rate {real_t},
            profit_factor {real_t},
            trade_count {int_t},
            turnover {real_t},
            fees {real_t},
            slippage {real_t},
            status TEXT,
            metrics_json {json_t},
            created_at {ts_t}
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS walk_forward_runs (
            walk_forward_run_id TEXT PRIMARY KEY,
            experiment_id TEXT,
            artifact_id TEXT,
            symbol TEXT,
            strategy_name TEXT,
            timeframe TEXT,
            train_start TEXT,
            train_end TEXT,
            test_start TEXT,
            test_end TEXT,
            window_count {int_t},
            avg_sharpe {real_t},
            median_sharpe {real_t},
            avg_return {real_t},
            max_drawdown {real_t},
            pass_rate {real_t},
            stability_score {real_t},
            status TEXT,
            metrics_json {json_t},
            created_at {ts_t}
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS universe_runs (
            universe_run_id TEXT PRIMARY KEY,
            experiment_id TEXT,
            artifact_id TEXT,
            universe_name TEXT,
            theme TEXT,
            symbol_count {int_t},
            selected_count {int_t},
            symbols_json {json_t},
            ranking_json {json_t},
            status TEXT,
            created_at {ts_t}
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS feature_snapshots (
            feature_snapshot_id TEXT PRIMARY KEY,
            artifact_id TEXT,
            symbol TEXT,
            as_of TEXT,
            timeframe TEXT,
            feature_set_name TEXT,
            features_json {json_t},
            source_module TEXT,
            created_at {ts_t}
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS risk_snapshots (
            risk_snapshot_id TEXT PRIMARY KEY,
            artifact_id TEXT,
            symbol TEXT,
            as_of TEXT,
            portfolio_value {real_t},
            position_value {real_t},
            exposure {real_t},
            volatility {real_t},
            var_95 {real_t},
            expected_shortfall {real_t},
            max_drawdown {real_t},
            sizing_method TEXT,
            risk_json {json_t},
            created_at {ts_t}
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS model_candidates (
            model_candidate_id TEXT PRIMARY KEY,
            experiment_id TEXT,
            artifact_id TEXT,
            symbol TEXT,
            model_name TEXT,
            model_type TEXT,
            target_name TEXT,
            feature_set_name TEXT,
            features_json {json_t},
            metrics_json {json_t},
            status TEXT,
            created_at {ts_t}
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS data_quality_events (
            event_id TEXT PRIMARY KEY,
            artifact_id TEXT,
            symbol TEXT,
            dataset_name TEXT,
            severity TEXT,
            event_type TEXT,
            message TEXT,
            details_json {json_t},
            created_at {ts_t}
        )
        """,
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_experiment_runs_experiment_id ON experiment_runs(experiment_id)",
        "CREATE INDEX IF NOT EXISTS idx_strategy_runs_symbol ON strategy_runs(symbol)",
        "CREATE INDEX IF NOT EXISTS idx_strategy_runs_strategy ON strategy_runs(strategy_name)",
        "CREATE INDEX IF NOT EXISTS idx_strategy_runs_created_at ON strategy_runs(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_backtest_runs_symbol ON backtest_runs(symbol)",
        "CREATE INDEX IF NOT EXISTS idx_backtest_runs_strategy ON backtest_runs(strategy_name)",
        "CREATE INDEX IF NOT EXISTS idx_backtest_runs_sharpe ON backtest_runs(sharpe)",
        "CREATE INDEX IF NOT EXISTS idx_backtest_runs_created_at ON backtest_runs(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_walk_forward_runs_symbol ON walk_forward_runs(symbol)",
        "CREATE INDEX IF NOT EXISTS idx_walk_forward_runs_strategy ON walk_forward_runs(strategy_name)",
        "CREATE INDEX IF NOT EXISTS idx_universe_runs_theme ON universe_runs(theme)",
        "CREATE INDEX IF NOT EXISTS idx_feature_snapshots_symbol ON feature_snapshots(symbol)",
        "CREATE INDEX IF NOT EXISTS idx_risk_snapshots_symbol ON risk_snapshots(symbol)",
        "CREATE INDEX IF NOT EXISTS idx_data_quality_events_symbol ON data_quality_events(symbol)",
        "CREATE INDEX IF NOT EXISTS idx_data_quality_events_severity ON data_quality_events(severity)",
    ]


def migrate_quant_schema(db: Any) -> None:
    statements = _statements(db)
    table_statements = [statement for statement in statements if "CREATE TABLE" in statement.upper()]
    index_statements = [
        statement
        for statement in statements
        if statement.lstrip().upper().startswith(("CREATE INDEX", "CREATE UNIQUE INDEX"))
    ]

    for statement in table_statements:
        _execute(db, statement)
    _upgrade_legacy_tables(db)
    _backfill_legacy_experiment_runs(db)
    for statement in index_statements:
        _execute(db, statement)
    _commit(db)


def quant_table_counts(db: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in QUANT_TABLES:
        cur = _cursor(db)
        try:
            cur.execute(f"SELECT COUNT(*) AS n FROM {table}")
            row = cur.fetchone()
            if isinstance(row, dict):
                counts[table] = int(row.get("n", 0))
            else:
                counts[table] = int(row[0])
        except Exception:
            counts[table] = -1
        finally:
            cur.close()
    return counts
