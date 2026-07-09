# v24.8.1 — Main App Quant Dashboard Tab

## Purpose

Merge the standalone Quant Research Dashboard into the main Dash app safely.

This patch does **not** move the Quant Dashboard code into Data Library. It adds a separate top-level tab that embeds the already-working standalone dashboard with an iframe.

## Adds

- `Live/services/quant_dashboard/self_test_v24_8_1.py`
- `docs/patches/v24_8_1_main_app_quant_dashboard_tab.md`

## Patches

- `Live/app.py`

## Behavior

- Adds a new top-level tab named `Quant Dashboard`
- Embeds `http://127.0.0.1:8061` by default
- Moves the existing `Settings` tab to the end
- Does not modify `Live/ui/data_library_ui.py`
- Does not modify Data Library callbacks
- Does not add quant callbacks to the main app

## Runtime

Start the standalone dashboard in a second terminal:

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader\Live"

$PY = "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe"

& $PY -m services.quant_dashboard.app `
  --repo-root "C:\Users\sunny\Documents\GitHub\AlgoTrader" `
  --backend sqlite `
  --port 8061
```

Then start the main app normally and open the `Quant Dashboard` tab.

## Optional URL override

```powershell
$env:ALGOTRADER_QUANT_DASHBOARD_URL = "http://127.0.0.1:8061"
```

## Safety

Read-only UI integration.

- No Data Library edits
- No broker calls
- No live trading
- No order placement
- No inserts, updates, deletes, or file moves
- No credentials written
