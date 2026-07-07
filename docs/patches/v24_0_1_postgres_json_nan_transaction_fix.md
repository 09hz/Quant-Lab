# v24.0.1 — PostgreSQL JSON NaN + Transaction Recovery Fix

## Purpose

Fix PostgreSQL ingestion failure when cataloged JSON files contain Python/JavaScript non-standard numeric tokens such as `NaN`, `Infinity`, or `-Infinity`.

PostgreSQL `JSONB` rejects those tokens. The ingestion layer now sanitizes them to JSON `null` before insert.

## Fixes

- Converts `NaN`, `Infinity`, and `-Infinity` to `null` before JSONB insertion.
- Uses strict `json.dumps(..., allow_nan=False)` for database-bound JSON.
- Adds per-artifact transaction recovery so one bad file does not poison the entire ingestion transaction.
- Keeps SQLite as the default/safe fallback.
- Adds a v24.0.1 self-test with a JSON file containing `NaN`.

## Safety

Research/simulation only.

- No live trading
- No broker calls
- No order placement
- No file moves
- No file deletes
- No credentials written
