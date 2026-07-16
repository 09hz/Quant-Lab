from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any
import uuid


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, allow_nan=False, default=str)


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


def _execute(db: Any, sql: str, params: tuple[Any, ...]) -> None:
    cur = _cursor(db)
    try:
        cur.execute(sql, params)
    finally:
        cur.close()


def upsert_symbol(
    db: Any,
    *,
    symbol: str,
    name: str | None = None,
    asset_type: str = "equity",
    exchange: str | None = None,
    currency: str | None = "USD",
    sector: str | None = None,
    industry: str | None = None,
    active: bool = True,
    metadata: dict[str, Any] | None = None,
    commit: bool = True,
) -> str:
    symbol = symbol.upper().strip()
    now = utc_now()
    if _is_postgres(db):
        sql = """
        INSERT INTO symbols
            (symbol, name, asset_type, exchange, currency, sector, industry, active, metadata_json, created_at, updated_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
        ON CONFLICT (symbol) DO UPDATE SET
            name=EXCLUDED.name,
            asset_type=EXCLUDED.asset_type,
            exchange=EXCLUDED.exchange,
            currency=EXCLUDED.currency,
            sector=EXCLUDED.sector,
            industry=EXCLUDED.industry,
            active=EXCLUDED.active,
            metadata_json=EXCLUDED.metadata_json,
            updated_at=EXCLUDED.updated_at
        """
    else:
        sql = """
        INSERT OR REPLACE INTO symbols
            (symbol, name, asset_type, exchange, currency, sector, industry, active, metadata_json, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """
    _execute(db, sql, (symbol, name, asset_type, exchange, currency, sector, industry, active, _json(metadata), now, now))
    if commit:
        _commit(db)
    return symbol


def insert_experiment_run(
    db: Any,
    *,
    experiment_id: str | None = None,
    module: str,
    experiment_name: str | None = None,
    status: str = "created",
    started_at: str | None = None,
    finished_at: str | None = None,
    config: dict[str, Any] | None = None,
    notes: str | None = None,
    artifact_id: str | None = None,
    commit: bool = True,
) -> str:
    experiment_id = experiment_id or _id("exp")
    now = utc_now()
    if _is_postgres(db):
        sql = """
        INSERT INTO experiment_runs
            (experiment_id, module, experiment_name, status, started_at, finished_at, config_json, notes, artifact_id, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
        """
    else:
        sql = """
        INSERT INTO experiment_runs
            (experiment_id, module, experiment_name, status, started_at, finished_at, config_json, notes, artifact_id, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        """
    _execute(db, sql, (experiment_id, module, experiment_name, status, started_at or now, finished_at, _json(config), notes, artifact_id, now))
    if commit:
        _commit(db)
    return experiment_id


def insert_strategy_run(
    db: Any,
    *,
    strategy_run_id: str | None = None,
    experiment_id: str | None = None,
    artifact_id: str | None = None,
    strategy_name: str,
    strategy_family: str | None = None,
    symbol: str | None = None,
    timeframe: str | None = None,
    parameters: dict[str, Any] | None = None,
    signal_count: int | None = None,
    status: str = "created",
    created_at: str | None = None,
    commit: bool = True,
) -> str:
    strategy_run_id = strategy_run_id or _id("strat")
    now = created_at or utc_now()
    if symbol:
        symbol = symbol.upper().strip()
    if _is_postgres(db):
        sql = """
        INSERT INTO strategy_runs
            (strategy_run_id, experiment_id, artifact_id, strategy_name, strategy_family, symbol, timeframe,
             parameters_json, signal_count, status, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
        """
    else:
        sql = """
        INSERT INTO strategy_runs
            (strategy_run_id, experiment_id, artifact_id, strategy_name, strategy_family, symbol, timeframe,
             parameters_json, signal_count, status, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """
    _execute(db, sql, (strategy_run_id, experiment_id, artifact_id, strategy_name, strategy_family, symbol, timeframe, _json(parameters), signal_count, status, now))
    if commit:
        _commit(db)
    return strategy_run_id


