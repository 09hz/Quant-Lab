# diagnose_auto_lab_engine_map_v21_0

## Purpose

Read-only diagnostic to map the existing app before building the larger AI Auto Lab orchestrator.

This script identifies:

```text
Dash callbacks
callback inputs/outputs/states
backtest-related modules
strategy-related modules
optimizer-related modules
AutoLab/research-related modules
function/class signatures
candidate engine entrypoints
imports between modules
data/debug output locations
```

## Why this exists

Before connecting a new Auto Lab orchestrator, we need to know exactly where the current engines and callbacks live.

The goal is not to rewrite your backtester or strategy engine. The goal is to create a clean orchestration layer above the existing system.

## Files written

```text
docs/patches/diagnose_auto_lab_engine_map_v21_0.md
diagnostics_auto_lab_engine_map_v21_0.json
diagnostics_auto_lab_engine_map_v21_0.md
```

## Safety

```text
Read-only scan of source files.
No app code modified.
No backups created.
No __pycache__ compile output created.
No broker/order/live-trading behavior added.
```

## Test tools

### Run diagnostic

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader"

& "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe" ".\diagnose_auto_lab_engine_map_v21_0.py" `
  --repo-root "C:\Users\sunny\Documents\GitHub\AlgoTrader"
```

### Open markdown report

```powershell
notepad ".\diagnostics_auto_lab_engine_map_v21_0.md"
```

### Quick terminal checks

```powershell
Select-String -Path ".\diagnostics_auto_lab_engine_map_v21_0.md" `
  -Pattern "Likely Backtest Engines|Likely Strategy Engines|Likely AutoLab|Dash Callback Map|Candidate Engine Entrypoints"
```

## What to paste back

Paste the sections:

```text
1. Summary
2. Likely Backtest Engines
3. Likely Strategy Engines
4. Likely AutoLab / Optimizer / Research Engines
5. Candidate Engine Entrypoints
6. Dash Callback Map
```

## Next step after diagnostic

Use the report to build:

```text
v21_0_auto_lab_orchestrator_foundation.py
```

That patch should connect to the existing engines instead of rebuilding them.
