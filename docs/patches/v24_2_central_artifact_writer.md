# v24.2 — Central Artifact Writer

Adds a central writer for future research artifacts.

New modules can call:

- `save_json(...)`
- `save_csv(...)`
- `save_markdown(...)`

The writer saves files to disk, computes metadata, records them in a local SQLite registry, attempts PostgreSQL ingestion when configured, and queues failed database ingestion for retry.

Security/safety:

- No passwords written.
- No `.env` written.
- No files moved or deleted.
- No broker calls or live trading.
