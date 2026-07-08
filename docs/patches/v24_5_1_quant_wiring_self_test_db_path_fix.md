# v24.5.1 — Quant Wiring Self-Test Database Path Fix

## Purpose

Fix the v24.5 self-test failure:

```text
sqlite3.OperationalError: no such table: backtest_runs
```

## Cause

The v24.5 self-test assumed the SQLite fallback database file was always:

```text
Live/data/catalog/algotrader.sqlite
```

But the project's database config layer controls the actual SQLite database path. The capture logic wrote typed quant rows correctly, but the self-test checked the wrong SQLite file.

## Fix

Rewrite `self_test_v24_5.py` so it uses the same database config layer as the application:

- `services.database.config.load_database_config`
- `services.database.backend.connect_database` or `services.database.connections.connect_database`
- `services.quant_schema.migrations.quant_table_counts`

This verifies the real configured SQLite fallback database instead of guessing the file path.

## Safety

Research/simulation only.

- No broker calls
- No live trading
- No order placement
- No file moves
- No file deletes
- No credentials written
