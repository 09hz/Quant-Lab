# Provider Architecture Patch 06 — Tradier Market Data Provider Scaffold

## Purpose

Adds a market-data-only Tradier provider.

This patch does not add live order routing. It is intentionally limited to quotes
and OHLCV bars so the app can test Tradier as a lower-cost data path before any
broker execution work.

## Files Changed

- `Live/services/market_data/tradier_provider.py`
- `Live/services/market_data/provider_factory.py`
- `Live/services/market_data/__init__.py`
- `Live/.env.example`

## Provider Selection

```env
MARKET_DATA_PROVIDER=tradier
TRADIER_ENV=sandbox
TRADIER_ACCESS_TOKEN=your_token_here
```

Live environment:

```env
MARKET_DATA_PROVIDER=tradier
TRADIER_ENV=live
TRADIER_ACCESS_TOKEN=your_live_token_here
```

## Endpoints Used

- `/markets/quotes`
- `/markets/timesales`
- `/markets/history`

## Notes

- `1 min`, `5 mins`, and `15 mins` use Tradier Time & Sales.
- `1 hour` fetches 15-minute bars and resamples locally.
- `1 day` uses Tradier historical pricing.
- The provider has small in-memory quote/history caches so Dash refreshes do not
  hammer the API.
- Missing tokens produce a clear runtime error only when the provider is selected
  or called.

## Security

Never commit real Tradier tokens.

Keep credentials in `.env` or your shell environment only.

## Test Commands

```powershell
python -m py_compile .\Live\services\market_data\tradier_provider.py
python -m py_compile .\Live\services\market_data\provider_factory.py
python -m py_compile .\Live\services\market_data\__init__.py
python .\Live\scripts\check_market_data_provider.py --provider tradier --skip-history --skip-snapshot
```

With credentials:

```powershell
$env:MARKET_DATA_PROVIDER="tradier"
$env:TRADIER_ENV="sandbox"
$env:TRADIER_ACCESS_TOKEN="your_token_here"
python .\Live\scripts\check_market_data_provider.py --provider tradier --symbol MSFT --timeframe "1 min"
```

## Rollback

Use Git:

```powershell
git restore .\Live\services\market_data\tradier_provider.py
git restore .\Live\services\market_data\provider_factory.py
git restore .\Live\services\market_data\__init__.py
git restore .\Live\.env.example
```
