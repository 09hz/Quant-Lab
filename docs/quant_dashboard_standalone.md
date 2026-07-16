# Standalone Quant Research Dashboard

v24.8.0 adds a separate local dashboard for typed quant research results.

It deliberately does not modify the working main Dash app or Data Library tab.

## SQLite

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader\Live"

$PY = "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe"

& $PY -m services.quant_dashboard.app `
  --repo-root "C:\Users\sunny\Documents\GitHub\AlgoTrader" `
  --backend sqlite `
  --port 8061
```

Open:

```text
http://127.0.0.1:8061
```

Research/simulation only.
