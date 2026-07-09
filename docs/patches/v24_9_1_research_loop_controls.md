# v24.9.1 — Research Loop Controls in Native Quant Dashboard

## Purpose

Add browser controls for the strategy/backtest research loop inside the native Quant Dashboard tab.

After this patch, the user can run the v24.9.0 research loop from the main app instead of using PowerShell.

## Adds

- Research Loop control panel inside the `Quant Dashboard` tab
- Browser button: `Run Research Loop`
- Inputs:
  - Theme
  - Symbols
  - Max candidates
  - Backend
- Result summary panel
- Auto-refresh trigger for the native Quant Dashboard after the loop completes
- CSS for the research loop control panel
- Self-test

## Patches

- `Live/app.py`
- `Live/assets/v24_9_1_research_loop_controls.css`
- `Live/services/research_loop/self_test_v24_9_1.py`
- `docs/patches/v24_9_1_research_loop_controls.md`

## Does not touch

- `Live/ui/data_library_ui.py`
- `Live/assets/data_library.css`

## Safety

Simulation/research only.

- No broker calls
- No live trading
- No order placement
- No credentials written
- No file moves or deletes
- No Data Library layout edits
