# Patch 21 — Revert Tradier UI/provider work, keep read-only Newsroom and Settings

This patch backs the app away from the unstable Tradier/tabs work and restores a clean read-only layout:

- Settings remains visible through the old `build_charts_tab(...)` call.
- Newsroom remains visible through the old `build_quotes_tab(...)` call.
- Both wrappers accept legacy `app.py` keyword arguments.
- Tradier market-data provider wiring is disabled for now.
- IBKR and CSV providers remain available.
- No order routing, no broker-account access, and no autonomous AI actions are added.

## Active providers after this patch

Supported:

- `MARKET_DATA_PROVIDER=ibkr`
- `MARKET_DATA_PROVIDER=csv`

Temporarily disabled:

- `MARKET_DATA_PROVIDER=tradier`

Tradier can be reintroduced later in a clean provider-only patch after the UI is stable.

## Local secret reminder

Do not commit `.env`, Tradier tokens, OpenAI keys, exported CSV cache, `__pycache__`, or `.pyc` files.
