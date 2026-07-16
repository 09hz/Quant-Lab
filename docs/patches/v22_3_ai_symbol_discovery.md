# v22_3_ai_symbol_discovery

## Purpose

Add AI-assisted symbol discovery to the main AI Auto Lab tab.

This feature lets the app suggest a better research universe from:

```text
seed symbols
theme/focus text
sector/peer relationship map
liquidity/research suitability rules
```

Example:

```text
Seed: AMD
Theme: semiconductors, AI infrastructure

Suggested:
AMD, NVDA, AVGO, QCOM, MU, TSM, ASML, MRVL, SMH, SOXX
```

## Safety boundary

This suggests symbols to research/test. It does not suggest buying/selling and does not place orders.

```text
Research/simulation only.
No live orders.
No broker connection.
No PaperBroker calls.
No account credentials.
No trade execution.
```

## Files added

```text
Live/services/ai/auto_lab_orchestrator/symbol_discovery.py
Live/services/ai/auto_lab_orchestrator/symbol_discovery_reporter.py
Live/services/ai/auto_lab_orchestrator/symbol_discovery_self_test.py
```

## Files updated

```text
Live/ui/auto_lab_ui.py
Live/services/ai/auto_lab_orchestrator/auto_lab_main_callbacks.py
Live/assets/auto_lab.css
```

## UI additions

```text
AI Symbol Discovery
- Theme / focus
- Max symbols
- Suggest Symbols button
- Discovery report panel
- Suggested universe output
```

## Outputs

```text
Live/data/auto_lab_symbol_discovery/<run_id>/
  symbol_discovery_report.md
  suggested_universe.json
  00_ui_run_manifest.json
```

## Run

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader"

& "C:\\Users\\sunny\\Documents\\GitHub\\StockVisualizer\\.venv\\Scripts\\python.exe" ".\\v22_3_ai_symbol_discovery.py" `
  --repo-root "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader" `
  --run-self-test
```
