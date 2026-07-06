# Patch 37b7 - Newsroom allow distinct same-URL sources

## Purpose

Fixes Research Brief additions where useful, distinct source cards were skipped as
"duplicates" only because they shared the same URL.

Example:

- `CPIAUCSL` live FRED data card
- `FRED series: Consumer Price Index (CPIAUCSL)` official context card

Both may point to the same FRED series URL, but they are different evidence
roles and should both be addable when the user selects them.

## Behavior

The brief now dedupes conservatively by:

- source
- kind/type
- title
- URL
- summary

It no longer collapses rows by URL alone.

## Safety

This does not loosen AI truth rules. Low-confidence/context/search rows can still
be included with caution labels, and the AI must separate confirmed evidence from
context or assumptions.

## Files

- `Live/services/research/newsroom_callbacks.py`
- `Live/scripts/check_newsroom_distinct_same_url_sources.py`
