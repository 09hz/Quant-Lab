# Patch 30 — Newsroom FRED Connector

This patch adds the first structured macro-data connector for Newsroom.

## Why FRED first?

FRED is the best first connector because it has official economic series pages and an official API for series metadata, search, and observations. The app can use curated series IDs for common macro questions such as inflation, rates, labor, GDP, housing, consumer demand, and liquidity.

## Files added

- `Live/services/research/fred_connector.py`
- `Live/scripts/check_fred_connector.py`
- `Live/docs/patches/newsroom_fred_connector_patch_30.md`

## Files updated

- `Live/services/research/__init__.py`
- `Live/.env.example`

## Environment

Add this to `Live/.env` when you are ready to fetch structured FRED data:

```env
FRED_API_KEY=your_fred_api_key_here
RESEARCH_FRED_TIMEOUT_SECONDS=8
```

Without `FRED_API_KEY`, the connector still returns curated official FRED links. With `FRED_API_KEY`, it can fetch metadata and recent observations.

## Test commands

From the repo root:

```powershell
python -m py_compile .\Live\services\research\fred_connector.py
python -m py_compile .\Live\scripts\check_fred_connector.py
```

Links-only / no API key required:

```powershell
python .\Live\scripts\check_fred_connector.py --query "inflation rate"
```

Fetch one series when `FRED_API_KEY` is configured:

```powershell
python .\Live\scripts\check_fred_connector.py --series CPIAUCSL
```

Build JSON for Newsroom / AI context:

```powershell
python .\Live\scripts\check_fred_connector.py --query "inflation rate" --json
```

Use FRED API search when `FRED_API_KEY` is configured:

```powershell
python .\Live\scripts\check_fred_connector.py --query "inflation rate" --search
```

## Safety model

The AI does not receive direct arbitrary FRED access. The app connector fetches selected structured data, summarizes it, and then a later patch can pass the resulting brief to the AI advisor.
