# v22_0_auto_lab_ui_launcher

## Purpose

Add the first local Auto Lab UI launcher.

This is a research/simulation-only UI for the backend already built in v21.x:

```text
single-symbol Auto Lab
multi-symbol universe runner
walk-forward validation
strategy build trace
execution quality report
overfit warning report
```

v22.0 is intentionally standalone first. It does **not** patch the main Dash app yet. That keeps risk low and lets us test the Auto Lab UI before wiring it into the bigger platform layout.

## User-selected variables

```text
1. UI type: local standalone Dash launcher first.
2. Safety mode: research/simulation only.
3. Actions: run universe and run walk-forward.
4. Reports: show latest universe/walk-forward markdown reports.
5. Trading: no live trading, no broker calls, no order routing.
6. Patch name: v22_0_auto_lab_ui_launcher.py.
```

## Files added

```text
Live/services/ai/auto_lab_orchestrator/ui_report_loader.py
Live/services/ai/auto_lab_orchestrator/auto_lab_ui_launcher.py
Live/services/ai/auto_lab_orchestrator/auto_lab_ui_self_test.py
```

## What the UI does

```text
- Choose symbols.
- Choose train/test windows.
- Choose sizing mode and cash exposure.
- Run multi-symbol universe Auto Lab.
- Run multi-symbol walk-forward validation.
- Display command output.
- Load latest universe report.
- Load latest walk-forward report.
- Show direct report paths.
```

## What the UI does not do

```text
- Does not place orders.
- Does not connect to brokers.
- Does not call PaperBroker.
- Does not trade.
- Does not store secrets.
- Does not provide financial advice.
```

## Run patch

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader"

& "C:\\Users\\sunny\\Documents\\GitHub\\StockVisualizer\\.venv\\Scripts\\python.exe" ".\\v22_0_auto_lab_ui_launcher.py" `
  --repo-root "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader" `
  --run-ui-self-test
```

## Start UI

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader"

& "C:\\Users\\sunny\\Documents\\GitHub\\StockVisualizer\\.venv\\Scripts\\python.exe" ".\\Live\\services\\ai\\auto_lab_orchestrator\\auto_lab_ui_launcher.py" `
  --host 127.0.0.1 `
  --port 8077
```

Open:

```text
http://127.0.0.1:8077
```

## Next likely patch

```text
v22.1 — integrate Auto Lab UI tab into the main app layout
```

That should only happen after the standalone launcher works.
