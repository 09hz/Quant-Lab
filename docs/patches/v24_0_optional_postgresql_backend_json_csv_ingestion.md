# v24.0 — Optional PostgreSQL Backend + JSON/CSV Ingestion

## Purpose

Add a database backend layer for research data. SQLite remains the default and PostgreSQL is optional.

## Adds

- `Live/services/database/` backend configuration, connections, migrations, and status CLI.
- `Live/services/data_catalog/database_ingestion.py` ingestion engine.
- `Live/services/data_catalog/ingest_to_database.py` ingestion CLI.
- SQLite-only self-test so the patch can pass without requiring PostgreSQL credentials.

## Credential policy

Credentials are never written by this patch.

Preferred local Windows development variables:

- `ALGOTRADER_DB_BACKEND=postgres`
- `ALGOTRADER_DB_HOST=localhost`
- `ALGOTRADER_DB_PORT=5432`
- `ALGOTRADER_DB_NAME=algotrader`
- `ALGOTRADER_DB_USER=algotrader_app`
- `ALGOTRADER_DB_PASSWORD=<runtime only>`
- `ALGOTRADER_DB_SCHEMA=algotrader`

`ALGOTRADER_DATABASE_URL` is also supported, but separate variables avoid URL escaping issues when passwords contain `@`, `:`, `/`, `?`, `&`, or `%`.

## Safety

Research/simulation only.

- No live trading
- No broker calls
- No order placement
- No file moves
- No file deletes
- No secrets committed
