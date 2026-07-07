# v24.1.1 — Database Config Compatibility Fix

## Purpose

Fix v24.1 self-test failure caused by an older/local `services.database.config` module that does not expose `describe_database_config`.

## Error fixed

```text
ImportError: cannot import name 'describe_database_config' from 'services.database.config'
```

## Fix

- Adds `describe_database_config(config)` to `Live/services/database/config.py` if missing.
- Makes `postgres_status_service.py` resilient if the helper is missing in future local variants.
- Adds a v24.1.1 self-test.

## Security

- No credentials are written.
- Passwords remain environment-variable only.
- `.env.local` remains ignored.

## Safety

Research/simulation only.

- No broker calls
- No live trading
- No order placement
- No file moves
- No file deletes
