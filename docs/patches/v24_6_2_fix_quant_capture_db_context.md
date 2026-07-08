# v24.6.2 — Fix Quant Capture Database Context for Direct Wiring

## Purpose

Fix the direct producer wiring capture path so wrapped producer outputs actually write into the typed quant schema.

## Error fixed

The v24.6 self-test wrapped functions correctly, but typed table counts stayed at zero:

```text
AssertionError: {'symbols': 0, 'experiment_runs': 0, 'strategy_runs': 0, 'backtest_runs': 0, ...}
```

## Cause

`result_capture.py` opened the project database through the database backend layer but attempted to migrate the quant schema before entering the database context manager.

In other words, the capture layer could fail internally before it reached the real SQLite/PostgreSQL connection. Direct producer wiring swallowed the capture exception by design so the app would not crash, but the self-test then saw zero typed rows.

## Fix

Rewrite `_db_connect(...)` in `result_capture.py` as a real context manager:

```python
@contextmanager
def _db_connect(repo, backend):
    with connect_database(config) as db:
        migrate_quant_schema(db)
        yield db
```

This makes capture, runtime hooks, and direct producer wiring use the same connection lifecycle as the rest of the app.

## Safety

Research/simulation only.

- No broker calls
- No live trading
- No order placement
- No file moves
- No file deletes
- No credentials written
