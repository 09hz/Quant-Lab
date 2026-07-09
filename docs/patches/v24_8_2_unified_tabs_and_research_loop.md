# v24.8.2 — Unified Main Tab Styling + Research Loop Design

## Purpose

Make the main app tabs look consistent now that Quant Dashboard is part of the app.

This patch is intentionally CSS-only for the app UI. It does not modify `Live/app.py`, `Live/ui/data_library_ui.py`, or callbacks.

## Adds

- `Live/assets/v24_8_2_unified_main_tabs.css`
- `Live/services/quant_dashboard/self_test_v24_8_2.py`
- `docs/research_ai_loop.md`
- `docs/patches/v24_8_2_unified_tabs_and_research_loop.md`

## What the CSS does

- Gives all top-level tabs consistent spacing, height, borders, and hover behavior.
- Makes selected tabs visually consistent.
- Keeps Settings visually consistent even after being moved to the end.
- Adds a consistent embedded Quant Dashboard panel style.
- Does not hide or disable tabs.

## Research loop design

The included `docs/research_ai_loop.md` describes the next architecture:

```text
Market Memory
  -> Universe Builder
  -> Strategy Generator
  -> Backtest
  -> Walk-forward
  -> Risk/Data Quality checks
  -> Quant Schema
  -> Dashboard
  -> Market Memory feedback
  -> next iteration
```

This is research/simulation only.

## Safety

- No broker calls
- No live trading
- No order placement
- No Python callback changes
- No app layout mutation
- No Data Library edits
- No credentials written
