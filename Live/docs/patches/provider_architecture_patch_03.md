# Provider Architecture Patch 03

## Purpose

Route the Watch live-chart bar path through `MarketDataProvider`.

This keeps the current IBKR behavior while removing another direct dependency on
`RealTimeIB` from the live Watch chart preparation flow.

## Files changed

- `Live/app.py`
- `Live/callbacks.py`
- `Live/services/bar_view_service.py`
- `Live/services/market_data/ibkr_provider.py`

## Design

Before:

```text
BarViewService -> RealTimeIB
```

After:

```text
BarViewService -> MarketDataProvider -> IBKRMarketDataProvider -> RealTimeIB
```

## Safety

This patch is intentionally transitional:

- `register_callbacks(...)` still receives `rt`
- `market_data_provider` is optional
- if no provider is passed, callbacks fall back to `rt`
- `request_symbol(...)` is best-effort and optional

That keeps the app compatible while provider routing is staged.

## Test

```powershell
python -m py_compile .\Live\app.py
python -m py_compile .\Live\callbacks.py
python -m py_compile .\Live\services\bar_view_service.py
python -m py_compile .\Live\services\market_data\ibkr_provider.py
python .\Live\app.py
```

Then test:

- Dashboard opens
- Watch tab opens
- Watch live mode still shows data
- Replay mode still works
- Strategy overlays still render
- Paper trading still works
