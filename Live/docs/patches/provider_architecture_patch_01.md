# Provider Architecture Patch 01

This is an add-only foundation patch for Stock Visualizer Live.

## Goal

Create a provider-neutral market data interface before adding Tradier, Alpaca,
FastAPI, S3, or LLM features.

This patch does **not** remove IBKR. It wraps the current `RealTimeIB` object so
the app can keep working while future providers are added safely.

## Files added

```text
Live/services/market_data/
├── __init__.py
├── base.py
├── ibkr_provider.py
├── csv_provider.py
└── provider_factory.py
```

## Install

From the project root:

```powershell
Copy-Item .\provider_architecture_patch_01\Live\services\market_data .\Live\services\ -Recurse -Force
Copy-Item .\provider_architecture_patch_01\docs\patches\provider_architecture_patch_01.md .\Live\docs\patches\provider_architecture_patch_01.md -Force
```

Then compile:

```powershell
python -m py_compile .\Live\services\market_data\base.py
python -m py_compile .\Live\services\market_data\ibkr_provider.py
python -m py_compile .\Live\services\market_data\csv_provider.py
python -m py_compile .\Live\services\market_data\provider_factory.py
```

## Commit

```powershell
git add Live\services\market_data Live\docs\patches\provider_architecture_patch_01.md
git commit -m "Add market data provider foundation"
```

## Next patch

Patch 02 should route `ReplayService` through `MarketDataProvider`.

Do not add Tradier before patch 02 is stable.