def insert_backtest_run(
    db: Any,
    *,
    backtest_run_id: str | None = None,
    strategy_run_id: str | None = None,
    experiment_id: str | None = None,
    artifact_id: str | None = None,
    symbol: str,
    strategy_name: str,
    timeframe: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    initial_capital: float | None = None,
    ending_capital: float | None = None,
    total_return: float | None = None,
    cagr: float | None = None,
    sharpe: float | None = None,
    sortino: float | None = None,
    max_drawdown: float | None = None,
    win_rate: float | None = None,
    profit_factor: float | None = None,
    trade_count: int | None = None,
    turnover: float | None = None,
    fees: float | None = None,
    slippage: float | None = None,
    status: str = "created",
    metrics: dict[str, Any] | None = None,
    created_at: str | None = None,
    commit: bool = True,
) -> str:
    backtest_run_id = backtest_run_id or _id("bt")
    now = created_at or utc_now()
    symbol = symbol.upper().strip()
    if _is_postgres(db):
        sql = """
        INSERT INTO backtest_runs
            (backtest_run_id, strategy_run_id, experiment_id, artifact_id, symbol, strategy_name, timeframe,
             start_date, end_date, initial_capital, ending_capital, total_return, cagr, sharpe, sortino,
             max_drawdown, win_rate, profit_factor, trade_count, turnover, fees, slippage, status, metrics_json, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
        """
    else:
        sql = """
        INSERT INTO backtest_runs
            (backtest_run_id, strategy_run_id, experiment_id, artifact_id, symbol, strategy_name, timeframe,
             start_date, end_date, initial_capital, ending_capital, total_return, cagr, sharpe, sortino,
             max_drawdown, win_rate, profit_factor, trade_count, turnover, fees, slippage, status, metrics_json, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """
    _execute(db, sql, (backtest_run_id, strategy_run_id, experiment_id, artifact_id, symbol, strategy_name, timeframe, start_date, end_date, initial_capital, ending_capital, total_return, cagr, sharpe, sortino, max_drawdown, win_rate, profit_factor, trade_count, turnover, fees, slippage, status, _json(metrics), now))
    if commit:
        _commit(db)
    return backtest_run_id


def insert_walk_forward_run(
    db: Any,
    *,
    walk_forward_run_id: str | None = None,
    experiment_id: str | None = None,
    artifact_id: str | None = None,
    symbol: str,
    strategy_name: str,
    timeframe: str | None = None,
    train_start: str | None = None,
    train_end: str | None = None,
    test_start: str | None = None,
    test_end: str | None = None,
    window_count: int | None = None,
    avg_sharpe: float | None = None,
    median_sharpe: float | None = None,
    avg_return: float | None = None,
    max_drawdown: float | None = None,
    pass_rate: float | None = None,
    stability_score: float | None = None,
    status: str = "created",
    metrics: dict[str, Any] | None = None,
    commit: bool = True,
) -> str:
    walk_forward_run_id = walk_forward_run_id or _id("wf")
    symbol = symbol.upper().strip()
    now = utc_now()
    if _is_postgres(db):
        sql = """
        INSERT INTO walk_forward_runs
            (walk_forward_run_id, experiment_id, artifact_id, symbol, strategy_name, timeframe, train_start, train_end,
             test_start, test_end, window_count, avg_sharpe, median_sharpe, avg_return, max_drawdown, pass_rate,
             stability_score, status, metrics_json, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
        """
    else:
        sql = """
        INSERT INTO walk_forward_runs
            (walk_forward_run_id, experiment_id, artifact_id, symbol, strategy_name, timeframe, train_start, train_end,
             test_start, test_end, window_count, avg_sharpe, median_sharpe, avg_return, max_drawdown, pass_rate,
             stability_score, status, metrics_json, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """
    _execute(db, sql, (walk_forward_run_id, experiment_id, artifact_id, symbol, strategy_name, timeframe, train_start, train_end, test_start, test_end, window_count, avg_sharpe, median_sharpe, avg_return, max_drawdown, pass_rate, stability_score, status, _json(metrics), now))
    if commit:
        _commit(db)
    return walk_forward_run_id


def insert_universe_run(
    db: Any,
    *,
    universe_run_id: str | None = None,
    experiment_id: str | None = None,
    artifact_id: str | None = None,
    universe_name: str,
    theme: str | None = None,
    symbols: list[str] | None = None,
    selected_count: int | None = None,
    ranking: list[dict[str, Any]] | None = None,
    status: str = "created",
    commit: bool = True,
) -> str:
    universe_run_id = universe_run_id or _id("uni")
    symbols = [s.upper().strip() for s in (symbols or [])]
    now = utc_now()
    if _is_postgres(db):
        sql = """
        INSERT INTO universe_runs
            (universe_run_id, experiment_id, artifact_id, universe_name, theme, symbol_count, selected_count,
             symbols_json, ranking_json, status, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s)
        """
    else:
        sql = """
        INSERT INTO universe_runs
            (universe_run_id, experiment_id, artifact_id, universe_name, theme, symbol_count, selected_count,
             symbols_json, ranking_json, status, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """
    _execute(db, sql, (universe_run_id, experiment_id, artifact_id, universe_name, theme, len(symbols), selected_count, _json(symbols), _json(ranking or []), status, now))
    if commit:
        _commit(db)
    return universe_run_id


