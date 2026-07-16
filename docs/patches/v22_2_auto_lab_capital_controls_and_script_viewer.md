# v22_2_auto_lab_capital_controls_and_script_viewer

## Purpose

Add practical research controls and transparency to the new main-app AI Auto Lab tab.

## Adds

- Simulated starting cash input.
- Simulated target cash input.
- Capital assumptions panel.
- Strategy/script viewer panel.
- Human-readable run index/manifest writer for latest Auto Lab run folders.
- Safer capital flag handling: the UI only passes capital flags to backend runner scripts if those scripts advertise/support the relevant CLI flag.

## Important safety boundary

This is still research/simulation only.

```text
No live orders.
No broker connection.
No PaperBroker calls.
No account credentials.
No trade execution.
No financial advice.
```

## Files added

```text
Live/services/ai/auto_lab_orchestrator/capital_controls.py
Live/services/ai/auto_lab_orchestrator/script_viewer.py
Live/services/ai/auto_lab_orchestrator/auto_lab_v22_2_self_test.py
```

## Files replaced/updated

```text
Live/ui/auto_lab_ui.py
Live/services/ai/auto_lab_orchestrator/auto_lab_main_callbacks.py
Live/assets/auto_lab.css
```

## What the JSON files are for

Markdown files are for humans.
JSON files are for the app.

The UI uses JSON/manifests to power later features:

```text
ranked tables
clickable strategy detail
equity curve panels
trade tables
run comparison
latest-run detection
market-memory links
```

## Run

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader"

& "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe" ".\v22_2_auto_lab_capital_controls_and_script_viewer.py" `
  --repo-root "C:\Users\sunny\Documents\GitHub\AlgoTrader" `
  --run-self-test
```
