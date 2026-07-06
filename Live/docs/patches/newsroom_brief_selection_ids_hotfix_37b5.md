# Newsroom brief selection repair hotfix 37b5

## Purpose

Fix Newsroom cases where selected source rows do not append to the research brief,
especially after multiple searches or when several visible rows reuse the same raw
result id.

## Change

- Adds stable brief dedupe keys based primarily on URL.
- Adds unique visible-row checklist ids.
- Stores the visible rows with those unique ids in `newsroom-results-store`.
- Keeps old raw ids as fallback selection matches.
- Keeps `Clear Brief` as the only explicit clear action.

## Files touched

- `Live/services/research/newsroom_callbacks.py`
- `Live/scripts/check_newsroom_brief_selection_ids.py`

## Safety

This is research-context only. It does not touch broker access, order placement,
or trading execution.
