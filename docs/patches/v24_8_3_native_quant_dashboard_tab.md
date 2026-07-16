# v24.8.3 — Native Quant Dashboard Tab

## Purpose

Remove the need to run the Quant Dashboard in a second terminal.

v24.8.1 embedded the standalone Quant Dashboard with an iframe pointing to:

```text
http://127.0.0.1:8061
```

That worked safely, but it required a second Dash server. v24.8.3 converts the Quant Dashboard into a native top-level tab inside the main app.

## Behavior

- Adds/updates the top-level `Quant Dashboard` tab.
- Uses native Dash components, not an iframe.
- Queries the same `services.quant_dashboard.queries.load_quant_dashboard()` service directly.
- Keeps `Settings` at the end.
- Does not touch Data Library.
- Does not require a second terminal or port 8061.
- Main app runs with one command:

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader\Live"

$PY = "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe"

& $PY ".\app.py"
```

## Safety

- Read-only dashboard
- No broker calls
- No live trading
- No order placement
- No inserts, updates, deletes, or file moves
- No credentials written
- No Data Library layout edits