def insert_feature_snapshot(
    db: Any,
    *,
    feature_snapshot_id: str | None = None,
    artifact_id: str | None = None,
    symbol: str,
    as_of: str,
    timeframe: str | None = None,
    feature_set_name: str | None = None,
    features: dict[str, Any] | None = None,
    source_module: str | None = None,
    commit: bool = True,
) -> str:
    feature_snapshot_id = feature_snapshot_id or _id("feat")
    symbol = symbol.upper().strip()
    now = utc_now()
    if _is_postgres(db):
        sql = """
        INSERT INTO feature_snapshots
            (feature_snapshot_id, artifact_id, symbol, as_of, timeframe, feature_set_name, features_json, source_module, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
        """
    else:
        sql = """
        INSERT INTO feature_snapshots
            (feature_snapshot_id, artifact_id, symbol, as_of, timeframe, feature_set_name, features_json, source_module, created_at)
        VALUES (?,?,?,?,?,?,?,?,?)
        """
    _execute(db, sql, (feature_snapshot_id, artifact_id, symbol, as_of, timeframe, feature_set_name, _json(features), source_module, now))
    if commit:
        _commit(db)
    return feature_snapshot_id


def insert_risk_snapshot(
    db: Any,
    *,
    risk_snapshot_id: str | None = None,
    artifact_id: str | None = None,
    symbol: str | None = None,
    as_of: str,
    portfolio_value: float | None = None,
    position_value: float | None = None,
    exposure: float | None = None,
    volatility: float | None = None,
    var_95: float | None = None,
    expected_shortfall: float | None = None,
    max_drawdown: float | None = None,
    sizing_method: str | None = None,
    risk: dict[str, Any] | None = None,
    commit: bool = True,
) -> str:
    risk_snapshot_id = risk_snapshot_id or _id("risk")
    if symbol:
        symbol = symbol.upper().strip()
    now = utc_now()
    if _is_postgres(db):
        sql = """
        INSERT INTO risk_snapshots
            (risk_snapshot_id, artifact_id, symbol, as_of, portfolio_value, position_value, exposure, volatility,
             var_95, expected_shortfall, max_drawdown, sizing_method, risk_json, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
        """
    else:
        sql = """
        INSERT INTO risk_snapshots
            (risk_snapshot_id, artifact_id, symbol, as_of, portfolio_value, position_value, exposure, volatility,
             var_95, expected_shortfall, max_drawdown, sizing_method, risk_json, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """
    _execute(db, sql, (risk_snapshot_id, artifact_id, symbol, as_of, portfolio_value, position_value, exposure, volatility, var_95, expected_shortfall, max_drawdown, sizing_method, _json(risk), now))
    if commit:
        _commit(db)
    return risk_snapshot_id


def insert_model_candidate(
    db: Any,
    *,
    model_candidate_id: str | None = None,
    experiment_id: str | None = None,
    artifact_id: str | None = None,
    symbol: str | None = None,
    model_name: str,
    model_type: str | None = None,
    target_name: str | None = None,
    feature_set_name: str | None = None,
    features: list[str] | None = None,
    metrics: dict[str, Any] | None = None,
    status: str = "created",
    commit: bool = True,
) -> str:
    model_candidate_id = model_candidate_id or _id("model")
    if symbol:
        symbol = symbol.upper().strip()
    now = utc_now()
    if _is_postgres(db):
        sql = """
        INSERT INTO model_candidates
            (model_candidate_id, experiment_id, artifact_id, symbol, model_name, model_type, target_name,
             feature_set_name, features_json, metrics_json, status, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s)
        """
    else:
        sql = """
        INSERT INTO model_candidates
            (model_candidate_id, experiment_id, artifact_id, symbol, model_name, model_type, target_name,
             feature_set_name, features_json, metrics_json, status, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """
    _execute(db, sql, (model_candidate_id, experiment_id, artifact_id, symbol, model_name, model_type, target_name, feature_set_name, _json(features or []), _json(metrics), status, now))
    if commit:
        _commit(db)
    return model_candidate_id


def insert_data_quality_event(
    db: Any,
    *,
    event_id: str | None = None,
    artifact_id: str | None = None,
    symbol: str | None = None,
    dataset_name: str,
    severity: str,
    event_type: str,
    message: str,
    details: dict[str, Any] | None = None,
    commit: bool = True,
) -> str:
    event_id = event_id or _id("dq")
    if symbol:
        symbol = symbol.upper().strip()
    now = utc_now()
    if _is_postgres(db):
        sql = """
        INSERT INTO data_quality_events
            (event_id, artifact_id, symbol, dataset_name, severity, event_type, message, details_json, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
        """
    else:
        sql = """
        INSERT INTO data_quality_events
            (event_id, artifact_id, symbol, dataset_name, severity, event_type, message, details_json, created_at)
        VALUES (?,?,?,?,?,?,?,?,?)
        """
    _execute(db, sql, (event_id, artifact_id, symbol, dataset_name, severity, event_type, message, _json(details), now))
    if commit:
        _commit(db)
    return event_id
