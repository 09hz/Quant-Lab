# Patch 20c — Restore Settings tab after Newsroom/Research patch

## Problem

The Newsroom/Quotes conversion introduced a fallback that rendered:

`Settings tab builder is not available.`

This happened because the existing Settings builder was overwritten or no longer exposed from `ui.tabs_ui`.

## Fix

This patch adds a dedicated, self-contained Settings UI module:

- `Live/ui/settings_ui.py`

It also adds compatibility functions at the bottom of:

- `Live/ui/tabs_ui.py`

So these imports remain available:

- `build_settings_tab`
- `build_charts_tab`

`build_charts_tab()` remains a compatibility alias to Settings because the old Charts slot was previously repurposed.

## Safety

This is UI-only. It does not change broker logic, orders, provider logic, LLM generation, or external tool access.
