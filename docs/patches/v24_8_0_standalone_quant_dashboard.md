# v24.8.0 — Standalone Quant Dashboard

Adds a read-only Quant Research Dashboard as a separate local Dash app.

This patch intentionally does not edit:
- Live/app.py
- Live/ui/data_library_ui.py
- Live/assets/data_library.css

Run after install:

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader\Live"

$PY = "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe"

& $PY -m services.quant_dashboard.app `
  --repo-root "C:\Users\sunny\Documents\GitHub\AlgoTrader" `
  --backend sqlite `
  --port 8061
```

Open: `http://127.0.0.1:8061`

Safety:
- Read-only
- No broker calls
- No live trading
- No order placement
- No inserts, updates, deletes, or file moves
- No credentials written
