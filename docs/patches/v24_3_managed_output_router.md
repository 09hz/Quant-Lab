# v24.3 — Managed Output Router

## Purpose

Start routing existing AlgoTrader research outputs through the new v24.2 Central Artifact Writer.

This patch adds a bridge that scans `Live/data`, classifies research artifacts, registers them in the artifact-writer registry, and optionally ingests JSON/CSV/Markdown metadata into PostgreSQL when credentials are available.

## Why this is useful

This is the safe first step before editing every producer module.

It lets the project bring existing real outputs under the new artifact system without moving or deleting any files.

## Adds

- `Live/services/artifacts/output_router.py`
- `Live/services/artifacts/route_existing_outputs.py`
- `Live/services/artifacts/output_router_self_test_v24_3.py`
- `docs/output_router.md`
- `docs/patches/v24_3_managed_output_router.md`

## Behavior

The router scans files under `Live/data`, skipping:

- `Live/data/managed_artifacts`
- catalog SQLite databases
- raw SQLite databases
- cache-like files
- oversized files above the configured limit

It classifies outputs such as:

- Market Memory research packets
- Market Memory reports
- Auto Lab results
- Walk-forward results
- Universe runs
- Backtest results
- Newsroom exports
- Diagnostic reports
- Strategy results
- Generic JSON/CSV/Markdown outputs

Then it calls:

```python
register_existing_file(...)
```

from the central artifact writer.

## Database behavior

- If PostgreSQL credentials are available, JSON/CSV are ingested.
- Markdown and non-tabular files are metadata-only.
- If PostgreSQL is unavailable, files are still registered locally and may be queued as pending.
- The router can also be run with `--no-ingest`.

## Safety

Research/simulation only.

- No broker calls
- No live trading
- No order placement
- No file moves
- No file deletes
- No credentials written
