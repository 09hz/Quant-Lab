# Patch 31 — FRED Newsroom UI Integration

This patch wires the existing FRED connector into the Newsroom result flow.

## Added

- `Live/services/research/fred_newsroom_adapter.py`
- `Live/scripts/check_newsroom_fred_ui.py`
- `Live/docs/patches/newsroom_fred_ui_patch_31.md`

## Updated

- `Live/services/research/newsroom_callbacks.py`
- `Live/services/research/__init__.py`
- `Live/assets/zz_newsroom_interactive.css`

## Behavior

When the Newsroom source filter includes FRED, `Fetch Research` now prepends structured FRED data cards to the normal research links.

For example, a query like:

```text
inflation rate
```

can produce selectable cards for series such as CPI, core CPI, PCE inflation, breakeven inflation, and Fed funds. With `FRED_API_KEY` configured, the cards include recent observation summaries. Without a key, the cards fall back to official FRED series links.

## Safety

The AI does not get direct API access. The app fetches FRED data and stores only curated, selected summaries in the research brief.
