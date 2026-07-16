# Patch 25 — Dash ID Inventory

This patch adds a static Dash component ID inspection script.

## Purpose

Before wiring Strategy exports, AI context attachment, and Newsroom callbacks, we need the exact current IDs used by the app. Prior UI patches were fragile because wrappers and tabs changed over time. This script avoids importing `app.py`; it scans source files for Dash component IDs.

## Added

- `Live/scripts/inspect_dash_component_ids.py`

## Usage

```powershell
python .\Live\scripts\inspect_dash_component_ids.py
python .\Live\scripts\inspect_dash_component_ids.py --filter strategy
python .\Live\scripts\inspect_dash_component_ids.py --filter backtest
python .\Live\scripts\inspect_dash_component_ids.py --filter ai
python .\Live\scripts\inspect_dash_component_ids.py --summary-only
```

## Next patch

Use this output to wire:

- Strategy script export
- Backtest report export
- Attach current strategy/backtest context to AI Advisor
- Research brief attachment from Newsroom
