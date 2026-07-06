# Patch 20 — Convert Quotes tab to Newsroom

## Goal

Reuse the old Quotes tab slot as a new Newsroom/Research room.

## Scope

Added:

- `Live/ui/newsroom_ui.py`
- `Live/assets/zz_newsroom_tab.css`
- `Live/docs/patches/newsroom_quotes_tab_patch_20.md`

Changed where possible:

- `Live/ui/tabs_ui.py`
- `Live/app.py` visible label text only if present

## Design

The new Newsroom is read-only. It is meant to become the place for:

- trusted economic/market sources
- general economic news
- source manifests used by AI research prompts
- future source-linked research briefs

## Safety

This patch does not add:

- order placement
- broker/account access
- autonomous AI browsing
- AI tool calling
- secrets in the browser

The old tab value/IDs are intentionally left alone where possible so existing callbacks do not break.
