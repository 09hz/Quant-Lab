# v24.1 — PostgreSQL Setup + Data Library Status Panel

## Purpose

Make PostgreSQL visible and usable from the Data Library instead of only from PowerShell or DBeaver.

## Adds

- PostgreSQL status service
- Data Library PostgreSQL status panel
- Safe check/migrate button
- Safe ingest-to-PostgreSQL button
- Table counts
- Latest ingestion run
- Skipped-file summary
- User setup scripts
- `.env.example`
- `.gitignore` protection for local env files
- Setup documentation

## Security

- No database passwords are written to the repo.
- The UI reads credentials only from the current process environment.
- Scripts prompt for passwords at runtime.
- `.env.example` contains placeholders only.
- `.env`, `.env.local`, and `.env.*.local` are git-ignored.

## Safety

Research/simulation only.

- No broker calls
- No live trading
- No order placement
- No file moves
- No file deletes
