# v23.0.1 — SQLite connection close fix

## Purpose

Fix the Windows self-test failure:

```text
PermissionError: [WinError 32] ... market_memory.sqlite is being used by another process
```

## Cause

SQLite is already included with Python. No SQLite install is needed.

The failure came from Windows trying to delete the temporary self-test SQLite file while a SQLite connection could still be open/locked. Python's `sqlite3.Connection` context manager commits/rolls back, but it does not necessarily close the connection immediately.

## Fix

- Add a `MarketMemoryStore.session()` context manager.
- Ensure every SQLite connection is explicitly committed and closed.
- Update `self_test.py` to use `TemporaryDirectory(ignore_cleanup_errors=True)` for extra Windows tolerance.

## Safety

Research/simulation only. No live orders, no broker connection, no PaperBroker calls, no account credentials, no trade execution.
