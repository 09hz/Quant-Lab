# v24.1.2 — Browser PostgreSQL Setup Wizard

## Purpose

Allow a local user to type PostgreSQL credentials in the Data Library UI and press buttons to:

- Test an app-user PostgreSQL connection
- Create/repair the AlgoTrader database, schema, and app user
- Run migrations
- Ingest cataloged JSON/CSV into PostgreSQL

This removes the requirement to type the database password in PowerShell before launching Dash for normal local use.

## Security model

This is intended for local development only.

- Password fields use browser password inputs.
- Passwords are not written to the repo.
- Passwords are not written to `.env`.
- Passwords are not saved in Dash stores.
- Passwords are used only for the current callback request.
- Existing environment-variable mode still works.
- In shared/hosted deployments, prefer environment variables or a secrets manager and do not expose admin setup controls.

## Adds

- `services.data_catalog.postgres_setup_service`
- UI credential fields
- Setup/repair database button
- Test typed credentials button
- Ingest with typed credentials button
- v24.1.2 self-test

## Safety

Research/simulation only.

- No broker calls
- No live trading
- No order placement
- No file moves
- No file deletes
