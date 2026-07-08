# v24.4 — Quant Research Schema

## Purpose

Add a typed quant research schema on top of the existing SQLite/PostgreSQL database layer.

This moves the project from generic artifact storage toward fast, queryable quant research tables.

## Adds

- `Live/services/quant_schema/__init__.py`
- `Live/services/quant_schema/migrations.py`
- `Live/services/quant_schema/repository.py`
- `Live/services/quant_schema/status.py`
- `Live/services/quant_schema/self_test_v24_4.py`
- `docs/quant_research_schema.md`
- `docs/patches/v24_4_quant_research_schema.md`

## Tables

- `symbols`
- `experiment_runs`
- `strategy_runs`
- `backtest_runs`
- `walk_forward_runs`
- `universe_runs`
- `feature_snapshots`
- `risk_snapshots`
- `model_candidates`
- `data_quality_events`

## Why this matters

The existing database layer stores artifacts in generic tables:

- `db_json_payloads`
- `db_csv_rows`
- `db_ingested_artifacts`

That is useful for preservation and search, but quant dashboards and research workflows need typed columns such as:

- `symbol`
- `strategy_name`
- `timeframe`
- `start_date`
- `end_date`
- `sharpe`
- `sortino`
- `max_drawdown`
- `win_rate`
- `profit_factor`
- `created_at`

Typed columns make it much faster and cleaner to rank backtests, compare walk-forward runs, search strategy history, and build dashboards.

## Security

- No credentials are written.
- PostgreSQL credentials are still read from runtime environment variables or the Data Library browser setup flow.
- No secrets are committed.

## Safety

Research/simulation only.

- No broker calls
- No live trading
- No order placement
- No file moves
- No file deletes
